<p align="center">
  <a href="https://ainative.business/field-notes/"><img src="public/og-image.png" alt="AI Field Notes — field notes on the DGX Spark" width="100%" /></a>
</p>

<p align="center">
  <a href="https://ainative.business/field-notes/"><b>Live site</b></a>
  &nbsp;·&nbsp;
  <a href="#articles">Articles</a>
  &nbsp;·&nbsp;
  <a href="#at-a-glance">At a glance</a>
  &nbsp;·&nbsp;
  <a href="#run-locally">Run locally</a>
</p>

<sub>Vol. 01 &nbsp;·&nbsp; ai-field-notes &nbsp;·&nbsp; May 2026</sub>

# Field notes on the *DGX Spark*.

> One builder maximising the NVIDIA DGX Spark as a personal AI power user and edge AI rig. Every article is a session transcript turned into a deep-dive essay.

<sub><b>27 articles published</b> &nbsp;·&nbsp; Apache 2.0 &nbsp;·&nbsp; by <a href="https://github.com/manavsehgal">Manav Sehgal</a></sub>

---

## At a glance

| Articles | Words | Lines of code | Models | NVIDIA products |
|:-:|:-:|:-:|:-:|:-:|
| **27** *(+4 upcoming)* | **68,725** | **38,421** | **8** | **11** |

### Stages

| Stage | Published | Upcoming |
|---|:-:|:-:|
| [Foundations](https://ainative.business/field-notes/stage/foundations/) | 11 | — |
| [Training](https://ainative.business/field-notes/stage/training/) | 7 | 1 |
| [Fine-tuning](https://ainative.business/field-notes/stage/fine-tuning/) | 4 | 1 |
| [Inference](https://ainative.business/field-notes/stage/inference/) | 12 | — |
| [Deployment](https://ainative.business/field-notes/stage/deployment/) | 2 | — |
| [Agentic](https://ainative.business/field-notes/stage/agentic/) | 9 | — |
| [Observability](https://ainative.business/field-notes/stage/observability/) | 4 | 1 |
| [Dev-tools](https://ainative.business/field-notes/stage/dev-tools/) | 2 | 1 |

### Products & frameworks

| Product | Articles |
|---|:-:|
| DGX Spark | 26 |
| NVIDIA NIM | 26 |
| NeMo Framework | 20 |
| TensorRT-LLM | 14 |
| pgvector | 12 |
| Triton Inference Server | 10 |
| NeMo Retriever | 10 |
| NemoClaw | 8 |
| Ollama | 4 |
| NeMo Guardrails | 4 |
| OpenClaw | 3 |

### Models

| Model | Articles |
|---|:-:|
| Llama 3.1 8B Instruct | 17 |
| Nemotron Reranker 1B | 6 |
| Nemotron Super 49B | 5 |
| Qwen2.5 3B Instruct | 4 |
| Nemotron Embed 1B v2 | 4 |
| Llama 3.3 70B Instruct | 3 |
| Nemotron Nano 9B v2 | 1 |
| Qwen2.5 7B Instruct | 1 |

---

## Articles

Each article is a deep-dive essay grown from a single session transcript on the Spark. Click through for the full piece on the live site.

### Foundations

- **[Looking Beyond Spark — KV-Cache Arithmetic at Inference](https://ainative.business/field-notes/articles/kv-cache-arithmetic-at-inference/)** — The serving memory bill is not weights. It's KV cache, and KV scales with concurrent users × context length, not parameters. Same four bills as training; different weights. A 70B at 32 users × 16k context wants 168 GB just for KV — and the Spark teaches you the per-token math.
- **[What the Agent Actually Built — Five Articles in Plain English, and Why You Probably Don't Want to Train From Scratch](https://ainative.business/field-notes/articles/what-the-agent-actually-built/)** — Five technical articles in one day built an unattended AI research loop on a desk for $0.02 of electricity. The plain-English readout: what the agent built (not a usable model), what it changes for one person, and a four-tier roadmap from LoRA in minutes to from-scratch in weeks.
- **[Looking Beyond Spark — Fine-Tuning a 100B Nemotron](https://ainative.business/field-notes/articles/gpu-sizing-math-for-fine-tuning/)** — A working answer to: how many GPUs to fine-tune a 100B Nemotron? Three methods, three memory footprints — full FT ≈ 1.6 TB needs 24× H100; LoRA ≈ 250 GB fits 8× H100; QLoRA ≈ 65 GB fits 1× H200. The Spark's 3B LoRA teaches the math.
- **[One Substrate, Three Apps — Where the Foundation Forks](https://ainative.business/field-notes/articles/one-substrate-three-apps/)** — Seven articles installed one stack on the Spark — NIM, Embed, pgvector, RAG glue, reranker, generator A/B, Guardrails. This bridge retells that install as three different answers to one question — corpus plus 128 GB — and walks readers to the top of three tracks.
- **[Access First, Models Second — How I Set Up My DGX Spark for Solo AI Work](https://ainative.business/field-notes/articles/dgx-spark-day-one-access-first/)** — Most DGX Spark walkthroughs open with CUDA and tokens/sec. This one opens with streaming, AI-pair-programming, sandboxed agents, and browser automation — the access layer. For a solo edge builder, that interaction stack is more load-bearing than the model stack.

### Training

- **[Derisking the Cloud Pretrain — How a $5K Spark Saves $50K on H100 Rentals](https://ainative.business/field-notes/articles/derisk-cloud-pretraining-on-the-spark/)** — The Spark is too small for a serious pretrain — but it's the right size for the recipe-search that precedes one. Cull 100 candidate architectures down to 3 on one Spark for ~$1 of electricity, then book the cloud node knowing what to train. The expected savings per campaign run into the thousands.
- **[NeMo Framework on the Spark — What It Earns Over a Hand-Rolled train.py](https://ainative.business/field-notes/articles/nemo-framework-on-spark/)** — Same 354M GPT, same 100 steps, same random tokens — once in a hand-rolled train.py against vanilla PyTorch, once via Megatron-Core inside the NeMo Framework container. Same hardware (GB10, 128 GB unified). The framework earns +5.8% throughput and 30% less GPU memory.
- **[The Data-Path Envelope — When Real Tokens Beat Random Tokens at Pretrain Throughput](https://ainative.business/field-notes/articles/nemo-curator-training-data-prep/)** — Curator-cleaned wikitext-103 (109M tokens, 417 MiB packed) feeding the same 354M GPT pretrain loop from A2. Eight configs swept; data-path overhead is 0.01–0.04% across all of them. New peak: 14,980 tok/s — slightly above A2's random-token ceiling.
- **[The GB10 Pretrain Envelope — Sweeping Batch, Sequence, and Precision on One Spark](https://ainative.business/field-notes/articles/baseline-training-loop-on-spark/)** — Same 354M GPT, same training loop, swept across micro-batch (2,4,8,16), sequence length (1024,2048), and precision (bf16,fp8). 16 configurations, 30 steps each. Peak: 14,266 tokens/sec at batch=16, seq=1024, fp8 — 18% above the hand-rolled PyTorch baseline.
- 🔜 **[Continued Pre-training on a DGX Spark — NeMo Framework Without a Cluster](https://ainative.business/field-notes/articles/nemo-framework-continued-pretraining-on-spark/)** *(planned 2026-05-07)* — When does it make sense to continue pre-training on a single GB10 box, and when is it a category error? A planned run that pushes NeMo Framework, Megatron-LM parallelism, and BF16 mixed precision against the 128 GB unified-memory wall with a small domain corpus.

### Fine-tuning

- **[Distilling the Architect — A 3B LoRA Trained on the Agent's Own Trajectory](https://ainative.business/field-notes/articles/distill-architect-lora-from-trajectories/)** — A4's 50-iter trajectory becomes training data for a Qwen2.5-3B LoRA proposer. Holding out 8 iters, the 3B mode-collapses onto d_model=768 (the trajectory's most-frequent keep) and matches 0 / 8 exact; the 8B at T=0.5 matches 4 / 8 of its own past picks.
- **[LoRA on Your Own Q&A — What 231 Pairs Actually Teach a 3B Model](https://ainative.business/field-notes/articles/lora-on-your-own-qa-pairs/)** — 231 own-voice Q&A pairs, a rank-16 LoRA, 69 s of training on a GB10 Spark. The adapter won't memorize your exact numbers, but it will take a model that refuses 61% of questions about your work and turn it into one that answers all of them in your voice. For facts you still need RAG.
- 🔜 **[LoRA on Nemotron Nano — Fine-tuning a 9B Without Blowing Unified Memory](https://ainative.business/field-notes/articles/lora-fine-tune-nemotron-on-spark/)** *(planned 2026-05-14)* — A planned walk through LoRA fine-tuning on Nemotron Nano 9B with NeMo Customizer: rank and alpha sweeps, a tiny domain corpus, and the memory accounting that keeps a PEFT run from tripping the Spark's 128 GB unified-memory wall.

### Inference

- **[Test-Time Distilling on Spark — Same Compute Envelope, Wider Semantic Reach](https://ainative.business/field-notes/articles/test-time-distilling-for-exploration/)** — ESamp adds a tiny test-time-trained probe to vLLM that converts decoding from lexical resampling into semantic exploration. The runtime is vLLM-native — and that is a Spark catalog-gap story before it is a benchmark.
- **[Hybrid Retrieval on the Spark — BM25, Dense, Fusion, Rerank](https://ainative.business/field-notes/articles/rerank-fusion-retrieval-on-spark/)** — Four retrieval modes on one corpus — naive dense, BM25, Reciprocal Rank Fusion, Nemotron rerank. Dense is already 92% recall@5; rerank adds a point at K=10 and reorders the top. The 8B generator still refuses where retrieval is perfect — grounding, not retrieval, is the new bottleneck.
- **[Where Your Vectors Live — pgvector on a DGX Spark](https://ainative.business/field-notes/articles/pgvector-on-spark/)** — The substrate between the embed call and the retrieve call — pgvector 0.8.2 running as a Postgres 16 container on GB10, with 1000 Nemotron vectors, HNSW and ivfflat both indexed, and a planner that prefers seq scan until you tell it otherwise.
- **[Your First NIM on a DGX Spark — What 24.8 Tokens Per Second Doesn't Tell You](https://ainative.business/field-notes/articles/nim-first-inference-dgx-spark/)** — First-contact notes on NVIDIA's DGX-Spark-specific Llama 3.1 8B NIM. 9.4 GB image, ~108 s warm-cache cold-start, 24.8 tok/s steady, OpenAI-compatible on :8000 — and a confidently wrong Python one-liner that clarifies what small-model FP8 buys and what it costs.
- **[Your Own Semantic Space — a Nemotron Embedding NIM on a DGX Spark](https://ainative.business/field-notes/articles/nemo-retriever-embeddings-local/)** — The embedding endpoint that every downstream RAG, wiki, and agent piece will reuse — a 2048-dim Nemotron Retriever NIM running locally on GB10, ready 52 seconds after docker run and holding 28 docs/s under batched load.
- **[Three Endpoints, One Answer — Naive RAG on a DGX Spark](https://ainative.business/field-notes/articles/naive-rag-on-spark/)** — Three endpoints in one curl chain — a query embeds through Nemotron, pgvector returns top-5 chunks in under 80 ms, and a Llama 3.1 8B NIM stuffs them into a strict-context prompt. The chain works; the 8B generator still refuses on questions its own context answers.
- **[One Rail, Three Policies — NeMo Guardrails on the Retrieval Path](https://ainative.business/field-notes/articles/guardrails-on-the-retrieval-path/)** — NeMo Guardrails drops a policy gate between retrieval and generation. One install, three per-arc configs — PII for Second Brain, style for LLM Wiki, code-safety for Autoresearch — and a 15-query benchmark: 100% block recall, 100% clean pass. Rails are scaffolding; detectors are the content.
- **[Bigger Generator, Same Grounding — 8B vs 49B vs 70B on One Retrieval Chain](https://ainative.business/field-notes/articles/bigger-generator-grounding-on-spark/)** — The rerank-and-fusion article bet that a bigger generator would heal the 8B Google-IPO refusal. Ran the A/B across three sizes on one retrieval chain. Bet lost: Nemotron-Super-49B over-refuses the 8B baseline; Llama 3.3 70B narrows the gap, not closes it. The refusal was the scaffold working.

### Deployment

- **[TensorRT-LLM on the Spark — FP8 Isn't the Reason to Drop NIM. NVFP4 Is.](https://ainative.business/field-notes/articles/trtllm-and-triton-on-spark/)** — Dropping below NIM to raw TensorRT-LLM on a GB10 Spark. FP8 beats NIM's vLLM by 10-15% — barely worth the rebuild. NVFP4 beats it by 76% on decode, 43% on TTFT, and ships a 34%-smaller engine. The reason to drop NIM is the Blackwell-native 4-bit kernel, not FP8.

### Agentic

- **[Guardrails Before the Agent Edits — Code-Edit Policy as a Programmatic Funnel](https://ainative.business/field-notes/articles/guardrails-for-code-generation/)** — Five programmatic rails between the Autoresearch agent's proposal and any mutation of train.py — schema, menu, range, cross-constraint, diff lint. 27 adversarial test cases: block recall 1.0, clean pass 1.0, every rail attribution correct. Zero LLM-as-judge calls.
- **[The Autoresearch Loop — 50 Iterations of an LLM Editing Its Own Trainer Overnight](https://ainative.business/field-notes/articles/autoresearch-agent-loop/)** — NIM Llama 3.1 8B drives a structured-perturbation agent loop against a 354M GPT pretrain. 50 iterations, 73.4 min wall, 0.07 kWh of electricity. 8 keeps, 42 reverts, 0 rail blocks, 0 crashes. Best result: val_bpb 10.8534, +0.93% over baseline at d_model=768.
- **[Second Brain as a Tool — Wrapping the RAG Stack in MCP for Claude Code](https://ainative.business/field-notes/articles/mcp-second-brain-in-claude-code/)** — Closing the Second Brain arc. Four MCP tools wrap the RAG chain — embed, retrieve, optionally rerank, generate — and any Claude Code session anywhere on the box becomes a grounded research client. 200 lines of Python, one launcher, one .mcp.json entry.
- **[The Sandbox Tax That Wasn't — NemoClaw vs OpenClaw on One DGX Spark](https://ainative.business/field-notes/articles/nemoclaw-vs-openclaw-dgx-spark/)** — I ran NemoClaw's sandboxed agent stack and the host Ollama-OpenClaw CLI side by side on one DGX Spark with the same 123B Nemotron model. The sandbox overhead I went looking for is real but modest (~2× raw inference); the real tax is onboarding, and NemoClaw paid it at install time.

### Observability

- **[AutoResearchBench on Spark — Two NIMs, One Bench, Two Failure Modes](https://ainative.business/field-notes/articles/autoresearchbench-on-spark/)** — Two Spark-tuned NIMs run AutoResearchBench's three Deep-Research example questions. Llama-3.1-8B crashes by turn 5-6 on its 8K context; Nemotron-Nano-9B-v2 finishes cleanly at 128K. Both score 0% Accuracy@1 — for completely different reasons.
- **[Was the Agent Researching, or Flailing? An Observability Pass on the Trajectory](https://ainative.business/field-notes/articles/trajectory-eval-is-the-agent-flailing/)** — A8 said the LoRA mode-collapsed because the trajectory was thin. This puts numbers on it: 6 of 13 knobs ever touched, 72% of proposals repeated a prior pair, and the proposer's k=5 history window is the structural cause.
- **[Ragas, Reranked — What 44 Held-Out Questions Say About the Second Brain Stack](https://ainative.business/field-notes/articles/rag-eval-ragas-and-nemo-evaluator/)** — A Ragas-style harness written in 200 lines of stdlib Python, run locally on the DGX Spark, against four variants of the Second Brain RAG chain. Naive RAG scores 3.30 / 5. Rerank RAG scores 4.27. LoRA+RAG is a surprise — it does not beat naive. Retrieval is where the points come from.
- 🔜 **[Watching the GPU — DCGM, Prometheus, and a Local Grafana for the Spark](https://ainative.business/field-notes/articles/spark-gpu-telemetry-prometheus-grafana/)** *(planned 2026-05-28)* — A planned setup of DCGM Exporter → Prometheus → Grafana entirely on the Spark itself. The goal is a single dashboard that tells the truth about GPU memory, SM occupancy, and per-container utilization for a rig that's running NIMs, pgvector, and an occasional training job at the same time.

### Dev-tools

- 🔜 **[Tracing a NIM Request with Nsight Systems — What the 24.8 tok/s Number Hides](https://ainative.business/field-notes/articles/nsight-systems-on-spark/)** *(planned 2026-06-04)* — A planned kernel-level trace of a single NIM inference request on GB10. Where does the wall-clock time actually go — tokenization, KV-cache attention, the sampling loop, memcpy? The article turns 24.8 tokens per second into a timeline you can point at and say 'that line is the bottleneck'.

---

## Run locally

```bash
npm install        # one-time
npm run dev        # dev server: http://localhost:4321/
                   #              http://<spark-lan-ip>:4321/
npm run build      # static build to dist/ (uses /field-notes/ base)
npm run preview    # preview the production build
```

The dev server binds to all interfaces (`server.host: true` in `astro.config.mjs`), so the site is reachable on the LAN or tailnet, not just on the Spark itself.

## Authoring articles

Articles live at `articles/<slug>/article.md`. Each folder also holds `screenshots/`, `transcript.md` (source provenance), and `assets/`.

Voice, structure, frontmatter schema, screenshot workflow, and privacy scrub are handled by the **tech-writer** Claude Code skill — invoke it from inside Claude Code to draft, polish, or publish an article. The skill keeps this README in sync by calling `~/.claude/skills/tech-writer/scripts/refresh_readme.py` whenever an article is created or its frontmatter changes.

## Design

The site is an editorial research-index — dark-first OKLCH palette at hue 250 (indigo-blue accent), **Geist Sans** for display and body, **Geist Mono** for metadata and code. Tokens and component styles live in `src/styles/global.css`.

The **Marked Field** logo is a custom geometric mark: three nodes on an implied 3×3 graph-paper grid with a glowing spark in the bottom-right. See `src/components/Logo.astro`. The favicon, Apple touch icon, and 1200×630 social card live in `public/`.

## License

Apache 2.0 &nbsp;·&nbsp; by [Manav Sehgal](https://github.com/manavsehgal)

<sub>Generated by `~/.claude/skills/tech-writer/scripts/refresh_readme.py` from `src/data/project-stats.json` and per-article frontmatter. Do not hand-edit — rerun the script.</sub>
