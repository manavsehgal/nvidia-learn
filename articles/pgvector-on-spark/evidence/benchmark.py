#!/usr/bin/env python3
"""Benchmark exact KNN vs ivfflat vs HNSW on the ingested pgvector corpus.

For each of 20 hand-crafted queries (5 per AG-News class) we:

1. Embed the query with the Nemotron NIM (input_type=query, 1024-d).
2. Run the same ORDER-BY-distance query against three index configurations
   and capture both latency and the top-10 ID set.
3. Treat the exact (seq-scan) top-10 as ground truth and compute recall@10
   for each approximate index.

The indexes are built once per run. For ivfflat we sweep `probes` and for
HNSW we sweep `ef_search` to show the classical recall/latency knob.

No Python deps beyond stdlib — all DB work goes through `docker exec psql`.
"""
import json
import os
import statistics
import subprocess
import time
import urllib.request

NIM_URL = os.environ.get("NIM_URL", "http://localhost:8001/v1/embeddings")
MODEL = "nvidia/llama-nemotron-embed-1b-v2"
DIM = 1024
TOP_K = 10

QUERIES = {
    "Sports": [
        "tennis tournament grand slam",
        "soccer world cup qualifier",
        "olympic gold medal winner",
        "NBA basketball playoffs",
        "baseball pitcher strikeout",
    ],
    "World": [
        "war in iraq casualties",
        "north korea nuclear program",
        "palestinian israeli conflict",
        "united nations peacekeeping",
        "european union expansion",
    ],
    "Business": [
        "crude oil price surge",
        "stock market rally wall street",
        "corporate earnings report",
        "federal reserve interest rates",
        "mergers and acquisitions deal",
    ],
    "Sci/Tech": [
        "google search engine technology",
        "microsoft windows software update",
        "nasa mars rover mission",
        "apple ipod music player launch",
        "open source linux kernel",
    ],
}

def psql(sql, timing=False):
    cmd = ["docker", "exec", "-i", "pgvector",
           "psql", "-U", "spark", "-d", "vectors", "-At", "-F", "|",
           "-v", "ON_ERROR_STOP=1"]
    if timing:
        cmd += ["-c", "\\timing on"]
    p = subprocess.run(cmd + ["-c", sql], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"psql failed: {p.stderr}")
    return p.stdout

def embed(text):
    body = json.dumps({"model": MODEL, "input": [text], "input_type": "query",
                       "encoding_format": "float", "dimensions": DIM}).encode()
    req = urllib.request.Request(NIM_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["data"][0]["embedding"]

def vec_lit(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"

def query_top_k(qvec, session_sql=""):
    """Run a top-K cosine-distance query, return (ids, execution_ms)."""
    sql = f"""
    {session_sql}
    EXPLAIN (ANALYZE, FORMAT JSON)
    SELECT id FROM chunks ORDER BY embedding <=> '{vec_lit(qvec)}' LIMIT {TOP_K};
    """
    out = psql(sql)
    # psql echoes "SET" lines for each SET statement before the JSON EXPLAIN.
    # Strip anything before the first '[' so json.loads sees only the plan.
    json_start = out.find("[")
    plan = json.loads(out[json_start:])
    exec_ms = plan[0]["Execution Time"]

    sql2 = f"""
    {session_sql}
    SELECT id FROM chunks ORDER BY embedding <=> '{vec_lit(qvec)}' LIMIT {TOP_K};
    """
    lines = [l for l in psql(sql2).strip().splitlines() if l and l.strip().isdigit()]
    ids = [int(x) for x in lines]
    return ids, exec_ms

def recall_at_k(pred, truth):
    return len(set(pred) & set(truth)) / len(truth)

def bench_config(name, session_sql):
    latencies, recalls = [], []
    all_queries = [(cls, q) for cls, qs in QUERIES.items() for q in qs]
    per_class_hit = {cls: 0 for cls in QUERIES}

    for cls, q in all_queries:
        qvec = embed(q)

        exact_ids, _ = query_top_k(qvec, session_sql="SET enable_indexscan = off; SET enable_bitmapscan = off;")
        ids, ms = query_top_k(qvec, session_sql=session_sql)

        latencies.append(ms)
        recalls.append(recall_at_k(ids, exact_ids))

        # Topic precision: of the top-10 for this query, how many are the
        # query's class? Measures whether the embedding+index preserve the
        # label signal — a useful sanity check on the whole pipeline.
        rows_out = psql(f"""
            {session_sql}
            SELECT label FROM chunks ORDER BY embedding <=> '{vec_lit(qvec)}' LIMIT {TOP_K};
        """).strip().splitlines()
        labels = [l for l in rows_out if l and l != "SET"]
        per_class_hit[cls] += sum(1 for r in labels if r == cls)

    p50 = statistics.median(latencies)
    p95 = sorted(latencies)[int(len(latencies) * 0.95) - 1]
    mean_recall = statistics.mean(recalls)
    topic_prec = {cls: per_class_hit[cls] / (len(QUERIES[cls]) * TOP_K) for cls in QUERIES}
    print(f"{name:40s}  p50={p50:6.2f}ms  p95={p95:6.2f}ms  recall@10={mean_recall:.3f}")
    return {
        "name": name,
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "recall_at_10": round(mean_recall, 3),
        "topic_precision": {k: round(v, 3) for k, v in topic_prec.items()},
    }

def main():
    out = {"configs": []}

    # Warm the cache: touch the heap once so the exact-scan baseline isn't
    # artificially slow on the first query.
    psql("SELECT count(*) FROM chunks;")

    # ------ Exact baseline (seq scan, cosine distance) ------
    out["configs"].append(bench_config(
        "exact (seq scan)",
        "SET enable_indexscan = off; SET enable_bitmapscan = off;"))

    # ------ ivfflat ------
    print("\n[building ivfflat index: lists=32 ...]")
    t0 = time.perf_counter()
    psql("DROP INDEX IF EXISTS chunks_ivfflat; "
         "CREATE INDEX chunks_ivfflat ON chunks "
         "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 32);")
    out["ivfflat_build_s"] = round(time.perf_counter() - t0, 2)
    print(f"  built in {out['ivfflat_build_s']}s")

    # Force the planner onto the index. At 1k rows the cost model picks seq
    # scan unless we disable it — which hides the actual approximate-index
    # behavior we're trying to measure.
    force_index = "SET enable_seqscan = off;"
    for probes in [1, 4, 10, 32]:
        out["configs"].append(bench_config(
            f"ivfflat  lists=32  probes={probes:<3}",
            f"DROP INDEX IF EXISTS chunks_hnsw; "
            f"{force_index} SET ivfflat.probes = {probes};"))

    # ------ HNSW ------
    print("\n[building hnsw index: m=16, ef_construction=64 ...]")
    psql("DROP INDEX IF EXISTS chunks_ivfflat;")
    t0 = time.perf_counter()
    psql("DROP INDEX IF EXISTS chunks_hnsw; "
         "CREATE INDEX chunks_hnsw ON chunks "
         "USING hnsw (embedding vector_cosine_ops) "
         "WITH (m = 16, ef_construction = 64);")
    out["hnsw_build_s"] = round(time.perf_counter() - t0, 2)
    print(f"  built in {out['hnsw_build_s']}s")

    for ef in [10, 40, 100]:
        out["configs"].append(bench_config(
            f"hnsw     m=16  ef_search={ef:<3}",
            f"{force_index} SET hnsw.ef_search = {ef};"))

    # Index sizes for the prose.
    sizes = psql("""
        SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid))
        FROM pg_stat_user_indexes WHERE relname = 'chunks';
    """).strip().splitlines()
    out["index_sizes"] = dict(row.split("|") for row in sizes)
    print("\nindex sizes:", out["index_sizes"])

    with open("benchmark.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nwrote benchmark.json")

if __name__ == "__main__":
    main()
