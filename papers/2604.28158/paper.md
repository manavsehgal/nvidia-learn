---
arxiv_id: 2604.28158
title: "Intern-Atlas: A Methodological Evolution Graph as Research Infrastructure for AI Scientists"
published: 2026-04-29
primary_category: cs.AI
hf_upvotes: 13
popularity_score: 21
suggested_stage: agentic
suggested_series: Autoresearch
fast_verdict: spark-feasible
relevance_score: 0.75
has_deep_eval: false
promoted_to: null
abs_url: https://arxiv.org/abs/2604.28158
pdf_url: https://arxiv.org/pdf/2604.28158
hf_paper_url: https://huggingface.co/papers/2604.28158
---

# Intern-Atlas: A Methodological Evolution Graph as Research Infrastructure for AI Scientists

**Verdict:** spark-feasible · **Series:** Autoresearch · **Stage:** agentic · **Relevance:** 0.75 · **Popularity:** 21/100

> Method-evolution graph extraction is an LLM-over-corpus pipeline that maps directly onto NIM + NeMo Retriever + pgvector on Spark, on a subset.

## Abstract

Existing research infrastructure is fundamentally document-centric, providing citation links between papers but lacking explicit representations of methodological evolution. In particular, it does not capture the structured relationships that explain how and why research methods emerge, adapt, and build upon one another. With the rise of AI-driven research agents as a new class of consumers of scientific knowledge, this limitation becomes increasingly consequential, as such agents cannot reliably reconstruct method evolution topologies from unstructured text. We introduce Intern-Atlas, a methodological evolution graph that automatically identifies method-level entities, infers lineage relationships among methodologies, and captures the bottlenecks that drive transitions between successive innovations. Built from 1,030,314 papers spanning AI conferences, journals, and arXiv preprints, the resulting graph comprises 9,410,201 semantically typed edges, each grounded in verbatim source evidence, forming a queryable causal network of methodological development. To operationalize this structure, we further propose a self-guided temporal tree search algorithm for constructing evolution chains that trace the progression of methods over time. We evaluate the quality of the resulting graph against expert-curated ground-truth evolution chains and observe strong alignment. In addition, we demonstrate that Intern-Atlas enables downstream applications in idea evaluation and automated idea generation. We position methodological evolution graphs as a foundational data layer for the emerging automated scientific discovery.

## Why this matters for ai-field-notes

- **Topic tags:** agentic, rag, retrieval, knowledge-graph
- **NVIDIA stack:** NIM, NeMo Retriever, pgvector, NemoClaw
- **Fast verdict rationale:** Method-evolution graph extraction is an LLM-over-corpus pipeline that maps directly onto NIM + NeMo Retriever + pgvector on Spark, on a subset.

## Repos

_No public repo yet._

## Citations

`citations: 0`

## Links

- [arXiv abstract](https://arxiv.org/abs/2604.28158)
- [PDF](https://arxiv.org/pdf/2604.28158)
- [HuggingFace daily papers](https://huggingface.co/papers/2604.28158)
