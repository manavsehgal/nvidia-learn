# 2026-04-22 — NIM benchmark + cold-start + GPU telemetry

Container: `nim-llama31-8b` (`nvcr.io/nim/meta/llama-3.1-8b-instruct-dgx-spark:latest`).
Model served: `meta/llama-3.1-8b-instruct` (vLLM, FP8, tp=1, pp=1, max_model_len=8192).

## Cold-start time decomposition

- **Container start** → `/v1/models` returns 200: **205 s** (first run, empty cache).
- Phase breakdown from `docker logs` + cache growth:
  - 0–5 s: profile selection, NGC manifest fetch.
  - 5–~60 s: model-file downloads from `api.ngc.nvidia.com` (cache hit 5.9 GB at t+55s, 8.5 GB at t+115s).
  - ~60–~180 s: `Loading safetensors checkpoint shards` → CUDA graph compilation. Log confirms: `Compiling a graph for dynamic shape takes 5.87 s` (multiple graphs compiled).
  - ~180–205 s: HTTP server binding, final readiness.

Second run (weights cached): expected to skip the ~60s download, so ~150s estimate. Not re-measured this session; add to article #1 as a follow-up measurement.

## Apples-to-apples benchmark

Prompt (identical to nemoclaw article's Round 2): `Write a Python one-liner that returns the nth Fibonacci number.`
`max_tokens=512`, `temperature=0.7`, non-streaming.

| Round | Wall-clock | Completion tokens | tok/s |
|---:|---:|---:|---:|
| 1 (first after ready) | 10.22 s | 253 | 24.8 |
| 2 | 6.66 s | 165 | 24.8 |
| 3 | 8.88 s | 219 | 24.7 |
| 4 | 8.86 s | 219 | 24.7 |

**Steady-state: ~24.8 tok/s sustained** — variance explained entirely by output length, not throughput.

Streaming round (same prompt, `stream: true`):
- **TTFT: 52 ms** (fifty-two milliseconds from POST to first SSE event)
- Total: 6.15 s, 153 SSE events (token-equivalent).

## Baseline comparison — NIM Llama 3.1 8B (FP8) vs. Ollama Nemotron-3-Super 123.6B (Q4_K_M)

From `nemoclaw-vs-openclaw-dgx-spark` transcript, same Fibonacci prompt, Ollama raw warm: **25.8 s** wall-clock.

| Stack | Model | Params | Quant | Steady wall-clock | Notes |
|---|---|---:|---|---:|---|
| Ollama (raw) | nemotron-3-super | 123.6 B | Q4_K_M (gguf) | 25.8 s | baseline from nemoclaw article |
| NIM DGX-Spark | meta/llama-3.1-8b-instruct | 8 B | FP8 | ~8 s (warm, median) | this session |

**The honest quality tradeoff.** NIM Llama 8B at ~8s is ~3× faster than Nemotron 123B at ~26s. But the actual NIM response was **not a one-liner** — it proposed `def fibonacci(n): return (fibonacci_matrix([[1,1],[1,0]], n-1)[0][0])` and then said "the `fibonacci_matrix` function is not shown here". That's a hallucinated dependency, not a one-liner. Nemotron 123B on Ollama produced a correct `lambda n: n if n<2 else fib(n-1)+fib(n-2)`.

That's the real headline for article #1: **on the Spark, the speed/quality curve between 8B FP8 and 123B Q4 is steep, and "faster" isn't automatically "better" for your actual task.** A great hook — precisely the "inference economics on-device" thesis the learning matrix flags as Topic 3.

## GPU + container telemetry (idle post-benchmark)

```
NVIDIA GB10 | util.gpu: 2%  | util.memory: 0% | temp: 43°C | power: 10.94 W
```

```
docker stats nim-llama31-8b (idle)
  CPU 1.63%   MEM 2.488 GiB / 121.7 GiB (2.04%)   NET in 9.24 GB / out 116 MB   BLOCK in 9.11 MB / out 9.36 GB
```

## Spark-specific observability gotcha

**Three tools, three blind spots:**

- `nvidia-smi --query-gpu=memory.*` returns `[N/A]` on GB10 — unified memory is OS-managed, not driver-reported.
- `docker stats` reports **container RSS** (2.488 GiB — this is vLLM Python + CUDA driver + tokenizer + kernel stubs, *not* the model weights). Unified memory mapped into the GPU doesn't show here.
- `free -h` (host) would show the model weights as used system memory — but indistinguishable from page cache or any other allocation.

On a discrete x86 GPU, `nvidia-smi` tells you GPU-side memory and `docker stats` tells you CPU-side memory; the split is clean. On the Spark, **nothing individually tells you "how much is the model using"** — you have to correlate `free -h` deltas across load/unload cycles, or instrument the NIM process directly. Worth flagging loudly in the article.

## Current state of the apps (per arc closing pattern)

- **Second Brain now:** has a brain. Can answer `curl /v1/chat/completions` in ~8 s warm at 24.8 tok/s. No memory, no corpus, no retrieval yet. Next up: `nemo-retriever-embeddings-local`.
- **LLM Wiki now:** has a writer. No pages to write to, no schema, no ingest pipeline. Next up: same (Retriever — pages start as vectors for dedup before they become markdown).
- **Autoresearch now:** has a driver. No training loop yet, no `train.py`, no critic. Next up: same shared foundation first — Retriever for trajectory embedding.

## Anomalies worth revisiting

- Llama 8B FP8 response quality on a trivial prompt was weak (hallucinated helper function). Worth a second test with `temperature=0` to rule out sampling variance before writing it into the article as a durable finding.
- Cold-start 205s includes one-time weight download. Second-run number with warm cache is the more useful "daily life" figure. Measure before drafting article #1.
- `NIM_GPU_MEM_FRACTION=0.5` is a Spark-specific default limiting model-visible memory. Try raising to 0.8 and re-benchmark — may unlock higher throughput or larger batch.
