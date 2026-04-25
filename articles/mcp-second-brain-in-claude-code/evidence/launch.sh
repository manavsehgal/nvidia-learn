#!/usr/bin/env bash
# Launcher for the Second Brain MCP server.
# Sources NGC_API_KEY (needed for the hosted reranker) and exec's the venv
# Python at the FastMCP server. Claude Code invokes this via stdio.
set -eu
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$HOME/.nim/secrets.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$HOME/.nim/secrets.env"
  set +a
fi
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/server.py"
