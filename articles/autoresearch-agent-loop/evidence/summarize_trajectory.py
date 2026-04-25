"""
Summarize an agent_loop trajectory.jsonl into the numbers the A4 article
quotes: accept/revert ratio, block distribution, top proposals,
agent-diversity, per-iteration timing.

Reads the trajectory, prints a human-readable report, also writes
trajectory_summary.json next to it.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median


def load(path: Path) -> tuple[dict, list[dict], dict | None]:
    """Returns (header, iterations, summary). Header is the first record
    (with `_meta`); iterations are the per-iter records; summary is the
    last record if it has stage='loop_complete'."""
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    header = records[0] if records and records[0].get("_meta") else {}
    summary = (
        records[-1] if records and records[-1].get("stage") == "loop_complete" else None
    )
    iterations = [r for r in records if "iter" in r]
    return header, iterations, summary


def summarize(path: Path) -> dict:
    header, iters, summary = load(path)
    n = len(iters)
    if n == 0:
        return {"error": "no iterations in trajectory"}

    blocks = [i for i in iters if i.get("stage") == "blocked"]
    nim_errors = [i for i in iters if i.get("stage") == "nim_error"]
    eval_fails = [i for i in iters if i.get("stage") == "eval_failed"]
    evaluated = [i for i in iters if i.get("stage") == "evaluated"]
    keeps = [i for i in evaluated if i.get("decision") == "keep"]
    reverts = [i for i in evaluated if i.get("decision") == "revert"]

    # Block distribution
    block_by_rail = Counter(i.get("rail") for i in blocks)

    # Knob diversity: of all PROPOSED knobs (passed schema), how many distinct?
    proposed_knobs = [i["proposal"]["knob"] for i in iters
                      if i.get("proposal") and i["proposal"].get("knob")]
    knob_distribution = Counter(proposed_knobs)

    # Top improvers: by improvement_frac, descending
    by_improvement = sorted(
        (i for i in evaluated if i.get("improvement_frac") is not None),
        key=lambda r: r["improvement_frac"], reverse=True
    )
    top5 = [{
        "iter": i["iter"],
        "knob": i["proposal"]["knob"],
        "new_value": i["proposal"]["new_value"],
        "val_bpb": i.get("val_bpb"),
        "improvement_pct": round(i["improvement_frac"] * 100, 3),
        "decision": i["decision"],
        "reason": i["proposal"].get("reason", ""),
    } for i in by_improvement[:5]]

    # Worst regressions (negative improvement_frac)
    bottom3 = [{
        "iter": i["iter"],
        "knob": i["proposal"]["knob"],
        "new_value": i["proposal"]["new_value"],
        "val_bpb": i.get("val_bpb"),
        "improvement_pct": round(i["improvement_frac"] * 100, 3),
        "decision": i["decision"],
        "reason": i["proposal"].get("reason", ""),
    } for i in by_improvement[-3:]]

    # Per-iteration timing
    iter_walls = [i["iter_wall_s"] for i in iters if i.get("iter_wall_s")]
    nim_lats = [i["nim_latency_s"] for i in iters if i.get("nim_latency_s")]
    train_walls = [i["eval_metrics"]["train_wall_s"] for i in evaluated
                   if i.get("eval_metrics", {}).get("train_wall_s")]

    # Did the agent ever propose the same knob/value twice?
    seen_proposals = Counter()
    repeats = []
    for i in iters:
        if not i.get("proposal"):
            continue
        key = (i["proposal"]["knob"], json.dumps(i["proposal"]["new_value"]))
        seen_proposals[key] += 1
        if seen_proposals[key] >= 2:
            repeats.append({
                "iter": i["iter"], "knob": key[0], "new_value": json.loads(key[1]),
                "n_seen": seen_proposals[key],
            })

    s = {
        "trajectory_path": str(path),
        "iterations_total": n,
        "iterations_evaluated": len(evaluated),
        "iterations_blocked": len(blocks),
        "iterations_nim_error": len(nim_errors),
        "iterations_eval_failed": len(eval_fails),
        "decisions_keep": len(keeps),
        "decisions_revert": len(reverts),
        "block_by_rail": dict(block_by_rail),
        "knob_distribution": dict(knob_distribution),
        "knob_diversity_unique": len(knob_distribution),
        "knob_diversity_total_proposals": sum(knob_distribution.values()),
        "repeat_proposals": repeats,
        "top5_by_improvement": top5,
        "bottom3_by_improvement": bottom3,
        "timing": {
            "iter_wall_s_mean": round(mean(iter_walls), 1) if iter_walls else None,
            "iter_wall_s_median": round(median(iter_walls), 1) if iter_walls else None,
            "nim_latency_s_mean": round(mean(nim_lats), 2) if nim_lats else None,
            "train_wall_s_mean": round(mean(train_walls), 1) if train_walls else None,
        },
        "baseline_val_bpb": header.get("baseline_val_bpb"),
        "summary_record": summary,
    }
    return s


def print_report(s: dict) -> None:
    print(f"=== trajectory: {s['trajectory_path']} ===\n")
    print(f"iterations          {s['iterations_total']}")
    print(f"  evaluated         {s['iterations_evaluated']}")
    print(f"  blocked           {s['iterations_blocked']}")
    print(f"  nim_error         {s['iterations_nim_error']}")
    print(f"  eval_failed       {s['iterations_eval_failed']}")
    print(f"\ndecisions")
    print(f"  keep              {s['decisions_keep']}")
    print(f"  revert            {s['decisions_revert']}")

    if s["block_by_rail"]:
        print(f"\nblocks by rail:")
        for rail, c in sorted(s["block_by_rail"].items()):
            print(f"  {rail:14s} {c}")

    print(f"\nknob diversity      {s['knob_diversity_unique']} unique / "
          f"{s['knob_diversity_total_proposals']} proposals")
    if s["knob_distribution"]:
        print(f"knob distribution:")
        for k, c in sorted(s["knob_distribution"].items(), key=lambda x: -x[1]):
            print(f"  {k:14s} {c}")

    if s["repeat_proposals"]:
        print(f"\nrepeat proposals (agent re-tried the same knob+value):")
        for r in s["repeat_proposals"][:10]:
            print(f"  iter {r['iter']:>3d}  {r['knob']}={r['new_value']}  (seen {r['n_seen']}x)")

    print(f"\ntop 5 improvers:")
    for r in s["top5_by_improvement"]:
        print(f"  iter {r['iter']:>3d}  {r['knob']:14s} = {str(r['new_value']):<10s}  "
              f"val_bpb {r['val_bpb']}  Δ{r['improvement_pct']:+.2f}%  "
              f"{r['decision']:>6s}  — {r['reason'][:50]}")

    print(f"\nbottom 3 (worst regressions):")
    for r in s["bottom3_by_improvement"]:
        print(f"  iter {r['iter']:>3d}  {r['knob']:14s} = {str(r['new_value']):<10s}  "
              f"val_bpb {r['val_bpb']}  Δ{r['improvement_pct']:+.2f}%  "
              f"{r['decision']:>6s}  — {r['reason'][:50]}")

    if s["timing"]["iter_wall_s_mean"]:
        print(f"\ntiming")
        print(f"  iter wall  mean {s['timing']['iter_wall_s_mean']:.1f}s · "
              f"median {s['timing']['iter_wall_s_median']:.1f}s")
        print(f"  NIM call   mean {s['timing']['nim_latency_s_mean']:.2f}s")
        print(f"  train wall mean {s['timing']['train_wall_s_mean']:.1f}s")

    if s["summary_record"]:
        sr = s["summary_record"]
        print(f"\noverall best:  val_bpb {sr['best_val_bpb']:.4f}  "
              f"(baseline {sr['baseline_val_bpb']:.4f}, "
              f"improvement {sr['best_improvement_frac']*100:+.2f}%)")
        if sr.get("best_proposal"):
            bp = sr["best_proposal"]
            print(f"               {bp['knob']} = {bp['new_value']}  — {bp['reason'][:80]}")
        print(f"loop wall: {sr['loop_wall_min']:.1f} min")


def main() -> None:
    if len(sys.argv) < 2:
        # Default to trajectory.jsonl in the script dir
        path = Path(__file__).resolve().parent / "trajectory.jsonl"
    else:
        path = Path(sys.argv[1])
    if not path.exists():
        print(f"trajectory not found: {path}", file=sys.stderr)
        sys.exit(1)
    s = summarize(path)
    print_report(s)
    out = path.parent / (path.stem + "_summary.json")
    with open(out, "w") as f:
        json.dump(s, f, indent=2)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
