#!/usr/bin/env python3
"""Grade all variants against held-out references.

Computes:
 - retrieval: P@5, R@5, P@3, gold_rank (for variants with retrieval)
 - correctness: judge 0-5 vs reference (NIM 8B judge)
 - refusal rate
 - faithfulness: NIM 8B judge scores answer-vs-context grounding (0-1)
 - answer_relevance: NIM 8B judge scores answer-addresses-question (0-1)
 - wall_s, new_tokens
"""
import json
import os
import re
import time
import urllib.request
from pathlib import Path

LLM_URL = os.environ.get("LLM_URL", "http://localhost:8000/v1/chat/completions")
LLM_MODEL = "meta/llama-3.1-8b-instruct"

IN = Path("/home/nvidia/rag-eval-work/preds_all.jsonl")
OUT_DETAIL = Path("/home/nvidia/rag-eval-work/graded.jsonl")
OUT_SUMMARY = Path("/home/nvidia/rag-eval-work/summary.json")

REFUSAL_PATTERNS = [
    r"(?i)i (?:do not|don['’]t) (?:know|have)",
    r"(?i)i (?:cannot|can['’]t|am (?:not )?able to) (?:answer|provide|determine|find)",
    r"(?i)(?:the )?(?:provided )?context (?:does not|doesn['’]t) (?:contain|include|mention)",
    r"(?i)not (?:specified|mentioned|provided|available|stated|given)",
    r"(?i)i (?:am unable|cannot) to (?:determine|verify)",
    r"(?i)no information",
    r"(?i)\bunclear\b",
    r"(?i)insufficient (?:information|context|data)",
]


def is_refusal(text: str) -> bool:
    if not text:
        return True
    return any(re.search(p, text) for p in REFUSAL_PATTERNS)


def judge_call(system, user, max_tokens=120):
    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        LLM_URL, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


CORRECTNESS_SYS = (
    "You are an impartial grader. Score a predicted answer against a reference "
    "answer on a 0-5 scale: 5=exactly correct, 4=essentially correct with "
    "minor wording differences, 3=partially correct, 2=mostly wrong but with "
    "a correct fragment, 1=confidently wrong or unrelated, 0=refusal or empty. "
    "Return ONLY a JSON object: {\"score\": N, \"rationale\": \"...\"}"
)

FAITH_SYS = (
    "You are an impartial grader of answer faithfulness. Given context passages "
    "and an answer, decide if every factual claim in the answer is SUPPORTED by "
    "the context. Score: 1.0 = all claims supported, 0.5 = some claims "
    "supported, 0.0 = no claims supported. If the answer is a refusal or says "
    "the context doesn't contain the answer, score N/A -> use 0.5 if the "
    "context indeed does not contain a direct answer and 0.0 if it does. "
    "Return ONLY a JSON object: {\"score\": X, \"rationale\": \"...\"}"
)

RELEVANCE_SYS = (
    "You are an impartial grader of answer relevance. Given a question and an "
    "answer, score whether the answer addresses the question: 1.0 = directly "
    "answers, 0.5 = partially addresses or hedges, 0.0 = off-topic or refuses. "
    "Return ONLY a JSON object: {\"score\": X, \"rationale\": \"...\"}"
)


def parse_json_score(text: str):
    m = re.search(r"\{[^{}]*\"score\"\s*:\s*([\d.]+)[^{}]*\}", text, re.DOTALL)
    if m:
        return float(m.group(1)), text.strip()
    m = re.search(r"\"score\"\s*:\s*([\d.]+)", text)
    if m:
        return float(m.group(1)), text.strip()
    return None, text.strip()


def retrieval_metrics(row):
    if not row.get("contexts"):
        return {}
    gold_slug = row["gold_slug"]
    gold_chunk = row["gold_chunk"]
    ranks = [(h["slug"], h["chunk_idx"]) for h in row["contexts"]]
    gold_idx = None
    for i, (s, c) in enumerate(ranks):
        if s == gold_slug and c == gold_chunk:
            gold_idx = i
            break
    return {
        "hit_at_k": gold_idx is not None,
        "gold_rank": gold_idx,  # 0-indexed within the prompt's top-3
        "slug_match_at_k": any(s == gold_slug for s, _ in ranks),
    }


def main():
    rows = [json.loads(l) for l in IN.open()]
    print(f"grading {len(rows)} rows", flush=True)
    out = OUT_DETAIL.open("w")
    t0 = time.time()
    for i, row in enumerate(rows):
        # retrieval
        rtr = retrieval_metrics(row)

        # correctness (judge 0-5)
        user = (
            f"Question: {row['question']}\n"
            f"Reference answer: {row['reference']}\n"
            f"Predicted answer: {row['prediction']}\n\nGrade:"
        )
        raw = judge_call(CORRECTNESS_SYS, user)
        corr_score, corr_text = parse_json_score(raw)

        # relevance (judge 0-1)
        user = f"Question: {row['question']}\nAnswer: {row['prediction']}\n\nGrade:"
        raw = judge_call(RELEVANCE_SYS, user)
        rel_score, rel_text = parse_json_score(raw)

        # faithfulness (judge 0-1) — only when contexts present
        faith_score = None
        faith_text = ""
        if row.get("contexts"):
            # Truncate each chunk to first 500 words to fit judge context.
            def _trim(txt, w=500):
                ws = txt.split()
                return " ".join(ws[:w]) + (" [...truncated]" if len(ws) > w else "")
            ctx = "\n\n".join(
                f"[{h['slug']} #{h['chunk_idx']}]\n{_trim(h['text'])}"
                for h in row["contexts"]
            )
            user = f"Context passages:\n\n{ctx}\n\nAnswer: {row['prediction']}\n\nGrade:"
            try:
                raw = judge_call(FAITH_SYS, user, max_tokens=160)
                faith_score, faith_text = parse_json_score(raw)
            except urllib.error.HTTPError as e:
                faith_text = f"<judge error {e.code}>"
                faith_score = None

        refused = is_refusal(row["prediction"])
        detail = {
            **row,
            "refused": refused,
            "retrieval": rtr,
            "correctness": corr_score,
            "correctness_rationale": corr_text[:400],
            "relevance": rel_score,
            "relevance_rationale": rel_text[:200],
            "faithfulness": faith_score,
            "faithfulness_rationale": faith_text[:400],
        }
        out.write(json.dumps(detail) + "\n")
        out.flush()
        if (i + 1) % 10 == 0 or i + 1 == len(rows):
            print(f"  {i + 1}/{len(rows)}  ({time.time() - t0:.1f}s)", flush=True)
    out.close()

    # summary
    import statistics
    graded = [json.loads(l) for l in OUT_DETAIL.open()]
    variants = {}
    for r in graded:
        v = r["variant"]
        variants.setdefault(v, []).append(r)
    summary = {}
    for v, items in variants.items():
        corr = [r["correctness"] for r in items if r["correctness"] is not None]
        rel = [r["relevance"] for r in items if r["relevance"] is not None]
        faith = [r["faithfulness"] for r in items if r["faithfulness"] is not None]
        refused = sum(1 for r in items if r["refused"])
        walls = [r["wall_s"] for r in items]
        tokens = [r.get("new_tokens") or r.get("completion_tokens") or 0 for r in items]
        hit = [r["retrieval"].get("hit_at_k", False) for r in items if r["retrieval"]]
        slug_hit = [r["retrieval"].get("slug_match_at_k", False) for r in items if r["retrieval"]]
        s = {
            "n": len(items),
            "mean_correctness_0_5": round(statistics.mean(corr), 2) if corr else None,
            "correctness_ge_4": sum(1 for c in corr if c >= 4),
            "correctness_eq_5": sum(1 for c in corr if c >= 5),
            "mean_relevance_0_1": round(statistics.mean(rel), 3) if rel else None,
            "mean_faithfulness_0_1": round(statistics.mean(faith), 3) if faith else None,
            "refusal_rate": round(refused / len(items), 3),
            "mean_wall_s": round(statistics.mean(walls), 3),
            "mean_new_tokens": round(statistics.mean(tokens), 1),
            "p_chunk_at_k": round(sum(hit) / len(hit), 3) if hit else None,
            "p_slug_at_k": round(sum(slug_hit) / len(slug_hit), 3) if slug_hit else None,
        }
        summary[v] = s
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
