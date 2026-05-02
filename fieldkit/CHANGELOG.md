# Changelog

All notable changes to `fieldkit` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). While the package is on `0.x`, minor versions may include breaking changes. `1.0` will mark API stability.

## [Unreleased]

## [0.1.0] — 2026-05-02

First public release. Four library modules + a CLI + a docs site section, lifted from 25+ articles in [ai-field-notes](https://ainative.business/field-notes/).

### Added

- **`fieldkit.capabilities`** — typed Python facade over `spark-capabilities.json`. `Capabilities.load()` cached singleton (with `.hardware`, `.memory_budget_rules_of_thumb`, `.stack`, `.in_envelope_signals`, `.out_of_envelope_signals`, `.stage_routing_hints`, `.series_routing_hints`), plus canonical math helpers `kv_cache_bytes()`, `weight_bytes()`, `practical_inference_envelope()`. Numbers pinned to `kv-cache-arithmetic-at-inference` and `gpu-sizing-math-for-fine-tuning`. ([#capabilities])
- **`fieldkit.nim`** — OpenAI-compatible `NIMClient` over `httpx` with `tenacity`-backed retries on 429 / 503 / `ConnectError` / timeouts. `NIMClient.chat()` runs a pre-flight context check and raises `NIMContextOverflowError` with the estimated token count *before any network call*, so the opaque NIM 400 from a >8192-token request never surfaces. Helpers: `chunk_text()` (paragraph→sentence→word splitting under a `max_tokens` budget), `estimate_tokens()` (1 tok ≈ 4 chars), `wait_for_warm()` (polls `/v1/models` for the ~90s NIM cold start). Constants: `NIM_CONTEXT_WINDOW = 8192`, `DEFAULT_CHUNK_TOKENS = 1024`. Errors: `NIMError` → `NIMHTTPError`, `NIMTimeoutError`, `NIMContextOverflowError`. ([#nim])
- **`fieldkit.rag`** — composable ingest → retrieve → rerank → fuse pipeline backed by pgvector + a NIM embedder + the strict-context grounded prompt from `naive-rag-on-spark`. `Pipeline.ingest()` chunks via `fieldkit.nim.chunk_text` and upserts in batches of 32; `Pipeline.retrieve()` does pgvector cosine top-K; `Pipeline.rerank()` is a pass-through when `rerank_url=None`; `Pipeline.fuse()` builds the strict-context messages list and calls the generator; `Pipeline.ask()` chains all three. Embed and rerank inherit `NIMClient.chat`'s retry policy so co-resident memory pressure doesn't fail the pipeline. ([#rag])
- **`fieldkit.eval`** — `Bench` (latency aggregation with the same `{summary, calls}` JSON shape as the article evidence files), `Judge` (LLM-as-judge with built-in `correctness` / `faithfulness` / `relevance` rubrics + a static `Judge.parse()` JSON-then-regex extractor), `Trajectory` (agent-loop JSONL analyzer with `knob_coverage / repeat_rate / mode_dominance / cumulative_best`), `is_refusal()` (regex catalog unioned across the project's articles), `summarize_metric()`. ([#eval])
- **`fieldkit.cli`** — Typer wrapper exposing `fieldkit version`, `fieldkit envelope <size>`, `fieldkit feasibility <model_id> [--ctx --batch --dtype]`, `fieldkit bench rag`. On `$PATH` after `pip install`. ([#cli])
- **Astro docs site** — `/fieldkit/` landing page with install + quickstart + module grid, and `/fieldkit/api/<module>/` reference pages backed by a new `fieldkit_docs` content collection. Articles can opt-in via `fieldkit_modules:` frontmatter to display a "USES fieldkit.X" chip on cards and appear under each module's "Articles that use fieldkit.<module>" footer. 11 articles opted in for the v0.1.0 launch.
- **Samples**: `samples/feasibility-math.py` (capabilities reproduction of the kv-cache article's table), `samples/hello-nim.py` (Python equivalent of the curl one-liner), `samples/naive-rag.py` (end-to-end RAG in <30 lines), `samples/bench-rag.py` (offline `Bench` + `Judge.parse()` walkthrough).
- `scripts/sync_capabilities.py` keeps the package-bundled `spark-capabilities.json` in sync with the source-of-truth at `scripts/lib/spark-capabilities.json` (pre-commit-enforced).
- `pytest --spark` flag (via `tests/conftest.py`) gates integration tests that need a live NIM / pgvector on the DGX Spark; default runs skip them.

### Changed

- `frontier-scout` skill (`refresh` and `eval` modes, plus `references/feasibility-prompt.md` and `references/classifier-prompt.md`) now teaches the typed `from fieldkit.capabilities import …` API as the preferred grounding path; raw JSON read is the documented fallback.

### Verified on Spark

Phases 3, 4, 5 were live-verified end-to-end against the chat NIM (Llama 3.1 8B, port 8000), the embed NIM (Nemotron Embed 1B v2, port 8001), and pgvector (port 5432) before being committed. Phase 5 in particular rewrote `articles/naive-rag-on-spark/evidence/benchmark.py` against `fieldkit.eval.Bench` + `fieldkit.rag.Pipeline.fuse` and reproduced the original article's behavioral fingerprint (5 of 6 refusals incl. the canonical Google-IPO false refusal, plus the Ian Thorpe grounded answer).

### Test suite

**157 passing, 2 skipped** without `--spark` (151 passing with `--spark` against warm NIMs + pgvector). Reproduce: `pip install fieldkit/[dev]` then `pytest`; for the live tests, `pytest --spark`.

[#capabilities]: https://github.com/manavsehgal/ai-field-notes/tree/main/fieldkit/src/fieldkit/capabilities
[#nim]: https://github.com/manavsehgal/ai-field-notes/tree/main/fieldkit/src/fieldkit/nim
[#rag]: https://github.com/manavsehgal/ai-field-notes/tree/main/fieldkit/src/fieldkit/rag
[#eval]: https://github.com/manavsehgal/ai-field-notes/tree/main/fieldkit/src/fieldkit/eval
[#cli]: https://github.com/manavsehgal/ai-field-notes/tree/main/fieldkit/src/fieldkit/cli
