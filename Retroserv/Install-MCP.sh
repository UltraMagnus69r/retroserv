#!/usr/bin/env bash
# Install official Python MCP SDK in selected Fedora environment.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -L)"
exec "$ROOT/scripts/run.sh" install-mcp
