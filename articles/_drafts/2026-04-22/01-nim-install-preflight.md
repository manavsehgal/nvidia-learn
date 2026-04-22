# 2026-04-22 — NIM preflight on DGX Spark

**Context.** Starting the shared foundation article #1 — first NIM inference on the Spark. Llama 3.1 8B Instruct, DGX-Spark-specific build at `nvcr.io/nim/meta/llama-3.1-8b-instruct-dgx-spark`. This article opens both the Second Brain arc and the Autoresearch arc.

## Preflight snapshot (before any pull)

- **Docker**: 29.2.1, daemon running, `nvidia` runtime registered (`Runtimes: io.containerd.runc.v2 nvidia runc`). Cgroup v2 + systemd driver.
- **Already running**: 1 container (`docker ps` shows 1 running — NemoClaw's `clawnav` sandbox from prior articles).
- **Disk**: 3.4 TB free on `/` (root is `/dev/nvme0n1p2`, 3.7 TB total, 154 GB used). Comfortable headroom for a multi-GB NIM image.
- **GPU**: `NVIDIA GB10` visible via `nvidia-smi`, driver 580.142. Unified-memory Spark quirk: `memory.total / used / free` columns report `[N/A]` — memory is OS-managed on Grace, not driver-reported. Worth a callout in the article.
- **Port 8000**: free. Port 8080 is held (NemoClaw auth-proxy), port 11434 is Ollama. NIM's default 8000 is unconflicted.
- **Ollama**: `active` (from nemoclaw article) — Nemotron 3 Super 123.6B Q4_K_M still pulled. Leaving running; measuring NIM alongside, not instead of.
- **NGC credentials**: **none found**. No `~/.ngc/config`, no `$NGC_API_KEY` in env, no `nvcr.io` auth in `~/.docker/config.json`. `ngc` CLI also not installed. Hard blocker until the user pastes a key.

## The image target (from NGC catalog search, not yet pulled)

- Container: `nvcr.io/nim/meta/llama-3.1-8b-instruct-dgx-spark`
- Spark-specific build exists — this is not a generic Llama NIM with a hope it runs on aarch64; NVIDIA ships a dedicated DGX Spark variant.
- Authoritative runbook location: `https://build.nvidia.com/spark/nim-llm` (the page timed out on one fetch attempt; retrying after auth).

## Decisions made

- **Host port**: use 8000 (default). No conflict.
- **Baseline for comparison**: same Fibonacci one-liner prompt used in the nemoclaw article (Ollama Nemotron). Gives apples-to-apples NIM-vs-Ollama steady-state tok/s.
- **Leave Ollama running during the benchmark**. If memory pressure triggers OOM we stop it and re-measure; don't stop pre-emptively — the Spark's unified 128 GB should carry both a 123.6B Q4 model and an 8B NIM in concurrent idle memory. Worth measuring.
- **Don't touch NemoClaw sandbox**. Orthogonal to this work.

## Open questions to resolve with NGC key in hand

- Exact image tag (`:latest` vs. versioned).
- Whether `docker login` alone suffices or whether the container reads `$NGC_API_KEY` at runtime for model-weight downloads.
- Whether the container auto-downloads weights on first run (common for NIMs) and where those land — a model cache volume mount is critical to avoid re-downloading.
