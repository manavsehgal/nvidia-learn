"""Side-by-side compare of two AutoResearchBench summaries.

Reads N summary JSONs produced by `analyze_run.py` and emits a unified
comparison: per-model status counts, wall-time / turn / candidate stats,
and a tabular per-question delta.

Usage:
    python scripts/compare_runs.py \
        evidence/llama-3.1-8b-summary.json \
        evidence/llama-3.3-70b-q4-summary.json \
        --output evidence/comparison.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("summaries", nargs="+", type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()

    runs = [json.loads(s.read_text()) for s in args.summaries]

    out = {
        "models": [r["label"] for r in runs],
        "n_questions": runs[0]["n_questions"],
        "by_model": {},
        "per_question": [],
    }
    for r in runs:
        out["by_model"][r["label"]] = {
            "status_counts": r["status_counts"],
            "wall_seconds": r["wall_seconds"],
            "turns": r["turns"],
            "candidates": r["candidates"],
        }

    n = runs[0]["n_questions"]
    for i in range(n):
        row: dict = {"q_index": i,
                     "arxiv_id": runs[0]["per_question"][i]["arxiv_id"],
                     "truth_title": runs[0]["per_question"][i]["truth_title"]}
        for r in runs:
            q = r["per_question"][i]
            row[r["label"]] = {
                "status": q["status"],
                "wall_seconds": q["wall_seconds"],
                "turns": q["turns"],
                "candidates": q["candidates"],
            }
        out["per_question"].append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {args.output}")
    print(f"  models       : {out['models']}")
    print(f"  n_questions  : {out['n_questions']}")
    for label, agg in out["by_model"].items():
        print(f"  --- {label} ---")
        print(f"     status      : {agg['status_counts']}")
        print(f"     wall_s mean : {agg['wall_seconds']['mean']:.1f}")
        print(f"     turns mean  : {agg['turns']['mean']:.2f}")
        print(f"     cands mean  : {agg['candidates']['mean']:.2f}")


if __name__ == "__main__":
    main()
