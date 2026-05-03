# Source material: runtime-frontier-six-patches-on-spark

Cleaned session log and provenance for this article. Raw material that became evidence in `article.md` lives here. The full diffs, patched files, and bench JSONs live alongside the prior article's evidence at `articles/test-time-distilling-for-exploration/evidence/runs/2026-05-03-A2-patches/` (gitignored — local-only working tree).

_Populated on 2026-05-03._

## Session shape

Single-day session on 2026-05-03, picking up from the prior session's article #2 (`test-time-distilling-for-exploration`, commit `5f4f6e8`) which closed at "two upstream patches needed."

Context for the session: the harness lived in a Docker container `tllm-build` (PyTorch 25.11 base, vLLM 0.20.0, torch 2.11.0+cu130) with the tLLM source at `/tmp/tllm-rw/` (writable, container-local) and a read-only bind mount of the snapshot at `/tllm`. Models cached at `/root/.cache/huggingface/hub/`: Qwen/Qwen2.5-0.5B-Instruct (cached from prior session), Qwen/Qwen2.5-7B-Instruct (pulled this session, ~17 minutes for 14 files / ~15 GB).

## Drifts found, in the order the box exposed them

1. **`Sampler.apply_temperature`** gained `all_random` 3rd positional arg. Already known from article #2; the prior session's writable copy had it pre-applied.

2. **`GPUModelRunner._prepare_inputs`** gained `num_scheduled_tokens` 2nd positional arg. Three wrapper sites in tLLM:
   - `tllm/runtime/residual_runtime.py:_wrapped_prepare_inputs`
   - `tllm/runtime/vllm_patch/port_runtime_hooks.py:wrapped_prepare_inputs`
   - `tllm/workflows/repro/prefill_capture_support.py:_wrapped_prepare_inputs`

3. **`Sampler.sample` and `Sampler.topk_topp_sampler` return tuples**. Previously `Tensor`, now `tuple[Tensor, Tensor | None]`. Eight call sites across:
   - `tllm/runtime/vllm_patch/sampler_patch.py` (`_vanilla_sample`, `_maybe_sample_precomputed_dense_fast`, `wrapped_sampler_sample`, `_wrapped`)
   - `tllm/runtime/sampler_bridge/bridge.py` (`_sample_full_vanilla` and inline `topk_topp_sampler` call)

   The `_wrapped` shim also gained a `logprobs_mode_override` kwarg the new `Sampler.sample` accepts.

4. **`_prepare_inputs` return shape changed silently**. Old: `(attn_metadata, logits_indices, ...)`. New: `(logits_indices, spec_decode_metadata)`. Adapter in `tllm/runtime/vllm_patch/adapters/base.py` was reading `out[1]` as `logits_indices` and getting `None` or a `SpecDecodeMetadata` object. No exception — `view.logits_indices = None` short-circuited `prepare_decode_localization` silently. Diagnosed via three rounds of `print()`:
   - First instrumented `_forward_with_tap` in `residual_capture_hooks` — confirmed taps fire
   - Then instrumented `maybe_launch_post_logits_decode_work` — saw `decode_count=0` on every step
   - Then instrumented `prepare_decode_localization` itself — saw `view.logits_indices is None` on every call
   - Pulled the actual return signature from installed vLLM and the `(logits_indices, spec_decode_metadata)` shape was visible in `inspect.signature(GPUModelRunner._prepare_inputs)`
   - Fix: new branch in `unpack_prepare_inputs_output` that handles `len(out) == 2 and isinstance(out[0], Tensor)` by mapping `out[0] → logits_indices` and synthesizing a `_SyntheticCommonAttnMetadata` carrying `num_actual_tokens` from `scheduler_output`

5. **`LLMEngine.add_request` reassigns request_id internally**. vLLM 0.20.0 calls `input_processor.assign_request_id(request)` between accepting the input id and queuing — so the runtime sees `"0-a13b2024"` instead of `"0"`. tLLM's `capture_runner._wrapped_add_request` was registering `runtime.reqid_to_promptidx[request_id]` against the input id (`"0"`) but the runtime then queries against the assigned id. Fix: capture the *return value* of `orig_add_request` (which is the assigned id) and register against that.

6. **Pre-existing latent bug in `residual_capture_hooks._forward_with_tap`**. The tap calls `torch.index_select(tensor, 0, decode_row_idx, out=decode_buf)` if `decode_row_idx is not None`, but doesn't gate on `decode_count > 0`. Stale row indices from a previous decode batch's last step go out-of-bounds against a fresh prefill tensor → `device-side assert`. Single-`generate()` smoke tests never expose this. Fix: one-line `decode_count > 0` guard before the index_select.

## Smoke shape that confirmed each fix

After drift 6, smoke on Qwen 2.5 0.5B Instruct (4 prompts × 16 tokens, β=0.8, `enforce_eager=True`):

```text
ESamp stats: loss_avg=4.155429 loss_count=16 answers=4
distiller_enabled=True distiller_beta=0.8
distiller_port_hits=15 distiller_candidate_samples=15
distiller_candidate_tokens=226 distiller_candidate_max=23
```

Loss accumulating, port hits one-less-than-loss-count (post-logits is one step ahead of post-sample), candidate tokens > 0. Consumer is firing.

## Bench shape

Two scripts at `articles/test-time-distilling-for-exploration/evidence/runs/2026-05-03-A2-patches/patched-source/`:

- `bench_a2.py` — tok/s microbench. Two modes (`baseline`, `esamp`), each run as a separate process so the install_runner_patch state can't leak. Same prompts × n=16 × max_new_tokens=64. Reports `tok_per_s = decode_tokens / elapsed_s` after warmup.
- `passatk_a2.py` — HumanEval Pass@k. Reads `human_eval` problems, builds prompt-per-problem (×n), generates, extracts `def func(...):` body from fenced block, exec's against the reference test under a SIGALRM timeout. Reports unbiased Pass@k via the Codex paper estimator.

## Headline measurements

```
=== 7B baseline (3 trials) ===
  tok/s: 210.08, 210.36, 209.40 → mean 209.95, sd 0.50
=== 7B esamp (3 trials, β=0.8) ===
  tok/s: 206.48, 203.57, 203.59 → mean 204.55, sd 1.65
  loss_count=64, port_hits=63, candidate_tokens=1593 (per run)
  ratio: 0.974× of baseline (97.4%)

=== 0.5B baseline (3 trials) ===
  tok/s: 1166.65, 1166.95, 1169.41 → mean 1167.7, sd 1.5
=== 0.5B esamp (3 trials, β=0.8) ===
  tok/s: 959.90, 975.81, 953.27 → mean 963.0, sd 11.5
  loss_count=64, port_hits=63, candidate_tokens=2634 (per run)
  ratio: 0.825× of baseline (82.5%)
```

Reference paper number (from article #2's source): **0.9878×** on RTX 4090 + CUDA graphs at 7B.

## Pass@k pilot (baseline only — ESamp blocked)

Qwen 2.5 0.5B Instruct, 10 HumanEval problems, n=8 samples per problem, max_new_tokens=256:

- Single-batch (10×8=80 prompts in one `generate()`): pass@1 = 6.25%, pass@8 = 40%, tok/s = 457.7
- Per-problem-loop (10 sequential `generate()` calls of 8): pass@1 = 10%, pass@8 = 40%, tok/s = 93.7

ESamp mode of the same harness fails on the second problem with a `device-side assert` (followed by a cascade `CUBLAS_STATUS_INTERNAL_ERROR`). With `enable_distiller_intervention=False`, multi-`generate()` runs cleanly — so the issue is specifically in the intervention path's state-isolation across batches. Suspected cause: model-bank slot state carrying across diverse prompts. Not a 0.20.0 drift; queued as a follow-up engineering project.

## fieldkit candidates surfaced

Both proposed for `fieldkit v0.2`:

- **`fieldkit.inference.VLLMClient`** — mirror of `fieldkit.nim.NIMClient` for vLLM-side experiments. Wraps `make_llm` + `LLM` constructors, `SamplingParams` boilerplate, three-trial throughput measurement. Working sketch at `bench_a2.py`.
- **`fieldkit.eval.PassAtK`** — verifier-loop primitive with the unbiased estimator. Working sketch at `passatk_a2.py`. Pairs with `Bench` and the proposed `VLLMClient`.

## Working tree state at session end

- `tllm-build` container left running with all six patches in `/tmp/tllm-rw/`. Diffs and patched-source snapshots in `articles/test-time-distilling-for-exploration/evidence/runs/2026-05-03-A2-patches/` (gitignored).
- HANDOFF.md updated with the new state.
- 7B model cached for next session (15 GB).

## What was scrubbed from this transcript

- Raw shell command logs with absolute paths beyond what the prose calls out as relevant (kept function-of-the-output as prose; dropped verbatim shell history).
- Mid-session debug print noise from the diagnostic walks (kept the meaningful `[DIAG-LOC]` and `[DIAG-PUB]` outputs that show the diagnosis arc).
- Three poll commands that were just bookkeeping while the 7B model downloaded.
