#!/usr/bin/env bash
# Select host native or Distrobox Python, forwarding arguments unmodified.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -L)"
source "$ROOT/scripts/common.sh"
if [[ $# -eq 0 ]]; then echo 'ERROR: run.sh requires an entrypoint.' >&2; exit 2; fi
ENTRY="$1"; shift
MODE="$(retroserv_mode)"
if [[ "$MODE" == native ]]; then
  PY="$ROOT/.venv/bin/python"
  if [[ ! -x "$PY" ]]; then
    echo 'ERROR: Native environment missing. Run ./Setup-Fedora.sh first.' >&2; exit 2
  fi
  case "$ENTRY" in
    mcp) cd -- "$ROOT"; exec "$PY" -m retroserv.mcp_server ;;
    install-mcp) exec "$PY" -m pip install -e "$ROOT[mcp]" ;;
    cli) cd -- "$ROOT"; exec "$PY" -m retroserv "$@" ;;
    *) echo "ERROR: Unknown Retroserv entrypoint: $ENTRY" >&2; exit 2 ;;
  esac
else
  retroserv_require_home
  if ! command -v distrobox >/dev/null 2>&1; then
    echo 'ERROR: Distrobox missing. Run ./Setup-Fedora.sh first.' >&2; exit 2
  fi
  BOX="${RETROSERV_DISTROBOX:-retroserv-dev}"
  case "$ENTRY" in
    mcp) exec distrobox enter --no-tty --name "$BOX" -- bash "$ROOT/scripts/mcp-in-box.sh" "$ROOT" ;;
    install-mcp) exec distrobox enter --no-tty --name "$BOX" -- bash "$ROOT/scripts/install-mcp-in-box.sh" "$ROOT" ;;
    cli) exec distrobox enter --no-tty --name "$BOX" -- bash "$ROOT/scripts/launch-in-box.sh" "$ROOT" "$@" ;;
    *) echo "ERROR: Unknown Retroserv entrypoint: $ENTRY" >&2; exit 2 ;;
  esac
fi
