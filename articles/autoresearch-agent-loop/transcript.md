# Transcript — A4: autoresearch-agent-loop

Provenance for the agent-loop article. 2026-04-25 afternoon session.

## Components built

- `cfg.py` — Cfg dataclass with all 13 knobs that match A5's `perturbation_menu.json`. `with_(knob, val)` returns a new Cfg with one field changed.
- `evaluator.py` — A2's training harness wrapped as `evaluate(cfg) → metrics dict`. Same Megatron-Core scaffolding; reads from A3's `packed.int32.npy` (95% train / 5% val split). Returns `val_bpb = mean(cross_entropy) / log(2)`.
- `proposer.py` — builds a system + user prompt, calls NIM Llama 3.1 8B at `localhost:8000/v1/chat/completions`. Returns the raw text. Schema validation deferred to A5's `gate()`.
- `agent_loop.py` — the main loop. Step 0: evaluate baseline. Per iter: pause-flag check → propose → gate → apply → evaluate → decide → log. Trajectory line-flushed after every iter so pause is safe.
- `summarize_trajectory.py` — read trajectory.jsonl → print accept/revert/block tallies, knob distribution, top/bottom 5 by improvement, timing histograms. Writes `trajectory_summary.json`.
- `PAUSE_RESUME.md` — documents three pause paths (flag file, SIGTERM, SIGKILL) and the `--resume` flow.

## Pause/resume design

Three pause paths, all preserving prior work:

1. `touch evidence/pause.flag` — agent checks at top of each iter, writes paused record, exits cleanly. Zero work lost.
2. `docker stop --time=180 agent-overnight` — SIGTERM trapped, current iter completes, then paused-marker. Zero work lost.
3. `docker kill agent-overnight` — SIGKILL, in-progress iter discarded, prior iters in trajectory.jsonl preserved (line-flushed).

Resume reads `baseline_eval.json` (no re-evaluation — same baseline, comparisons stay consistent) and `trajectory.jsonl` (rebuilds in-memory history from existing records), continues at `last_iter + 1`.

Defensive against truncated lines from SIGKILL mid-write.

## Smoke test (3 iterations)

```
[2026-04-25 17:58:15] iter   0  evaluating baseline cfg ...
[2026-04-25 17:59:33] baseline val_bpb = 10.9558  params = 354.6M  step = 1287.8ms  peak = 24.32GiB
[2026-04-25 17:59:35]   PASSED rails. proposal = n_head=8
[2026-04-25 18:00:48]   evaluated: val_bpb=10.9527  Δ=+0.03%  → REVERT
[2026-04-25 18:00:49]   PASSED rails. proposal = d_model=1536
[2026-04-25 18:02:32]   evaluated: val_bpb=10.9188  Δ=+0.34%  → REVERT
[2026-04-25 18:02:33]   PASSED rails. proposal = d_model=768
[2026-04-25 18:03:35]   evaluated: val_bpb=10.8870  Δ=+0.63%  → KEEP
3 iters · 1 keep · 4 min wall.
```

Baseline reproducibility: smoke = 10.9558, prod run = 10.9554. Drift 0.04%.

## Production run (50 iterations)

```
[2026-04-25 18:04:53] iter   0  evaluating baseline cfg ...
[2026-04-25 18:06:08] baseline val_bpb = 10.9554  params = 354.6M  step = 1213.5ms  peak = 24.32GiB
... 50 iters ...
[2026-04-25 19:19:34] === LOOP COMPLETE ===
  iters         50
  accepted      8
  reverted      42
  blocked       0
  eval failed   0
  total wall    73.4 min
  baseline      val_bpb = 10.9554
  best          val_bpb = 10.8534  (improvement +0.93%)
  best proposal d_model = 768
                reason: smaller hidden dimension may help
```

## Findings I'm carrying forward

1. **NIM 8B never produced malformed JSON in 50 iterations.** Block recall 1.0 in A5's bench is a cooperative-LLM result; a future article would adversarially prompt to actually exercise the rails.

2. **Agent's effective vocabulary was 6 of 13 knobs.** The seven untouched knobs (n_layer, lr_warmup, grad_clip, weight_decay, batch_size, seq_len, precision) never appeared. Strong NIM 8B prior on "model shape" knobs over "optimizer noise" knobs.

3. **Agent re-tried known failures.** d_model=1536 four times (all reverts), n_head=8 three times (all reverts), lr=0.0002 three times (all catastrophic). Recent-history window in the prompt was 5 iters; older failures scrolled out and got re-proposed.

4. **One winning recipe dominated.** d_model=768 was proposed 7 times, kept 5. Runaway A/B winner.

5. **Iter 38 disaster (d_model=256, val_bpb 13.7575, −25.6%).** Eval ran cleanly to completion. Crash prevention isn't the rails' job; bad training is a *training result*, not a safety violation. The next iter recovered.

6. **Power: 53.9 W mean / 62.1 W peak across 73.4 min.** Total electricity ≈ 0.07 kWh ≈ $0.02 at US residential rates.

7. **GPU memory headroom.** vLLM (NIM driver) held 59 GB constant; training process oscillated 22-39 GB depending on the cfg. Total never exceeded 102 / 128 GiB unified.

8. **Fixed baseline (not Markov drift) keeps the trajectory honest.** Every iteration's val_bpb is comparable to every other's because the comparison reference is constant. The cost: no compositional improvement (you can't stack iter 4's d_model=768 with iter 31's beta1 change in a single 50-iter run).

## What this unlocks for next articles

- **A6** (critic-nim-70b-on-spark): the trajectory.jsonl from this run is the input. The critic LLM evaluates each proposal *before* it goes to the trainer, predicting whether it'll improve val_bpb. Compare critic predictions to actual outcomes.
- **A8** (distill-architect-lora-from-trajectories): trajectory.jsonl is the training data. LoRA-tune a smaller proposer model on (cfg, val_bpb) → "is this knob+value a likely keeper?" The article would compare the LoRA'd 1B proposer to the unmodified NIM 8B baseline.
- **A9** (trajectory-eval-is-the-agent-flailing): metrics on the trajectory itself. Knob diversity, repeat-failure rate, accept rate, time-to-first-keep, improvement-per-watt-hour.
