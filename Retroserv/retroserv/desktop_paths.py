"""Resolve Fedora/XDG Desktop locations without executing a shell.

Some Fedora desktops redirect XDG_DESKTOP_DIR away from ~/Desktop, and a few
configure it as $HOME. The ROM-open dialog should still start somewhere valid.
"""
from __future__ import annotations

import os
from pathlib import Path


def _xdg_user_path(value: str, home: Path) -> Path | None:
    """Expand only standard HOME-based or absolute XDG user-directory values."""
    raw = value.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        raw = raw[1:-1]
    for prefix in ("$HOME", "${HOME}"):
        if raw == prefix:
            return home
        if raw.startswith(prefix + "/"):
            return home / raw[len(prefix) + 1 :]
    if raw == "~":
        return home
    if raw.startswith("~/"):
        return home / raw[2:]
    if raw.startswith("/"):
        return Path(raw)
    return None


def default_rom_directory(*, home: Path | None = None, config_home: Path | None = None) -> Path:
    """Pick the existing XDG Desktop folder, otherwise ~/Desktop, then home.

    Does not create directories or write desktop configuration. At each Open
    ROM request, the dialog starts at this location regardless of CWD or the
    most recently opened ROM. The current user's file chooser may remember
    its own last directory, depending on the desktop's native dialog backend.
    """
    base = Path(home) if home is not None else Path.home()
    if config_home is None:
        config_root = Path(os.environ.get('XDG_CONFIG_HOME', str(base / '.config')))
    else:
        config_root = Path(config_home)
    config_file = config_root / 'user-dirs.dirs'
    try:
        for line in config_file.read_text(encoding='utf-8').splitlines():
            if line.lstrip().startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            if key.strip() != 'XDG_DESKTOP_DIR':
                continue
            candidate = _xdg_user_path(value, base)
            if candidate is not None and candidate.is_dir():
                return candidate
    except (OSError, UnicodeError):
        pass

    desktop = base / 'Desktop'
    if desktop.is_dir():
        return desktop
    return base
