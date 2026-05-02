---
arxiv_id: 2604.28181
title: Synthetic Computers at Scale for Long-Horizon Productivity Simulation
published: 2026-04-29
primary_category: cs.AI
hf_upvotes: 9
popularity_score: 18
suggested_stage: agentic
suggested_series: Autoresearch
fast_verdict: spark-feasible
relevance_score: 0.78
has_deep_eval: false
promoted_to: null
abs_url: https://arxiv.org/abs/2604.28181
pdf_url: https://arxiv.org/pdf/2604.28181
hf_paper_url: https://huggingface.co/papers/2604.28181
---

# Synthetic Computers at Scale for Long-Horizon Productivity Simulation

**Verdict:** spark-feasible · **Series:** Autoresearch · **Stage:** agentic · **Relevance:** 0.78 · **Popularity:** 18/100

> Synthetic-computer long-horizon agent sims map directly onto OpenShell sandboxes inside NemoClaw, with NIM-hosted Nemotron driving the loop.

## Abstract

Realistic long-horizon productivity work is strongly conditioned on user-specific computer environments, where much of the work context is stored and organized through directory structures and content-rich artifacts. To scale synthetic data creation for such productivity scenarios, we introduce Synthetic Computers at Scale, a scalable methodology for creating such environments with realistic folder hierarchies and content-rich artifacts (e.g., documents, spreadsheets, and presentations). Conditioned on each synthetic computer, we run long-horizon simulations: one agent creates productivity objectives that are specific to the computer's user and require multiple professional deliverables and about a month of human work; another agent then acts as that user and keeps working across the computer -- for example, navigating the filesystem for grounding, coordinating with simulated collaborators, and producing professional artifacts -- until these objectives are completed.
  In preliminary experiments, we create 1,000 synthetic computers and run long-horizon simulations on them; each run requires over 8 hours of agent runtime and spans more than 2,000 turns on average. These simulations produce rich experiential learning signals, whose effectiveness is validated by significant improvements in agent performance on both in-domain and out-of-domain productivity evaluations. Given that personas are abundant at billion scale, this methodology can in principle scale to millions or even billions of synthetic user worlds with sufficient compute, enabling broader coverage of diverse professions, roles, contexts, environments, and productivity needs. We argue that scalable synthetic computer creation, together with at-scale simulations, is highly promising as a foundational substrate for agent self-improvement and agentic reinforcement learning in long-horizon productivity scenarios.

## Why this matters for ai-field-notes

- **Topic tags:** agentic, sandboxing, evals
- **NVIDIA stack:** NemoClaw, OpenClaw, NIM
- **Fast verdict rationale:** Synthetic-computer long-horizon agent sims map directly onto OpenShell sandboxes inside NemoClaw, with NIM-hosted Nemotron driving the loop.

## Repos

_No public repo yet._

## Citations

_not yet indexed_

## Links

- [arXiv abstract](https://arxiv.org/abs/2604.28181)
- [PDF](https://arxiv.org/pdf/2604.28181)
- [HuggingFace daily papers](https://huggingface.co/papers/2604.28181)
