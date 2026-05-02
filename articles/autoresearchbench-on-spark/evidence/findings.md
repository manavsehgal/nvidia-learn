# AutoResearchBench on Spark — Day-1 findings

Run date: **2026-05-02**. All numbers from `evidence/runs/<model>/inference_output.jsonl` and `evidence/<model>-summary.json`. Reproduce with `scripts/analyze_run.py` + `scripts/compare_runs.py`.

## Headline

Two NIMs with native DGX Spark engines, same 3 Deep-Research questions from `input_data/academic_deepsearch_example.jsonl`, web-search backend (Serper + Jina, no DeepXiv), summarizer pointed at the same Spark NIM:

| Model | Spark NIM image | max_ctx | status_counts | wall_s mean | turns mean | candidates | Accuracy@1 |
|---|---|---:|---|---:|---:|---:|---:|
| **Llama-3.1-8B-Instruct** | `meta/llama-3.1-8b-instruct-dgx-spark` | **8,192** | 2× context_length_exceeded, 1× finished | 253 | 4.0 | 0 | 0% |
| **Nemotron-Nano-9B-v2** | `nvidia/nvidia-nemotron-nano-9b-v2-dgx-spark` | **131,072** | 3× finished | 363 | 2.3 | 0 | 0% |

Both score 0%, **but the failure modes are unrelated**:

- **8B crashes** by turn 5–6 because tool-response context accumulates past the 8K window. The agent can't even *complete the loop*.
- **9B-v2 completes the loop cleanly**, retrieves 10 papers via web search, evaluates them with explicit chain-of-thought, and correctly judges `<candidates>None</candidates>` because none of the top-10 web-search results actually matches the query. The bottleneck is **retrieval coverage**, not model capability.

## Why this matters

The paper's headline ~9% Deep-Research accuracy was reported with **DeepXiv** (the authors' academic-paper-specialized retrieval API). Our run substitutes generic web search (Serper + Jina) because DeepXiv access wasn't available. With generic web search, no model — frontier or local — can do well on this bench, because the *truth papers don't surface in the top-10 results* for the obfuscated probing questions.

So the headline-level lesson for a Spark power user: **on agent benchmarks, retrieval quality dominates model quality**. Upgrading from 8B to 9B-v2 unlocks the agent loop (no more 8K crashes) but leaves accuracy floored at the retrieval ceiling.

## Per-question detail (9B-v2)

| Q | arxiv | turns | first-turn outcome | input_tokens (max) | total wall |
|---|---|---:|---|---:|---:|
| 1 | 2204.05525 | 3 | tool-format parse error → retry → finish | 4617 | 327.7s |
| 2 | 2011.04709 | 2 | retrieved 10 papers → judged "None" | 12589 | 432.8s |
| 3 | 2011.03802 | 2 | retrieved 10 papers → judged "None" | 11740 | 330.0s |

Q1's first-turn parse error is interesting: the **Nemotron-Hybrid model wraps tool calls in a `<tool_call>` block whose internal format diverges from what the bench's parser expects** (the bench was tuned against Qwen-Agent). Model recovered on turn 2 by emitting valid JSON. This is a model–harness compatibility wrinkle, not a model defect.

Q2 and Q3 each comfortably exceeded the 8B's hard limit (12.5K and 11.7K input tokens — both above 8K) and processed cleanly. The 128K context window is doing exactly the work the bench requires.

## The catalog-gap discovery

Original plan was to compare against Nemotron-Super-49B (NVIDIA's reasoning-tier model with 128K context). The image `nvcr.io/nim/nvidia/llama-3.3-nemotron-super-49b-v1:latest` is on disk (23.4 GB). Launching it produces:

```
ERROR utils.py:52] Could not find a profile that is currently runnable
with the detected hardware. Please check the system information below.
SYSTEM INFO
- Free GPUs:
  -  [2e12:10de] (0) NVIDIA GB10
```

`list-model-profiles` confirmed the image only ships TensorRT-LLM engines for **L40s, H100, H200, B200, A100, A100-SXM4** — no GB10 (Spark) profile. The `-dgx-spark` suffix is the convention NVIDIA uses for Spark-tuned NIMs, and not every published NIM has one.

After hitting this, I went down two paths:
1. **Ollama with `llama3.3:70b-instruct-q4_K_M`** — 43 GB pull at ~9 MB/s ETA 1h15m, killed mid-pull when the better candidate surfaced.
2. **Search NVIDIA's published Spark catalog** — found `nvcr.io/nim/nvidia/nvidia-nemotron-nano-9b-v2-dgx-spark`, which is what we ended up using.

**For Spark power users:** when NIM startup says "0 compatible profiles," the model exists in the catalog but not for your hardware. Look for a `-dgx-spark` variant of the same family before pivoting to Ollama.

## Spark engine internals (from container logs)

The 9B-v2 image runs on **vLLM v0.10.2+d8fcb151.nvmain** (NVIDIA's vLLM fork, not TensorRT-LLM) with **NVFP4 quantization** (`modelopt_fp4`). Profile tag: `vllm-nvfp4-tp1-pp1`. Architecture is **NemotronH** — a hybrid Mamba/state-space + Transformer design (`Hybrid or mamba-based model detected`), which is why a 9B can punch above its weight on reasoning despite the small parameter count. Attention block size is padded to align with mamba page size (1312 tokens vs. mamba 1296).

## Bandwidth note (operator)

Pull throughput averaged ~9 MB/s sustained on Wi-Fi (2.4 GHz, 802.11ax 2×2 MIMO, RX 216→135 Mbit/s degraded mid-session, signal -64 dBm). Wi-Fi peaks ~27 MB/s; the limiter is upstream NGC serving rate / mid-mile. The `enP7s7` wired interface is available but not in use — wired would help future pulls (next article's 49B-Nano-Omni or 120B Super images are 30+ GB).

## fieldkit notes

`fieldkit.eval.Bench` + `summarize_metric` cleanly aggregated per-question latency and metrics (wall_s, turns, candidates) into a fieldkit-style summary. Used for both runs and consumed by `compare_runs.py`.

`fieldkit.eval.Trajectory` is shaped for the autoresearch arc's scalar-score iterations (val_bpb-style loops with knob_coverage and repeat_rate). It's a poor structural fit for the per-turn (action, duration, papers_retrieved, tokens_in/out) shape that AutoResearchBench produces. **Proposed v0.2 addition: `fieldkit.eval.AgentRun`** — a thin abstraction over per-question, per-turn agent-loop telemetry, with summary methods for action-distribution, retrieval-yield, and parse-error rate.

## Files written

- `evidence/runs/llama-3.1-8b/inference_output.jsonl` (gitignored, 3 rows)
- `evidence/runs/nemotron-nano-9b-v2/inference_output.jsonl` (gitignored, 3 rows)
- `evidence/llama-3.1-8b-summary.json` (fieldkit Bench summary)
- `evidence/nemotron-nano-9b-v2-summary.json` (fieldkit Bench summary)
- `evidence/comparison.json` (side-by-side from compare_runs.py)
- `evidence/runs/<model>/inference_output_evaluation.json` (upstream Deep evaluator output)
- `scripts/analyze_run.py`, `scripts/compare_runs.py` (reusable for next model)
