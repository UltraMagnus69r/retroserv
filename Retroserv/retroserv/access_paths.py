"""Folders the local MCP tools are allowed to read and write.

ROM reads stay under the directories named in paths.json. Exports stay under
one directory. A path that resolves outside those folders is refused.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .desktop_paths import default_rom_directory


def config_directory() -> Path:
    root = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    return root / 'retroserv'


def data_directory() -> Path:
    root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    return root / 'retroserv'


def _paths_file(directory: Path | None) -> Path:
    return (directory if directory is not None else config_directory()) / 'paths.json'


def _load(directory: Path | None) -> dict:
    path = _paths_file(directory)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def rom_directories(directory: Path | None = None) -> tuple[Path, ...]:
    """Directories a tool may read a ROM from. The Desktop is the default."""
    listed = _load(directory).get('rom_directories')
    if isinstance(listed, list) and listed:
        return tuple(Path(str(item)).expanduser() for item in listed if str(item).strip())
    return (default_rom_directory(),)


def export_directory(directory: Path | None = None) -> Path:
    """The one directory a tool may write an export into."""
    chosen = _load(directory).get('export_directory')
    if isinstance(chosen, str) and chosen.strip():
        return Path(chosen).expanduser()
    return data_directory() / 'exports'


def require_rom_path(path: str, directory: Path | None = None) -> Path:
    return _require(path, rom_directories(directory), 'ROM folders')


def require_export_path(path: str, directory: Path | None = None) -> Path:
    return _require(path, (export_directory(directory),), 'the export folder')


def require_palette_path(path: str, directory: Path | None = None) -> Path:
    roots = rom_directories(directory) + (export_directory(directory),)
    return _require(path, roots, 'ROM folders or the export folder')


def _require(path: str, roots: tuple[Path, ...], label: str) -> Path:
    try:
        resolved = Path(path).expanduser().resolve()
    except OSError as exc:
        raise ValueError(f'Could not use {path}') from exc
    allowed = []
    for root in roots:
        try:
            folder = root.resolve()
        except OSError:
            continue
        allowed.append(folder)
        if resolved == folder or folder in resolved.parents:
            return resolved
    names = ', '.join(str(folder) for folder in allowed) or '(none configured)'
    raise ValueError(f'{resolved} is outside {label}: {names}')
