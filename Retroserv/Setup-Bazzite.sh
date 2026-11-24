#!/usr/bin/env bash
# Compatibility alias for older setup guides. Prefer Setup-Fedora.sh.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -L)"
RETROSERV_MODE="${RETROSERV_MODE:-distrobox}" exec "$ROOT/Setup-Fedora.sh" "$@"
