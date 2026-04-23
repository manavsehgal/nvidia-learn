#!/usr/bin/env python3
"""Embed corpus.jsonl via the Nemotron Retriever NIM at :8001 and stream
COPY records into the running pgvector container on :5432.

Design notes:
- No Python psycopg. We invoke `docker exec -i pgvector psql` once and feed
  it a COPY FROM STDIN stream, which is about 30x faster than individual
  INSERTs at this row count and also saves us a pip install.
- The embedder is 2048-d by default; we pass `dimensions=1024` to exploit
  Nemotron's Matryoshka layout and match the pgvector column type.
- Batch size 32 follows the article #4 benchmark sweet spot (~28 docs/s).
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

CORPUS = os.environ.get("CORPUS", "corpus.jsonl")
NIM_URL = os.environ.get("NIM_URL", "http://localhost:8001/v1/embeddings")
MODEL = "nvidia/llama-nemotron-embed-1b-v2"
DIM = 1024
BATCH = 32

PSQL = ["docker", "exec", "-i", "pgvector",
        "psql", "-U", "spark", "-d", "vectors", "-v", "ON_ERROR_STOP=1",
        "-c", "COPY chunks (id, label, text, embedding) FROM STDIN"]

def embed(texts):
    body = json.dumps({
        "model": MODEL,
        "input": texts,
        "input_type": "passage",
        "encoding_format": "float",
        "truncate": "END",
        "dimensions": DIM,
    }).encode()
    req = urllib.request.Request(NIM_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["data"]

def vec_literal(v):
    # pgvector COPY text format: a bracketed comma-separated list.
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"

def tsv_escape(s):
    # COPY text format: backslash-escape \, \n, \r, \t.
    return (s.replace("\\", "\\\\")
             .replace("\n", "\\n")
             .replace("\r", "\\r")
             .replace("\t", "\\t"))

def main():
    rows = [json.loads(l) for l in open(CORPUS)]
    print(f"loaded {len(rows)} rows from {CORPUS}")

    proc = subprocess.Popen(PSQL, stdin=subprocess.PIPE, text=True)
    t0 = time.perf_counter()
    sent = 0
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        texts = [r["text"] for r in batch]
        data = embed(texts)
        # NIM preserves input order in `data[].index`.
        data = sorted(data, key=lambda d: d["index"])
        for r, d in zip(batch, data):
            proc.stdin.write(
                f"{r['id']}\t{r['label']}\t{tsv_escape(r['text'])}\t{vec_literal(d['embedding'])}\n"
            )
        sent += len(batch)
        if sent % 128 == 0 or sent == len(rows):
            print(f"  embedded {sent}/{len(rows)}  ({sent / (time.perf_counter() - t0):.1f} docs/s)")

    proc.stdin.close()
    rc = proc.wait()
    elapsed = time.perf_counter() - t0
    if rc != 0:
        sys.exit(f"psql exited with {rc}")
    print(f"done: {sent} rows ingested in {elapsed:.1f}s "
          f"({sent / elapsed:.1f} docs/s end-to-end)")

if __name__ == "__main__":
    main()
