#!/usr/bin/env python3
"""Naive RAG on a DGX Spark: embed-query → pgvector top-K → strict-context
prompt → streaming chat/completions against a local Llama 3.1 8B NIM.

No third-party packages. stdlib only, matching the article #2 and #3 ethos.

Usage:
    python3 ask.py "What happened in the 2004 Athens Olympics?"
    python3 ask.py --k 5 --json "Who won the 2004 US presidential election?"
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
    """POST to the Nemotron Retriever NIM with input_type=query."""
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


def pgvector_search(qvec, k):
    """Top-K cosine neighbours via ORDER BY embedding <=> $1 LIMIT k.

    We feed SQL on stdin to psql so the 1024-float query vector doesn't have
    to survive shell quoting. Columns come back tab-separated: id, label,
    cosine distance, chunk text.
    """
    vec_literal = "[" + ",".join(f"{x:.6f}" for x in qvec) + "]"
    sql = (
        "SELECT id, label, (embedding <=> '" + vec_literal + "') AS dist, text "
        "FROM chunks "
        "ORDER BY embedding <=> '" + vec_literal + "' "
        f"LIMIT {int(k)};"
    )
    proc = subprocess.run(PSQL, input=sql, capture_output=True, text=True,
                          timeout=10, check=True)
    hits = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        row_id, label, dist, text = line.split("\t", 3)
        hits.append({
            "id": int(row_id),
            "label": label,
            "distance": float(dist),
            "text": text,
        })
    return hits


def build_messages(question, hits):
    context_block = "\n".join(f"[{h['id']}] ({h['label']}) {h['text']}"
                              for h in hits)
    user = (f"Context passages:\n{context_block}\n\n"
            f"Question: {question}")
    return [
        {"role": "system", "content": STRICT_SYSTEM},
        {"role": "user", "content": user},
    ]


def stream_answer(messages, max_tokens=256, temperature=0.0):
    """Stream chat/completions; return (answer_text, first_token_ms,
    total_generate_ms, completion_tokens)."""
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
    ap.add_argument("--k", type=int, default=5, help="top-K chunks to retrieve")
    ap.add_argument("--json", action="store_true",
                    help="emit one JSON record on stdout instead of prose")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress streaming echo (implied by --json)")
    args = ap.parse_args()

    # 1. Embed the query.
    t0 = time.perf_counter()
    qvec = embed_query(args.question)
    embed_ms = (time.perf_counter() - t0) * 1000

    # 2. pgvector top-K.
    t0 = time.perf_counter()
    hits = pgvector_search(qvec, args.k)
    retrieve_ms = (time.perf_counter() - t0) * 1000

    # 3. Format prompt + stream generation.
    messages = build_messages(args.question, hits)
    answer, ttft_ms, generate_ms, tok = stream_answer(messages)

    record = {
        "question": args.question,
        "k": args.k,
        "retrieved": [{"id": h["id"], "label": h["label"],
                       "distance": round(h["distance"], 4)} for h in hits],
        "answer": answer.strip(),
        "timings_ms": {
            "embed": round(embed_ms, 2),
            "retrieve": round(retrieve_ms, 2),
            "generate_first_token": round(ttft_ms, 2) if ttft_ms else None,
            "generate_total": round(generate_ms, 2),
            "end_to_end": round(embed_ms + retrieve_ms + generate_ms, 2),
        },
        "completion_tokens": tok,
    }

    if args.json:
        print(json.dumps(record))
        return

    print(f"Q: {args.question}\n")
    print("Retrieved:")
    for h in hits:
        preview = h["text"][:90].replace("\n", " ")
        print(f"  [{h['id']:>3}] {h['label']:<9} d={h['distance']:.3f}  "
              f"{preview}")
    print(f"\nA: {answer.strip()}\n")
    t = record["timings_ms"]
    print(f"Timings: embed {t['embed']} ms · retrieve {t['retrieve']} ms "
          f"· ttft {t['generate_first_token']} ms · "
          f"generate {t['generate_total']} ms · total {t['end_to_end']} ms "
          f"· {tok} tokens")


if __name__ == "__main__":
    main()
