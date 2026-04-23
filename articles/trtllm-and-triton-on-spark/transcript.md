# Transcript — trtllm-and-triton-on-spark

Session of 2026-04-23. Three-way benchmark of 8B serving stacks on a DGX
Spark (GB10, Blackwell SM 12.1, driver 580.142). Source material for the
published article; preserved for reproducibility.

## Starting state

- NIM 8B container stopped (`Exited (137) 11 hours ago`). Brought up with
  `docker start nim-llama31-8b`; took ~90 seconds to respond on
  `/v1/models`.
- `curl http://localhost:8000/v1/models` confirmed model name
  `meta/llama-3.1-8b-instruct`, max_model_len 8192.
- `docker inspect nim-llama31-8b --format '{{range .Config.Env}}…'`
  revealed:
  - `BACKEND_TYPE=vllm`
  - `VLLM_VERSION=0.10.1.1+381074ae`
  - `NVIDIA_VLLM_VERSION=25.09`
  - `TRT_VERSION=10.13.3.9` (bundled but unused by this NIM)
  - `MODEL_OPT_VERSION=0.33.0`
- `curl http://localhost:8000/v1/metadata` confirmed NGC ref
  `llama-3.1-8b-instruct-dgx-spark:hf-fp8-42d9515+chk1` — the
  Spark-specific FP8 quantization.
- `docker stats nim-llama31-8b`: 11.2 GiB resident of 121.7 GiB unified.

## Baseline — NIM vLLM FP8

### Serial streaming bench (5 runs)

Prompt: "In one paragraph: what is retrieval-augmented generation and
when is it the wrong tool?" (29 prompt tokens). Max tokens 200,
temperature 0 (greedy, deterministic).

- TTFT p50: 54.0 ms (p95 67.4 ms)
- Decode rate (median): 22.06 tok/s
- Wall (median): 7.33 s for 165 tokens

### Concurrency bench (non-stream, 4 workers spawned as threads)

| c | aggregate tok/s | per-req p50 |
|---:|---:|---:|
| 1 | 21.9 | 7572 ms |
| 2 | 45.0 | 7358 ms |
| 4 | 89.6 | 7367 ms |
| 8 | 175.2 | 7486 ms |

Near-linear scaling — vLLM's continuous batching earning its reputation.

## Asset inventory

### HuggingFace checkpoints (un-gated)

Probed via `curl https://huggingface.co/api/models/<repo>/tree/main`:

- `nvidia/Llama-3.1-8B-Instruct-FP8` — 9.09 GB total (5.00 + 4.08 GB
  safetensors, plus tokenizer). ModelOpt 0.33 producer.
  Safetensors dtype breakdown (shard 1):
  `F32: 292 (scales)  BF16: 37 (embed/norms)  F8_E4M3: 128 (linear)`
- `nvidia/Llama-3.1-8B-Instruct-NVFP4` — 6.05 GB total. ModelOpt 0.37
  producer. `hf_quant_config.json` declares
  `quant_algo: NVFP4, kv_cache_quant_algo: FP8, group_size: 16`.
  Safetensors dtype breakdown:
  `F32: 512 (scales)  BF16: 66 (embed/norms)  F8_E4M3: 224
  U8: 224 (packed FP4, 2 values per byte)`

Both downloaded directly with `curl` — no HF login or NGC auth needed.

### Triton/TRT-LLM container images (arm64 manifests)

- `nvcr.io/nvidia/tritonserver:25.01-trtllm-python-py3` — 44.4 GB
  extracted, TRT-LLM 0.17.0.post1. Container startup warned *"Detected
  NVIDIA GB10 GPU, which may not yet be supported in this version of the
  container"*. Heeded in retrospect.
- `nvcr.io/nvidia/tritonserver:25.12-trtllm-python-py3` — 34.6 GB
  extracted, TRT-LLM 1.1.0, Triton Server 2.64.0. No GB10 warning.

## The FP8 build failure on 25.01

Converted HF FP8 → TRT-LLM checkpoint in 16 seconds with
`convert_checkpoint.py --use_fp8`. The build failed 3 minutes into
`trtllm-build`:

```
[TRT-LLM] [I] Compute capability: (12, 1)
[TRT-LLM] [I] SM count: 48
[TRT-LLM] [I] SM clock: 3003 MHz
...
terminate called after throwing an instance of 'tensorrt_llm::common::TllmException'
  what():  [TensorRT-LLM][ERROR] Assertion failed: FP8 FMHA cannot be
    enabled except on Ada or Hopper or Blackwell Arch.
    (/workspace/tensorrt_llm/cpp/tensorrt_llm/common/attentionOp.cpp:2109)
```

Diagnosis: TRT-LLM 0.17's enumeration of "Blackwell Arch" recognises the
datacenter B100/B200 at SM 10.0 but not the Spark's GB10 at SM 12.1.
Classic version-skew bug. Full build log preserved at
`evidence/build-25.01-fp8-fail.log`.

## Successful builds on 25.12

### FP8 engine

```bash
# Convert (22 s)
python3 /app/examples/models/core/llama/convert_checkpoint.py \
  --model_dir /model --output_dir /out --dtype bfloat16 --use_fp8

# Build (42 s wall, 32 s actual compile)
trtllm-build --checkpoint_dir /ckpt --output_dir /engine \
  --gemm_plugin fp8 \
  --max_batch_size 8 --max_input_len 2048 --max_seq_len 4096 \
  --max_num_tokens 4096 \
  --use_paged_context_fmha enable --use_fp8_context_fmha enable
```

Artifact: `rank0.engine` 8.6 GB + `config.json`.

Log highlights:

```
[TRT-LLM] [I] Compute capability: (12, 1)
[TRT-LLM] [I] SM count: 48
[TRT-LLM] [W] Failed to infer cluster info for NVIDIA GB10, treat it
              as a L40 node with 121 GB memory. This setting makes no
              effect if you do not use auto parallel.
[TRT-LLM] [I] Total time of building all engines: 00:00:32
```

### NVFP4 engine

Convert: 13 s. Build: 27 s. One flag swap: `--gemm_plugin nvfp4` and
`--use_nvfp4` on the convert step. Artifact: `rank0.engine` 5.7 GB — 34%
smaller than FP8.

## Serving — `trtllm-serve serve` (not full Triton model_repository)

TRT-LLM 1.1 ships `trtllm-serve` which wraps engine + tokenizer + OpenAI
HTTP surface in one command. This was the shorter path for a
single-model endpoint vs. writing four `config.pbtxt` files for the
ensemble model_repository.

```bash
docker run -d --name trtllm-serve-fp8 --gpus all -p 8003:8003 \
  -v /home/nvidia/trtllm-work/fp8-engine-v12:/engine:ro \
  -v /home/nvidia/models/llama-3.1-8b-instruct-fp8:/tokenizer:ro \
  nvcr.io/nvidia/tritonserver:25.12-trtllm-python-py3 \
  trtllm-serve serve /engine \
    --tokenizer /tokenizer --backend tensorrt \
    --host 0.0.0.0 --port 8003 \
    --max_batch_size 8 --max_num_tokens 4096 --max_seq_len 4096 \
    --kv_cache_free_gpu_memory_fraction 0.4
```

Startup time from container run → `/v1/models` responsive: ~60 s for
either engine.

### NVFP4 tokenizer gotcha

First NVFP4 request returned HTTP 400: *"No chat template found for the
given tokenizer and tools."* The HF repo for the quantized model ships
`tokenizer_config.json` without a `chat_template` field. Fix: point
`--tokenizer` at the FP8 checkpoint dir (or the original Llama-3.1
Instruct dir). The tokenizer/vocab is identical across the base and both
quantized variants; only the weights differ.

## Full three-way benchmark

Same prompt, same temperature, same max_tokens, same harness
(evidence/benchmark.py). Raw per-stack JSON results are in
evidence/bench-*.json.

### Serial

| stack | TTFT p50 | TTFT p95 | decode | wall p50 |
|---|---:|---:|---:|---:|
| NIM vLLM FP8 | 54.0 ms | 67.4 ms | 22.06 tok/s | 7.33 s |
| TRT-LLM FP8 | 46.1 ms | 67.4 ms | 24.57 tok/s | 6.00 s |
| TRT-LLM NVFP4 | 30.8 ms | — | 38.82 tok/s | 5.11 s |

### Concurrent (aggregate tok/s)

| stack | c=1 | c=2 | c=4 | c=8 |
|---|---:|---:|---:|---:|
| NIM vLLM FP8 | 21.9 | 45.0 | 89.6 | 175.2 |
| TRT-LLM FP8 | 26.9 | 52.8 | 107.6 | 193.5 |
| TRT-LLM NVFP4 | 36.3 | 69.2 | 135.2 | 264.7 |

### Deltas vs NIM baseline

| stack | TTFT | decode | c=8 aggregate |
|---|---:|---:|---:|
| TRT-LLM FP8 | −14.7% | +11.4% | +10.5% |
| TRT-LLM NVFP4 | −42.9% | +76.0% | +51.1% |

## Memory footprint

From `docker stats --no-stream` after each run stabilized:

- NIM 8B: 11.2 GiB / 121.7 GiB (9.2%) at steady state serving
- TRT-LLM FP8 via trtllm-serve: ~3.5 GiB
- TRT-LLM NVFP4 via trtllm-serve: 2.5 GiB

The NVFP4 memory win is structural — 4-bit weights + FP8 KV cache add up
to roughly a quarter of what the NIM stack holds for equivalent work.

## Session timing

- NIM startup (cold): 90 s
- Baseline NIM bench: ~15 min (serial + concurrency across 5+ runs)
- Triton 25.01 pull: ~12 min
- FP8 checkpoint download (parallel): ~4 min
- NVFP4 checkpoint download (parallel): ~4 min
- 25.01 FP8 build attempt + failure + log capture: ~8 min
- Triton 25.12 pull: ~10 min (parallel with the above)
- 25.12 FP8 convert + build: ~1 min
- 25.12 NVFP4 convert + build: ~1 min
- trtllm-serve FP8 start + bench: ~3 min
- trtllm-serve NVFP4 start + tokenizer fix + bench: ~4 min
- Three-way results compilation: ~5 min

Total: ~60-70 min of active work, most of it parallelizable.

## Things left for a follow-up

- Check whether NVFP4 decode quality matches FP8 on a qrels-style
  grounding benchmark. Expected regression is small but non-zero.
- Stand up the full Triton model_repository ensemble and measure the
  delta vs trtllm-serve for a fair comparison (the working hypothesis:
  equal for one model, Triton's concurrent-model scheduling matters only
  when you're serving 2+ from one process).
- Pre-compile an AWQ-INT4 or INT8 variant and add a fourth column to the
  comparison table. NVFP4 is the Blackwell-native 4-bit path; the
  cross-architecture 4-bit paths may offer different latency/quality
  tradeoffs.
- Measure cold-start time for trtllm-serve vs NIM. Anecdotally the NIM
  warmup (~90 s) felt longer than trtllm-serve (~60 s) but neither was
  instrumented this session.
