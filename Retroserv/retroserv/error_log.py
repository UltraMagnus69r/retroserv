"""Write a short private error log under the Retroserv data folder."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from . import __version__
from .access_paths import data_directory


def log_directory() -> Path:
    return data_directory() / 'logs'


def write_error_log(exc: BaseException, *, context: str = '', directory: Path | None = None) -> Path | None:
    """Save the sentence, the run id, and the model. Returns the log path, or None if it cannot be written."""
    folder = directory if directory is not None else log_directory()
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    path = folder / f'Retroserv-error-{stamp}.log'
    lines = [
        f'Retroserv {__version__}',
        datetime.now().isoformat(timespec='seconds'),
        context,
        f'{type(exc).__name__}: {exc}',
    ]
    for label in ('status', 'run_id', 'model'):
        value = getattr(exc, label, None)
        if value:
            lines.append(f'{label}: {value}')
    try:
        folder.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            handle.write('\n'.join(lines).rstrip() + '\n')
    except (OSError, UnicodeError):
        return None
    return path
