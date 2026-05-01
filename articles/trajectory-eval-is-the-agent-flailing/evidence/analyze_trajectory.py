"""
Trajectory observability for the A4 agent loop.

Reads the 50-iter trajectory + the 13-knob perturbation menu and
computes the metrics that A8 needed before it shipped:

  - knob coverage  (touched / total)
  - (knob, value) repeat rate, total + by 10-iter window
  - mode dominance (most-proposed pair, top-N pairs)
  - cumulative-best curve + per-iter scatter
  - keep counts, time-to-first-keep, time-to-best
  - keep-side mode dominance (5 of 8 keeps were the same pair)
  - train/test keep split for the A8 LoRA corpus

Outputs analysis.json plus three matplotlib figures rendered against
the site's dark editorial palette.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/home/nvidia/ai-field-notes")
TRAJ = ROOT / "articles/autoresearch-agent-loop/evidence/trajectory.jsonl"
MENU = ROOT / "articles/guardrails-for-code-generation/evidence/perturbation_menu.json"
OUT = Path(__file__).resolve().parent

# A4's proposer.py builds the prompt with `_history_lines(history, k=5)`.
# That number is the central finding of this analysis — pinned here so the
# article stays in sync with the script.
HISTORY_WINDOW_K = 5


def main() -> None:
    with open(TRAJ) as f:
        rows = [json.loads(line) for line in f]
    header = rows[0]
    iters = [r for r in rows if r.get("stage") == "evaluated"]

    with open(MENU) as f:
        menu = json.load(f)
    all_knobs = list(menu["knobs"].keys())

    # 1) knob coverage
    knob_count = Counter(r["proposal"]["knob"] for r in iters)
    touched = set(knob_count.keys())
    untouched = [k for k in all_knobs if k not in touched]

    # 2) (knob, value) repeat rate
    seen: set[tuple[str, object]] = set()
    repeats: list[bool] = []
    for r in iters:
        pair = (r["proposal"]["knob"], r["proposal"]["new_value"])
        repeats.append(pair in seen)
        seen.add(pair)

    # 3) per-pair counts
    pair_counts = Counter(
        (r["proposal"]["knob"], r["proposal"]["new_value"]) for r in iters
    )

    # 4) keeps
    keep_rows = [r for r in iters if r.get("decision") == "keep"]
    keep_iters = [r["iter"] for r in keep_rows]
    first_keep = min(keep_iters) if keep_iters else None
    best_row = min(iters, key=lambda r: r.get("val_bpb", float("inf")))
    keep_pair_counts = Counter(
        (r["proposal"]["knob"], r["proposal"]["new_value"]) for r in keep_rows
    )

    # 5) cumulative best
    cum_best: list[float] = []
    cur = header["baseline_val_bpb"]
    for r in iters:
        v = r.get("val_bpb", float("inf"))
        if v < cur:
            cur = v
        cum_best.append(cur)

    # 6) repeat-rate by 10-iter window
    W = 10
    windows = []
    for ws in range(0, len(iters), W):
        chunk = repeats[ws : ws + W]
        if chunk:
            windows.append(
                {
                    "first": ws + 1,
                    "last": ws + len(chunk),
                    "rate": round(sum(chunk) / len(chunk), 3),
                }
            )

    # 7) train/test keep split for the A8 LoRA corpus
    # A8's prepare_corpus.py used a time-tail split: iters 1-42 train, 43-50 test.
    train_keeps = [r for r in keep_rows if r["iter"] <= 42]
    test_keeps = [r for r in keep_rows if r["iter"] > 42]
    train_keep_modes = Counter(
        (r["proposal"]["knob"], r["proposal"]["new_value"]) for r in train_keeps
    )

    analysis = {
        "trajectory_iters": len(iters),
        "knobs_total": len(all_knobs),
        "knobs_touched": len(touched),
        "knobs_touched_pct": round(100 * len(touched) / len(all_knobs), 1),
        "knobs_untouched": untouched,
        "knob_count": dict(knob_count.most_common()),
        "repeat_count": sum(repeats),
        "repeat_rate": round(sum(repeats) / len(repeats), 3),
        "unique_pairs": len(seen),
        "top_pairs": [
            {"knob": k, "value": v, "n": n}
            for (k, v), n in pair_counts.most_common(8)
        ],
        "keep_count": len(keep_rows),
        "keep_iters": keep_iters,
        "keep_pair_counts": [
            {"knob": k, "value": v, "n": n}
            for (k, v), n in keep_pair_counts.most_common()
        ],
        "first_keep_iter": first_keep,
        "best_iter": best_row["iter"],
        "best_val_bpb": best_row["val_bpb"],
        "best_pair": {
            "knob": best_row["proposal"]["knob"],
            "value": best_row["proposal"]["new_value"],
        },
        "baseline_val_bpb": header["baseline_val_bpb"],
        "improvement_pct": round(
            100 * (header["baseline_val_bpb"] - best_row["val_bpb"]) / header["baseline_val_bpb"],
            2,
        ),
        "windows_repeat_rate": windows,
        "train_keep_count": len(train_keeps),
        "test_keep_count": len(test_keeps),
        "train_keep_modes": [
            {"knob": k, "value": v, "n": n}
            for (k, v), n in train_keep_modes.most_common()
        ],
        "history_window_k": HISTORY_WINDOW_K,
    }

    out_json = OUT / "analysis.json"
    with open(out_json, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"wrote {out_json}")
    print(json.dumps(analysis, indent=2))

    # ----- figures -----
    plt.style.use("dark_background")
    BG = "#0f1115"
    FG = "#e6e6e6"
    BLUE = "#7aa2f7"
    PINK = "#f7768e"
    GREEN = "#9ece6a"

    # Figure 1 — cumulative best + per-iter
    fig, ax = plt.subplots(figsize=(10, 5))
    xs = [r["iter"] for r in iters]
    ys = [r.get("val_bpb", None) for r in iters]
    keeps_x = [r["iter"] for r in keep_rows]
    keeps_y = [r["val_bpb"] for r in keep_rows]
    ax.scatter(xs, ys, color=BLUE, s=18, alpha=0.55, label="proposal val_bpb")
    ax.plot(xs, cum_best, color=GREEN, lw=2.2, label="cumulative best")
    ax.scatter(
        keeps_x,
        keeps_y,
        color=PINK,
        s=90,
        marker="*",
        zorder=5,
        label=f"keep ({len(keep_rows)})",
    )
    ax.axhline(
        header["baseline_val_bpb"],
        color=FG,
        ls="--",
        alpha=0.4,
        label=f"baseline {header['baseline_val_bpb']:.4f}",
    )
    ax.set_xlabel("iteration")
    ax.set_ylabel("val_bpb (lower is better)")
    ax.set_title("A4 trajectory — per-iter val_bpb + cumulative best")
    ax.set_ylim(10.78, 11.20)  # clip the iter-38 d_model=256 outlier so structure shows
    ax.legend(loc="upper right", fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT / "cumulative_best.png", dpi=120, facecolor=BG)
    plt.close()

    # Figure 2 — knob coverage
    fig, ax = plt.subplots(figsize=(10, 5.5))
    counts = [knob_count.get(k, 0) for k in all_knobs]
    colors = [PINK if c == 0 else BLUE for c in counts]
    ax.barh(all_knobs, counts, color=colors)
    for i, c in enumerate(counts):
        if c > 0:
            ax.text(c + 0.3, i, str(c), va="center", color=FG, fontsize=10)
        else:
            ax.text(0.3, i, "0  (never proposed)", va="center", color=PINK, fontsize=10)
    ax.set_xlabel("# proposals over 50 iters")
    ax.set_title(
        f"Knob coverage — {len(touched)} of {len(all_knobs)} knobs ever touched "
        f"({analysis['knobs_touched_pct']}%)"
    )
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(OUT / "knob_coverage.png", dpi=120, facecolor=BG)
    plt.close()

    # Figure 3 — repeat-rate per 10-iter window
    fig, ax = plt.subplots(figsize=(10, 4.6))
    labels = [f"{w['first']}-{w['last']}" for w in windows]
    rates = [100 * w["rate"] for w in windows]
    bars = ax.bar(labels, rates, color=BLUE)
    for bar, rate in zip(bars, rates):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.5,
            f"{rate:.0f}%",
            ha="center",
            color=FG,
            fontsize=10,
        )
    ax.set_xlabel("iteration window")
    ax.set_ylabel("% of proposals that repeat a prior (knob, value)")
    ax.set_title(
        f"Repeat-proposal rate climbs as the proposer's k={HISTORY_WINDOW_K} history window forgets"
    )
    ax.set_ylim(0, 100)
    plt.tight_layout()
    plt.savefig(OUT / "repeat_rate_over_time.png", dpi=120, facecolor=BG)
    plt.close()

    print(f"\nfigures written to {OUT}")


if __name__ == "__main__":
    main()
