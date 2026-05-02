---
arxiv_id: 2604.27039
title: "Length Value Model: Scalable Value Pretraining for Token-Level Length Modeling"
published: 2026-04-28
hf_upvotes: 16
popularity_score: 22
suggested_stage: inference
suggested_series: LLM Wiki
fast_verdict: spark-feasible
relevance_score: 0.7
has_deep_eval: false
promoted_to: null
abs_url: https://arxiv.org/abs/2604.27039
pdf_url: https://arxiv.org/pdf/2604.27039
hf_paper_url: https://huggingface.co/papers/2604.27039
---

# Length Value Model: Scalable Value Pretraining for Token-Level Length Modeling

**Verdict:** spark-feasible · **Series:** LLM Wiki · **Stage:** inference · **Relevance:** 0.7 · **Popularity:** 22/100

> Token-level length value head over a 7B model is a small auxiliary network atop standard inference — comfortably inside Spark's envelope.

## Abstract

Token serves as the fundamental unit of computation in modern autoregressive models, and generation length directly influences both inference cost and reasoning performance. Despite its importance, existing approaches lack fine-grained length modeling, operating primarily at the coarse-grained sequence level. We introduce the Length Value Model (LenVM), a token-level framework that models the remaining generation length. By formulating length modeling as a value estimation problem and assigning a constant negative reward to each generated token, LenVM predicts a bounded, discounted return that serves as a monotone proxy for the remaining generation horizon. This formulation yields supervision that is annotation-free, dense, unbiased, and scalable. Experiments on LLMs and VLMs demonstrate LenVM provides a highly effective signal at inference time. On the LIFEBench exact length matching task, applying LenVM to a 7B model improves the length score from 30.9 to 64.8, significantly outperforming frontier closed-source models. Furthermore, LenVM enables continuous control over the trade off between performance and efficiency. On GSM8K at a budget of 200 tokens, LenVM maintains 63% accuracy compared to 6 percent for token budget baseline. It also accurately predicts total generation length from the prompt boundary. Finally, LenVM's token-level values offer an interpretable view of generation dynamics, revealing how specific tokens shift reasoning toward shorter or longer regimes. Results demonstrate that LenVM supports a broad range of applications and token length can be effectively modeled as a token-level value signal, highlighting the potential of LenVM as a general framework for length modeling and as a length-specific value signal that could support future RL training. Code is available at https://github.com/eric-ai-lab/Length-Value-Model.

## Why this matters for ai-field-notes

- **Topic tags:** decoding, sampling, rl, multimodal
- **NVIDIA stack:** NIM, NeMo
- **Fast verdict rationale:** Token-level length value head over a 7B model is a small auxiliary network atop standard inference — comfortably inside Spark's envelope.

## Repos

_No public repo yet._

## Citations

_not yet indexed_

## Links

- [arXiv abstract](https://arxiv.org/abs/2604.27039)
- [PDF](https://arxiv.org/pdf/2604.27039)
- [HuggingFace daily papers](https://huggingface.co/papers/2604.27039)
