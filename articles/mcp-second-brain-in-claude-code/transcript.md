# Transcript — mcp-second-brain-in-claude-code

Session date: 2026-04-24. Goal: close the Second Brain track (S4) by wrapping
the existing RAG chain (NIM Embed → pgvector → hosted Nemotron Reranker →
NIM Llama 3.1 8B) as four MCP tools and registering them in Claude Code.

## Decisions (in order)

1. **Python over TypeScript.** The rest of the Second Brain stack is Python
   (`retrieve.py`, `generate_nim.py`, `grade.py`, `ingest_blog.py`). FastMCP
   is a clean fit. Same patterns as the eval harness.

2. **psycopg over `docker exec psql`.** First version of `server.py` reused
   the `subprocess.run(["docker", "exec", ...])` pattern from `retrieve.py`.
   That's a single-shot pattern; the MCP server is long-lived. Switched to a
   plain `psycopg.connect("host=127.0.0.1 port=5432 dbname=vectors …")` —
   one connection per tool call, no shell quoting, no docker plumbing in the
   hot path. The pgvector container already publishes 5432 to the host.

3. **Four tools, not nine.** Considered exposing one tool per backing
   service (embed_query, pgvector_topk, rerank, nim_complete). Walked back —
   the agent doesn't want "complete API coverage", it wants a small surface
   it can compose. Four tools landed:
   - `search_blog(query, top_k, rerank)` — chunks
   - `ask_blog(question, top_k, rerank, max_tokens)` — grounded answer
   - `list_articles()` — discovery
   - `read_article_chunk(slug, chunk_idx)` — verbatim follow-up

4. **stdio transport.** Streaming HTTP would have required deciding where
   to host (port? socket? service unit?). stdio sidesteps all of it — the
   server is a child process of the Claude Code session, lifecycle bound.

5. **NGC API key in env, not in `.mcp.json`.** Sourcing `~/.nim/secrets.env`
   from the launcher means the secret never appears in any file under git
   (the `.mcp.json` is committed to the repo). `set -a` is the part that
   was easy to get wrong — bare `source` doesn't export to children.

6. **Top-3, 500-word trim per chunk.** `ask_blog` defaults to top_k=3 and
   trims each retrieved chunk to 500 words before generation. Both choices
   come from the project memory note about the NIM 8192-token ceiling that
   bit the eval harness as an opaque HTTP 400. Validated in advance instead
   of failing in the field.

## Build steps

```bash
mkdir -p /home/nvidia/second-brain-mcp
cd /home/nvidia/second-brain-mcp
python3 -m venv .venv
.venv/bin/pip install --quiet 'mcp[cli]' psycopg[binary]
# wrote server.py, launch.sh, requirements.txt
chmod +x launch.sh
```

Smoke test of the stdio handshake:

```bash
$ python3 demo_trace.py
server: {'name': 'second-brain', 'version': '1.27.0'}
tools: ['search_blog', 'ask_blog', 'list_articles', 'read_article_chunk']
  ✓ list_articles (0.021s) → {12 articles, 61 chunks}
  ✓ search_blog (2.498s) → {ranked chunks, all from pgvector-on-spark for the unified-mem query}
  ✓ ask_blog (6.459s) → "24.8 tokens per second … 8.9 seconds wall …"
  ✓ ask_blog (7.330s) → rerank-fusion comparison answer
  ✓ ask_blog (3.127s) → "The provided context does not contain the answer." (correct refusal)
  ✓ read_article_chunk (0.006s) → naive-rag-on-spark #0 (7312 chars)
```

Full JSON-RPC trace at `evidence/demo_trace.jsonl`.

## Registration

`.mcp.json` at repo root:

```json
{
  "mcpServers": {
    "second-brain": {
      "command": "/home/nvidia/second-brain-mcp/launch.sh",
      "args": [],
      "env": {}
    }
  }
}
```

Verified visible to the CLI:

```
$ claude mcp list
…
playwright: npx -y @playwright/mcp@latest …  - ✓ Connected
second-brain: /home/nvidia/second-brain-mcp/launch.sh  - ✓ Connected
```

## End-to-end demo through Claude Code

```bash
echo "How fast did the first NIM inference run on the Spark, and was that \
latency-bound or throughput-bound? Cite the article slug." \
  | claude -p \
      --output-format stream-json \
      --include-partial-messages --verbose \
      --permission-mode bypassPermissions \
      --allowedTools 'mcp__second-brain__list_articles' \
                     'mcp__second-brain__search_blog' \
                     'mcp__second-brain__ask_blog' \
                     'mcp__second-brain__read_article_chunk'
```

Result (parsed from `evidence/claude_code_stream.jsonl`):

- 18.5 s wall, 3 turns, $0.32 in Claude API tokens
- Agent called `ask_blog` first (6.4 s server-side) → got grounded answer
- Then called `search_blog` to verify and pull verbatim passages
- Final assistant text named the right number (24.8 t/s) and the right
  citation (`nim-first-inference-dgx-spark`)

## Gotchas

- **First version used `docker exec psql`.** That's the same pattern the
  eval scripts use, and the docker-exec call got denied at the harness
  layer in the same session. Switched to psycopg over loopback — better
  design *and* unblocked the build.

- **Corpus is one article behind.** `blog_chunks` has 12 articles, the
  state at the Ragas eval ingest. Articles published since (the gpu-sizing
  piece, this MCP article itself) aren't in pgvector yet. `ask_blog`
  questions about them refuse correctly. Re-ingest is one `ingest_blog.py`
  run away.

- **NIM 8192-token ceiling.** Top-3 with 500-word trim per chunk leaves
  comfortable headroom (~3000 prompt tokens for typical questions). Same
  budget the eval harness landed on after the original HTTP 400.

- **`set -a` matters.** First launcher used bare `source ~/.nim/secrets.env`
  and `NGC_API_KEY` did not propagate to the python child — rerank tool
  silently failed. `set -a && source && set +a` is the working incantation
  and is the only non-obvious line in `launch.sh`.

## Why this article matters for the arc

This is the S4 closer for the Second Brain track. The chain has been
working since S3; this article is what makes it *callable* from the
agent that lives in front of the user every day. After this, all three
arcs — Second Brain (done), LLM Wiki (W1 next), Autoresearch (A1
waiting) — share the same MCP-as-surface pattern.
