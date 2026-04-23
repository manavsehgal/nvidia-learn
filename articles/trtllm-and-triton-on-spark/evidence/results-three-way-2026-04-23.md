# Three-way benchmark — 2026-04-23

## Setup

- Hardware: NVIDIA DGX Spark, GB10 (Blackwell SM 12.1), 121.7 GiB unified
- Prompt: 29 tokens, max_tokens 200, temperature 0, greedy
- FP8 checkpoint: `nvidia/Llama-3.1-8B-Instruct-FP8` (ModelOpt 0.33 export)
- NVFP4 checkpoint: `nvidia/Llama-3.1-8B-Instruct-NVFP4` (ModelOpt 0.37, group_size 16, FP8 KV cache)
- NIM stack: vLLM 0.10.1.1+381074ae, NVIDIA Spark-specific FP8 build
- TRT-LLM stack: Triton 25.12 / TRT-LLM 1.1.0 / `trtllm-serve` OpenAI endpoint

## Serial (single stream, p50)

| stack | TTFT (ms) | decode (tok/s) | end-to-end wall (s) | engine size |
|---|---:|---:|---:|---:|
| NIM vLLM FP8 | 54.0 | 22.06 | 7.33 | n/a |
| TRT-LLM FP8 | 46.1 | 24.57 | 6.00 | 8.6 GB |
| TRT-LLM NVFP4 | 30.8 | 38.82 | 5.11 | 5.7 GB |

## Concurrent (aggregate tok/s by client count)

| stack | c=1 | c=2 | c=4 | c=8 |
|---|---:|---:|---:|---:|
| NIM-vLLM-FP8 | 21.9 | 45.0 | 89.6 | 175.2 |
| TRT-LLM-FP8 | 26.9 | 52.8 | 107.6 | 193.5 |
| TRT-LLM-NVFP4 | 36.3 | 69.2 | 135.2 | 264.7 |

## Deltas (vs NIM vLLM FP8 baseline)

| stack | TTFT | decode | c=8 throughput |
|---|---:|---:|---:|
| TRT-LLM-FP8 | -14.7% | +11.4% | +10.5% |
| TRT-LLM-NVFP4 | -42.9% | +76.0% | +51.1% |

## Headline

TRT-LLM FP8 wins the single-stream race by ~10-15% vs NIM's vLLM FP8 — real but
not decisive given the build complexity. The step-change is **NVFP4**: 76% faster
decode, 43% lower TTFT, 51% higher c=8 aggregate, and a 34%-smaller engine file.
NVFP4 is Blackwell's payoff — the reason to drop NIM is the 4-bit kernel, not the
FP8 one. On a Second Brain that sits at concurrency 1-2, NVFP4 cuts wall-clock
from ~7.3s to ~5.1s per response.
