---
arxiv_id: 2604.25719
title: Step-Audio-R1.5 Technical Report
published: 2026-04-27
hf_upvotes: 13
popularity_score: 20
suggested_stage: fine-tuning
suggested_series: Frontier Scout
fast_verdict: borderline
relevance_score: 0.55
has_deep_eval: false
promoted_to: null
abs_url: https://arxiv.org/abs/2604.25719
pdf_url: https://arxiv.org/pdf/2604.25719
hf_paper_url: https://huggingface.co/papers/2604.25719
---

# Step-Audio-R1.5 Technical Report

**Verdict:** borderline · **Series:** Frontier Scout · **Stage:** fine-tuning · **Relevance:** 0.55 · **Popularity:** 20/100

> Audio reasoning post-training fits NeMo's speech surface but RLVR-on-audio at scale is a non-trivial Spark workload.

## Abstract

Recent advancements in large audio language models have extended Chain-of-Thought (CoT) reasoning into the auditory domain, enabling models to tackle increasingly complex acoustic and spoken tasks. To elicit and sustain these extended reasoning chains, the prevailing paradigm -- driven by the success of text-based reasoning models -- overwhelmingly relies on Reinforcement Learning with Verified Rewards (RLVR). However, as models are strictly optimized to distill rich, continuous auditory contexts into isolated, verifiable text labels, a fundamental question arises: are we fostering true audio intelligence, or merely reducing a continuous sensory medium into a discrete puzzle? We identify this as the "verifiable reward trap." While RLVR yields remarkable scores on standardized objective benchmarks, it systematically degrades the real-world conversational feel of audio models. By prioritizing isolated correctness over acoustic nuance, RLVR reduces dynamic interactions to mechanical "answering machines," severely compromising prosodic naturalness, emotional continuity, and user immersion, particularly in long-turn dialogues. To bridge the gap between mechanical objective verification and genuine sensory empathy, we introduce Step-Audio-R1.5, marking a paradigm shift toward Reinforcement Learning from Human Feedback (RLHF) in audio reasoning. Comprehensive evaluations demonstrate that Step-Audio-R1.5 not only maintains robust analytical reasoning but profoundly transforms the interactive experience, redefining the boundaries of deeply immersive long-turn spoken dialogue.

## Why this matters for ai-field-notes

- **Topic tags:** multimodal, rlvr, evals
- **NVIDIA stack:** NeMo, NIM
- **Fast verdict rationale:** Audio reasoning post-training fits NeMo's speech surface but RLVR-on-audio at scale is a non-trivial Spark workload.

## Repos

_No public repo yet._

## Citations

`citations: 0`

## Links

- [arXiv abstract](https://arxiv.org/abs/2604.25719)
- [PDF](https://arxiv.org/pdf/2604.25719)
- [HuggingFace daily papers](https://huggingface.co/papers/2604.25719)
