"""Which assistant names rooms. Cursor is the first provider; the menu can grow."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

PROVIDERS = (
    ('picture', 'Picture match'),
    ('cursor', 'Cursor'),
)
DEFAULT_MODEL = 'composer-2.5'


@dataclass(frozen=True)
class AssistantSettings:
    provider: str = 'cursor'
    model: str = DEFAULT_MODEL
    screenshot_folder: str = ''

    def to_dict(self) -> dict:
        provider = self.provider if self.provider in dict(PROVIDERS) else 'cursor'
        return {
            'provider': provider,
            'model': self.model.strip() or DEFAULT_MODEL,
            'screenshot_folder': self.screenshot_folder.strip(),
        }


def config_directory() -> Path:
    root = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    return root / 'retroserv'


def load_settings(directory: Path | None = None) -> AssistantSettings:
    path = (directory if directory is not None else config_directory()) / 'assistant.json'
    if not path.is_file():
        return AssistantSettings()
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return AssistantSettings()
    if not isinstance(payload, dict):
        return AssistantSettings()
    provider = str(payload.get('provider') or 'cursor')
    if provider not in dict(PROVIDERS):
        provider = 'cursor'
    model = str(payload.get('model') or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    folder = str(payload.get('screenshot_folder') or '').strip()
    return AssistantSettings(provider, model, folder)


def save_settings(settings: AssistantSettings, directory: Path | None = None) -> Path:
    folder = directory if directory is not None else config_directory()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'assistant.json'
    path.write_text(json.dumps(settings.to_dict(), indent=2) + '\n', encoding='utf-8')
    return path


def key_path(directory: Path | None = None) -> Path:
    return (directory if directory is not None else config_directory()) / 'cursor-key'


def api_key(directory: Path | None = None) -> str:
    path = key_path(directory)
    if path.is_file():
        try:
            saved = path.read_text(encoding='utf-8').strip()
        except (OSError, UnicodeError):
            saved = ''
        if saved:
            return saved
    return os.environ.get('CURSOR_API_KEY', '').strip()


def save_api_key(key: str, directory: Path | None = None) -> None:
    path = key_path(directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key.strip() + '\n', encoding='utf-8')
    path.chmod(0o600)


def clear_api_key(directory: Path | None = None) -> None:
    path = key_path(directory)
    if path.is_file():
        path.unlink()
