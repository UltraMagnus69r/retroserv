#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${1:?missing Retroserv path}"
PY="$ROOT/.venv-distrobox/bin/python"
if [[ ! -x "$PY" ]]; then
  echo 'ERROR: Distrobox environment missing. Run ./Setup-Fedora.sh first.' >&2; exit 2
fi
"$PY" -m pip install -e "$ROOT[mcp]"
"$PY" -c 'from mcp.server.fastmcp import FastMCP; import retroserv.mcp_server; print("MCP module imports successfully (Cursor handshake not yet verified).")'
