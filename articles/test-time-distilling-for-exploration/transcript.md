# Provenance: test-time-distilling-for-exploration

Promoted from Frontier Scout on 2026-05-02 (see `evidence/feasibility-eval.md`).
Drafted into `article.md` on 2026-05-02 in the same session that landed
[autoresearchbench-on-spark](/articles/autoresearchbench-on-spark/).

## Source material

- **Paper**: arXiv:2604.24927 — *Large Language Models Explore by Latent
  Distilling*. PDF at `evidence/paper.pdf` (6.6 MB).
- **Repository**: [LinesHogan/tLLM](https://github.com/LinesHogan/tLLM)
  shallow clone at `evidence/repo-snapshot/`. Top-level layout: `tllm/`
  (the runtime package), `starter.py` (the documented quickstart),
  `doc/` (English) + `doc_zh/` (Chinese), `test/`. README pinned the
  validated environment to `vllm==0.10.x`; the install on Spark
  resolved to `vllm==0.20.0`.
- **Frontier Scout eval**: `evidence/feasibility-eval.md` (immutable). Verdict:
  spark-feasible — Qwen/Llama 7–8B + a ~1 GB Distiller fit inside 20 GB of
  the 128 GB pool. Predicted blocker that turned out to be the load-bearing
  one: *vLLM is not a verified Spark inference path*.

## Spark-side install transcript

The install ran in `nvcr.io/nvidia/pytorch:25.11-py3` started in long-lived
mode with the tLLM repo snapshot bind-mounted read-only at `/tllm`:

```bash
docker run -d --name tllm-build --gpus all --ipc=host \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  -v /tmp/tllm-spark:/work \
  -v /home/nvidia/ai-field-notes/articles/test-time-distilling-for-exploration/evidence/repo-snapshot:/tllm:ro \
  nvcr.io/nvidia/pytorch:25.11-py3 sleep infinity
```

Container baseline before any installs:

```text
torch 2.10.0a0+b558c986e8.nv25.11
cuda  13.0
device  NVIDIA GB10
sm    (12, 1)
```

`pip install vllm` resolved to `vllm-0.20.0`. The install replaced the
container's nightly torch with the open-source `torch-2.11.0+cu130`,
pulled `flashinfer-cubin-0.6.8.post1`, the full CUDA-13 user-space stack
(`nvidia-cublas-13.1.0.3`, `nvidia-cudnn-cu13-9.19.0.56`,
`nvidia-cusparselt-cu13-0.8.0`, `nvidia-nccl-cu13-2.28.9`,
`nvidia-nvshmem-cu13-3.4.5`), and a long tail of OSS deps. The build
walked through `fastsafetensors` source compilation; total wall ~14 minutes.

Post-install verification:

```text
torch 2.11.0+cu130
cuda  13.0
avail True
device  NVIDIA GB10
sm    (12, 1)
vllm  0.20.0
```

The validated tLLM environment is `vllm==0.10.x` per the repo's
`doc/getting-started/installation.md`. The article's first measurement was
whether the install resolves at all on the Spark's torch+CUDA+SM triple;
the second is whether tLLM's runtime hooks bind into the v1-engine surface
that has churned across 0.10 → 0.20.

## Evidence map

- `evidence/paper.pdf` — arxiv PDF
- `evidence/paper-meta.json` — papers.json entry (popularity 31/100, 59 HF upvotes)
- `evidence/feasibility-eval.md` — Frontier Scout deep eval
- `evidence/spark-recipe.md` — recipe sketch from the eval
- `evidence/repo-snapshot/` — tLLM clone
- `evidence/repro-on-spark.md` — Spark-side install + run log (this session)
- `scripts/run_esamp_bench.py` — fieldkit.eval.Bench harness scaffold for
  the throughput-comparison loop (referenced in the article's Journey
  section; the executable next-step is the AIME/HumanEval Pass@k follow-up)

## Patched-starter retry + second drift

After patching the sampler signature locally (one-line change at
`tllm/runtime/vllm_patch/sampler_patch.py:181` to thread
`sampling_metadata.all_random` as the third argument to
`Sampler.apply_temperature`), the starter retried as:

```bash
cd /tmp/tllm-rw && timeout 600 python3 starter.py \
  --model-name Qwen/Qwen2.5-0.5B-Instruct \
  --max-new-tokens 16 --num-answers 4 \
  --gpu-memory-utilization 0.4 --max-model-len 256
```

This run cleared engine init: KV cache 3,894,336 tokens, FlashInfer
autotune in 60 ms, 51 PIECEWISE + 35 FULL CUDA graphs captured in
3 seconds, `init engine took 82.18 s (compilation: 5.15 s)`. The first
`execute_model` then died inside tLLM's wrapper at
`tllm/runtime/vllm_patch/port_runtime_hooks.py:511`:

```text
TypeError: _wrapped_prepare_inputs() takes 2 positional arguments but 3 were given
```

vLLM 0.20.0 added a required `num_scheduled_tokens: numpy.ndarray`
argument to `GPUModelRunner._prepare_inputs`; tLLM's wrapper was written
against the 0.10.x signature. Fix is multi-line — wrapper accepts the
new argument keyword-only, the adapter call unpacking the prepare-inputs
output threads it through, and downstream consumer bundle assembly does
not break — and is the work the next session picks up (or that the
tLLM upstream lands first).

Both run logs live at `evidence/runs/`:

- `starter-qwen-0.5b-vllm-0.20.log` — first failure (sampler signature)
- `starter-qwen-0.5b-vllm-0.20-patch1.log` — second failure (prepare_inputs signature) after the one-line sampler patch

## Open follow-ups (the next article in the series)

- AIME and HumanEval Pass@k verifier loops, n=8 samples per task, baseline
  vs ESamp, on Qwen 2.5 7B and DeepSeek-R1-Distill-Qwen-7B.
- Distiller-beta sweep on a single AIME problem to map the sample-spread
  vs Pass@k tradeoff at fixed n.
- Semantic-diversity measurement via `nemotron-embed-1b-v2` cosine matrix
  on the n samples per problem.
- A `fieldkit.inference.VLLMClient` proposal — captured in this article's
  Tradeoffs section and to be filed in `fieldkit/CHANGELOG.md` under
  `[Unreleased]` after the next session.
- A `fieldkit.eval.PassAtK` proposal — same destination.

## Privacy + security pass

No credentials, PII, or system fingerprinting in any committed file.
Container hostnames (`tllm-build`) are generic. Repo paths (`/home/nvidia/...`)
appear in the install transcript as the bind-mount source — same convention
as prior articles in this repo, no new surface.
