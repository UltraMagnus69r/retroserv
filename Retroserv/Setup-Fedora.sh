#!/usr/bin/env bash
# Fedora Workstation/KDE/Spins: native virtualenv.
# Fedora Atomic/Bazzite: Distrobox virtualenv, no host RPM layering.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -L)"
source "$ROOT/scripts/common.sh"

if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  cat <<'HELP'
Usage: ./Setup-Fedora.sh [--check]
  --check   Display chosen installation mode and dependencies; do not install.

Default: Fedora Workstation/KDE/Spins -> native virtualenv;
         Fedora Atomic/Bazzite -> Distrobox (no RPM layering).
Override: RETROSERV_MODE=native|distrobox ./Setup-Fedora.sh
HELP
  exit 0
fi
if [[ $# -gt 1 || ( $# -eq 1 && "${1:-}" != --check ) ]]; then
  echo 'ERROR: Only --check or --help are supported.' >&2
  exit 2
fi
MODE="$(retroserv_mode)"
if [[ "${1:-}" == --check ]]; then
  echo "Retroserv directory: $ROOT"
  echo "Installation mode: $MODE"
  for cmd in python3 dnf sudo distrobox podman; do
    if command -v "$cmd" >/dev/null 2>&1; then echo "  $cmd: found"; else echo "  $cmd: missing"; fi
  done
  echo "  desktop display: ${DISPLAY:-${WAYLAND_DISPLAY:-not set}}"
  if [[ "$MODE" == native ]]; then
    python3 -c 'import sys; print("  Python:", sys.version.split()[0]); import tkinter; print("  Tkinter: installed")' 2>&1 || true
  fi
  exit 0
fi

if [[ "$MODE" == native ]]; then
  if ! command -v dnf >/dev/null 2>&1; then
    echo 'ERROR: Native setup currently supports Fedora systems with dnf. Use RETROSERV_MODE=distrobox where available.' >&2
    exit 2
  fi
  # Only use host RPM installation where necessary. Never install system-wide Python packages via pip.
  if ! python3 -c 'import tkinter, pip, venv' >/dev/null 2>&1; then
    if ! command -v sudo >/dev/null 2>&1; then
      echo 'ERROR: Install Python, pip and Tkinter with dnf or enable sudo.' >&2
      exit 2
    fi
    echo 'Installing required Fedora system packages (may request sudo password)...'
    sudo dnf install -y python3 python3-pip python3-tkinter
  fi
  python3 - <<'PYVER'
import sys
if sys.version_info < (3, 11):
    raise SystemExit('ERROR: Retroserv requires Python >= 3.11')
import tkinter
PYVER
  echo 'Creating/updating Retroserv native virtual environment...'
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/python" -m pip install -e "$ROOT[test]"
  "$ROOT/.venv/bin/python" -m pytest -q "$ROOT/tests"
else
  retroserv_require_home
  if ! command -v distrobox >/dev/null 2>&1 || ! command -v podman >/dev/null 2>&1; then
    echo 'ERROR: Atomic setup needs Distrobox and Podman on the host.' >&2
    echo 'Install Distrobox/Podman using your distribution documentation, then rerun.' >&2
    echo 'Alternatively: RETROSERV_MODE=native ./Setup-Fedora.sh (requires host Python/Tk).'
    exit 2
  fi
  BOX="${RETROSERV_DISTROBOX:-retroserv-dev}"
  IMAGE="${RETROSERV_FEDORA_IMAGE:-registry.fedoraproject.org/fedora-toolbox:44}"
  if podman container exists "$BOX"; then
    echo "Using existing Distrobox: $BOX"
  else
    echo "Creating Fedora Distrobox: $BOX from $IMAGE"
    distrobox create --yes --name "$BOX" --image "$IMAGE"
  fi
  distrobox enter --no-tty --name "$BOX" -- bash "$ROOT/scripts/setup-in-box.sh" "$ROOT"
fi
printf '%s\n' "$MODE" > "$ROOT/.retroserv-install-mode"
echo "Retroserv setup completed ($MODE). Start with: ./Start-Retroserv.sh"
