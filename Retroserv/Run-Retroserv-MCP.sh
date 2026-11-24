#!/usr/bin/env bash
# Cursor MCP stdio server: never print startup/status to stdout.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -L)"
exec "$ROOT/scripts/run.sh" mcp
