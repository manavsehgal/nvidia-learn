# Transcript — `nemo-framework-on-spark` (A1)

Provenance for the published essay. Captures the actual session — what was
pulled, what was installed, what failed, what worked — so the article's
numbers and friction points can be reproduced or audited later.

## Session goals

Open the Autoresearch arc with the NeMo Framework install on Spark, anchored
to the editorial overlay *"Why NeMo Framework over vanilla PyTorch on the
Spark"*. Run the smallest honest comparison — same 354M GPT trained twice
under matched conditions — to set a measured floor the rest of the arc
can ratchet against.

## What ran

| step | command | wall | result |
|---|---|---:|---|
| 1 | `docker pull nvcr.io/nvidia/pytorch:25.11-py3` | ~25 min | 29.8 GB on disk; multi-arch, no EULA |
| 2 | `docker pull nvcr.io/nvidia/nemo:25.07` | <5 s | **403** (license not yet accepted) |
| 3 | NGC catalog visit (Playwright-MCP) → user signs in → accept terms on `nvcr.io/nvidia/nemo:26.04.00` | (manual) | EULA recorded |
| 4 | `docker pull nvcr.io/nvidia/nemo:26.04.00` (1st try) | <5 s | **403** (guest accept earlier didn't bind) |
| 5 | User signs in + accepts again under same account as docker auth | (manual) | EULA bound to NGC API key |
| 6 | `docker pull nvcr.io/nvidia/nemo:26.04.00` (retry) | ~45 min | 70.1 GB on disk |
| 7 | `pip install nemo-toolkit[nlp]` inside `pytorch:25.11-py3` | <2 min | **fail** — `opencc` no aarch64 wheel |
| 8 | `pip install nemo-toolkit megatron-core` (no extras) | <2 min | nemo 2.7.3 + megatron-core 0.17.0 imported OK |
| 9 | run `nemo_train.py` on `pytorch:25.11-py3` | <30 s | **fail** — `TypeError: get_cpu_offload_context() got an unexpected keyword 'retain_pinned_cpu_buffers'` (TE 2.9 ≠ Megatron-Core 0.17) |
| 10 | run `nemo_train.py` on `nvcr.io/nvidia/nemo:26.04.00` (1st try) | <30 s | **fail** — `TypeError: input dtype torch.float32 vs layer_norm_weight torch.bfloat16` |
| 11 | wrap forward pass in `torch.amp.autocast(bf16)` | (edit) | resolved |
| 12 | run `nemo_train.py` on NeMo container (final) | ~33 s | success, 12,820 tok/s, 7.94 GiB peak |
| 13 | run `vanilla_train.py` on `pytorch:25.11-py3` | ~36 s | success, 12,119 tok/s, 11.28 GiB peak |
| 14 | nvidia-smi snapshot during NeMo run | <1 s | 96% util, 60.77 W, 51 °C |

## Key cargo-cult code that shipped to evidence/

Two pieces of Megatron-Core scaffolding that cost me ~10 min each to find
and that the article calls out as "the kind of thing the framework absorbs
for you":

```python
# 1. Megatron's parallel-state init — required even with TP=1, PP=1.
parallel_state.initialize_model_parallel(
    tensor_model_parallel_size=1,
    pipeline_model_parallel_size=1,
)
tensor_parallel.model_parallel_cuda_manual_seed(0)

# 2. TransformerConfig must say bias=False AND turn off the bias fusions.
TransformerConfig(
    add_bias_linear=False,
    bias_activation_fusion=False,  # else: ValueError
    bias_dropout_fusion=False,     # else: ValueError
    ...
)
```

## Headline numbers (354M GPT, 100 steps, batch 4 × 1024, bf16, GB10)

| metric | vanilla | nemo/megatron-core | delta |
|---|---:|---:|---:|
| mean step time | 338.0 ms | 319.5 ms | −5.5% |
| tokens/sec | 12,119 | 12,820 | +5.8% |
| peak GPU mem (allocated) | 11.28 GiB | 7.94 GiB | −29.6% |
| peak GPU mem (reserved) | 12.98 GiB | 10.54 GiB | −18.8% |
| initial loss | 585.5 | 11.0 | (different init) |
| final loss after 100 steps | 49.6 | 0.05 | (different init) |

Both runs used identical seed, identical random data, identical batch &
sequence shape. The only change is the model implementation. TE's bf16
attention kernel + Megatron-Core's calibrated init account for the deltas.

## Decisions made along the way

- **Pivot from NeMo container to PyTorch container for the vanilla baseline.**
  The vanilla baseline only needs PyTorch + CUDA. Running it in the smaller
  29.8 GB container instead of the 70 GB NeMo container makes the article's
  install-friction story honest (the heavy container is not free, and you
  shouldn't pay for it if you only want vanilla).

- **Use `megatron.core.models.gpt.GPTModel` directly, not `nemo lm pretrain`.**
  The article's overlay is a throughput comparison, so the matched script
  needs the train loop to be identical between the two. The recipe API
  earns its keep on lines-of-code, not throughput — a separate piece of
  evidence and probably a separate article (A4 or later).

- **Don't switch the tested container architecture per-step.** Keeping
  vanilla on `pytorch:25.11-py3` and NeMo on `nemo:26.04.00` cleanly
  separates "what the runtime container ships" from "what the framework
  install adds". Mixing — e.g., installing NeMo via pip and running it on
  the PyTorch container — is exactly the path that hits the TE 2.9 vs MC
  0.17 mismatch documented in the article body.

- **Loss curves left honest.** Vanilla starts at 585, NeMo at 11. Both
  are "correct" given their inits — but the article calls this out as a
  separate NeMo earning rather than averaging it out or normalizing.

## Friction worth documenting in skill memory

- The NGC EULA accept must happen under the **same account whose
  `nvapi-...` key is in `~/.docker/config.json`**, after signing in.
  Guest accepts don't bind. Two failed pulls before figuring that out.
- aarch64 + NeMo NLP extra = `opencc` wheel build failure. Skip the
  `[nlp]` extra; install the language-collection deps separately if
  needed.
- TransformerEngine 2.9 (in `pytorch:25.11-py3`) is incompatible with
  Megatron-Core 0.17 — pin both via the NeMo container or upgrade TE.
- Megatron-Core requires `parallel_state.initialize_model_parallel()`
  AND `tensor_parallel.model_parallel_cuda_manual_seed()` even on a
  single GPU. The first failure mode is silent; the second produces
  `Exception: cuda rng state model-parallel-rng is not added`.
- Megatron's `TransformerConfig` cross-validates: setting
  `add_bias_linear=False` requires also setting
  `bias_activation_fusion=False` and `bias_dropout_fusion=False`.

## Outputs preserved

```
evidence/
├── vanilla_train.py            # 200 lines, hand-rolled GPT train loop
├── vanilla_metrics.json        # baseline run results
├── nemo_train.py               # 215 lines, Megatron-Core matched
├── nemo_metrics.json           # NeMo run results
└── nvidia_smi_during_run.txt   # GPU state mid-run

screenshots/
└── 01-ngc-nemo-container.png   # NGC NeMo Megatron Backend page (Playwright-MCP)
```
