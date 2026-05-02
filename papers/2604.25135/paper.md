---
arxiv_id: 2604.25135
title: "FAMA: Failure-Aware Meta-Agentic Framework for Open-Source LLMs in Interactive Tool Use Environments"
published: 2026-04-27
hf_upvotes: 8
popularity_score: 17
suggested_stage: agentic
suggested_series: Autoresearch
fast_verdict: spark-feasible
relevance_score: 0.72
has_deep_eval: false
promoted_to: null
abs_url: https://arxiv.org/abs/2604.25135
pdf_url: https://arxiv.org/pdf/2604.25135
hf_paper_url: https://huggingface.co/papers/2604.25135
---

# FAMA: Failure-Aware Meta-Agentic Framework for Open-Source LLMs in Interactive Tool Use Environments

**Verdict:** spark-feasible · **Series:** Autoresearch · **Stage:** agentic · **Relevance:** 0.72 · **Popularity:** 17/100

> Failure-trajectory analysis + targeted helper agents over open-source LLMs runs cleanly atop NemoClaw with a Spark-hosted Nemotron.

## Abstract

Large Language Models are being increasingly deployed as the decision-making core of autonomous agents capable of effecting change in external environments. Yet, in conversational benchmarks, which simulate real-world customer-centric issue resolution scenarios, these agents frequently fail due to the cascading effects of incorrect decision-making. These challenges are particularly pronounced for open-source LLMs with smaller parameter sizes, limited context windows, and constrained inference budgets, which contribute to increased error accumulation in agentic settings. To tackle these challenges, we present the Failure-Aware Meta-Agentic (FAMA) framework. FAMA operates in two stages: first, it analyzes failure trajectories from baseline agents to identify the most prevalent errors; second, it employs an orchestration mechanism that activates a minimal subset of specialized agents tailored to address these failures by injecting a targeted context for the tool-use agent before the decision-making step. Experiments across open-source LLMs demonstrate performance gains up to 27% across evaluation modes over standard baselines. These results highlight that targeted curation of context through specialized agents to address common failures is a valuable design principle for building reliable, multi-turn tool-use LLM agents that simulate real-world conversational scenarios.

## Why this matters for ai-field-notes

- **Topic tags:** agentic, tool-use, observability, evals
- **NVIDIA stack:** NemoClaw, NIM, Guardrails
- **Fast verdict rationale:** Failure-trajectory analysis + targeted helper agents over open-source LLMs runs cleanly atop NemoClaw with a Spark-hosted Nemotron.

## Repos

_No public repo yet._

## Citations

_not yet indexed_

## Links

- [arXiv abstract](https://arxiv.org/abs/2604.25135)
- [PDF](https://arxiv.org/pdf/2604.25135)
- [HuggingFace daily papers](https://huggingface.co/papers/2604.25135)
