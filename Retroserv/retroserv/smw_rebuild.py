"""Replace guessed room titles with the names the overworld actually stores."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path

from PIL import Image

from .assistant import AssistantChange, AssistantFile, AssistantRoom
from .smw_courses import room_titles
from .smw_foreground import _palette, render_opening_foreground
from .smw_level import level_catalog, read_level
from .smw_map_check import CheckProgress


def rebuild_from_rom(rom, assistant: AssistantFile | None = None, maps=(),
                     progress=lambda _update: None, findings=(),
                     screenshot_folder: str = '') -> AssistantFile:
    """Name every horizontal room the overworld or a screen exit can name."""
    progress(CheckProgress('Reading course names from the ROM'))
    titles = room_titles(rom)
    progress(CheckProgress('Naming rooms opened by a screen exit', 1, 2))
    urls = _unique_urls(maps)
    used = Counter(_norm(title) for title in titles.values())
    rooms = {}
    for label, key in level_catalog(rom):
        ident = label.split('  ', 1)[0]
        title = titles.get(str(key))
        url = urls.get(_norm(title)) if title and used[_norm(title)] == 1 else None
        rooms[str(key)] = AssistantRoom(ident, title, url)
    kept = tuple(change for change in (assistant.changes if assistant else ()) if change.kind != 'finding')
    observed = _foreground_finding(rom, screenshot_folder)
    shot = _shot_finding(rom, screenshot_folder)
    report = AssistantFile(
        sha256(rom.data).hexdigest(),
        assistant.source if assistant else '',
        len(maps) or (assistant.source_map_count if assistant else 0),
        rooms,
        kept + (observed,) + ((shot,) if shot is not None else ()) + tuple(findings),
    )
    named = sum(room.title is not None for room in rooms.values())
    progress(CheckProgress(f'Named {named} of {len(rooms)} rooms from the ROM', 2, 2))
    return report


def foreground_report(rom, level_id: int = 0x105, screenshot_folder: str = '') -> str:
    """A text report Cursor can read. It names differences. It does not edit pixels."""
    level = read_level(rom, level_id)
    header = bytes.fromhex(level.layer1.header_hex)
    rendered = render_opening_foreground(rom, level_id)
    counts = Counter(tile.map16_id for tile in rendered.tiles.values())
    shown = _palette(rom, header)[0x64]
    lines = [
        f'key: {level_id}',
        f'Room ${level_id:03X}, {level.screen_count} screens.',
        f'Map16 $11E item boxes: {counts[0x11E]} cells.',
        f'Map16 $106 rope row: {counts[0x106]} cells.',
        f'The level display uses RGB {shown} for palette row 6 color 4.',
        'Describe what is visible. Do not propose a replacement color or a tile address.',
    ]
    shot = _screenshot(screenshot_folder, level_id)
    if shot is not None:
        differences = left_screen_differences(rendered, shot)
        lines.append(f'Left screen differs in {len(differences)} cells.')
        lines.extend(differences[:12])
    return '\n'.join(lines) + '\n'


def left_screen_differences(rendered, shot: Image.Image) -> list[str]:
    """Cells on the left screen whose opaque pixels differ from a Snes9x shot."""
    reference = shot.convert('RGB')
    width = min(256, rendered.image.width, reference.width)
    height = min(rendered.image.height, reference.height)
    lines = []
    for y in range(height // 16):
        for x in range(width // 16):
            tile = rendered.tiles.get((x, y))
            if tile is None or not _cell_differs(rendered.image, reference, x, y):
                continue
            kind = 'object' if tile.source.kind == 'object' else tile.source.kind
            lines.append(
                f'differs: {x},{y} Map16 ${tile.map16_id:03X} {kind} ${tile.source.type_id:02X}')
    return lines


def _cell_differs(rendered: Image.Image, reference: Image.Image, x: int, y: int) -> bool:
    for dy in range(16):
        for dx in range(16):
            pixel = rendered.getpixel((x * 16 + dx, y * 16 + dy))
            if pixel[3] == 0:
                continue
            other = reference.getpixel((x * 16 + dx, y * 16 + dy))
            if max(abs(channel - other[index]) for index, channel in enumerate(pixel[:3])) > 2:
                return True
    return False


def _screenshot(folder: str, level_id: int) -> Image.Image | None:
    if not folder:
        return None
    path = Path(folder) / f'${level_id:03X}.png'
    if not path.is_file():
        return None
    try:
        return Image.open(path)
    except OSError:
        return None


def _foreground_finding(rom, screenshot_folder: str = '') -> AssistantChange:
    text = foreground_report(rom, screenshot_folder=screenshot_folder)
    summary = ' '.join(text.splitlines()[1:4])
    return AssistantChange('rom-finding-261', 'finding', summary[:240], '261', {'provider': 'rom'})


def _shot_finding(rom, screenshot_folder: str) -> AssistantChange | None:
    text = foreground_report(rom, screenshot_folder=screenshot_folder)
    differences = [line for line in text.splitlines() if line.startswith('differs:')]
    if not differences:
        return None
    summary = ' '.join(differences[:3])
    return AssistantChange('shot-finding-261', 'finding', summary[:240], '261', {'provider': 'snes9x'})


def _unique_urls(maps) -> dict[str, str]:
    grouped: dict[str, list[str]] = {}
    for course in maps:
        grouped.setdefault(_norm(course.title), []).append(course.url)
    return {title: urls[0] for title, urls in grouped.items() if len(urls) == 1 and urls[0]}


def _norm(title: str) -> str:
    return ' '.join(title.replace('’', "'").replace('‘', "'").casefold().split())
