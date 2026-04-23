# Baseline: NIM 8B on DGX Spark — 2026-04-23

## Container

- Image: `nvcr.io/nim/meta/llama-3.1-8b-instruct-dgx-spark:latest`
- Model: `meta/llama-3.1-8b-instruct` (NIM-reported name)
- NGC ref: `llama-3.1-8b-instruct-dgx-spark:hf-fp8-42d9515+chk1`
- Backend: **vLLM 0.10.1.1+381074ae** (NVIDIA fork, `NVIDIA_VLLM_VERSION=25.09`)
- Precision: **FP8** (NVIDIA's Spark-specific quantized build)
- TRT version bundled: 10.13.3.9; Model Optimizer 0.33.0 — unused by this backend
- Max model len: 8192 tokens
- Resident memory: 11.2 GiB of 121.7 GiB unified (9.2%)

## Host

- Hardware: NVIDIA DGX Spark (GB10, SM 12.1 Blackwell, driver 580.142)
- Arch: aarch64

## Serial latency (stream, 5 runs each)

- Prompt: 29 tokens ("In one paragraph: what is retrieval-augmented generation...")
- Max tokens: 200, temperature 0, greedy decode
- **TTFT p50: 54.0 ms**
- **TTFT p95: 67.4 ms**
- **Decode rate: 22.06 tok/s** (median across runs)
- **End-to-end wall p50: 7.33 s** for 165-token completion

## Concurrency scaling (non-streaming POSTs)

| Concurrency | Aggregate tok/s | Per-request p50 |
|---:|---:|---:|
| 1 | 21.9 | 7572 ms |
| 2 | 45.0 | 7358 ms |
| 4 | 89.6 | 7367 ms |
| 8 | 175.2 | 7486 ms |

vLLM's continuous batching scales **near-linearly 8×** with almost no per-request
latency penalty. This is the bar TRT-LLM must beat on a single GB10.

## What this reframes for the article

The original placeholder framed TRT-LLM as "lower per-token latency than NIM's
fixed stack." That framing assumes NIM is convenient but slow. The actual NIM
build is (a) already FP8, (b) vLLM-backed with excellent continuous batching,
and (c) tuned for Spark specifically. The comparison the article should make is:

1. Can TRT-LLM FP8 beat NIM vLLM FP8 on **single-stream TTFT/decode**? (The
   Second Brain case — one user, one query at a time.)
2. Can TRT-LLM NVFP4 (Blackwell-native 4-bit) beat both on decode rate and
   memory, given SM 12.1's hardware FP4 support?
3. Does TRT-LLM + Triton dynamic batching meaningfully outperform vLLM's
   continuous batching at concurrency 4 and 8?

Answers pending engine build.
