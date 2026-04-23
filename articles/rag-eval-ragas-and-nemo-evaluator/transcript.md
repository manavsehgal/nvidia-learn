# Transcript — rag-eval-ragas-and-nemo-evaluator

Raw command log and working transcript from the Second Brain S3 session.
Date: 2026-04-23. Picks up immediately after S2 (lora-on-your-own-qa-pairs)
shipped at commit 48eb01f.

## Runtime smoke test

```
curl -sf http://localhost:8000/v1/models >/dev/null && echo "LLM NIM up"       # ✓
curl -sf http://localhost:8001/v1/models >/dev/null && echo "Embed NIM up"     # ✓
docker exec pgvector pg_isready -U spark -d vectors                            # ✓
ss -tlnp | grep :4321 >/dev/null && echo "Astro up"                            # ✓
systemctl is-active ollama                                                     # inactive ✓
docker ps --format '{{.Names}}' | grep -q clawnav                              # stopped ✓
```

## Pre-existing state

- `articles/*/article.md` — 16 slugs, 12 `status: published`, 4 `status: upcoming`
- `pgvector.chunks` — 1000 AG-News rows, 1024-dim Nemotron embeddings (F4/F5 build)
- `pgvector.blog_chunks` — did not exist at session start; created here
- S2 eval set at `articles/lora-on-your-own-qa-pairs/evidence/qa-eval.jsonl` — 44 pairs, each with `{question, answer, source (slug), chunk}`

## Ingest

Decision: rebuild a new `blog_chunks` table rather than re-use AG-News. S2 questions reference blog slugs and per-slug chunk indices, so to measure retrieval precision/recall we need the blog itself indexed, using the exact same chunker (900 words, 150 overlap).

`ingest_blog.py` — chunks all 12 published articles, embeds in batches of 16 through the local 1B embed NIM, COPY-loads into pgvector, creates HNSW + GIN-FTS + (slug) btree indexes. 61 chunks total, 37.3 s end-to-end.

```
chunks: 61 across 12 articles
  embedded 16/61
  embedded 32/61
  embedded 48/61
  embedded 61/61
loading…
creating indexes…
done in 37.3s
```

Per-slug count:

```
 bigger-generator-grounding-on-spark |     4
 dgx-spark-day-one-access-first      |     5
 guardrails-on-the-retrieval-path    |     5
 lora-on-your-own-qa-pairs           |     6
 naive-rag-on-spark                  |     5
 nemoclaw-vs-openclaw-dgx-spark      |     7
 nemo-retriever-embeddings-local     |     5
 nim-first-inference-dgx-spark       |     6
 one-substrate-three-apps            |     3
 pgvector-on-spark                   |     5
 rerank-fusion-retrieval-on-spark    |     5
 trtllm-and-triton-on-spark          |     5
```

## Retrieval

`retrieve.py` — for each held-out question, embed via query NIM, `pgvector top-20 (<=> cosine)`, rerank via hosted `llama-3.2-nv-rerankqa-1b-v2`. Save both naive top-5 and rerank top-5 to `retrieved.jsonl`.

First question spot-check — rerank promoted the gold chunk to slot 0:

```
Q: What is the purpose of the `classify_block` function?
gold: guardrails-on-the-retrieval-path #2

naive_top5:
  guardrails-on-the-retrieval-path #3  dist=0.7671
  guardrails-on-the-retrieval-path #0  dist=0.7709
  guardrails-on-the-retrieval-path #2  dist=0.7709   ← gold, rank 2
  guardrails-on-the-retrieval-path #1  dist=0.7750
  guardrails-on-the-retrieval-path #4  dist=0.8288

rerank_top5:
  guardrails-on-the-retrieval-path #2  logit=-1.138   ← gold, rank 0
  guardrails-on-the-retrieval-path #3  logit=-2.133
  naive-rag-on-spark #1                logit=-10.242
  guardrails-on-the-retrieval-path #0  logit=-10.242
  guardrails-on-the-retrieval-path #1  logit=-11.375
```

Total: 44 questions × (embed + top-20 + rerank) = 102.3 s wall.

Hosted-reranker auth:

```
set -a && source ~/.nim/secrets.env && set +a
# NGC_API_KEY exported to subprocess
```

## Generation — 8B variants

`generate_nim.py` — first run with top-5 context + max_tokens=220 hit HTTP 400 (context overflow against 8192-token NIM). Reduced to top-3 context + max_tokens=160. All 88 completions (naive + rerank × 44) ran in 251.3 s, mean wall 2.75 s (naive) / 2.96 s (rerank), mean completion 49.4 / 55.8 tokens.

Spot-check: naive_8b and rerank_8b both produce correct answers to Q0 (classify_block) — the variant that LoRA-only failed on in S2.

## Generation — LoRA + RAG

LoRA artifacts at `/home/nvidia/lora-work/base/` (Qwen-2.5-3B-Instruct bf16) and `/home/nvidia/lora-work/adapter/` (rank-16 LoRA). Host has no peft/transformers/torch; ran inside `nvcr.io/nvidia/tritonserver:25.12-trtllm-python-py3` container.

`make_lora_prompts.py` — builds `prompts_lora.jsonl` with top-3 naive context per question.

`lora_rag_bench.py` — in-container script, loads base + adapter once (~37 s), generates on 44 items. Mean wall 2.07 s/item, mean output 7.1 tokens.

Docker invocation:

```
docker run --rm --gpus all \
  -v /home/nvidia/lora-work:/work \
  -v /home/nvidia/rag-eval-work:/rag \
  nvcr.io/nvidia/tritonserver:25.12-trtllm-python-py3 \
  python3 /rag/lora_rag_bench.py
```

Sample outputs — note extreme terseness:

```
Q: What is the purpose of the `classify_block` function?
REF: A three-line check against the canonical refusal strings each arc emits
RAG_LORA: to check whether the answer was blocked by the rail

Q: What is the size of the AG News corpus used in the benchmark?
REF: 1000 rows
RAG_LORA: 1000 headlines       ← terse fact, not quite the reference wording

Q: What is the name of the CLI shipped with TRT-LLM 1.1 for serving a single-model OpenAI-compatible endpoint?
REF: trtllm-serve
RAG_LORA: trtllm-serve          ← perfect atom

Q: What is the size of the resulting relation for 1000 rows?
REF: six megabytes
RAG_LORA: six megabytes         ← perfect
```

## Grading

`grade.py` — three NIM-as-judge calls per prediction: correctness (0–5), relevance (0–1), faithfulness (0–1). First run hit HTTP 400 on faithfulness for naive_8b rows: three 900-word chunks in the judge prompt + the answer + system = >8K tokens. Fix: trim each chunk to first 500 words before faithfulness grading. Re-ran; 176 rows × 3 metrics ≈ 396 judge calls completed in ~22 minutes wall (grading is sequential against a single NIM).

## Headline numbers

From `summary.json`:

```json
{
  "lora_only":  { "n": 44, "mean_correctness_0_5": 1.70, "correctness_ge_4": 9,  "correctness_eq_5": 3,  "refusal_rate": 0.000, "mean_wall_s": 0.44 },
  "naive_8b":   { "n": 44, "mean_correctness_0_5": 3.30, "correctness_ge_4": 29, "correctness_eq_5": 20, "refusal_rate": 0.182, "mean_wall_s": 2.75, "p_chunk_at_k": 0.659, "p_slug_at_k": 0.864 },
  "rag_lora":   { "n": 44, "mean_correctness_0_5": 3.39, "correctness_ge_4": 28, "correctness_eq_5": 21, "refusal_rate": 0.000, "mean_wall_s": 2.07, "p_chunk_at_k": 0.568, "p_slug_at_k": 0.750 },
  "rerank_8b":  { "n": 44, "mean_correctness_0_5": 4.27, "correctness_ge_4": 39, "correctness_eq_5": 25, "refusal_rate": 0.000, "mean_wall_s": 2.96, "p_chunk_at_k": 0.955, "p_slug_at_k": 0.977 }
}
```

Faithfulness–correctness Pearson (from `analysis.json`):

```
naive_8b  : 0.440
rerank_8b : 0.146
rag_lora  : 0.103
```

Cross-variant stats: 6 questions scored ≥4 in every variant; 3 scored ≤1 in every variant.

## Decisions taken during the run

- Kept top-K=5 for retrieval metrics but dropped to K=3 for generation context (8192-token NIM window).
- Skipped `naive_lora` variant (Qwen-3B with naive context but no LoRA) — not the comparison that ships the finding. The 4 variants already tell the retrieval-is-the-lever story clearly.
- Wrote Ragas metrics by hand rather than pulling `pip install ragas` — the library pulls LangChain and OpenAI, neither of which belongs on this Spark. Spec-not-library was the right call.
- NeMo Evaluator: wrote the `nemo_evaluator_config.yaml` as the productionization path but didn't stand up the Evaluator service this session. The service is a conceptual graduation; the article closes on this.

## Carried forward — next article

S3 done. Next is **S4** — `mcp-second-brain-in-claude-code`. Wraps the whole retrieve → rerank → generate → grade chain as a Model Context Protocol tool; plugs into Claude Code itself via `.mcp.json`. Makes the blog one `@`-mention away from every coding session on the Spark.

Second open threads from this session:
- **Train a LoRA on (question, context, answer) triples.** The current LoRA was trained on (question, answer) — it doesn't know how to use retrieved context. A context-aware LoRA is the real LoRA+RAG experiment.
- **Swap the judge.** Rerun with 49B Nemotron-Super as the judge and then 70B Llama-3.3 — inter-judge correlation is a production-signal about whether the 8B-graded scoreboard can be trusted.
- **Retrieval-knob sweep.** top-K ∈ {1,3,5,10,20}, rerank on/off, chunk-size ∈ {500, 900, 1200}, 30 combinations × 9 min grader = 4.5 h overnight.
