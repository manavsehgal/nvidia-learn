---
arxiv_id: 2604.27083
title: Co-Evolving Policy Distillation
published: 2026-04-28
hf_upvotes: 35
popularity_score: 28
suggested_stage: fine-tuning
suggested_series: Frontier Scout
fast_verdict: borderline
relevance_score: 0.55
has_deep_eval: false
promoted_to: null
abs_url: https://arxiv.org/abs/2604.27083
pdf_url: https://arxiv.org/pdf/2604.27083
hf_paper_url: https://huggingface.co/papers/2604.27083
---

# Co-Evolving Policy Distillation

**Verdict:** borderline · **Series:** Frontier Scout · **Stage:** fine-tuning · **Relevance:** 0.55 · **Popularity:** 28/100

> Co-evolving multiple experts in parallel during RLVR is memory-heavy; whether it fits the 128 GB unified pool depends on expert sizes.

## Abstract

RLVR and OPD have become standard paradigms for post-training. We provide a unified analysis of these two paradigms in consolidating multiple expert capabilities into a single model, identifying capability loss in different ways: mixed RLVR suffers from inter-capability divergence cost, while the pipeline of first training experts and then performing OPD, though avoiding divergence, fails to fully absorb teacher capabilities due to large behavioral pattern gaps between teacher and student. We propose Co-Evolving Policy Distillation (CoPD), which encourages parallel training of experts and introduces OPD during each expert's ongoing RLVR training rather than after complete expert training, with experts serving as mutual teachers (making OPD bidirectional) to co-evolve. This enables more consistent behavioral patterns among experts while maintaining sufficient complementary knowledge throughout. Experiments validate that CoPD achieves all-in-one integration of text, image, and video reasoning capabilities, significantly outperforming strong baselines such as mixed RLVR and MOPD, and even surpassing domain-specific experts. The model parallel training pattern offered by CoPD may inspire a novel training scaling paradigm.

## Why this matters for ai-field-notes

- **Topic tags:** distillation, rlvr, rl, multimodal
- **NVIDIA stack:** NeMo
- **Fast verdict rationale:** Co-evolving multiple experts in parallel during RLVR is memory-heavy; whether it fits the 128 GB unified pool depends on expert sizes.

## Repos

_No public repo yet._

## Citations

_not yet indexed_

## Links

- [arXiv abstract](https://arxiv.org/abs/2604.27083)
- [PDF](https://arxiv.org/pdf/2604.27083)
- [HuggingFace daily papers](https://huggingface.co/papers/2604.27083)
