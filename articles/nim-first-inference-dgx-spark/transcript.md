# Source material: nim-first-inference-dgx-spark

Cleaned session log and provenance for article #1. This is the evidence
that became prose in `article.md` — raw measurements, timings, log
excerpts, and decisions, with credentials and system-fingerprinting
content redacted.

_Session date: 2026-04-22. Compiled from five capture notes in
`articles/_drafts/2026-04-22/` and a resume session the same day._

---

## Preflight inventory (before any pull)

- **Docker:** 29.2.1, daemon running, `nvidia` runtime registered
  (`Runtimes: io.containerd.runc.v2 nvidia runc`). Cgroup v2 + systemd
  driver.
- **Already running containers:** 1 (`openshell-cluster-nemoclaw` from a
  prior article, holding port 8080).
- **Disk:** 3.4 TB free on `/` (root is `/dev/nvme0n1p2`, 3.7 TB total,
  154 GB used).
- **GPU:** `NVIDIA GB10` visible via `nvidia-smi`, driver 580.142.
  Unified-memory quirk: `memory.total / used / free` columns report
  `[N/A]` — memory is OS-managed on Grace, not driver-reported.
- **Port 8000:** free. Port 8080 held by `openshell` (NemoClaw
  auth-proxy). Port 11434 held by Ollama.
- **Ollama:** active, Nemotron-3-Super 123.6B Q4_K_M pulled. Left
  running to serve as an on-box quality baseline.
- **NGC credentials:** none found at session start. No `~/.ngc/config`,
  no `NGC_API_KEY` in env, no `nvcr.io` auth in `~/.docker/config.json`.
  Hard blocker until a key was created at `build.nvidia.com` and
  written to `~/.nim/secrets.env` (chmod 600, redacted).

## The image target

- Container: `nvcr.io/nim/meta/llama-3.1-8b-instruct-dgx-spark`
- Tag used: `:latest` (resolves to `1.0.0-variant` as of 2026-04-22)
- Spark-specific build — distinct NGC namespace from the generic
  `llama-3.1-8b-instruct` NIM. NVIDIA ships dedicated build recipes
  per device class, not a shared image with an aarch64 manifest.
- Compressed size per catalog listing: 9.2 GB (image-on-disk after
  pull: ~9.88 GB; weights cache after first run: ~8.5 GB).
- Catalog page: `catalog.ngc.nvidia.com/orgs/nim/teams/meta/containers/llama-3.1-8b-instruct-dgx-spark`
- Playbook: `build.nvidia.com/spark/nim-llm`

## What the container actually is

From `docker inspect` and `docker logs` on first run:

- Base user: `nvs:1000`, non-root. UID matches the host `nvidia` user,
  so bind-mounted cache directories work without a `-u` override.
- Working dir: `/opt/nim`
- Exposed ports (declared): `6006/tcp` (TensorBoard), `8888/tcp`
  (JupyterLab), `8000/tcp` (HTTP API). Only `8000` is the API; the
  other two are *declared* but left unmapped unless you `-p` them.
- API port: `NIM_HTTP_API_PORT=8000`
- GPU fraction: `NIM_GPU_MEM_FRACTION=0.5` (Spark default)
- Telemetry: `NIM_TELEMETRY_MODE=0` (off by default)
- Startup script: `/opt/nim/start_server.sh`

### Profile match from first-run logs

```
INFO 2026-04-22 18:56:49.541 profiles.py:345 Matched profile:
  feat_lora=false, gpu_device=2e12:10de, llm_engine=vllm,
  precision=fp8, pp=1, tp=1
  profile_id: bfb2c8a2d4dceba7d2629c856113eb12f5ce60d6de4e10369b4b334242229cfa
```

Confirms: vLLM (not TRT-LLM), FP8 weights, single-GPU, no LoRA. The
`nim_workspace_hash_v1` tag matched a Spark-specific storage path at
`nim/meta/llama-3.1-8b-instruct-dgx-spark` with tag
`hf-fp8-42d9515+chk1` (HuggingFace weight format, FP8 quant, git hash).
Weights are fetched per-profile at first run, not baked into the
container — keeps the image at ~9.88 GB vs. shipping every precision.

### Cache architecture

- Host-side: `~/.nim/cache/llama-3.1-8b-instruct/` (chmod 700,
  bind-mounted to the container)
- Container-side:
  `/opt/nim/.cache/ngc/hub/models--nim--meta--llama-3.1-8b-instruct-dgx-spark/blobs/`
- Hash-named blobs (content-addressed, HuggingFace-style) with resolved
  symlinks at the cache top-level for `config.json`,
  `tokenizer_config.json`, `model.safetensors.index.json`.

## Cold-start measurements

### First run (empty cache)

- **`docker run` → `/v1/models` returns 200: 205 s**
- Phase breakdown (from `docker logs` and cache directory growth):
  - 0–5 s: profile selection, NGC manifest fetch.
  - 5–~60 s: model-weight downloads from `api.ngc.nvidia.com` (cache
    reached 5.9 GB at t+55 s, 8.5 GB at t+115 s).
  - ~60–~180 s: `Loading safetensors checkpoint shards` → CUDA graph
    compilation. Log confirms multiple graphs compiled, each ~5.87 s.
  - ~180–205 s: HTTP server binding and final readiness.

### Warm-cache (second and third runs, cache retained)

- Run A (default `NIM_GPU_MEM_FRACTION=0.5`): **110 s**
- Run B (`NIM_GPU_MEM_FRACTION=0.8`): **106 s**
- Mean: **~108 s**
- Weight-download phase drops to zero; shard-load-plus-CUDA-graph-compile
  remains.

## Inference benchmark

**Prompt:** `Write a Python one-liner that returns the nth Fibonacci number.`
Identical to the Round 2 prompt used against Ollama/Nemotron in the
`nemoclaw-vs-openclaw-dgx-spark` article. `max_tokens=512`,
`temperature=0.7`, non-streaming.

### Round-by-round, `NIM_GPU_MEM_FRACTION=0.5`

| Round | Wall-clock | Completion tokens | tok/s |
|---:|---:|---:|---:|
| 1 | 10.22 s | 253 | 24.89 |
| 2 | 6.66 s | 165 | 24.90 |
| 3 | 8.88 s | 219 | 24.72 |
| 4 | 8.86 s | 219 | 24.84 |

Mean: 24.84 tok/s. Variance explained by output length, not throughput.

### Round-by-round, `NIM_GPU_MEM_FRACTION=0.8`

| Round | Wall-clock | Completion tokens | tok/s |
|---:|---:|---:|---:|
| 1 | 10.28 s | 253 | 24.60 |
| 2 | 6.68 s | 165 | 24.72 |
| 3 | 8.91 s | 219 | 24.57 |
| 4 | 8.88 s | 219 | 24.67 |

Mean: 24.64 tok/s. Within 0.2 tok/s of the 0.5 baseline — no throughput
gain from raising the fraction on a single-request workload.

### Streaming

- `stream: true`, same prompt.
- **TTFT: 52 ms** (POST → first SSE event)
- Total: 6.15 s, 153 SSE events.

## Quality findings

### Temperature 0.7 response (verbatim, Round 1)

> ```python
> def fibonacci(n):
>     return (fibonacci_matrix([[1, 1], [1, 0]], n - 1)[0][0])
> ```
>
> *Note: the `fibonacci_matrix` function is not shown here.*

Not a one-liner. `fibonacci_matrix` is a hallucinated helper — no such
function exists in the Python stdlib or in any mainstream package.

### Temperature 0 response (verbatim, follow-up)

```python
def fibonacci(n): return (pow([[1, 1], [1, 0]], n - 1, mod=10**9 + 7))[0][0]
```

Invalid Python. `pow(x, y, z)` takes scalars; there is no `mod=` kwarg.
`TypeError` on first call. Durable failure, not sampling noise.

### Baseline comparison (prior session)

Ollama Nemotron-3-Super 123B Q4_K_M on same prompt:
**25.8 s wall-clock, correct one-liner** (`lambda n: n if n<2 else fib(n-1)+fib(n-2)`).

### Identical completion counts across A/B

Across both `NIM_GPU_MEM_FRACTION` settings, the four rounds produced
the same token counts both times: 253, 165, 219, 219. Suggests vLLM
default determinism or strong prefix caching. For genuinely variable
sampling, pass an explicit `"seed"` per request.

## Telemetry (idle post-benchmark)

```
NVIDIA GB10 | util.gpu: 2% | util.memory: 0% | temp: 43C | power: 10.94 W
```

```
docker stats nim-llama31-8b (idle)
  CPU 1.63%   MEM 2.488 GiB / 121.7 GiB (2.04%)
  NET in 9.24 GB / out 116 MB
  BLOCK in 9.11 MB / out 9.36 GB
```

### The Spark observability blind spot

Three tools, three blind spots for "how much memory is the model using":

- `nvidia-smi --query-gpu=memory.*` returns `[N/A]` on GB10 — unified
  memory is OS-managed, not driver-reported.
- `docker stats` reports container RSS only (2.49 GiB = Python + vLLM
  bindings + tokenizer + CUDA driver stubs). Model weights mapped into
  unified memory do **not** show here.
- `free -h` (host) would show model weights as used system memory but
  is indistinguishable from page cache or any other allocation.

On a discrete x86 GPU, `nvidia-smi` tells you GPU-side memory and
`docker stats` tells you CPU-side; the split is clean. On the Spark,
nothing individually tells you "how much is the model using." Correlate
`free -h` deltas across load/unload, or instrument the NIM process.

## Decisions and rationale

- **Host port 8000** (default). No conflict. The `build.nvidia.com`
  playbook uses 8080 but the image's `NIM_HTTP_API_PORT` is 8000 —
  chose image-default for minimum friction.
- **Left Ollama + NemoClaw sandbox running during benchmark.** Spark's
  128 GB carried all three concurrently with no measurable impact on
  NIM throughput (GPU util was near-zero between requests anyway).
- **Baseline prompt reused.** Apples-to-apples with the Ollama/Nemotron
  baseline from the prior article.

## Open threads that didn't make the article

- Bigger prompt benchmarks (longer context, code-completion,
  multi-turn).
- Concurrent-request throughput — where `NIM_GPU_MEM_FRACTION=0.8`
  might actually earn its keep.
- The bundled JupyterLab — does the Spark NIM's workbench framing hold
  up for real notebook work, or is it a checkbox? Tangential to article
  #1; good candidate for a follow-up or polish pass.
- Qwen3-32B NIM for DGX Spark, linked from the playbook page. Potential
  article once the embedding + RAG foundation is in place.

## Scrub summary

Content removed or not-included in this transcript during the scrub:

- **NGC API keys:** two distinct keys pasted during setup; both
  redacted. The `~/.nim/secrets.env` file lives outside the repo
  (chmod 600) and is not tracked.
- **Container hashes left in place intentionally:** the
  `profile_id` and `nim_workspace_hash_v1` values are NVIDIA-published
  build identifiers, not secrets.
- No emails, phone numbers, home-network public IPs, MAC addresses,
  or personal hostnames appear in the source notes.
- No full-desktop screenshots; all three captures were Playwright
  scoped to specific URLs (NGC catalog, playbook overview, playbook
  instructions).
