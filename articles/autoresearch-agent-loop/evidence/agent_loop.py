"""
The Autoresearch agent loop. For N iterations:

  1. Ask NIM 8B for one structured perturbation proposal
     (proposer.py builds the prompt + calls /v1/chat/completions)
  2. Run it through A5's gate(): R1 schema → R2 menu → R3 range
     → R4 cross → R5 diff_lint
  3. If blocked: log {iter, rail, reason}; do not touch cfg
  4. If passed: apply (mutate cfg in-memory), evaluate (cfg.steps of
     training + val pass on held-out wikitext slice), compute val_bpb
  5. Decision: keep if val_bpb improved by >= ACCEPT_DELTA, else revert
  6. Append iteration record to trajectory.jsonl

The trajectory log is the article's primary artifact — every
iteration's proposal, verdict, evaluation result, and decision land
there as one JSON line.

CLI:
    python3 agent_loop.py --iters 30 --out trajectory.jsonl
    python3 agent_loop.py --iters 3 --out smoke.jsonl    # smoke test
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

# SIGTERM-triggered pause: if docker stop / kill -TERM arrives, set a
# flag and let the next iter-boundary check act on it. We never abort
# mid-iter — that would lose the in-progress training run's wall time
# without a record. The next iter sees the flag, writes a 'paused'
# record, and exits cleanly. The same trajectory.jsonl is then
# resumable via --resume without re-running the baseline.
_TERM_RECEIVED = False


def _on_sigterm(signum, frame):  # noqa: ARG001
    global _TERM_RECEIVED
    _TERM_RECEIVED = True
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] SIGTERM received — will pause "
          f"after the current iteration finishes. (To force-stop now: send SIGKILL.)",
          flush=True)


signal.signal(signal.SIGTERM, _on_sigterm)
signal.signal(signal.SIGINT, _on_sigterm)

EVIDENCE = Path(__file__).resolve().parent
# A5 + A3 paths can be overridden by env (useful when running in containers
# that mount the sibling article evidence dirs at non-canonical paths).
A5_EVIDENCE = Path(os.environ.get(
    "A5_EVIDENCE",
    str(EVIDENCE.parent.parent / "guardrails-for-code-generation" / "evidence"),
))
sys.path.insert(0, str(EVIDENCE))
sys.path.insert(0, str(A5_EVIDENCE))

from cfg import BASELINE, Cfg  # noqa: E402
from rails import gate           # noqa: E402  (A5)
from proposer import propose     # noqa: E402
from evaluator import evaluate   # noqa: E402

# Acceptance threshold: keep proposal if val_bpb improves by >= 0.5%.
ACCEPT_DELTA_FRAC = 0.005


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _restore_state(out_path: Path, baseline_eval_path: Path) -> tuple:
    """Resume mode: read trajectory + baseline_eval, rebuild history,
    return (baseline_cfg_dict, baseline_metrics, history, last_iter,
    accept_count, revert_count, block_count, eval_fail_count,
    best_val_bpb, best_proposal)."""
    if not out_path.exists() or not baseline_eval_path.exists():
        raise FileNotFoundError(
            f"--resume needs both {out_path.name} and {baseline_eval_path.name} on disk")
    with open(baseline_eval_path) as f:
        baseline = json.load(f)
    baseline_cfg_dict = baseline["baseline_cfg"]
    baseline_metrics = baseline["baseline_metrics"]
    history: list[dict] = []
    last_iter = 0
    accept_count = revert_count = block_count = eval_fail_count = 0
    best_val_bpb = baseline_metrics["val_bpb"]
    best_proposal = None
    with open(out_path) as f:
        for ln_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                # Defensive: a SIGKILL between write() and the OS flushing
                # the page cache could leave the last line truncated. Skip
                # malformed tails rather than refusing to resume.
                print(f"[{_now()}] resume: skipping malformed line {ln_no} in {out_path.name}")
                continue
            if "iter" not in r:
                continue
            history.append(r)
            last_iter = max(last_iter, r["iter"])
            stage = r.get("stage")
            if stage == "blocked":
                block_count += 1
            elif stage == "evaluated":
                if r.get("decision") == "keep":
                    accept_count += 1
                else:
                    revert_count += 1
                vb = r.get("val_bpb")
                if vb is not None and vb < best_val_bpb:
                    best_val_bpb = vb
                    best_proposal = r["proposal"]
            elif stage == "eval_failed":
                eval_fail_count += 1
            elif stage == "paused":
                pass  # informational
    return (baseline_cfg_dict, baseline_metrics, history, last_iter,
            accept_count, revert_count, block_count, eval_fail_count,
            best_val_bpb, best_proposal)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=30)
    ap.add_argument("--out", type=str, default="trajectory.jsonl")
    ap.add_argument("--baseline-out", type=str, default="baseline_eval.json")
    ap.add_argument("--accept-delta", type=float, default=ACCEPT_DELTA_FRAC,
                    help="Keep a proposal if val_bpb improves by this fraction "
                         "(0.005 = 0.5%%)")
    ap.add_argument("--resume", action="store_true",
                    help="Continue an existing trajectory.jsonl + baseline_eval.json. "
                         "Skips baseline re-evaluation; picks up at the next iter "
                         "after the last record.")
    ap.add_argument("--pause-flag", type=str, default="pause.flag",
                    help="If a file with this name appears in EVIDENCE/, the loop "
                         "will write a 'paused' record and exit cleanly at the next "
                         "iteration boundary. Resume with --resume.")
    args = ap.parse_args()

    out_path = EVIDENCE / args.out
    baseline_eval_path = EVIDENCE / args.baseline_out
    pause_flag_path = EVIDENCE / args.pause_flag

    if args.resume:
        (baseline_cfg_dict, baseline_metrics, history, last_iter,
         accept_count, revert_count, block_count, eval_fail_count,
         best_val_bpb, best_proposal) = _restore_state(out_path, baseline_eval_path)
        baseline_cfg = Cfg(**{k: v for k, v in baseline_cfg_dict.items()
                              if k in {f.name for f in Cfg.__dataclass_fields__.values()}})
        start_iter = last_iter + 1
        if start_iter > args.iters:
            print(f"[{_now()}] resume: trajectory already has {last_iter} iters, "
                  f"args.iters={args.iters} — nothing to do")
            return
        print(f"[{_now()}] === RESUME from iter {start_iter}/{args.iters} ===")
        print(f"[{_now()}] reloaded {len(history)} prior records  "
              f"(accept={accept_count}, revert={revert_count}, "
              f"blocked={block_count}, eval_failed={eval_fail_count}, "
              f"best_val_bpb={best_val_bpb:.4f})")
        if pause_flag_path.exists():
            pause_flag_path.unlink()
            print(f"[{_now()}] cleared stale pause flag at {pause_flag_path}")
        # Append, don't truncate
        fout = open(out_path, "a")
    else:
        # Step 0: evaluate the baseline once. All subsequent decisions
        # compare to THIS baseline, not the last accepted state.
        print(f"[{_now()}] iter   0  evaluating baseline cfg ...")
        baseline_cfg = deepcopy(BASELINE)
        baseline_metrics = evaluate(baseline_cfg)
        if not baseline_metrics.get("ok"):
            print(f"[{_now()}] baseline FAILED: {baseline_metrics}")
            sys.exit(1)
        print(f"[{_now()}] baseline val_bpb = {baseline_metrics['val_bpb']:.4f}  "
              f"params = {baseline_metrics['params_m']}M  "
              f"step = {baseline_metrics['mean_step_ms']:.1f}ms  "
              f"peak = {baseline_metrics['peak_gpu_mem_gib']:.2f}GiB  "
              f"({baseline_metrics['train_wall_s']:.1f}s train + "
              f"{baseline_metrics['val_wall_s']:.1f}s val)")

        with open(baseline_eval_path, "w") as f:
            json.dump({"baseline_cfg": baseline_cfg.to_dict(),
                       "baseline_metrics": baseline_metrics}, f, indent=2)

        history = []
        accept_count = block_count = eval_fail_count = revert_count = 0
        best_val_bpb = baseline_metrics["val_bpb"]
        best_proposal = None
        start_iter = 1

        fout = open(out_path, "w")
        fout.write(json.dumps({"_meta": "trajectory log; first record is baseline; "
                                        "subsequent records are agent iterations",
                                "baseline_val_bpb": baseline_metrics["val_bpb"],
                                "baseline_cfg": baseline_cfg.to_dict(),
                                "accept_delta_frac": args.accept_delta}) + "\n")
        fout.flush()

    t_loop0 = time.perf_counter()
    for i in range(start_iter, args.iters + 1):
        # Pause-flag check at the top of each iter — clean stop point
        # before any LLM call or training run.
        pause_reason = None
        if pause_flag_path.exists():
            pause_reason = f"pause flag at {pause_flag_path}"
        elif _TERM_RECEIVED:
            pause_reason = "SIGTERM received"
        if pause_reason:
            pause_rec = {
                "iter": i, "ts": _now(), "stage": "paused",
                "reason": (f"{pause_reason}; completed through iter {i-1}; "
                           f"resume with --resume"),
                "completed_iters": i - 1, "requested_iters": args.iters,
            }
            fout.write(json.dumps(pause_rec) + "\n"); fout.flush()
            fout.close()
            print(f"\n[{_now()}] === PAUSED at iter {i}/{args.iters} ===")
            print(f"[{_now()}] cause: {pause_reason}")
            print(f"[{_now()}] resume with: python3 agent_loop.py --resume "
                  f"--iters {args.iters} --out {args.out}")
            if pause_flag_path.exists():
                print(f"[{_now()}] (the pause flag will be cleared automatically by "
                      f"--resume; delete by hand if needed)")
            return

        t_iter0 = time.perf_counter()
        print(f"\n[{_now()}] === iter {i:>3d}/{args.iters} ===")

        # Step 1: ask NIM 8B for a proposal.
        nim_resp = propose(history, baseline_cfg.to_dict())
        if not nim_resp["ok"]:
            print(f"[{_now()}]   NIM call failed: {nim_resp.get('error', '?')}")
            rec = {"iter": i, "ts": _now(), "stage": "nim_error",
                   "nim_error": nim_resp.get("error"),
                   "iter_wall_s": round(time.perf_counter() - t_iter0, 1)}
            fout.write(json.dumps(rec) + "\n"); fout.flush()
            continue
        raw = nim_resp["text"].strip()
        print(f"[{_now()}]   NIM responded ({nim_resp['latency_s']:.1f}s):  "
              f"{raw[:120]}{'…' if len(raw) > 120 else ''}")

        # Step 2: run through A5's rails.
        verdict = gate(raw, baseline_cfg.to_dict())
        if not verdict.ok:
            block_count += 1
            print(f"[{_now()}]   BLOCKED at {verdict.rail}: {verdict.reason}")
            rec = {
                "iter": i, "ts": _now(), "stage": "blocked",
                "verdict_ok": False, "rail": verdict.rail, "reason": verdict.reason,
                "proposal": verdict.proposal,
                "raw": raw[:300],
                "nim_latency_s": nim_resp["latency_s"],
                "iter_wall_s": round(time.perf_counter() - t_iter0, 1),
            }
            history.append(rec)
            fout.write(json.dumps(rec) + "\n"); fout.flush()
            continue

        proposal = verdict.proposal
        print(f"[{_now()}]   PASSED rails. proposal = {proposal['knob']}={proposal['new_value']}")

        # Step 4: apply (in-memory) + evaluate.
        candidate_cfg = baseline_cfg.with_(proposal["knob"], proposal["new_value"])
        metrics = evaluate(candidate_cfg)
        if not metrics.get("ok"):
            eval_fail_count += 1
            print(f"[{_now()}]   EVAL FAILED ({'OOM' if metrics.get('oom') else 'ERR'}): "
                  f"{metrics.get('error', '?')[:100]}")
            rec = {
                "iter": i, "ts": _now(), "stage": "eval_failed",
                "verdict_ok": True,
                "proposal": proposal, "diff": verdict.diff,
                "candidate_cfg": candidate_cfg.to_dict(),
                "eval_metrics": metrics,
                "decision": "revert (eval crash)",
                "baseline_val_bpb": baseline_metrics["val_bpb"],
                "nim_latency_s": nim_resp["latency_s"],
                "iter_wall_s": round(time.perf_counter() - t_iter0, 1),
            }
            history.append(rec)
            fout.write(json.dumps(rec) + "\n"); fout.flush()
            continue

        val_bpb = metrics["val_bpb"]
        improvement_frac = (baseline_metrics["val_bpb"] - val_bpb) / baseline_metrics["val_bpb"]
        keep = improvement_frac >= args.accept_delta
        decision = "keep" if keep else "revert"
        if keep:
            accept_count += 1
        else:
            revert_count += 1
        if val_bpb < best_val_bpb:
            best_val_bpb = val_bpb
            best_proposal = proposal

        print(f"[{_now()}]   evaluated: val_bpb={val_bpb:.4f}  "
              f"baseline={baseline_metrics['val_bpb']:.4f}  "
              f"Δ={improvement_frac*100:+.2f}%  "
              f"step={metrics['mean_step_ms']:.0f}ms  "
              f"peak={metrics['peak_gpu_mem_gib']:.2f}GiB  "
              f"({metrics['train_wall_s']:.0f}s train, {metrics['val_wall_s']:.1f}s val)  "
              f"→ {decision.upper()}")

        rec = {
            "iter": i, "ts": _now(), "stage": "evaluated",
            "verdict_ok": True,
            "proposal": proposal, "diff": verdict.diff,
            "candidate_cfg": candidate_cfg.to_dict(),
            "eval_metrics": metrics,
            "val_bpb": val_bpb,
            "baseline_val_bpb": baseline_metrics["val_bpb"],
            "improvement_frac": round(improvement_frac, 4),
            "decision": decision,
            "is_new_best": (val_bpb == best_val_bpb),
            "nim_latency_s": nim_resp["latency_s"],
            "iter_wall_s": round(time.perf_counter() - t_iter0, 1),
        }
        history.append(rec)
        fout.write(json.dumps(rec) + "\n"); fout.flush()

    loop_wall = time.perf_counter() - t_loop0
    summary = {
        "stage": "loop_complete",
        "iters_requested": args.iters,
        "accept_count": accept_count,
        "revert_count": revert_count,
        "block_count": block_count,
        "eval_fail_count": eval_fail_count,
        "loop_wall_s": round(loop_wall, 1),
        "loop_wall_min": round(loop_wall / 60, 1),
        "baseline_val_bpb": baseline_metrics["val_bpb"],
        "best_val_bpb": best_val_bpb,
        "best_proposal": best_proposal,
        "best_improvement_frac": round(
            (baseline_metrics["val_bpb"] - best_val_bpb) / baseline_metrics["val_bpb"], 4
        ) if best_proposal else 0.0,
    }
    fout.write(json.dumps(summary) + "\n")
    fout.close()

    print(f"\n[{_now()}] === LOOP COMPLETE ===")
    print(f"  iters         {args.iters}")
    print(f"  accepted      {accept_count}")
    print(f"  reverted      {revert_count}")
    print(f"  blocked       {block_count}")
    print(f"  eval failed   {eval_fail_count}")
    print(f"  total wall    {loop_wall/60:.1f} min")
    print(f"  baseline      val_bpb = {baseline_metrics['val_bpb']:.4f}")
    print(f"  best          val_bpb = {best_val_bpb:.4f}  "
          f"(improvement {(baseline_metrics['val_bpb'] - best_val_bpb)/baseline_metrics['val_bpb']*100:+.2f}%)")
    if best_proposal:
        print(f"  best proposal {best_proposal['knob']} = {best_proposal['new_value']}")
        print(f"                reason: {best_proposal['reason']}")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
