---
arxiv_id: 2604.26779
title: Accelerating RL Post-Training Rollouts via System-Integrated Speculative Decoding
published: 2026-04-28
hf_upvotes: 6
popularity_score: 15
suggested_stage: training
suggested_series: LLM Wiki
fast_verdict: spark-feasible
relevance_score: 0.85
has_deep_eval: false
promoted_to: null
abs_url: https://arxiv.org/abs/2604.26779
pdf_url: https://arxiv.org/pdf/2604.26779
hf_paper_url: https://huggingface.co/papers/2604.26779
---

# Accelerating RL Post-Training Rollouts via System-Integrated Speculative Decoding

**Verdict:** spark-feasible · **Series:** LLM Wiki · **Stage:** training · **Relevance:** 0.85 · **Popularity:** 15/100

> Speculative decoding inside NeMo-RL with vLLM at 8B scale is exactly Spark-class — 8B target + small draft model fit comfortably in 128 GB.

## Abstract

RL post-training of frontier language models is increasingly bottlenecked by autoregressive rollout generation, making rollout acceleration a central systems challenge. Many existing efficiency methods improve throughput by changing the rollout or optimization regime, for example, through off-policy execution, replay, or lower-precision generation. We study speculative decoding as a lossless acceleration primitive for RL rollouts that preserves the target model's output distribution. We implement speculative decoding in NeMo-RL with a vLLM backend, supporting both synchronous and asynchronous pipelines and enabling speculation during RL rollouts. This benefit is realizable across speculation mechanisms, such as pretrained MTP heads, small external draft models or even techniques such as Eagle3, which are traditionally applied after RL phase. This yields a deployment path for state-of-the-art speculative decoding inside RL training. In a reasoning post-training workload at 8B scale under synchronous RL, speculative decoding improves rollout throughput by 1.8x. Using a high-fidelity performance simulator, we project that combining speculative decoding with asynchronous RL yields up to 2.5x end-to-end training speedup at 235B scale.

## Why this matters for ai-field-notes

- **Topic tags:** rlvr, rl, kv-cache, fine-tuning, nemo
- **NVIDIA stack:** NeMo, NIM
- **Fast verdict rationale:** Speculative decoding inside NeMo-RL with vLLM at 8B scale is exactly Spark-class — 8B target + small draft model fit comfortably in 128 GB.

## Repos

_No public repo yet._

## Citations

_not yet indexed_

## Links

- [arXiv abstract](https://arxiv.org/abs/2604.26779)
- [PDF](https://arxiv.org/pdf/2604.26779)
- [HuggingFace daily papers](https://huggingface.co/papers/2604.26779)
