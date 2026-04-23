# Source transcript — pgvector-on-spark

Session: 2026-04-22 (article #3 in the shared-foundation retrieval arc).
Prior handoff: `handoff/2026-04-22-svg-sidequest-and-article3-queue.md`.

## Shape of the session

1. Smoke-checked inherited runtime — both NIMs (:8000 LLM, :8001 embed),
   Astro dev (:4321), `verify_svg.sh` canary on article #2 all green.
2. Picked **container-first** pgvector (`pgvector/pgvector:pg16`), launched
   on :5432 with a `pgvector-data` Docker volume and
   `POSTGRES_USER=spark / POSTGRES_DB=vectors`. `CREATE EXTENSION vector`
   reported 0.8.2 on Postgres 16.13 `aarch64-unknown-linux-gnu`.
3. Committed to **1024-d Matryoshka**. Verified the Nemotron NIM's
   `dimensions=1024` param does real Matryoshka truncation (first-1024
   prefix of the 2048-d output, L2-renormalised to unit norm).
4. Fetched **1000 AG News rows stratified 250/class** via the Hugging Face
   datasets-server HTTP API (stdlib-only fetch script). Stratification
   mattered — the naïve first-1000 pull was 47 % Sci/Tech.
5. Wrote a stdlib-only `ingest.py` that batches 32 chunks per embed call
   and streams `COPY chunks FROM STDIN` records through `docker exec -i`.
   **99.5 docs/s end-to-end** for 1000 rows / 10.1 s.
6. Ran the benchmark across exact seq scan + ivfflat (probes ∈ {1,4,10,32})
   + HNSW (ef_search ∈ {10,40,100}). First pass showed non-monotonic recall
   — `EXPLAIN` revealed the Postgres planner prefers seq scan at 1000 rows.
   Rerun with `SET enable_seqscan = off;` forced the index and produced
   clean monotonic recall/latency curves.
7. Built `PgvectorStore.astro` signature (table → HNSW graph) and an
   in-body layered-stack fn-diagram (app → driver → pgvector → PG → disk).
   First pass had blank lines inside the SVG which the markdown parser
   terminated the HTML block on; removing them fixed the render.
8. Vibe-checked the article in Firefox in light + dark mode. `verify_svg.sh`
   and `verify_article.sh` both green.

## Evidence layout

- `evidence/fetch_corpus.py` — stratified AG News puller
- `evidence/corpus.jsonl` — 1000 rows, 250 per class
- `evidence/schema.sql` — `vector(1024)` schema
- `evidence/ingest.py` — embed + COPY pipeline
- `evidence/benchmark.py` — exact vs ivfflat vs HNSW, recall@10 against exact
- `evidence/benchmark.json` — final numbers
- `evidence/01-fetch.log`, `02-ingest.log`, `03-benchmark.log` — run logs
- `evidence/04-explain-plans.txt` — planner choice at each probes setting
- `evidence/05-pg-version.txt` — `SELECT version()` + extension version
- `evidence/06-container.txt` — image arch + size
