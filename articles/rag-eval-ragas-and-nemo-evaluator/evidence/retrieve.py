#!/usr/bin/env python3
"""For each held-out question, run naive-pgvector and rerank retrieval.

Saves retrieved.jsonl with one record per question containing both hit lists.
Hits include slug, chunk_idx, text, and distance/score.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

EMBED_URL = os.environ.get("EMBED_URL", "http://localhost:8001/v1/embeddings")
EMBED_MODEL = "nvidia/llama-nemotron-embed-1b-v2"
EMBED_DIM = 1024

RERANK_URL = ("https://ai.api.nvidia.com/v1/retrieval/nvidia/"
              "llama-3_2-nv-rerankqa-1b-v2/reranking")
RERANK_MODEL = "nvidia/llama-3.2-nv-rerankqa-1b-v2"
NGC_API_KEY = os.environ.get("NGC_API_KEY", "")

EVAL = Path("/home/nvidia/nvidia-learn/articles/lora-on-your-own-qa-pairs/"
            "evidence/qa-eval.jsonl")
OUT = Path("/home/nvidia/rag-eval-work/retrieved.jsonl")

PSQL = ["docker", "exec", "-i", "pgvector",
        "psql", "-U", "spark", "-d", "vectors",
        "-v", "ON_ERROR_STOP=1", "-qAt", "-F", "\t"]


def embed_query(text):
    body = json.dumps({
        "model": EMBED_MODEL,
        "input": [text],
        "input_type": "query",
        "encoding_format": "float",
        "truncate": "END",
        "dimensions": EMBED_DIM,
    }).encode()
    req = urllib.request.Request(
        EMBED_URL, data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["data"][0]["embedding"]


def pgvector_topk(qvec, k):
    sql = (
        "SELECT id, slug, chunk_idx, embedding <=> $1 AS dist, text "
        "FROM blog_chunks ORDER BY embedding <=> $1 LIMIT " + str(k) + ";"
    )
    prepared = (
        "\\set qvec '" + json.dumps(qvec) + "'\n"
        "PREPARE q AS " + sql.replace("$1", "$1::vector") + "\n"
        "EXECUTE q(:'qvec');\n"
    )
    r = subprocess.run(PSQL, input=prepared.encode(), capture_output=True)
    if r.returncode:
        sys.stderr.write(r.stderr.decode())
        raise SystemExit(r.returncode)
    hits = []
    for line in r.stdout.decode().strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        row_id, slug, chunk_idx, dist, text = parts[0], parts[1], parts[2], parts[3], "\t".join(parts[4:])
        hits.append({
            "id": int(row_id),
            "slug": slug,
            "chunk_idx": int(chunk_idx),
            "dist": float(dist),
            "text": text,
        })
    return hits


def rerank(question, hits, top_k):
    if not NGC_API_KEY:
        raise RuntimeError("NGC_API_KEY not set")
    body = json.dumps({
        "model": RERANK_MODEL,
        "query": {"text": question},
        "passages": [{"text": h["text"]} for h in hits],
    }).encode()
    req = urllib.request.Request(RERANK_URL, data=body, headers={
        "Authorization": f"Bearer {NGC_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        rankings = json.loads(r.read())["rankings"]
    # rankings: [{"index": i, "logit": s}, ...] sorted best-first.
    ranked = []
    for entry in rankings[:top_k]:
        hit = dict(hits[entry["index"]])
        hit["rerank_logit"] = entry["logit"]
        ranked.append(hit)
    return ranked


def main():
    items = [json.loads(l) for l in EVAL.open()]
    print(f"eval items: {len(items)}", flush=True)

    out = OUT.open("w")
    t0 = time.time()
    for i, it in enumerate(items):
        q = it["question"]
        qvec = embed_query(q)

        hits20 = pgvector_topk(qvec, 20)
        naive5 = hits20[:5]
        reranked5 = rerank(q, hits20, top_k=5)

        rec = {
            "idx": i,
            "question": q,
            "reference": it["answer"],
            "gold_slug": it["source"],
            "gold_chunk": it["chunk"],
            "naive_top5": [{"slug": h["slug"], "chunk_idx": h["chunk_idx"],
                             "dist": h["dist"], "text": h["text"]} for h in naive5],
            "rerank_top5": [{"slug": h["slug"], "chunk_idx": h["chunk_idx"],
                              "dist": h["dist"], "rerank_logit": h["rerank_logit"],
                              "text": h["text"]} for h in reranked5],
        }
        out.write(json.dumps(rec) + "\n")
        out.flush()
        if (i + 1) % 5 == 0 or i + 1 == len(items):
            print(f"  {i + 1}/{len(items)}  ({time.time() - t0:.1f}s)", flush=True)

    out.close()
    print(f"wrote {OUT}  in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
