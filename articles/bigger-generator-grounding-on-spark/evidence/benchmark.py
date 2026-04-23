#!/usr/bin/env python3
"""Article-6 benchmark: sweep the 30-query qrels set across multiple
generators under a fixed retrieval mode (rerank from article #7).

Records per-query: retrieved ids, answer text, refusal boolean,
recall@5/10 (retrieval — same across generators, sanity check),
and end-to-end latency. Emits per-generator summary with:

    mean recall@5, mean recall@10
    refusal_rate_all
    refusal_rate_on_perfect_retrieval  (refusal | recall@5 == 1.0)
    median / p95 / max wall ms

Usage:
    python3 benchmark.py \\
      --generators llama31-8b,nemotron-super-49b-local,llama33-70b-hosted \\
      --mode rerank --qrels qrels.jsonl --out benchmark.json
"""
import argparse
import json
import statistics
import sys
import time

import hybrid_ask as h

DEFAULT_QRELS = "qrels.jsonl"
DEFAULT_GENERATORS = ["llama31-8b", "nemotron-super-49b-local", "llama33-70b-hosted"]
DEFAULT_MODE = "rerank"


def recall_at(retrieved_ids, relevant_ids, k):
    if not relevant_ids:
        return None
    top = set(retrieved_ids[:k])
    hit = top.intersection(relevant_ids)
    return len(hit) / min(len(relevant_ids), k)


def run_one(query, mode, generator, k_feed, relevant_ids):
    t0 = time.perf_counter()
    hits, retrieval_t = h.retrieve(query, mode, k_feed)
    retrieved_ids = [x["id"] for x in hits]
    messages = h.build_messages(query, hits)
    answer, ttft_ms, gen_ms, tok = h.stream_answer(messages, generator)
    wall_ms = (time.perf_counter() - t0) * 1000
    return {
        "retrieved_ids": retrieved_ids,
        "answer": answer.strip(),
        "refusal": h.is_refusal(answer),
        "completion_tokens": tok,
        "timings_ms": {
            **{k: round(v, 2) for k, v in retrieval_t.items()},
            "generate_first_token": round(ttft_ms, 2) if ttft_ms else None,
            "generate_total": round(gen_ms, 2),
        },
        "wall_ms": round(wall_ms, 2),
        "recall@5": recall_at(retrieved_ids, relevant_ids, 5),
        "recall@10": recall_at(retrieved_ids, relevant_ids, 10),
    }


def summarise(rows):
    by_gen = {}
    for r in rows:
        by_gen.setdefault(r["generator"], []).append(r)
    out = {}
    for gen, rs in by_gen.items():
        r5 = [x["recall@5"] for x in rs if x.get("recall@5") is not None]
        r10 = [x["recall@10"] for x in rs if x.get("recall@10") is not None]
        refusals = [1 if x.get("refusal") else 0 for x in rs if "error" not in x]
        perfect_r5 = [x for x in rs if (x.get("recall@5") or 0) >= 0.999]
        perfect_refusals = [1 if x.get("refusal") else 0 for x in perfect_r5]
        wall = [x["wall_ms"] for x in rs if "wall_ms" in x]
        n_err = sum(1 for x in rs if "error" in x)
        out[gen] = {
            "n": len(rs),
            "n_errors": n_err,
            "mean_recall@5": round(statistics.mean(r5), 4) if r5 else None,
            "mean_recall@10": round(statistics.mean(r10), 4) if r10 else None,
            "refusal_rate_all": round(statistics.mean(refusals), 4) if refusals else None,
            "n_perfect_retrieval": len(perfect_r5),
            "refusal_rate_on_perfect_retrieval": (
                round(statistics.mean(perfect_refusals), 4) if perfect_refusals else None
            ),
            "median_wall_ms": round(statistics.median(wall), 2) if wall else None,
            "p95_wall_ms": round(sorted(wall)[int(0.95 * len(wall))], 2) if wall else None,
            "max_wall_ms": round(max(wall), 2) if wall else None,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qrels", default=DEFAULT_QRELS)
    ap.add_argument("--generators", default=",".join(DEFAULT_GENERATORS))
    ap.add_argument("--mode", default=DEFAULT_MODE,
                    choices=["naive", "bm25", "rrf", "rerank"])
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--out", default="benchmark.json")
    args = ap.parse_args()

    generators = [g.strip() for g in args.generators.split(",") if g.strip()]
    for g in generators:
        if g not in h.GENERATORS:
            sys.exit(f"unknown generator: {g}. Choices: {list(h.GENERATORS)}")

    qrels = [json.loads(line) for line in open(args.qrels)]

    rows = []
    total = len(qrels) * len(generators)
    print(f"Running {len(qrels)} queries × {len(generators)} generators "
          f"(mode={args.mode}) = {total} LLM calls", file=sys.stderr)
    done = 0
    for q in qrels:
        for gen in generators:
            done += 1
            try:
                r = run_one(q["query"], args.mode, gen, args.k, q["relevant_ids"])
            except Exception as e:
                r = {"error": str(e), "retrieved_ids": [], "wall_ms": 0,
                     "recall@5": 0.0, "recall@10": 0.0, "refusal": False,
                     "answer": "", "timings_ms": {}}
            r.update({"id": q["id"], "query": q["query"], "mode": args.mode,
                      "generator": gen,
                      "relevant_count": len(q["relevant_ids"])})
            rows.append(r)
            marker = "REFUSE" if r.get("refusal") else ("ERR" if "error" in r else "ANS")
            r5 = r.get("recall@5")
            print(f"  [{done:>3}/{total}] {q['id']:>4}  {gen:<28} "
                  f"{marker:<6} r@5={(r5 if r5 is not None else float('nan')):.2f}  "
                  f"wall={r['wall_ms']:.0f} ms",
                  file=sys.stderr, flush=True)

    summary = summarise(rows)
    out = {"summary": summary, "per_query": rows}
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)

    print("\n=== summary ===")
    hdr = (f"{'generator':<30} {'n':>3} {'r@5':>6} {'r@10':>6} "
           f"{'refuse':>7} {'refOnR5':>8} {'med_ms':>8} {'p95_ms':>8}")
    print(hdr)
    print("-" * len(hdr))
    for gen in generators:
        s = summary.get(gen, {})
        if not s:
            continue
        print(f"{gen:<30} {s['n']:>3} "
              f"{(s['mean_recall@5'] or 0):>6.3f} "
              f"{(s['mean_recall@10'] or 0):>6.3f} "
              f"{(s['refusal_rate_all'] or 0):>7.3f} "
              f"{(s['refusal_rate_on_perfect_retrieval'] or 0):>8.3f} "
              f"{(s['median_wall_ms'] or 0):>8.1f} "
              f"{(s['p95_wall_ms'] or 0):>8.1f}")


if __name__ == "__main__":
    main()
