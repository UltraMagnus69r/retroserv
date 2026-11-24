#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${1:?missing Retroserv path}"
shift
PY="$ROOT/.venv-distrobox/bin/python"
if [[ ! -x "$PY" ]]; then
  echo 'ERROR: Distrobox environment missing. Run ./Setup-Fedora.sh first.' >&2; exit 2
fi
cd -- "$ROOT"
exec "$PY" -m retroserv "$@"
