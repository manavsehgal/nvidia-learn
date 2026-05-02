---
arxiv_id: 2604.27251
title: "Compliance versus Sensibility: On the Reasoning Controllability in Large Language Models"
published: 2026-04-28
hf_upvotes: 5
popularity_score: 14
suggested_stage: inference
suggested_series: LLM Wiki
fast_verdict: spark-feasible
relevance_score: 0.55
has_deep_eval: false
promoted_to: null
abs_url: https://arxiv.org/abs/2604.27251
pdf_url: https://arxiv.org/pdf/2604.27251
hf_paper_url: https://huggingface.co/papers/2604.27251
---

# Compliance versus Sensibility: On the Reasoning Controllability in Large Language Models

**Verdict:** spark-feasible · **Series:** LLM Wiki · **Stage:** inference · **Relevance:** 0.55 · **Popularity:** 14/100

> Behavioral study of induction/deduction/abduction conflicts in LLMs is a pure-inference replication runnable against any NIM-hosted model.

## Abstract

Large Language Models (LLMs) are known to acquire reasoning capabilities through shared inference patterns in pre-training data, which are further elicited via Chain-of-Thought (CoT) practices. However, whether fundamental reasoning patterns, such as induction, deduction, and abduction, can be decoupled from specific problem instances remains a critical challenge for model controllability, and for shedding light on reasoning controllability. In this paper, we present the first systematic investigation of this problem through the lens of reasoning conflicts: an explicit tension between parametric and contextual information induced by mandating logical schemata that deviate from those expected for a target task. Our evaluation reveals that LLMs consistently prioritize sensibility over compliance, favoring task-appropriate reasoning patterns despite conflicting instructions. Notably, task accuracy is not strictly determined by sensibility, with models often maintaining high performance even when using conflicting patterns, suggesting a reliance on internalized parametric memory that increases with model size. We further demonstrate that reasoning conflicts are internally detectable, as confidence scores significantly drop during conflicting episodes. Probing experiments confirm that reasoning types are linearly encoded from middle-to-late layers, indicating the potential for activation-level controllability. Leveraging these insights, we steer models towards compliance, increasing instruction following by up to 29%. Overall, our findings establish that while LLM reasoning is anchored to concrete instances, active mechanistic interventions can effectively decouple logical schemata from data, offering a path toward improved controllability, faithfulness, and generalizability.

## Why this matters for ai-field-notes

- **Topic tags:** reasoning, decoding, evals
- **NVIDIA stack:** NIM
- **Fast verdict rationale:** Behavioral study of induction/deduction/abduction conflicts in LLMs is a pure-inference replication runnable against any NIM-hosted model.

## Repos

_No public repo yet._

## Citations

_not yet indexed_

## Links

- [arXiv abstract](https://arxiv.org/abs/2604.27251)
- [PDF](https://arxiv.org/pdf/2604.27251)
- [HuggingFace daily papers](https://huggingface.co/papers/2604.27251)
