#!/usr/bin/env python3
"""Generate answers with NIM 8B for naive_8b and rerank_8b variants.

Input: retrieved.jsonl
Output: preds_nim.jsonl — one record per (question, variant) with prediction + wallclock.
"""
import json
import os
import time
import urllib.request
from pathlib import Path

LLM_URL = os.environ.get("LLM_URL", "http://localhost:8000/v1/chat/completions")
LLM_MODEL = "meta/llama-3.1-8b-instruct"

IN = Path("/home/nvidia/rag-eval-work/retrieved.jsonl")
OUT = Path("/home/nvidia/rag-eval-work/preds_nim.jsonl")

SYS = (
    "You are a careful assistant answering questions about the nvidia-learn "
    "project (articles by Manav Sehgal on running AI locally on the NVIDIA "
    "DGX Spark). Answer using ONLY the provided context passages, each "
    "labeled with its source article slug and chunk index like "
    "[article-slug #N]. Answer concisely and concretely. Cite the "
    "passages you used in a trailing line: 'Sources: [slug #N, slug #N]'. "
    "If the context does not contain the answer, reply with exactly one "
    "sentence: 'The provided context does not contain the answer.'"
)


def build_user_prompt(question, contexts):
    parts = []
    for h in contexts:
        parts.append(f"[{h['slug']} #{h['chunk_idx']}]\n{h['text']}")
    ctx = "\n\n".join(parts)
    return f"Context passages:\n\n{ctx}\n\nQuestion: {question}\n\nAnswer:"


def nim_call(question, contexts, max_tokens=160):
    # Use top-3 for generation (k=5 kept in retrieval for P/R@5 metrics).
    contexts = contexts[:3]
    msgs = [
        {"role": "system", "content": SYS},
        {"role": "user", "content": build_user_prompt(question, contexts)},
    ]
    body = json.dumps({
        "model": LLM_MODEL,
        "messages": msgs,
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        LLM_URL, data=body,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    dt = time.time() - t0
    txt = resp["choices"][0]["message"]["content"].strip()
    usage = resp.get("usage", {})
    return {
        "prediction": txt,
        "wall_s": dt,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
    }


def main():
    records = [json.loads(l) for l in IN.open()]
    print(f"items: {len(records)}", flush=True)

    out = OUT.open("w")
    t0 = time.time()
    for i, r in enumerate(records):
        for variant in ("naive_8b", "rerank_8b"):
            ctxs = r["naive_top5"] if variant == "naive_8b" else r["rerank_top5"]
            pred = nim_call(r["question"], ctxs)
            row = {
                "idx": r["idx"],
                "variant": variant,
                "question": r["question"],
                "reference": r["reference"],
                "gold_slug": r["gold_slug"],
                "gold_chunk": r["gold_chunk"],
                "contexts": [
                    {"slug": h["slug"], "chunk_idx": h["chunk_idx"], "text": h["text"]}
                    for h in ctxs
                ],
                **pred,
            }
            out.write(json.dumps(row) + "\n")
            out.flush()
        if (i + 1) % 5 == 0 or i + 1 == len(records):
            print(f"  {i + 1}/{len(records)}  ({time.time() - t0:.1f}s)", flush=True)
    out.close()
    print(f"wrote {OUT} in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
