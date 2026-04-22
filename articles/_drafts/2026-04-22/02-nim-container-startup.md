# 2026-04-22 18:56:52 UTC — NIM container startup

Container `nim-llama31-8b` from `nvcr.io/nim/meta/llama-3.1-8b-instruct-dgx-spark:latest` launched.

## What the image actually is

- **Content size**: 9.88 GB (32.4 GB on-disk with overlayfs)
- **Base user**: `nvs:1000` — non-root, UID matches the host `nvidia` user. No `-u` override needed; host cache volume writable as-is.
- **Working dir**: `/opt/nim`
- **Exposed ports (declared)**: `6006/tcp` (TensorBoard), `8888/tcp` (Jupyter). Not 8000.
- **Actual API port**: `NIM_HTTP_API_PORT=8000` (env var). The OpenAI-compatible HTTP API lives on 8000 regardless of what the image EXPOSEs.
- **Extra bundled services on this DGX-Spark variant**: JupyterLab on 8888, TensorBoard on 6006. This is a **model workbench**, not a bare inference endpoint — notable departure from stock NIM. Skipped for this benchmark (only mapped 8000).
- **GPU memory fraction**: `NIM_GPU_MEM_FRACTION=0.5` (NVIDIA-selected Spark default — leaves room for Jupyter / concurrent loads).
- **Telemetry**: Off by default (`NIM_TELEMETRY_MODE=0`).
- **Startup script**: `$SERVER_START_SCRIPT_PATH=/opt/nim/start_server.sh` (called by entrypoint).

## What the first run does

From log line `INFO 2026-04-22 18:56:49.541 profiles.py:345 Matched profile ...`:

```
tags: {
  feat_lora: 'false',
  gpu_device: '2e12:10de',     # GB10 PCI ID
  llm_engine: 'vllm',
  nim_workspace_hash_v1: 'e8fd1d48...',
  pp: '1',
  precision: 'fp8',
  tp: '1'
}
profile_id: bfb2c8a2d4dceba7d2629c856113eb12f5ce60d6de4e10369b4b334242229cfa
```

**Runtime engine is vLLM**, not TensorRT-LLM. Precision is **FP8**. Single-GPU (tp=1, pp=1). No LoRA feature. The Spark variant has its own NGC storage namespace: `nim/meta/llama-3.1-8b-instruct-dgx-spark` with tag `hf-fp8-42d9515+chk1` (HuggingFace format, FP8 quant, git hash). Weights are fetched per-profile at first run, not baked into the container — keeps the image at a manageable 9.88 GB vs. shipping all precisions.

## Cache architecture (confirmed from downloads)

- Host-side: `~/.nim/cache/llama-3.1-8b-instruct/` (700 perms, bind-mounted)
- Container-side: `/opt/nim/.cache/ngc/hub/models--nim--meta--llama-3.1-8b-instruct-dgx-spark/blobs/`
- Hash-named blobs (content-addressed, HuggingFace-style); filenames like `config.json`, `tokenizer_config.json`, `model.safetensors.index.json` get resolved symlinks at the cache top-level.

First-run model-weights pull is happening now. Subsequent runs should skip this and go straight to engine init.

## Spark-quirks noted

- `nvidia-smi --query-gpu=memory.*` returns `[N/A]` on GB10 — unified memory is OS-managed, not driver-reported. Container startup log shows `current utilization: N/A%` for the same reason.
- The "DGX Spark" variant of this NIM has a **different NGC path** from the generic one (`nim/meta/llama-3.1-8b-instruct-dgx-spark` vs. `nim/meta/llama-3.1-8b-instruct`) — NVIDIA ships distinct build recipes for Spark, not a shared image with an aarch64 manifest.
