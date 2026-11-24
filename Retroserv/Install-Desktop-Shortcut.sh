#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -L)"
source "$ROOT/scripts/common.sh"
case "$(retroserv_mode)" in
  native) PY="$ROOT/.venv/bin/python" ;;
  distrobox) PY=python3 ;;
esac
if ! command -v "$PY" >/dev/null; then
  echo 'Run Retroserv setup first. The desktop shortcut installer also needs host Python 3.' >&2
  exit 2
fi
exec "$PY" - "$ROOT" <<'PY'
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import NamedTemporaryFile

root = Path(sys.argv[1])
home = Path.home()
data_home = Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share')
desktop = home / 'Desktop'
if shutil.which('xdg-user-dir'):
    desktop = Path(subprocess.check_output(['xdg-user-dir', 'DESKTOP'], text=True).rstrip('\n'))
# xdg-user-dir returns HOME when the desktop directory is disabled.
if desktop == home:
    desktop = home / 'Desktop'


def desktop_value(value):
    return value.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')


launcher = str(root / 'Start-Retroserv.sh')
exec_arg = '"' + ''.join(
    '%%' if c == '%' else '\\' + c if c in '\\"$`' else c for c in launcher
) + '"'
entry = f"""[Desktop Entry]
Type=Application
Name=Retroserv
Comment=Inspect SNES ROMs and extract graphics
Exec={desktop_value(exec_arg)}
Icon={desktop_value(str(root / 'retroserv/retroserv.png'))}
Terminal=false
Categories=Utility;
StartupWMClass=Retroserv
"""
for path in (data_home / 'applications/retroserv.desktop', desktop / 'Retroserv.desktop'):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as temp:
        temp.write(entry)
    staged = Path(temp.name)
    try:
        staged.chmod(0o755)
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)
    print(f'Installed {path}')
PY
