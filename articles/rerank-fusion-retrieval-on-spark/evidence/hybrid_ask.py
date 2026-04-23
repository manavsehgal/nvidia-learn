#!/usr/bin/env python3
"""Hybrid retrieval + optional rerank on a DGX Spark.

Four retrieval modes share one code path:

    naive  : pgvector top-K (dense cosine, Nemotron embeddings)
    bm25   : Postgres full-text ts_rank_cd top-K (lexical)
    rrf    : dense(20) + lexical(20) merged via Reciprocal Rank Fusion (k=60)
    rerank : rrf(20) → Nemotron Reranker logit scores → top-K

The reranker NIM (llama-3.2-nv-rerankqa-1b-v2) does not yet run locally on
GB10 — its TRT plans are compiled for RTX6000 Blackwell and its ONNX
fallback hits a missing CUDA symbol. We call NVIDIA's hosted NVCF endpoint
for that single stage and document the gap.

stdlib only. Same ethos as articles #4-4.

Usage:
    python3 hybrid_ask.py --mode rrf    "Did Google have an IPO in 2004?"
    python3 hybrid_ask.py --mode rerank "Playboy controversy around Google IPO"
    python3 hybrid_ask.py --mode naive  --json "What did Phelps win in Athens?"
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

EMBED_URL = os.environ.get("EMBED_URL", "http://localhost:8001/v1/embeddings")
EMBED_MODEL = "nvidia/llama-nemotron-embed-1b-v2"
EMBED_DIM = 1024

LLM_URL = os.environ.get("LLM_URL", "http://localhost:8000/v1/chat/completions")
LLM_MODEL = "meta/llama-3.1-8b-instruct"

RERANK_URL = os.environ.get(
    "RERANK_URL",
    "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-3_2-nv-rerankqa-1b-v2/reranking",
)
RERANK_MODEL = "nvidia/llama-3.2-nv-rerankqa-1b-v2"
NGC_API_KEY = os.environ.get("NGC_API_KEY")

PSQL = ["docker", "exec", "-i", "pgvector",
        "psql", "-U", "spark", "-d", "vectors",
        "-v", "ON_ERROR_STOP=1", "-qAt", "-F", "\t"]

STRICT_SYSTEM = (
    "You are a careful assistant. Answer the user's question using ONLY the "
    "provided context passages. Each passage is prefixed with its row id in "
    "square brackets like [123]. If the answer is present, state it plainly "
    "and cite the ids you used in a trailing 'Sources: [id, id]' line. If "
    "the context does not contain the answer, reply with exactly one "
    "sentence: 'The provided context does not contain the answer.' Do not "
    "fall back to general knowledge."
)


def embed_query(text):
    body = json.dumps({
        "model": EMBED_MODEL,
        "input": [text],
        "input_type": "query",
        "encoding_format": "float",
        "truncate": "END",
        "dimensions": EMBED_DIM,
    }).encode()
    req = urllib.request.Request(EMBED_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["data"][0]["embedding"]


def pgvector_topk(qvec, k):
    vec_literal = "[" + ",".join(f"{x:.6f}" for x in qvec) + "]"
    sql = (
        f"SELECT id, label, (embedding <=> '{vec_literal}') AS dist, text "
        f"FROM chunks ORDER BY embedding <=> '{vec_literal}' LIMIT {int(k)};"
    )
    return _psql_rows(sql)


def bm25_topk(question, k):
    """ts_rank_cd top-K. We derive an OR-of-stems tsquery from plainto_tsquery
    (which lemmatises and drops stopwords) by regexp-splitting its '&' and
    joining with '|'. OR semantics are standard for the lexical side of
    hybrid retrieval — every term gets a chance to contribute.
    """
    q = question.replace("'", "''")
    sql = (
        "WITH q AS ("
        "  SELECT NULLIF(array_to_string("
        "    regexp_split_to_array("
        f"      plainto_tsquery('english', '{q}')::text, ' & '), ' | '), '')"
        "    ::tsquery AS tsq"
        ") "
        "SELECT id, label, ts_rank_cd(to_tsvector('english', text), q.tsq) AS rank, text "
        "FROM chunks, q "
        "WHERE q.tsq IS NOT NULL AND to_tsvector('english', text) @@ q.tsq "
        "ORDER BY rank DESC "
        f"LIMIT {int(k)};"
    )
    return _psql_rows(sql, score_name="rank")


def _psql_rows(sql, score_name="dist"):
    proc = subprocess.run(PSQL, input=sql, capture_output=True, text=True,
                          timeout=10, check=True)
    rows = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        rid, label, score, text = parts
        rows.append({
            "id": int(rid),
            "label": label,
            score_name: float(score),
            "text": text,
        })
    return rows


def rrf_merge(dense_hits, lex_hits, top_k, k_rrf=60):
    """Reciprocal Rank Fusion. Each list contributes 1/(k_rrf + rank) to each
    document's fused score; documents appearing in both lists get additive
    credit. k_rrf=60 is the Carbonell+Cormack+Clarke default.
    """
    scores = {}
    meta = {}
    for rank, h in enumerate(dense_hits, start=1):
        scores[h["id"]] = scores.get(h["id"], 0.0) + 1.0 / (k_rrf + rank)
        meta[h["id"]] = h
    for rank, h in enumerate(lex_hits, start=1):
        scores[h["id"]] = scores.get(h["id"], 0.0) + 1.0 / (k_rrf + rank)
        meta.setdefault(h["id"], h)
    merged = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    out = []
    for rid, rrf_score in merged[:top_k]:
        h = dict(meta[rid])
        h["rrf"] = round(rrf_score, 6)
        out.append(h)
    return out


def rerank_hits(question, hits, top_k):
    """Post passages to the hosted Nemotron Reranker and reorder by logit
    score (higher = more relevant)."""
    if not NGC_API_KEY:
        raise RuntimeError("NGC_API_KEY required for --mode rerank; source ~/.nim/secrets.env")
    body = json.dumps({
        "model": RERANK_MODEL,
        "query": {"text": question},
        "passages": [{"text": h["text"]} for h in hits],
    }).encode()
    req = urllib.request.Request(RERANK_URL, data=body, headers={
        "Authorization": f"Bearer {NGC_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.loads(r.read())
    order = payload["rankings"]  # [{index, logit}, ...] sorted by logit desc
    out = []
    for rank_entry in order[:top_k]:
        idx = rank_entry["index"]
        h = dict(hits[idx])
        h["logit"] = round(float(rank_entry["logit"]), 4)
        out.append(h)
    return out


def retrieve(question, mode, k):
    """Returns (hits, timings_ms). top-K docs under the chosen mode."""
    t = {}
    if mode == "naive":
        t0 = time.perf_counter()
        qvec = embed_query(question)
        t["embed"] = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        hits = pgvector_topk(qvec, k)
        t["retrieve"] = (time.perf_counter() - t0) * 1000
        return hits, t

    if mode == "bm25":
        t0 = time.perf_counter()
        hits = bm25_topk(question, k)
        t["retrieve"] = (time.perf_counter() - t0) * 1000
        return hits, t

    if mode in ("rrf", "rerank"):
        # top-20 from each path then fuse.
        t0 = time.perf_counter()
        qvec = embed_query(question)
        t["embed"] = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        dense = pgvector_topk(qvec, 20)
        t["retrieve_dense"] = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        lex = bm25_topk(question, 20)
        t["retrieve_bm25"] = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        fused = rrf_merge(dense, lex, top_k=20)
        t["fuse"] = (time.perf_counter() - t0) * 1000
        if mode == "rrf":
            return fused[:k], t
        # rerank top-20 → top-K
        t0 = time.perf_counter()
        ranked = rerank_hits(question, fused, top_k=k)
        t["rerank"] = (time.perf_counter() - t0) * 1000
        return ranked, t

    raise ValueError(f"unknown mode: {mode}")


def build_messages(question, hits):
    context_block = "\n".join(f"[{h['id']}] ({h['label']}) {h['text']}"
                              for h in hits)
    user = f"Context passages:\n{context_block}\n\nQuestion: {question}"
    return [
        {"role": "system", "content": STRICT_SYSTEM},
        {"role": "user", "content": user},
    ]


def stream_answer(messages, max_tokens=256, temperature=0.0):
    body = json.dumps({
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }).encode()
    req = urllib.request.Request(LLM_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    t_start = time.perf_counter()
    first_token_ms = None
    parts = []
    token_count = 0
    with urllib.request.urlopen(req, timeout=120) as r:
        for raw in r:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            delta = chunk["choices"][0].get("delta", {})
            piece = delta.get("content") or ""
            if piece:
                if first_token_ms is None:
                    first_token_ms = (time.perf_counter() - t_start) * 1000
                parts.append(piece)
                token_count += 1
    total_ms = (time.perf_counter() - t_start) * 1000
    return "".join(parts), first_token_ms, total_ms, token_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--mode", choices=["naive", "bm25", "rrf", "rerank"],
                    default="rrf")
    ap.add_argument("--k", type=int, default=5,
                    help="top-K chunks to feed the generator")
    ap.add_argument("--no-generate", action="store_true",
                    help="skip the LLM step; emit retrieval only")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    hits, retrieval_t = retrieve(args.question, args.mode, args.k)

    record = {
        "question": args.question,
        "mode": args.mode,
        "k": args.k,
        "retrieved": [{"id": h["id"], "label": h["label"]} for h in hits],
        "timings_ms": {k: round(v, 2) for k, v in retrieval_t.items()},
    }

    if not args.no_generate:
        messages = build_messages(args.question, hits)
        answer, ttft_ms, generate_ms, tok = stream_answer(messages)
        record["answer"] = answer.strip()
        record["timings_ms"]["generate_first_token"] = round(ttft_ms, 2) if ttft_ms else None
        record["timings_ms"]["generate_total"] = round(generate_ms, 2)
        record["completion_tokens"] = tok

    if args.json:
        print(json.dumps(record))
        return

    print(f"Q: {args.question}   [mode={args.mode}, k={args.k}]\n")
    print("Retrieved:")
    for h in hits:
        preview = h["text"][:90].replace("\n", " ")
        print(f"  [{h['id']:>4}] {h['label']:<9} {preview}")
    if "answer" in record:
        print(f"\nA: {record['answer']}\n")
    tt = record["timings_ms"]
    print("Timings (ms): " + "  ".join(f"{k}={v}" for k, v in tt.items()))


if __name__ == "__main__":
    main()
