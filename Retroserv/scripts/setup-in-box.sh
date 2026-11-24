#!/usr/bin/env bash
# Runs inside Fedora Distrobox, not on the immutable host.
set -Eeuo pipefail
ROOT="${1:?missing Retroserv directory}"
if [[ ! -f "$ROOT/pyproject.toml" ]]; then
  echo "ERROR: Retroserv not visible from Distrobox at $ROOT" >&2; exit 2
fi
if ! command -v dnf >/dev/null 2>&1; then
  echo 'ERROR: Expected Fedora Distrobox with dnf.' >&2; exit 2
fi
sudo dnf install -y python3 python3-pip python3-tkinter
python3 - <<'PYVER'
import sys, tkinter
if sys.version_info < (3, 11):
    raise SystemExit('ERROR: Retroserv needs Python >= 3.11')
PYVER
python3 -m venv "$ROOT/.venv-distrobox"
"$ROOT/.venv-distrobox/bin/python" -m pip install -e "$ROOT[test]"
"$ROOT/.venv-distrobox/bin/python" -m pytest -q "$ROOT/tests"
