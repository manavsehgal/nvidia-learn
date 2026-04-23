#!/usr/bin/env python3
"""Build prompts for LoRA-with-RAG inference (top-3 naive ctx)."""
import json
from pathlib import Path

IN = Path("/home/nvidia/rag-eval-work/retrieved.jsonl")
OUT = Path("/home/nvidia/rag-eval-work/prompts_lora.jsonl")

records = [json.loads(l) for l in IN.open()]
with OUT.open("w") as f:
    for r in records:
        ctxs = r["naive_top5"][:3]
        ctx_block = "\n\n".join(
            f"[{h['slug']} #{h['chunk_idx']}]\n{h['text']}" for h in ctxs
        )
        user = (
            f"Context passages:\n\n{ctx_block}\n\nQuestion: {r['question']}\n\nAnswer:"
        )
        f.write(json.dumps({
            "idx": r["idx"],
            "question": r["question"],
            "reference": r["reference"],
            "gold_slug": r["gold_slug"],
            "gold_chunk": r["gold_chunk"],
            "user_prompt": user,
            "contexts": [
                {"slug": h["slug"], "chunk_idx": h["chunk_idx"], "text": h["text"]}
                for h in ctxs
            ],
        }) + "\n")
print(f"wrote {OUT}")
