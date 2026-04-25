# Pause / resume — `agent_loop.py`

The agent loop preserves all completed iterations in `trajectory.jsonl`
(line-flushed after every iteration). Pausing **never loses prior work**;
the worst case is one iteration of in-progress training discarded.

## Three ways to pause

### 1. Pause flag (cleanest — zero work lost)

```bash
touch /home/nvidia/ai-field-notes/articles/autoresearch-agent-loop/evidence/pause.flag
```

The agent checks for this file at the **top of each iteration**, BEFORE
making any LLM call or starting a training run. When it sees the flag:
- writes a `{stage: "paused", completed_iters: N}` record to the trajectory
- exits with code 0
- the in-progress iteration was never started, so no work is lost

### 2. SIGTERM (one in-progress iter completes first)

```bash
docker stop agent-overnight       # sends SIGTERM, then SIGKILL after 10s
```

The agent traps SIGTERM and sets the same pause flag internally. The
**current iteration finishes** (so its result lands in the trajectory),
then at the next iteration's top-boundary check the agent writes a
`{stage: "paused", reason: "SIGTERM received"}` record and exits cleanly.

If the in-progress iteration takes longer than docker's stop timeout
(default 10 seconds), Docker will escalate to SIGKILL — in that case the
in-progress iteration's wall time is lost. Set a longer timeout to avoid:

```bash
docker stop --time=180 agent-overnight   # 3 min — long enough for one iter
```

### 3. SIGKILL (in-progress iter lost; older iters still safe)

```bash
docker kill agent-overnight       # SIGKILL — no clean handoff
```

The trajectory is line-flushed after each iteration, so all **completed**
iterations are preserved. The currently-running iteration is discarded.
On resume, the agent picks up at iter (last_completed + 1).

## Resume

```bash
docker run --rm --gpus all --ipc=host \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  --shm-size=2g --network host \
  -v "$PWD/articles/autoresearch-agent-loop/evidence:/work" \
  -v "$PWD/articles/guardrails-for-code-generation/evidence:/a5_evidence:ro" \
  -v "$PWD/articles/nemo-curator-training-data-prep/evidence:/a3_evidence:ro" \
  -w /work -e PYTHONUNBUFFERED=1 \
  -e NIM_BASE=http://localhost:8000 \
  -e A5_EVIDENCE=/a5_evidence \
  -e A3_PACKED=/a3_evidence/packed.int32.npy \
  nemo-curator-spark:1.1 \
  python3 agent_loop.py --resume --iters 50 --out trajectory.jsonl
```

`--resume` does the following:
- reads `baseline_eval.json` — baseline cfg + metrics, **no re-evaluation**
- walks `trajectory.jsonl` — rebuilds in-memory history, accept/revert/block counts, best_val_bpb
- determines `start_iter = last_iter + 1`
- if `--iters` is at or below the existing iter count, exits without doing anything
- clears the pause flag (if present) before starting
- continues exactly as if no pause had happened

Resume preserves the baseline_val_bpb that all decisions are compared
against — this is essential. The agent's keep/revert decisions only mean
something if every iteration is compared to the **same** baseline; resuming
with a fresh baseline_eval would corrupt the comparison.

## What the trajectory looks like after a pause+resume

```
{"_meta": "trajectory log; ...", "baseline_val_bpb": 10.9554, ...}
{"iter": 1, "stage": "evaluated", "decision": "revert", ...}
{"iter": 2, "stage": "evaluated", "decision": "revert", ...}
{"iter": 3, "stage": "evaluated", "decision": "revert", ...}
{"iter": 4, "stage": "evaluated", "decision": "keep",   "val_bpb": 10.8722, ...}
{"iter": 5, "stage": "evaluated", "decision": "revert", ...}
{"iter": 6, "stage": "paused",    "reason": "pause flag at .../pause.flag", ...}
{"iter": 6, "stage": "evaluated", ...}    ← --resume continues here
{"iter": 7, "stage": "evaluated", ...}
...
```

Note the duplicate iter=6 line: the first is the "paused" marker (no
work done), the second is the resumed iteration's actual record. The
summarizer skips paused records when computing accept/revert ratios.

## Edge cases

- **Pause flag persists across resumes if not deleted manually.**
  `--resume` clears the flag at startup, but if you `touch pause.flag`
  again before the first iter runs, you'll pause again immediately.
- **Resume with `--iters 50` after 50 iters already done is a no-op.**
  The agent prints "trajectory already has 50 iters" and exits.
- **Changing `--iters` upward extends the run.** Resume with `--iters 100`
  on a trajectory that has 50 completed iters runs iters 51-100.
- **Baseline cfg cannot change between runs.** The baseline_eval.json
  is read as-is; if you want a new baseline, delete both files and
  start over (without `--resume`).
