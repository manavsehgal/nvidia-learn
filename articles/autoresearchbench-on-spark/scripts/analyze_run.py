"""Aggregate one AutoResearchBench inference run with fieldkit.eval.

Reads `inference_output.jsonl` produced by AutoResearchBench's `run_inference.sh`
and emits a compact summary JSON: per-question status, turn count, wall time,
candidate count, plus rolled-up stats via `fieldkit.eval.summarize_metric`.

Usage:
    python scripts/analyze_run.py \
        --input  evidence/runs/llama-3.1-8b/inference_output.jsonl \
        --label  llama-3.1-8b \
        --output evidence/llama-3.1-8b-summary.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fieldkit.eval import Bench, summarize_metric


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--label", required=True, help="Model label, e.g. llama-3.1-8b")
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()

    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]

    bench = Bench(name=f"autoresearchbench/{args.label}", metrics=["turns", "candidates"])
    per_q = []
    for i, r in enumerate(rows):
        ir = r["inference_results"][0]
        td = ir.get("turn_details") or []
        fc = ir.get("final_candidates") or []
        truth = r["input_data"]["answer"][0] if r["input_data"].get("answer") else None
        turn_detail = []
        for t in td:
            if isinstance(t, dict):
                turn_detail.append({
                    "turn": t.get("turn"),
                    "action": t.get("action"),
                    "duration_s": round(float(t.get("duration") or 0), 2),
                    "input_tokens": t.get("input_tokens"),
                    "output_tokens": t.get("output_tokens"),
                    "papers_retrieved": t.get("papers_retrieved_this_turn"),
                })
        rec = {
            "q_index": i,
            "arxiv_id": r["input_data"].get("arxiv_id"),
            "truth_title": truth,
            "status": ir["status"],
            "wall_seconds": round(float(ir["total_time"]), 2),
            "turns": len(td),
            "candidates": len(fc),
            "tool_format_errors": sum(1 for t in turn_detail if t["action"] == "error"),
            "tool_calls": sum(1 for t in turn_detail if t["action"] == "tool"),
            "papers_retrieved_total": sum(int(t["papers_retrieved"] or 0) for t in turn_detail),
            "turn_detail": turn_detail,
        }
        per_q.append(rec)
        bench.record(
            input=rec["arxiv_id"],
            output={"status": rec["status"], "candidates": rec["candidates"]},
            latency_ms=float(ir["total_time"]) * 1000.0,
            success=(rec["status"] == "finished" and rec["candidates"] > 0),
            error=None if rec["status"] == "finished" else rec["status"],
            tags={"q_index": i, "model": args.label},
            turns=float(rec["turns"]),
            candidates=float(rec["candidates"]),
        )

    statuses = [q["status"] for q in per_q]
    summary = {
        "label": args.label,
        "n_questions": len(rows),
        "status_counts": {s: statuses.count(s) for s in sorted(set(statuses))},
        "wall_seconds": summarize_metric(q["wall_seconds"] for q in per_q),
        "turns": summarize_metric(q["turns"] for q in per_q),
        "candidates": summarize_metric(q["candidates"] for q in per_q),
        "per_question": per_q,
        "fieldkit_bench": bench.to_dict(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {args.output}")
    print(f"  n_questions    : {summary['n_questions']}")
    print(f"  status_counts  : {summary['status_counts']}")
    print(f"  wall_seconds   : {summary['wall_seconds']}")
    print(f"  turns          : {summary['turns']}")
    print(f"  candidates     : {summary['candidates']}")


if __name__ == "__main__":
    main()
