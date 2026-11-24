"""A per-cartridge memory of names and corrections. The shell applies the file.

The file is not a second copy of a level. A room entry may name that room when
one outside map matched its picture and the others did not. A change entry
tells a game adapter what to do differently; adapters apply the kinds they
know, and this module does not interpret those kinds.
"""
from __future__ import annotations

import fcntl
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

FORMAT = 'retroserv-assistant-v1'


@dataclass(frozen=True)
class AssistantCandidate:
    title: str
    url: str
    score: float

    def to_dict(self) -> dict:
        return {'title': self.title, 'url': self.url, 'score': round(float(self.score), 4)}


@dataclass(frozen=True)
class AssistantRoom:
    subject: str
    title: str | None = None
    map_url: str | None = None
    candidates: tuple[AssistantCandidate, ...] = ()

    def to_dict(self) -> dict:
        return {'subject': self.subject, 'title': self.title, 'map_url': self.map_url,
                'candidates': [candidate.to_dict() for candidate in self.candidates]}


@dataclass(frozen=True)
class AssistantChange:
    id: str
    kind: str
    summary: str
    target: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {'id': self.id, 'kind': self.kind, 'summary': self.summary,
                'target': self.target, 'data': self.data}


@dataclass(frozen=True)
class AssistantFile:
    rom_sha256: str
    source: str = ''
    source_map_count: int = 0
    rooms: dict[str, AssistantRoom] = field(default_factory=dict)
    changes: tuple[AssistantChange, ...] = ()
    format: str = FORMAT

    def to_dict(self) -> dict:
        return {
            'format': self.format,
            'rom_sha256': self.rom_sha256,
            'source': self.source,
            'source_map_count': self.source_map_count,
            'rooms': {key: room.to_dict() for key, room in self.rooms.items()},
            'changes': [change.to_dict() for change in self.changes],
        }


def sidecar_path(rom_path: Path) -> Path:
    """`Game.sfc` keeps its assistant file as `Game-assistant.json` in the same folder."""
    rom_path = Path(rom_path)
    return rom_path.with_name(rom_path.stem + '-assistant.json')


def _legacy_path(rom_sha256: str) -> Path:
    root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    return root / 'retroserv' / 'assistants' / f'{rom_sha256}.json'


def read_assistant(path: Path) -> AssistantFile:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'Could not read the assistant file {path}') from exc
    if not isinstance(payload, dict) or payload.get('format') != FORMAT:
        raise ValueError(f'{path} is not a {FORMAT} file')
    sha = payload.get('rom_sha256')
    if not isinstance(sha, str) or len(sha) != 64:
        raise ValueError(f'{path} has no cartridge hash')
    rooms = {}
    for key, raw in payload.get('rooms', {}).items():
        if not isinstance(raw, dict):
            continue
        candidates = tuple(
            candidate for item in raw.get('candidates', [])
            if (candidate := _candidate(key, item)) is not None
        )
        title = raw.get('title') or None
        rooms[str(key)] = AssistantRoom(str(raw.get('subject') or key), title,
                                        raw.get('map_url') or None, candidates)
    changes = []
    for raw in payload.get('changes', []):
        if isinstance(raw, dict) and raw.get('id') and raw.get('kind'):
            changes.append(AssistantChange(
                str(raw['id']), str(raw['kind']), str(raw.get('summary') or ''),
                str(raw.get('target') or '*'), dict(raw.get('data') or {})))
    return AssistantFile(sha, str(payload.get('source') or ''),
                         int(payload.get('source_map_count') or 0), rooms, tuple(changes))


def _candidate(room_key: str, item) -> AssistantCandidate | None:
    if not isinstance(item, dict) or not item.get('title') or not item.get('url'):
        return None
    score = item.get('score')
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError(f'Room {room_key} has a map score that is not a number')
    return AssistantCandidate(str(item['title']), str(item['url']), float(score))


def write_assistant(assistant: AssistantFile, path: Path) -> Path:
    """Replace the file in one step so a crash cannot leave a half-written assistant."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(assistant.to_dict(), indent=2) + '\n'
    temporary = path.with_name(path.name + '.tmp')
    lock_path = path.with_name(path.name + '.lock')
    with lock_path.open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            temporary.write_text(payload, encoding='utf-8')
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
    return path


def bundled_assistants() -> tuple[AssistantFile, ...]:
    folder = Path(__file__).with_name('assistants')
    if not folder.is_dir():
        return ()
    return tuple(read_assistant(path) for path in sorted(folder.glob('*.json')))


def merge_assistant(base: AssistantFile | None, overlay: AssistantFile | None) -> AssistantFile | None:
    """Keep the overlay's names and source. Changes in the overlay replace the same id."""
    if overlay is None:
        return base
    if base is None or base.rom_sha256 != overlay.rom_sha256:
        return overlay
    changes = {change.id: change for change in base.changes}
    changes.update({change.id: change for change in overlay.changes})
    return AssistantFile(overlay.rom_sha256, overlay.source or base.source,
                         overlay.source_map_count or base.source_map_count,
                         overlay.rooms or base.rooms, tuple(changes.values()))


def _matching(path: Path, rom_sha256: str) -> AssistantFile | None:
    if not path.is_file():
        return None
    loaded = read_assistant(path)
    return loaded if loaded.rom_sha256 == rom_sha256 else None


def load_for_rom(rom_sha256: str, rom_path: Path | None = None) -> AssistantFile | None:
    """The file beside the ROM wins. An older hash-named file is used only when that one is absent."""
    bundled = next((item for item in bundled_assistants() if item.rom_sha256 == rom_sha256), None)
    stored = None
    if rom_path is not None:
        stored = _matching(sidecar_path(rom_path), rom_sha256)
        if stored is None:
            stored = _matching(_legacy_path(rom_sha256), rom_sha256)
    return merge_assistant(bundled, stored)


def save_for_rom(assistant: AssistantFile, rom_path: Path) -> Path:
    return write_assistant(assistant, sidecar_path(rom_path))


def apply_room_labels(rooms, assistant: AssistantFile | None):
    """Replace a room's name when the assistant file has accepted one."""
    if assistant is None:
        return tuple(rooms)
    labeled = []
    for label, key in rooms:
        room = assistant.rooms.get(str(key))
        if room is None or not room.title:
            labeled.append((label, key))
            continue
        head, separator, trailer = label.partition('  ·  ')
        ident = head.split('  ', 1)[0]
        renamed = f'{ident}  {room.title}'
        if separator:
            renamed += f'  ·  {trailer}'
        labeled.append((renamed, key))
    return tuple(labeled)


def closest_text(room: AssistantRoom | None) -> str:
    if room is None or not room.candidates:
        return ''
    listed = ', '.join(f'{candidate.title} ({candidate.score:.2f})' for candidate in room.candidates[:3])
    if room.title:
        return f'Matched {room.title}.'
    return f'No map was close enough to name this room. Closest: {listed}'


def apply_snapshot(snapshot, assistant: AssistantFile | None, room_key: str):
    if assistant is None:
        return snapshot
    room = assistant.rooms.get(str(room_key))
    name = room.title or snapshot.name if room is not None else snapshot.name
    summary = snapshot.summary
    note = closest_text(room)
    if note:
        summary = f'{summary}   •   {note}'
    notes = [change.summary for change in assistant.changes
             if change.target == str(room_key) and change.summary]
    if notes:
        summary = f'{summary}   •   {" ".join(notes)}'
    if name == snapshot.name and summary == snapshot.summary:
        return snapshot
    from dataclasses import replace
    return replace(snapshot, name=name, summary=summary)
