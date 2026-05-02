# Provenance: autoresearchbench-on-spark

Promoted from Frontier Scout on 2026-05-02; authored same day.

- arXiv: 2604.25256 — AutoResearchBench: Benchmarking AI Agents on Complex Scientific Literature Discovery
- Repo: https://github.com/CherYou/AutoResearchBench (29⭐, Apache-2.0, Python+Shell, last push 2026-04-24)
- Dataset: https://huggingface.co/datasets/Lk123/AutoResearchBench
- Frontier Scout fast verdict: spark-feasible
- Frontier Scout deep verdict: spark-feasible
- Fieldkit-fit annotation (2026-05-02): `fieldkit.nim` + `fieldkit.eval` validation candidate

## Source material map

- `evidence/paper.pdf` — arxiv PDF, 3.2 MB
- `evidence/paper-meta.json` — papers.json entry (popularity 26/100, 27 HF upvotes)
- `evidence/feasibility-eval.md` — full Frontier Scout eval (immutable)
- `evidence/spark-recipe.md` — extracted Proposed Spark recipe section as runbook
- `evidence/repo-snapshot/` — shallow clone of CherYou/AutoResearchBench (Apache-2.0)
- `evidence/findings.md` — consolidated Day-1 findings (the article's primary source)
- `evidence/runs/<model>/inference_output.jsonl` — bench output JSONL (gitignored, regenerable)
- `evidence/runs/<model>/inference_output_evaluation.json` — upstream Deep evaluator output
- `evidence/llama-3.1-8b-summary.json` — fieldkit.eval.Bench summary, 8B run
- `evidence/nemotron-nano-9b-v2-summary.json` — fieldkit.eval.Bench summary, 9B-v2 run
- `evidence/comparison.json` — side-by-side from `scripts/compare_runs.py`
- `scripts/analyze_run.py` — wraps `fieldkit.eval.Bench` around the bench's per-question output
- `scripts/compare_runs.py` — N-way comparison of summary JSONs

## Experiment chronology

1. **Plumbing.** Built `/tmp/arb-venv` from `evidence/repo-snapshot/requirements.txt` (qwen-agent 0.0.34, openai 2.33.0, tiktoken 0.12.0). Stood up the chat NIM with `docker start nim-llama31-8b`; waited for `/v1/models` (~96s cold start); smoke-tested `/v1/chat/completions` end-to-end.

2. **8B smoke run (3 Deep questions).** Configured `~/.config/autoresearchbench/.env` (out-of-repo, `chmod 600`) with the bench's NIM-flavored values: `OPENAI_API_BASE=http://localhost:8000/v1`, `MODEL=meta/llama-3.1-8b-instruct`, `SEARCH_TOOL=websearch`, `EVAL_END=3`, `MAX_WORKERS=2`. The web tool's summarizer slot pointed at the same NIM; only the agent-search backend (Serper + Jina) called external APIs. Output: 8m22s wall, 2/3 questions hit `context_length_exceeded` by turn 5–6, 0 candidate papers across all 3.

3. **49B detour (failed).** Attempted to run `nvcr.io/nim/nvidia/llama-3.3-nemotron-super-49b-v1:latest` for a stronger comparison. Container started, then died with `Detected 0 compatible profile(s)` — `list-model-profiles` showed engines for L40s/H100/H200/B200/A100/A100-SXM4 but no GB10 profile. Removed container, returned to drawing board.

4. **Ollama detour (abandoned).** Pulled `llama3.3:70b-instruct-q4_K_M` via Ollama as a non-NIM 70B fallback. Pull throttled at ~9 MB/s, ETA 1h15m. Killed mid-pull when a published Spark-tuned NIM with extended context was found.

5. **Catalog search.** WebSearch'd NVIDIA's published catalog and found `nvcr.io/nim/nvidia/nvidia-nemotron-nano-9b-v2-dgx-spark` — the Spark-curated reasoning NIM, 128K context, NVFP4 quantization on vLLM. Pulled (33 GB image + ~8 GB of model weights into the cache mount, ~16 min total at ~9 MB/s).

6. **9B-v2 smoke run (same 3 Deep questions).** Stopped 8B NIM, launched 9B-v2 with the same `docker run` shape (port 8000, GPU all, shm-size 16g, NGC key, cache mount). After ~3 min engine warm, `/v1/models` returned `id: nvidia/nemotron-nano-9b-v2 | max_model_len: 131072`. Updated `.env` with the new MODEL id and re-ran the same `bash run_inference.sh`. Output: 10m57s wall, 3/3 finished cleanly, 0 candidate papers across all 3 (all explicitly judged `<candidates>None</candidates>` after evaluating 10 web-search results).

7. **Analysis.** `scripts/analyze_run.py` rolled both runs into `fieldkit.eval.Bench` summaries (`evidence/<model>-summary.json`); `scripts/compare_runs.py` produced the side-by-side `evidence/comparison.json`. Per-turn detail (action, duration, papers retrieved, tokens in/out, tool-format errors) captured for each question.

8. **Upstream Deep evaluator.** Ran `bash evaluate/run_evaluate.sh deep` against both inference outputs with the 9B-v2 NIM as judge. Both returned `Accuracy@1: 0.00%` in 0.05 seconds (no judge calls needed since both produced 0 candidates) — formal closure of the bench loop.

## Notable findings worth preserving

**`fieldkit.eval.Bench` absorbed the AutoResearchBench per-question output cleanly.** The same Bench abstraction that aggregated naive-RAG latencies in the bench-rag sample worked unchanged here for agent-bench latencies + per-turn metrics. `summarize_metric` rolled the per-question stats. Drop-in for future agent-bench articles.

**`fieldkit.eval.Trajectory` was the wrong shape.** `Trajectory` is built around the autoresearch arc's scalar-score iterations (val_bpb-style with knob_coverage + repeat_rate). AutoResearchBench's per-turn schema (action, duration, papers_retrieved, tokens_in/out) didn't fit. Worth proposing a `fieldkit.eval.AgentRun` abstraction in v0.2 — same per-question, per-turn shape, with summary methods for action-distribution / retrieval-yield / parse-error rate.

**Tool-format compatibility is a real surface.** Q1 of the 9B-v2 run errored on the first turn with `Failed to parse tool format error: <tool_call>…` because Nemotron-Hybrid's tool-call serialization diverges slightly from what Qwen-Agent's parser expects. Model self-corrected on turn 2. This is a friction point worth a one-off shim if running this stack in a production loop.

**The Spark NIM catalog is curated.** The `-dgx-spark` suffix on the image name is the marker. `list-model-profiles` is the one-line check before pulling a multi-GB image only to find it has no GB10 engine.

**Llama-8B Spark NIM caps `max_model_len` at 8192.** This is a build choice for the smaller end of the GB10 envelope, not a Llama-3.1 model limit. For agent loops with accumulating tool-response context, check `/v1/models` before launching.

## What was scrubbed before publishing

- One NGC API key (`nvapi-…`) — replaced with `<redacted>` in the `docker run` block in the article.
- One Serper API key — embedded only in the out-of-repo `~/.config/autoresearchbench/.env`, never appeared in the article body.
- One Jina API key — same as above.
- The `.env` file itself lives at `~/.config/autoresearchbench/.env` with `chmod 600` and is not in the repo. Verified via `git check-ignore`.

## Files NOT committed (gitignored)

- `evidence/runs/<model>/inference_output.jsonl` (bulky, regenerable from the bench + the NIM)
- `evidence/runs/<model>/inference_output_evaluation.json` (also regenerable)
- The out-of-repo `~/.config/autoresearchbench/.env`

The summary JSONs (`evidence/<model>-summary.json` and `evidence/comparison.json`) are committed because they're small and they're what the article cites.
