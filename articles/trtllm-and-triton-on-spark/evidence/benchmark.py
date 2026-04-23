#!/usr/bin/env python3
"""Three-way benchmark: NIM vLLM FP8 vs TRT-LLM FP8 vs TRT-LLM NVFP4.

All three endpoints are expected to speak OpenAI-compatible /v1/chat/completions.
Measures:
  - TTFT (time to first streamed chunk)
  - decode rate (tok/s excluding first-chunk latency)
  - end-to-end wall time
  - aggregate throughput at concurrency ∈ {1, 2, 4, 8}
"""
import argparse, json, statistics, threading, time, urllib.request

PROMPT = (
    "In one paragraph: what is retrieval-augmented generation "
    "and when is it the wrong tool?"
)
MAX_TOKENS = 200


def call_stream(url: str, model: str) -> tuple[float, float, int]:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS, "temperature": 0, "stream": True,
    }).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    t0 = time.perf_counter()
    first = None
    toks = 0
    with urllib.request.urlopen(req) as r:
        for line in r:
            if not line.startswith(b"data:"):
                continue
            payload = line[5:].strip()
            if payload == b"[DONE]":
                break
            d = json.loads(payload)
            delta = d["choices"][0]["delta"].get("content") or ""
            if delta:
                if first is None:
                    first = time.perf_counter()
                toks += 1
    t1 = time.perf_counter()
    ttft = (first - t0) * 1000 if first else float("nan")
    decode_rate = (toks - 1) / (t1 - first) if first and toks > 1 else 0.0
    return ttft, decode_rate, toks


def call_block(url: str, model: str) -> tuple[float, int]:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS, "temperature": 0, "stream": False,
    }).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as r:
        d = json.loads(r.read())
    t1 = time.perf_counter()
    return t1 - t0, d["usage"]["completion_tokens"]


def serial_bench(name: str, url: str, model: str, runs: int = 5) -> dict:
    ttfts, rates, walls = [], [], []
    for _ in range(runs):
        ttft, rate, _ = call_stream(url, model)
        ttfts.append(ttft)
        rates.append(rate)
    for _ in range(runs):
        wall, _ = call_block(url, model)
        walls.append(wall)
    return {
        "name": name,
        "ttft_ms_p50": statistics.median(ttfts),
        "ttft_ms_p95": sorted(ttfts)[int(0.95 * len(ttfts))],
        "decode_tok_s": statistics.median(rates),
        "wall_s_p50": statistics.median(walls),
    }


def concurrency_bench(url: str, model: str, n: int) -> dict:
    results = []

    def hit() -> None:
        wall, toks = call_block(url, model)
        results.append((wall, toks))

    threads = [threading.Thread(target=hit) for _ in range(n)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    t1 = time.perf_counter()
    agg = sum(r[1] for r in results) / (t1 - t0)
    per_req_p50 = statistics.median(r[0] for r in results)
    return {"concurrency": n, "aggregate_tok_s": agg, "per_req_p50_s": per_req_p50}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoints", required=True,
                    help='JSON: [{"name":"NIM","url":"...","model":"..."},...]')
    ap.add_argument("--out", default="benchmark-results.json")
    args = ap.parse_args()

    endpoints = json.loads(args.endpoints)
    all_results = {}
    for ep in endpoints:
        print(f"[{ep['name']}] serial bench...")
        serial = serial_bench(ep["name"], ep["url"], ep["model"])
        print(f"  TTFT p50={serial['ttft_ms_p50']:.1f}ms "
              f"decode={serial['decode_tok_s']:.2f}tok/s")
        print(f"[{ep['name']}] concurrency bench...")
        conc = [concurrency_bench(ep["url"], ep["model"], n)
                for n in (1, 2, 4, 8)]
        for c in conc:
            print(f"  c={c['concurrency']}: "
                  f"{c['aggregate_tok_s']:.1f}tok/s agg, "
                  f"{c['per_req_p50_s']*1000:.0f}ms per-req p50")
        all_results[ep["name"]] = {"serial": serial, "concurrency": conc}

    with open(args.out, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
