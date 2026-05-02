---
arxiv_id: 2604.26951
title: "Turning the TIDE: Cross-Architecture Distillation for Diffusion Large Language Models"
published: 2026-04-28
hf_upvotes: 40
popularity_score: 29
suggested_stage: fine-tuning
suggested_series: Frontier Scout
fast_verdict: borderline
relevance_score: 0.62
has_deep_eval: false
promoted_to: null
abs_url: https://arxiv.org/abs/2604.26951
pdf_url: https://arxiv.org/pdf/2604.26951
hf_paper_url: https://huggingface.co/papers/2604.26951
---

# Turning the TIDE: Cross-Architecture Distillation for Diffusion Large Language Models

**Verdict:** borderline · **Series:** Frontier Scout · **Stage:** fine-tuning · **Relevance:** 0.62 · **Popularity:** 29/100

> 8B dense and 16B MoE teachers distilling into 0.6B student fits the 128 GB envelope, but full TIDE training pipeline is heavy and dLLM tooling on NeMo is unproven.

## Abstract

Diffusion large language models (dLLMs) offer parallel decoding and bidirectional context, but state-of-the-art dLLMs require billions of parameters for competitive performance. While existing distillation methods for dLLMs reduce inference steps within a single architecture, none address cross-architecture knowledge transfer, in which the teacher and student differ in architecture, attention mechanism, and tokenizer. We present TIDE, the first framework for cross-architecture dLLM distillation, comprising three modular components: (1) TIDAL, which jointly modulates distillation strength across training progress and diffusion timestep to account for the teacher's noise-dependent reliability; (2) CompDemo, which enriches the teacher's context via complementary mask splitting to improve predictions under heavy masking; and (3) Reverse CALM, a cross-tokenizer objective that inverts chunk-level likelihood matching, yielding bounded gradients and dual-end noise filtering. Distilling 8B dense and 16B MoE teachers into a 0.6B student via two heterogeneous pipelines outperforms the baseline by an average of 1.53 points across eight benchmarks, yielding notable gains in code generation, where HumanEval scores reach 48.78 compared to 32.3 for the AR baseline.

## Why this matters for ai-field-notes

- **Topic tags:** distillation, diffusion-llm, cross-architecture, tokenizer, moe, knowledge-transfer
- **NVIDIA stack:** NeMo, TRT-LLM
- **Fast verdict rationale:** 8B dense and 16B MoE teachers distilling into 0.6B student fits the 128 GB envelope, but full TIDE training pipeline is heavy and dLLM tooling on NeMo is unproven.

## Repos

_No public repo yet._

## Citations

_not yet indexed_

## Links

- [arXiv abstract](https://arxiv.org/abs/2604.26951)
- [PDF](https://arxiv.org/pdf/2604.26951)
- [HuggingFace daily papers](https://huggingface.co/papers/2604.26951)
