"""Build a game-neutral inspection snapshot from the SMW level adapter."""
from __future__ import annotations

from hashlib import sha256

from .assistant import apply_snapshot, load_for_rom
from .inspection import (
    FORMAT, InspectionCell, InspectionGuide, InspectionMarker, InspectionRecord,
    InspectionSnapshot, InspectionSurface,
)
from .rom import RomImage
from .smw import recognized
from .smw_background import place_background
from .smw_foreground import CELL_PIXELS, OpeningForeground, foreground_supported, render_opening_foreground
from .smw_level import LEVEL_NAMES, SMWLevel, level_catalog, read_level

OPENING_LEVEL = 0x105
LEGEND = 'Placement anchors • Green circles: objects • Gold circles: sprites'
KIND_LABELS = {'object': 'Object', 'extended_object': 'Extended object', 'sprite': 'Sprite',
               'screen_jump': 'Screen jump', 'screen_exit': 'Screen exit'}


def rooms(rom=None) -> tuple[tuple[str, int], ...]:
    """Rooms for the level list. With a verified ROM, every distinct horizontal level."""
    if rom is not None and recognized(rom):
        return level_catalog(rom)
    return tuple((f'${number:03X}  {name}', number) for number, name in LEVEL_NAMES.items())


def record_id(offset: int) -> str:
    return str(offset)


def snapshot_from_level(level: SMWLevel, surface: OpeningForeground | None, *,
                        cartridge_sha256: str) -> InspectionSnapshot:
    records = []
    markers = []
    for record in level.layer1.records + level.sprites.records:
        identity = record_id(record.offset)
        records.append(InspectionRecord(identity, _label(record), _detail(record),
                                        record.offset, record.raw_hex))
        if record.x is not None and record.y is not None and record.kind in ('object', 'extended_object', 'sprite'):
            shape = 'dot' if record.kind == 'sprite' else 'square'
            markers.append(InspectionMarker(identity, record.x, record.y, shape))
    object_count = sum(record.kind in ('object', 'extended_object') for record in level.layer1.records)
    rendered = _surface(surface) if surface is not None else None
    return InspectionSnapshot(
        FORMAT, 'snes', 'smw-usa-v1.0', f'${level.level_id:03X}', level.name, cartridge_sha256,
        level.source_name, level.copier_header_size,
        f'{level.screen_count} screens   •   {object_count} objects'
        f'   •   {len(level.sprites.records)} sprite records',
        LEGEND, f'smw-{level.level_id:03x}.json',
        level.screen_count * level.block_columns, level.block_rows, level.block_columns,
        foreground_supported(level),
        tuple(InspectionGuide(screen * level.block_columns, f'Screen ${screen:02X}')
              for screen in range(level.screen_count)),
        tuple(records), tuple(markers), rendered)


def inspect_level(rom: RomImage, level_id: int = OPENING_LEVEL, *,
                  include_surface: bool = True, assistant=None) -> InspectionSnapshot:
    """Read one supported SMW room, including its static foreground when requested."""
    cartridge_sha256 = sha256(rom.data).hexdigest()
    if assistant is None:
        assistant = load_for_rom(cartridge_sha256, rom.path)
    level = read_level(rom, level_id)
    surface = None
    if include_surface and foreground_supported(level):
        foreground = render_opening_foreground(rom, level_id, assistant)
        surface = OpeningForeground(
            place_background(rom, level, foreground.image),
            foreground.tiles, foreground.columns, foreground.rows)
    snapshot = snapshot_from_level(level, surface, cartridge_sha256=cartridge_sha256)
    return apply_snapshot(snapshot, assistant, str(level_id))


def _label(record) -> str:
    return f'{KIND_LABELS[record.kind]} ${record.type_id:02X}'


def _detail(record) -> str:
    screen = f'Screen ${record.screen:02X}'
    if record.x is not None and record.y is not None:
        return f'{screen} · {record.x}, {record.y}'
    if record.exit_destination_byte is not None:
        route = 'Secondary' if record.secondary_exit else 'Destination'
        return f'{screen} · {route} ${record.exit_destination_byte:02X}'
    return screen


def _surface(foreground: OpeningForeground) -> InspectionSurface:
    cells = {(x, y): InspectionCell(record_id(tile.source.offset), f'Map16 ${tile.map16_id:03X}')
             for (x, y), tile in foreground.tiles.items()}
    return InspectionSurface(foreground.image, CELL_PIXELS, foreground.columns, foreground.rows, cells)
