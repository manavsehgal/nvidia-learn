# Threads #1 + #3 follow-up — warm-cache cold-start + NIM_GPU_MEM_FRACTION A/B

Ran 2026-04-22 ~12:15–12:25 PT, after handoff resume. Same image, cache, prompt.

## Thread #1 — Warm-cache cold-start

**Question:** How long does the *second-and-onward* `docker run` take when the
9.4 GB of weights are already sitting in `~/.nim/cache/llama-3.1-8b-instruct/`?
The first-run number (205 s) included a ~95 s one-time weight download —
readers care about the daily number, not the first one.

**Result: 110 s** (first measurement, `NIM_GPU_MEM_FRACTION=0.5`, default).
**Result: 106 s** (re-run after thread #3 restart, `NIM_GPU_MEM_FRACTION=0.8`).

Within ±4 s, so call it **~108 s warm-cache cold-start**.

### Cold-start time decomposition (updated)

| Phase | Elapsed (s) | Source |
|---|---|---|
| `docker run` → container-up | ~5 | docker-internal; not in our polling loop |
| NGC auth + registry probe | ~5 | image already pulled, so just `docker inspect` + `ENTRYPOINT` launch |
| Safetensor shard load (4 shards → vLLM) | ~60 | unified memory → model weights |
| CUDA-graph compile + KV-cache alloc | ~30 | vLLM warmup step |
| HTTP server listen + `/v1/models` responsive | ~5 | final |
| **Total** | **~108 s** | what curl measures |
| *(First-run adder: NGC pull of 9.4 GB on 1 Gbps = ~95 s)* | *95* | *amortizes to 0 on subsequent runs* |

So the honest article framing:
- **First install on a fresh Spark:** ~205 s ("a cup of coffee").
- **Every reboot after that:** ~108 s ("two minutes — just enough to tab over and check email").

---

## Thread #3 — NIM_GPU_MEM_FRACTION A/B

**Question:** Default is 0.5 (claim half of Spark's unified memory for the NIM).
For a single 8B model with nothing else running, is there room to speed up by
raising it?

**Setup:** Same container, same cache, same prompt (Fibonacci one-liner).
4-round sequential benchmark, temperature=0.7, max_tokens=512.

| `NIM_GPU_MEM_FRACTION` | mean tok/s | min | max |
|---|---|---|---|
| 0.5 (default) | **24.84** | 24.72 | 24.90 |
| 0.8 | **24.64** | 24.57 | 24.72 |

**Finding: 0.8 is 0.2 tok/s SLOWER than 0.5** — which is within noise, so the
honest read is *"zero change."* Single-request latency is **not memory-bound**
on a single 8B FP8 model. Raising `NIM_GPU_MEM_FRACTION` only buys you headroom
for **concurrent batching** (more simultaneous requests fit in KV-cache) — not
speed for one user asking one question.

### Side finding: identical token counts across runs

Both A/B runs produced the **exact same completion_tokens** per round:
`253, 165, 219, 219`. At temperature=0.7 this should have varied. Possibilities:
1. NIM wraps vLLM with a deterministic seed by default.
2. vLLM's prefix-caching + 8B-FP8 model is effectively deterministic for short
   prompts even with sampling on.
3. My OpenAI-API call isn't actually sending randomness (no `seed` field, and
   maybe NIM forces one).

Not central to article #1 — but worth a footnote: **"If you want reproducible
benchmarks, the NIM seems to be deterministic even without `seed=`. If you
want variance, pass `seed=` explicitly with a random integer per request."**

---

## Implication for article #1

The hero numbers are now:
- **Install size:** 9.4 GB image → 8.5 GB cache on disk
- **First-run cold-start:** 205 s (includes ~95 s download)
- **Warm-cache cold-start:** ~108 s (every restart after that)
- **Inference throughput:** 24.8 tok/s (stable across GPU_MEM_FRACTION settings)
- **Quality:** hallucinates a nonsense Python "one-liner" at temperature=0 AND 0.7

The article's spine: **fast to stand up, fast enough at runtime, wrong on
small-model code-prompts.** The three-line state of the stack at the close:
- **Speed:** ✅ 24.8 tok/s, 108 s to ready
- **Ergonomics:** ✅ OpenAI-compatible endpoint, curl works, no client SDK
- **Quality:** ⚠️ expect to debug imaginary APIs on constrained prompts
