---
arxiv_id: 2604.27419
title: "InteractWeb-Bench: Can Multimodal Agent Escape Blind Execution in Interactive Website Generation?"
published: 2026-04-29
hf_upvotes: 9
popularity_score: 18
suggested_stage: agentic
suggested_series: Autoresearch
fast_verdict: spark-feasible
relevance_score: 0.65
has_deep_eval: false
promoted_to: null
abs_url: https://arxiv.org/abs/2604.27419
pdf_url: https://arxiv.org/pdf/2604.27419
hf_paper_url: https://huggingface.co/papers/2604.27419
---

# InteractWeb-Bench: Can Multimodal Agent Escape Blind Execution in Interactive Website Generation?

**Verdict:** spark-feasible · **Series:** Autoresearch · **Stage:** agentic · **Relevance:** 0.65 · **Popularity:** 18/100

> Multimodal agent benchmark with persona-driven instructions runs on Spark via NemoClaw + NIM-served MLLMs without training.

## Abstract

With the advancement of multimodal large language models (MLLMs) and coding agents, the website development has shifted from manual programming to agent-based project-level code synthesis. Existing benchmarks rely on idealized assumptions, especially for well-structured, information-rich inputs and static execution settings. In contrast, real-world development is constrained by a critical bottleneck: the semantic misalignment between ambiguous, low-quality instructions from non-expert users and model understanding, which results in a failure mode that we term blind execution. To address this gap, we introduce InteractWeb-Bench, the first multimodal interactive benchmark for website generation under non-expert low-code user conditions. InteractWeb-Bench introduces four types of user agents and persona-driven instruction perturbations to systematically simulate diverse user behaviors, including ambiguity, redundancy, and contradiction, grounded in requirement engineering defect taxonomies. We develop an interactive execution environment for agents, featuring a unified action space comprising Clarify, Implement, Verify, and Submit, enabling iterative intent refinement, code synthesis, and visual feedback-based validation. Extensive experiments and analysis reveal that frontier MLLM-based agents remain trapped in blind execution, exposing limitations in intent recognition and adaptive interaction.

## Why this matters for ai-field-notes

- **Topic tags:** agentic, multimodal, evals, tool-use
- **NVIDIA stack:** NemoClaw, NIM, Guardrails
- **Fast verdict rationale:** Multimodal agent benchmark with persona-driven instructions runs on Spark via NemoClaw + NIM-served MLLMs without training.

## Repos

_No public repo yet._

## Citations

_not yet indexed_

## Links

- [arXiv abstract](https://arxiv.org/abs/2604.27419)
- [PDF](https://arxiv.org/pdf/2604.27419)
- [HuggingFace daily papers](https://huggingface.co/papers/2604.27419)
