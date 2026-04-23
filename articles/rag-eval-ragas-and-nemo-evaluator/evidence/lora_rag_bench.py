"""Generate answers using LoRA'd Qwen-2.5-3B with RAG context.

Run inside Triton 25.12 container. Mounts:
  /home/nvidia/lora-work       -> /work
  /home/nvidia/rag-eval-work   -> /rag
"""
import json
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE = "/work/base"
ADAPTER = "/work/adapter"
IN = Path("/rag/prompts_lora.jsonl")
OUT = Path("/rag/preds_rag_lora.jsonl")

SYS = (
    "You are an assistant that answers questions about the nvidia-learn DGX Spark project "
    "(articles by Manav Sehgal on running AI locally on the NVIDIA DGX Spark). "
    "Answer concisely, grounded in the project's own content."
)


def main():
    print(f"torch {torch.__version__}  cuda {torch.cuda.is_available()}")
    tok = AutoTokenizer.from_pretrained(BASE)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    print("loading base…")
    base = AutoModelForCausalLM.from_pretrained(
        BASE, dtype=torch.bfloat16, device_map="cuda"
    )
    print("attaching adapter…")
    model = PeftModel.from_pretrained(base, ADAPTER)
    model.eval()

    items = [json.loads(l) for l in IN.open()]
    print(f"items: {len(items)}")
    out = OUT.open("w")
    for i, it in enumerate(items):
        msgs = [
            {"role": "system", "content": SYS},
            {"role": "user", "content": it["user_prompt"]},
        ]
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt").to(model.device)
        t0 = time.time()
        with torch.no_grad():
            gen = model.generate(
                **inputs,
                max_new_tokens=160,
                do_sample=False,
                temperature=1.0,
                top_p=1.0,
                pad_token_id=tok.eos_token_id,
                use_cache=True,
            )
        dt = time.time() - t0
        resp = tok.decode(
            gen[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        ).strip()
        row = {
            "idx": it["idx"],
            "variant": "rag_lora",
            "question": it["question"],
            "reference": it["reference"],
            "gold_slug": it["gold_slug"],
            "gold_chunk": it["gold_chunk"],
            "contexts": it["contexts"],
            "prediction": resp,
            "wall_s": dt,
            "new_tokens": int(gen.shape[1] - inputs["input_ids"].shape[1]),
            "prompt_tokens": int(inputs["input_ids"].shape[1]),
        }
        out.write(json.dumps(row) + "\n")
        out.flush()
        if (i + 1) % 5 == 0 or i + 1 == len(items):
            print(f"  {i + 1}/{len(items)}  dt={dt:.2f}s  tok={row['new_tokens']}")
    out.close()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
