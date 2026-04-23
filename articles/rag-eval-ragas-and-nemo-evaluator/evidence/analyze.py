#!/usr/bin/env python3
"""Post-grading analysis: headline table, per-variant breakdown, correlations."""
import json
import statistics
from collections import defaultdict
from pathlib import Path

GRADED = Path("/home/nvidia/rag-eval-work/graded.jsonl")
OUT = Path("/home/nvidia/rag-eval-work/analysis.json")


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 3) if xs else None


def main():
    rows = [json.loads(l) for l in GRADED.open()]
    by_variant = defaultdict(list)
    for r in rows:
        by_variant[r["variant"]].append(r)

    table = {}
    for v, items in by_variant.items():
        corr = [r["correctness"] for r in items if r["correctness"] is not None]
        rel = [r["relevance"] for r in items if r["relevance"] is not None]
        faith = [r["faithfulness"] for r in items if r["faithfulness"] is not None]
        walls = [r["wall_s"] for r in items]
        toks = [r.get("new_tokens") or r.get("completion_tokens") or 0 for r in items]
        refused = sum(1 for r in items if r["refused"])

        # retrieval at top-3 (what generator saw)
        rtr = [r["retrieval"] for r in items if r.get("retrieval")]
        chunk_hit = sum(1 for x in rtr if x.get("hit_at_k")) / len(rtr) if rtr else None
        slug_hit = sum(1 for x in rtr if x.get("slug_match_at_k")) / len(rtr) if rtr else None
        ranks = [x.get("gold_rank") for x in rtr if x.get("gold_rank") is not None]

        table[v] = {
            "n": len(items),
            "correctness_mean": mean(corr),
            "correctness_ge_4": sum(1 for c in corr if c >= 4),
            "correctness_eq_5": sum(1 for c in corr if c >= 5),
            "correctness_dist": {s: sum(1 for c in corr if round(c) == s) for s in range(6)},
            "relevance_mean": mean(rel),
            "faithfulness_mean": mean(faith),
            "refusal_rate": round(refused / len(items), 3),
            "wall_s_mean": round(statistics.mean(walls), 3),
            "tokens_mean": round(statistics.mean(toks), 1),
            "chunk_hit_at_3": round(chunk_hit, 3) if chunk_hit is not None else None,
            "slug_hit_at_3": round(slug_hit, 3) if slug_hit is not None else None,
            "gold_rank_when_hit_mean": mean(ranks),
        }

    # Correlations (per-row, RAG variants only): faithfulness vs correctness.
    faith_corr = defaultdict(list)
    for v, items in by_variant.items():
        for r in items:
            if r.get("faithfulness") is not None and r.get("correctness") is not None:
                faith_corr[v].append((r["faithfulness"], r["correctness"]))

    def corr_pearson(xys):
        if len(xys) < 3:
            return None
        xs, ys = zip(*xys)
        mx, my = statistics.mean(xs), statistics.mean(ys)
        num = sum((x - mx) * (y - my) for x, y in xys)
        dx = sum((x - mx) ** 2 for x, y in xys) ** 0.5
        dy = sum((y - my) ** 2 for x, y in xys) ** 0.5
        return round(num / (dx * dy), 3) if dx * dy else None

    correlations = {v: corr_pearson(pairs) for v, pairs in faith_corr.items()}

    # Per-question cross-variant: does the same question always fail?
    by_idx = defaultdict(dict)
    for r in rows:
        by_idx[r["idx"]][r["variant"]] = r["correctness"]

    always_fail = 0
    always_pass = 0
    variants_set = set(by_variant.keys())
    for idx, d in by_idx.items():
        if set(d.keys()) != variants_set:
            continue
        if all((v or 0) <= 1 for v in d.values()):
            always_fail += 1
        if all((v or 0) >= 4 for v in d.values()):
            always_pass += 1

    OUT.write_text(json.dumps({
        "table": table,
        "faithfulness_vs_correctness_pearson": correlations,
        "n_questions_all_variants_scored_ge_4": always_pass,
        "n_questions_all_variants_scored_le_1": always_fail,
    }, indent=2))
    print(json.dumps({
        "table": table,
        "faithfulness_vs_correctness_pearson": correlations,
        "always_pass_ge_4": always_pass,
        "always_fail_le_1": always_fail,
    }, indent=2))


if __name__ == "__main__":
    main()
