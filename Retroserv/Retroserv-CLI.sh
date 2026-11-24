#!/usr/bin/env bash
# Fedora CLI launcher (native Workstation or Distrobox on Atomic systems).
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -L)"
exec "$ROOT/scripts/run.sh" cli "$@"
