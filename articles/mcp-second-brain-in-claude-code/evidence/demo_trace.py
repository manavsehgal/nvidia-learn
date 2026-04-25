"""Capture a full Claude-Code-shaped session against the Second Brain MCP.

Spawns launch.sh, drives the stdio JSON-RPC protocol (initialize → tools/list
→ tools/call) for a fixed set of demo prompts, and writes a redacted trace
to demo_trace.jsonl for use as article evidence.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

OUT = Path("/home/nvidia/second-brain-mcp/demo_trace.jsonl")

DEMOS = [
    ("list_articles", {}),
    ("search_blog", {
        "query": "how does the DGX Spark unified memory pool work",
        "top_k": 3,
        "rerank": True,
    }),
    ("ask_blog", {
        "question": (
            "What tokens-per-second did the first NIM run measure on the "
            "Spark, and why was that number framed as misleading?"
        ),
        "top_k": 3,
        "rerank": True,
        "max_tokens": 320,
    }),
    ("ask_blog", {
        "question": (
            "Compare naive cosine retrieval vs reranked retrieval — what "
            "does the rerank-fusion article find about precision and latency?"
        ),
        "top_k": 3,
        "rerank": True,
        "max_tokens": 320,
    }),
    ("ask_blog", {
        "question": (
            "What did the Spark do for the Vienna Philharmonic concert "
            "stream live broadcast?"
        ),
        "top_k": 3,
        "rerank": True,
        "max_tokens": 200,
    }),
    ("read_article_chunk", {"slug": "naive-rag-on-spark", "chunk_idx": 0}),
]


def main() -> None:
    p = subprocess.Popen(
        ["/home/nvidia/second-brain-mcp/launch.sh"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )

    def send(obj: dict) -> None:
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()

    def recv() -> dict | None:
        line = p.stdout.readline()
        return json.loads(line) if line else None

    out = OUT.open("w")

    def log(kind: str, payload: dict) -> None:
        out.write(json.dumps({"kind": kind, "ts": round(time.time(), 3),
                               **payload}) + "\n")
        out.flush()

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "demo-trace", "version": "0"},
    }})
    init = recv()
    log("initialize", {"server": init["result"]["serverInfo"]})
    print(f"server: {init['result']['serverInfo']}", flush=True)

    send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    listed = recv()
    tools = [{"name": t["name"], "description": t["description"][:160],
              "annotations": t.get("annotations", {})}
             for t in listed["result"]["tools"]]
    log("tools_list", {"tools": tools})
    print(f"tools: {[t['name'] for t in tools]}", flush=True)

    rid = 100
    for name, args in DEMOS:
        rid += 1
        t0 = time.time()
        send({"jsonrpc": "2.0", "id": rid, "method": "tools/call",
              "params": {"name": name, "arguments": args}})
        resp = recv()
        dt = round(time.time() - t0, 3)
        if "error" in resp:
            log("call_error", {"tool": name, "args": args,
                                "error": resp["error"], "wall_s": dt})
            print(f"  ✗ {name} → ERROR {resp['error']}", flush=True)
            continue
        content = resp["result"].get("content", [])
        structured = resp["result"].get("structuredContent")
        text = next((c["text"] for c in content if c["type"] == "text"), "")
        log("call_ok", {"tool": name, "args": args, "wall_s": dt,
                        "structured": structured, "text_preview": text[:400]})
        print(f"  ✓ {name} ({dt}s) → {text[:120].replace(chr(10), ' ')}...", flush=True)

    p.stdin.close()
    p.wait(timeout=5)
    out.close()
    print(f"\nwrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
