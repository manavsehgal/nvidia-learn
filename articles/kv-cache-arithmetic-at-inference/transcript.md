# Transcript — kv-cache-arithmetic-at-inference

This article is a *Looking Beyond Spark* piece — the second in the series after `gpu-sizing-math-for-fine-tuning`. It is a synthesis article, not a session transcript: no new long-running experiment was run for it. Source material is the two existing Spark-measured anchor articles plus published model architecture facts.

## Provenance

Per the *Looking Beyond Spark* series convention, this piece extrapolates Spark-measurable arithmetic to frontier hardware the Spark itself cannot run. The Spark anchors:

- **`articles/nim-first-inference-dgx-spark/article.md`** — Llama 3.1 8B FP8 in NIM container on Spark. Measured: 24.84 tok/s steady decode, 52 ms TTFT, 8.5 GB cached weights, 11.2 GiB resident, `NIM_GPU_MEM_FRACTION=0.5` is the default and irrelevant for single-stream throughput. Cited in §Verification.

- **`articles/trtllm-and-triton-on-spark/article.md`** — Same 8B base, dropped from NIM to raw TensorRT-LLM. Measured: TRT-LLM FP8 24.6 tok/s · 46 ms TTFT · 8.6 GB engine; TRT-LLM NVFP4 38.8 tok/s · 31 ms TTFT · 5.7 GB engine · **2.5 GiB resident**. Build flags `--max_batch_size 8 --max_input_len 2048 --max_seq_len 4096 --use_paged_context_fmha enable --use_fp8_context_fmha enable` cited verbatim in §Verification.

## Architecture facts cited

Llama 3.1 family architecture (publicly documented on Meta's model cards and HuggingFace `config.json` files):

- **Llama 3.1 8B** — 32 layers, 32 attention heads, 8 KV heads (GQA-4), head_dim 128.
- **Llama 3.1 70B** — 80 layers, 64 attention heads, 8 KV heads (GQA-8), head_dim 128.
- **Llama 3.1 405B** — 126 layers, 128 attention heads, 8 KV heads (GQA-16), head_dim 128.

Notable: KV head count is constant at 8 across the family — a deliberate serving-friendly architectural decision.

## KV cache equation

```
KV bytes = 2 (K and V) × n_layers × n_kv_heads × head_dim × seq_len × batch × bytes_per_value
```

Per-token KV at FP16 (2 bytes per stored value):

| Model | n_layers × n_kv_heads × head_dim × 2 (K+V) × 2 bytes | Per-token KV |
|---|---|---|
| Llama 3.1 8B | 32 × 8 × 128 × 2 × 2 | 131,072 B ≈ 128 KB |
| Llama 3.1 70B | 80 × 8 × 128 × 2 × 2 | 327,680 B ≈ 320 KB |
| Llama 3.1 405B | 126 × 8 × 128 × 2 × 2 | 516,096 B ≈ 504 KB |

FP8 KV halves each figure. The article rounds 70B to 320 KB/tok (FP16) / 160 KB/tok (FP8) for the concurrency × context table.

## Concurrency × context table (70B, FP16 KV)

| Concurrency × Context | KV (FP16) | KV (FP8) | Hardware tier |
|---|---|---|---|
| 1 × 4k | 1.3 GB | 0.65 GB | trivial |
| 32 × 4k | 42 GB | 21 GB | 1× H100 80 GB |
| 32 × 16k | 168 GB | 84 GB | 1× H200 141 GB / 2× H100 |
| 128 × 8k | 336 GB | 168 GB | 4× H100 / 2× H200 |
| 32 × 128k | 1.3 TB | 656 GB | multi-node |

These numbers are computed from the equation, not benchmarked. Real serving stacks add 10–20% overhead for paged-block fragmentation, the speculative draft model's KV (if used), and continuous-batching workspace.

## Hardware bandwidth facts

- H100 SXM5: 80 GB HBM3, 3.35 TB/s memory bandwidth.
- H200 SXM5: 141 GB HBM3e, 4.8 TB/s memory bandwidth (~43% lift over H100).
- Decode is bandwidth-bound; prefill is compute-bound. The H200's bandwidth advantage is much more visible on long-context decode than on prefill-dominated prompts.

## Editorial overlay

Default for the *Looking Beyond Spark* series: same four memory bills as training; different weights. KV cache becomes the dominant bill at serving, scaling with concurrent users × context length rather than parameter count. Spark teaches the per-token math at 8B/single-user; multiplication takes it the rest of the way.

## What this article does NOT do

- Does not benchmark a 70B serve on rented H200s. The numbers are arithmetic, derived from published architecture facts and the cache equation.
- Does not exhaustively compare vLLM, TRT-LLM, NIM, SGLang, LMDeploy. The §Tradeoffs section names the dimension each optimizes (PagedAttention baseline / Blackwell NVFP4 / NVIDIA bundle / RadixAttention prefix sharing) and stops there.
- Does not cover disaggregated prefill/decode at frontier scale. That's the next *Looking Beyond Spark* installment, named in the closing.

## Diagrams

- **Inline fn-diagram** in §Architectural context — bar chart showing KV cache for 70B across five concurrency × context tiers, with hardware annotations. Indigo accent on the 32 × 16k row (the most representative real serve).
- **Signature SVG** at `src/components/svg/KvCacheArithmetic.astro` — 4-row variant of the same shape sized for the 300×200 thumbnail, with a Spark-anchor line at the bottom.

Both follow the visual language established by `FineTuneMemoryMath.astro` (signature for LBS #1) so the series reads as a coherent pair.
