# Session transcript — pass-at-k-after-the-seventh-patch

Captured 2026-05-03. Third article in the test-time-distilling triplet.

## Provenance

- Container: `tllm-build` (PyTorch 25.11 + vLLM 0.20.0 + tLLM working tree at `/work/tllm-rw/`).
- Patch arc context: see [runtime-frontier-six-patches-on-spark](../runtime-frontier-six-patches-on-spark/article.md). The seventh drift fixed in this session lives in the same `tllm/runtime/ports/residual_capture_hooks.py` as drift six.
- Harness: `articles/runtime-frontier-six-patches-on-spark/scripts/passatk_a2.py` (extended this session with `--task aime` mode, AIME prompt builder + integer-answer grader on top of the original HumanEval mode).
- Evidence runs (gitignored): `articles/runtime-frontier-six-patches-on-spark/evidence/runs/2026-05-03-A2-passatk/` — six JSON results across all four cells, the runner log, and a NOTES.md preserving session-time observations.
- The seventh-patch diff: `articles/runtime-frontier-six-patches-on-spark/evidence/runs/2026-05-03-A2-patches/seventh-patch.diff` (gitignored).

## Sequence

1. Reproduced the diverse-prompt crash with `CUDA_LAUNCH_BLOCKING=1` on a 10×n=8 ESamp run on Qwen 0.5B. Localized to `residual_capture_hooks.py:67` (`torch.index_select` against full-capacity `decode_row_idx`).
2. Audited `decode_row_idx` lifecycle in `port_runtime_hooks.prepare_decode_localization` and `producer/decode.compute_decode_localization`. Found that the buffer is sized to `graph_scratch_rows` and only the first `decode_count` slots are refreshed each step — slots beyond contain stale indices from prior steps. The compact-tap path two blocks below already sliced to the active count; the full-tap path did not.
3. Applied the one-line fix: slice `decode_row_idx[:decode_count_runtime]` and `decode_buf[:decode_count_runtime]`. Synced from `/tmp/tllm-rw` (tmpfs) to `/work/tllm-rw` (host bind) so the fix survives container restart.
4. Verified post-patch: 10×n=8 on Qwen 0.5B → pass@1=0.1375, pass@8=0.40, no crash. 164×n=8 on Qwen 7B Instruct also clean.
5. Ran full HumanEval × Qwen 2.5 7B Instruct matrix (164 problems × n=8, baseline + esamp). Result: deltas in noise (saturation finding).
6. Pulled DeepSeek-R1-Distill-Qwen-7B (15 GB, ~18 min on flapping Wi-Fi) and the AIME 2024 problem set (Maxwell-Jia/AIME_2024 on HF, 30 problems, integer answers).
7. Extended the harness with `--task` flag, AIME prompt builder, and integer-answer grader (last `\boxed{N}` or last standalone integer in [0, 999], compared against gold). Smoke-tested on 5 problems × n=2 with Qwen 7B.
8. Container lost CUDA mid-session (NVML init failure post engine-dead crash). Restarted via `docker restart tllm-build`. Patches and harness survived because they live in the host-bound `/work/tllm-rw`. After restart, working tree resumed clean.
9. Ran the four matrix cells sequentially via `/work/passatk-runner.sh`:
   - Qwen 7B × AIME × baseline (13 min, 30 problems × n=8)
   - Qwen 7B × AIME × esamp (12 min)
   - DS-R1-Distill 7B × AIME × baseline (75 min — R1-Distill reasoning chains average ~7K tokens per attempt)
   - DS-R1-Distill 7B × AIME × esamp (77 min)
10. Skipped DeepSeek × HumanEval entirely — R1-Distill is a math reasoner; HumanEval (code) is off-thesis and would have added ~40 minutes for a noisy result. The matrix scope is intentionally Qwen-as-instruct-reference + DS-as-reasoning-reference, both on the unsaturated task (AIME) plus Qwen on the saturated task (HumanEval) for the saturation comparison.

## Numbers (load-bearing)

- Seventh-patch fix: 1 line, anchored on `decode_row_idx[:decode_count_runtime]` slicing in `_forward_with_tap`.
- Matrix headlines: pass@8 deltas 0.0pp (saturated), +3.33pp (instruct unsaturated), +6.67pp (reasoning unsaturated). Tok/s ratios 1.018×, 1.124×, 0.971× respectively.
- DS × AIME esamp ran at 0.971× tok/s — within 0.3pp of the patches-article 0.974× number on a same-prompt bench workload. The "single-digit-percent throughput cost" claim from the ESamp paper holds across both workloads.
- Per-problem detail (DS × AIME esamp vs baseline): 3 problems flipped 0/8 → ≥1/8 (semantic recovery), 1 flipped 4/8 → 0/8 (intervention pushed all attempts down a bad path), 11 problems shifted by smaller amounts in both directions. Pass@8 delta = +3 -1 = +2 problems = +6.67pp.

## Settings

- `temperature=0.8`, `top_p=0.95`, `min_p=0.1`, `top_k=-1`, `seed=2026` (vLLM seed; per-sample seed=None for stochastic n>1).
- `enforce_eager=True`, `dtype=bfloat16`, `enable_prefix_caching=False`.
- `gpu_memory_utilization=0.55`.
- HumanEval: `max_new_tokens=300`, `max_model_len=1536`.
- Qwen × AIME: `max_new_tokens=4096`, `max_model_len=6144`.
- DS × AIME: `max_new_tokens=8192`, `max_model_len=10240`.
- ESamp: `model_bank_slots=num_problems × n`, `model_bank_rank=64`, `model_bank_flush_interval=1`, `model_bank_train_cudagraph=True`, `model_bank_forward_backend=torch`, `enable_distiller_intervention=True`, `distiller_beta=0.8`, `distiller_sampler_backend=post_filter_exact`, `distiller_hidden_dim=128`, `distiller_lr=1e-3`.
- Tap layers: `model.model.layers[0].input_layernorm` (source) and `model.model.layers[-1].input_layernorm` (target).

## Artifacts to keep out of repo

- `articles/runtime-frontier-six-patches-on-spark/evidence/runs/2026-05-03-A2-passatk/` — six JSON files, one runner log, one NOTES.md.
- `articles/runtime-frontier-six-patches-on-spark/evidence/runs/2026-05-03-A2-patches/seventh-patch.diff` and `residual_capture_hooks.py.patched`.
- In-container working tree at `/work/tllm-rw/` (host bind via `/tmp/tllm-spark`).
