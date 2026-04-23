#!/usr/bin/env python3
"""Run ask.py across a fixed set of questions and emit benchmark.json.

Three in-corpus questions (answerable from 2004 AG-News headlines) +
three out-of-corpus questions (post-2004 events or current-day trivia
the AG-News corpus cannot answer). Under the strict scaffold, the
in-corpus set should ground with citations; the out-of-corpus set
should trigger the canned refusal.
"""
import json
import subprocess
import sys
import time

QUESTIONS = [
    # In-corpus: AG News 2004 headlines have plenty of coverage.
    ("in_corpus", "Who won the 2004 US presidential election?"),
    ("in_corpus", "What happened at the 2004 Athens Olympics in swimming?"),
    ("in_corpus", "What did Google do in 2004 related to going public?"),
    # Out-of-corpus: nothing in AG-News 2004 can answer these.
    ("out_of_corpus", "Who won the 2020 US presidential election?"),
    ("out_of_corpus", "What is NVIDIA DGX Spark?"),
    ("out_of_corpus", "When was Claude 4 Opus released?"),
]


def ask(question):
    proc = subprocess.run(
        ["python3", "ask.py", "--json", "--k", "5", question],
        capture_output=True, text=True, check=True, timeout=120,
    )
    return json.loads(proc.stdout)


def main():
    results = []
    for kind, q in QUESTIONS:
        t0 = time.perf_counter()
        record = ask(q)
        wall = time.perf_counter() - t0
        record["kind"] = kind
        record["wall_seconds"] = round(wall, 2)
        results.append(record)
        t = record["timings_ms"]
        preview = record["answer"][:120].replace("\n", " ")
        print(f"[{kind:14}] embed {t['embed']:5.1f}  retrieve {t['retrieve']:5.1f}  "
              f"ttft {t['generate_first_token']:6.1f}  "
              f"gen {t['generate_total']:6.1f}  | {preview}")

    # Aggregate latency percentiles across all 6 queries.
    def stat(field):
        vals = sorted(r["timings_ms"][field] for r in results
                      if r["timings_ms"][field] is not None)
        n = len(vals)
        return {
            "mean": round(sum(vals) / n, 2),
            "median": vals[n // 2],
            "min": vals[0],
            "max": vals[-1],
        }

    summary = {
        "n": len(results),
        "embed_ms": stat("embed"),
        "retrieve_ms": stat("retrieve"),
        "generate_first_token_ms": stat("generate_first_token"),
        "generate_total_ms": stat("generate_total"),
        "end_to_end_ms": stat("end_to_end"),
    }

    blob = {"summary": summary, "queries": results}
    with open("benchmark.json", "w") as f:
        json.dump(blob, f, indent=2)
    print(f"\nWrote benchmark.json — {len(results)} queries")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
