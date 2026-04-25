"""Second Brain MCP server.

Exposes the personal-blog RAG stack (NIM Embed -> pgvector -> hosted reranker
-> NIM Llama 3.1 8B) as MCP tools so any Claude Code session can @-mention it.

All four tools are read-only. The server speaks JSON-RPC over stdio.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

import psycopg
from mcp.server.fastmcp import FastMCP

PG_DSN = os.environ.get(
    "SECOND_BRAIN_PG_DSN",
    "host=127.0.0.1 port=5432 dbname=vectors user=spark password=spark",
)
EMBED_URL = os.environ.get("EMBED_URL", "http://127.0.0.1:8001/v1/embeddings")
EMBED_MODEL = "nvidia/llama-nemotron-embed-1b-v2"
EMBED_DIM = 1024

LLM_URL = os.environ.get("LLM_URL", "http://127.0.0.1:8000/v1/chat/completions")
LLM_MODEL = "meta/llama-3.1-8b-instruct"

RERANK_URL = (
    "https://ai.api.nvidia.com/v1/retrieval/nvidia/"
    "llama-3_2-nv-rerankqa-1b-v2/reranking"
)
RERANK_MODEL = "nvidia/llama-3.2-nv-rerankqa-1b-v2"
NGC_API_KEY = os.environ.get("NGC_API_KEY", "")

CHUNK_WORD_BUDGET = 500  # trim per-chunk before generation; matches grade.py.

mcp = FastMCP("second-brain")


def _embed(text: str) -> list[float]:
    body = json.dumps({
        "model": EMBED_MODEL,
        "input": [text],
        "input_type": "query",
        "encoding_format": "float",
        "truncate": "END",
        "dimensions": EMBED_DIM,
    }).encode()
    req = urllib.request.Request(
        EMBED_URL, data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["data"][0]["embedding"]


def _topk(qvec: list[float], k: int) -> list[dict[str, Any]]:
    sql = (
        "SELECT id, slug, chunk_idx, embedding <=> %s::vector AS dist, text "
        "FROM blog_chunks ORDER BY embedding <=> %s::vector LIMIT %s"
    )
    qvec_str = json.dumps(qvec)
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, (qvec_str, qvec_str, k))
        rows = cur.fetchall()
    return [
        {"id": r[0], "slug": r[1], "chunk_idx": r[2], "dist": float(r[3]), "text": r[4]}
        for r in rows
    ]


def _rerank(question: str, hits: list[dict], top_k: int) -> list[dict]:
    if not NGC_API_KEY:
        raise RuntimeError(
            "NGC_API_KEY not set — rerank=true requires the hosted NeMo Retriever "
            "reranker. Source ~/.nim/secrets.env with `set -a` before launching."
        )
    body = json.dumps({
        "model": RERANK_MODEL,
        "query": {"text": question},
        "passages": [{"text": h["text"]} for h in hits],
    }).encode()
    req = urllib.request.Request(RERANK_URL, data=body, headers={
        "Authorization": f"Bearer {NGC_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        rankings = json.loads(r.read())["rankings"]
    out = []
    for entry in rankings[:top_k]:
        h = dict(hits[entry["index"]])
        h["rerank_logit"] = entry["logit"]
        out.append(h)
    return out


def _trim(text: str, words: int) -> str:
    parts = text.split()
    return text if len(parts) <= words else " ".join(parts[:words]) + " …"


def _retrieve(query: str, top_k: int, rerank: bool) -> list[dict]:
    qvec = _embed(query)
    pool = _topk(qvec, max(top_k, 20) if rerank else top_k)
    if rerank:
        return _rerank(query, pool, top_k)
    return pool[:top_k]


SYS_PROMPT = (
    "You are a careful assistant answering questions about the ai-field-notes "
    "project (articles by Manav Sehgal on running AI locally on the NVIDIA "
    "DGX Spark). Answer using ONLY the provided context passages, each "
    "labeled with its source article slug and chunk index like "
    "[article-slug #N]. Answer concisely and concretely. Cite the "
    "passages you used in a trailing line: 'Sources: [slug #N, slug #N]'. "
    "If the context does not contain the answer, reply with exactly one "
    "sentence: 'The provided context does not contain the answer.'"
)


def _generate(question: str, contexts: list[dict], max_tokens: int) -> dict:
    parts = [
        f"[{h['slug']} #{h['chunk_idx']}]\n{_trim(h['text'], CHUNK_WORD_BUDGET)}"
        for h in contexts
    ]
    user = (
        f"Context passages:\n\n{chr(10).join(parts)}\n\n"
        f"Question: {question}\n\nAnswer:"
    )
    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYS_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        LLM_URL, data=body,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(
            f"NIM HTTP {e.code}: {detail}. The 8B has an 8192-token context "
            "ceiling; if this is HTTP 400, try a smaller top_k or shorter chunks."
        ) from None
    return {
        "text": resp["choices"][0]["message"]["content"].strip(),
        "wall_s": round(time.time() - t0, 3),
        "prompt_tokens": resp.get("usage", {}).get("prompt_tokens"),
        "completion_tokens": resp.get("usage", {}).get("completion_tokens"),
    }


@mcp.tool(
    description=(
        "Semantic search over Manav's ai-field-notes blog corpus (articles on "
        "running AI locally on the NVIDIA DGX Spark). Returns top-k chunks "
        "with slug, chunk index, and prose. Use this to ground answers in the "
        "blog, find related articles, or pull verbatim excerpts. Set "
        "rerank=true (default) for high-precision retrieval; rerank=false is "
        "naive cosine and is faster but less accurate."
    ),
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
def search_blog(query: str, top_k: int = 5, rerank: bool = True) -> dict:
    if top_k < 1 or top_k > 20:
        raise ValueError("top_k must be between 1 and 20")
    t0 = time.time()
    hits = _retrieve(query, top_k, rerank)
    return {
        "query": query,
        "rerank": rerank,
        "wall_s": round(time.time() - t0, 3),
        "hits": [
            {
                "slug": h["slug"],
                "chunk_idx": h["chunk_idx"],
                "dist": round(h["dist"], 4),
                "rerank_logit": round(h.get("rerank_logit", 0.0), 4) if rerank else None,
                "text": h["text"],
            }
            for h in hits
        ],
    }


@mcp.tool(
    description=(
        "Ask a question of Manav's ai-field-notes blog corpus. Retrieves top-k "
        "chunks (default 3), optionally reranks (default true), and generates "
        "a grounded answer with NIM Llama 3.1 8B running locally on the Spark. "
        "Returns the answer text plus the cited sources and wall-clock latency. "
        "Use this when you want a synthesized answer rather than raw chunks."
    ),
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
def ask_blog(
    question: str,
    top_k: int = 3,
    rerank: bool = True,
    max_tokens: int = 256,
) -> dict:
    if top_k < 1 or top_k > 5:
        raise ValueError("top_k must be between 1 and 5 (NIM 8192-token ceiling)")
    if max_tokens < 16 or max_tokens > 1024:
        raise ValueError("max_tokens must be between 16 and 1024")
    t_total = time.time()
    hits = _retrieve(question, top_k, rerank)
    gen = _generate(question, hits, max_tokens)
    return {
        "question": question,
        "answer": gen["text"],
        "sources": [
            {"slug": h["slug"], "chunk_idx": h["chunk_idx"]} for h in hits
        ],
        "rerank": rerank,
        "wall_s": round(time.time() - t_total, 3),
        "generate_wall_s": gen["wall_s"],
        "prompt_tokens": gen["prompt_tokens"],
        "completion_tokens": gen["completion_tokens"],
    }


@mcp.tool(
    description=(
        "List every article in the ai-field-notes blog corpus with slug, chunk "
        "count, and total word count. Useful as a discovery surface — call "
        "this first if you want to know what's in the Second Brain before "
        "searching."
    ),
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
def list_articles() -> dict:
    sql = (
        "SELECT slug, COUNT(*) AS chunks, "
        "  SUM(array_length(regexp_split_to_array(text, E'\\\\s+'), 1)) AS words "
        "FROM blog_chunks GROUP BY slug ORDER BY slug"
    )
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return {
        "count": len(rows),
        "articles": [
            {"slug": r[0], "chunks": r[1], "words": int(r[2] or 0)} for r in rows
        ],
    }


@mcp.tool(
    description=(
        "Fetch a single chunk verbatim by (slug, chunk_idx). Use this after "
        "search_blog or ask_blog to read the full passage when the trimmed "
        "search hit isn't enough context."
    ),
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
def read_article_chunk(slug: str, chunk_idx: int) -> dict:
    sql = "SELECT text FROM blog_chunks WHERE slug = %s AND chunk_idx = %s"
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, (slug, chunk_idx))
        row = cur.fetchone()
    if row is None:
        raise ValueError(
            f"No chunk found for slug={slug!r} chunk_idx={chunk_idx}. "
            "Call list_articles() to see available slugs, or search_blog() "
            "to discover relevant chunk indices."
        )
    return {"slug": slug, "chunk_idx": chunk_idx, "text": row[0]}


if __name__ == "__main__":
    mcp.run()
