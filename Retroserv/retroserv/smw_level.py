"""Read-only level data for horizontal levels in verified vanilla SMW.

The adapter preserves source order and bytes. Coordinates describe placement
anchors in 16-pixel units, before the game's object routines build Map16 tiles.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterator

from .rom import RomImage
from .smw import SMW_USA_V10_SHA256, lorom_to_pc, recognized

# SMWDisX banks 05 (pointers/header/Layer 1), 0D (screen commands), 02 (sprites).
LEVEL_NAMES = {0x105: "Yoshi's Island 1", 0x1CB: "Yoshi's Island 1 bonus room"}
LAYER1_POINTERS = 0x05E000
LAYER2_POINTERS = 0x05E600
SPRITE_POINTERS = 0x05EC00


@dataclass(frozen=True)
class LevelRecord:
    kind: str
    offset: int
    raw_hex: str
    screen: int
    type_id: int
    x: int | None = None
    y: int | None = None
    exit_destination_byte: int | None = None
    secondary_exit: bool = False
    sprite_extra_bits: int | None = None


@dataclass(frozen=True)
class LevelStream:
    address: int
    offset: int
    header_hex: str
    terminator_offset: int
    records: tuple[LevelRecord, ...]


@dataclass(frozen=True)
class SMWLevel:
    level_id: int
    name: str
    screen_count: int
    layer2_pointer: int
    layer1: LevelStream
    sprites: LevelStream
    source_name: str
    copier_header_size: int
    block_columns: int
    block_rows: int

    def to_dict(self) -> dict:
        return {
            'format': 'retroserv-smw-level-v1',
            'platform': 'snes',
            'game': 'smw-usa-v1.0',
            'cartridge_sha256': SMW_USA_V10_SHA256,
            'coordinate_unit_pixels': 16,
            'offset_basis': 'cartridge data (add copier_header_size for file offsets)',
            **asdict(self),
        }


def _records(data: bytes, start: int, limit: int, *, objects: bool) -> Iterator[tuple[int, bytes]]:
    """Yield complete records and the terminator within the source LoROM bank."""
    while start < limit:
        if data[start] == 0xFF:
            yield start, data[start:start + 1]
            return
        end = start + 3
        if end > limit:
            break
        first, second, third = data[start:end]
        if objects and (first & 0x60) == 0 and second < 0x10 and third == 0:
            end += 1  # A screen exit consumes its destination byte.
        if end > limit:
            break
        yield start, data[start:end]
        start = end
    raise ValueError('Level stream has no complete terminator in its LoROM bank')


def _read_stream(rom: RomImage, address: int, *, objects: bool) -> LevelStream:
    offset = lorom_to_pc(address)
    header_size = 5 if objects else 1
    limit = min(len(rom.data), ((offset // 0x8000) + 1) * 0x8000)
    if offset + header_size >= limit:
        raise ValueError('Level stream header leaves no room for records in its LoROM bank')
    header = rom.slice(offset, header_size)
    records = []
    screen = 0
    for at, raw in _records(rom.data, offset + header_size, limit, objects=objects):
        if len(raw) == 1:
            return LevelStream(address, offset, header.hex(' '), at, tuple(records))
        a, b, param = raw[:3]
        raw_hex = raw.hex(' ')
        if objects:
            screen += a >> 7
            object_id = ((a & 0x60) >> 1) | (b >> 4)
            if object_id == 0 and param == 0:
                record = LevelRecord('screen_exit', at, raw_hex, a & 0x1F, 0,
                                     # The game supplies the bank from the overworld context.
                                     exit_destination_byte=raw[3],
                                     secondary_exit=bool(b >> 1))
            elif object_id == 0 and param == 1:
                screen = a & 0x1F
                record = LevelRecord('screen_jump', at, raw_hex, screen, 1)
            else:
                kind = 'object' if object_id else 'extended_object'
                record = LevelRecord(kind, at, raw_hex, screen, object_id or param,
                                     screen * 16 + (b & 0xF), a & 0x1F)
        else:
            screen = ((a & 2) << 3) | (b & 0xF)
            record = LevelRecord('sprite', at, raw_hex, screen, param,
                                 screen * 16 + (b >> 4), (a >> 4) | ((a & 1) << 4),
                                 sprite_extra_bits=(a >> 2) & 3)
        records.append(record)
    raise AssertionError('A complete level stream returns at its terminator')


def level_catalog(rom: RomImage) -> tuple[tuple[str, int], ...]:
    """One entry per distinct horizontal level. Shared pointers stay as one room."""
    if not recognized(rom):
        raise ValueError('SMW level inspection requires the verified USA v1.0 ROM')
    groups: dict[int, list[int]] = {}
    base = lorom_to_pc(LAYER1_POINTERS)
    for level_id in range(0x200):
        address = int.from_bytes(rom.slice(base + 3 * level_id, 3), 'little')
        groups.setdefault(address, []).append(level_id)
    rooms = []
    for address, level_ids in groups.items():
        header = rom.slice(lorom_to_pc(address), 5)
        if len(header) < 5 or (header[1] & 0x1F) != 0:
            continue
        chosen = next((level_id for level_id in level_ids if level_id in LEVEL_NAMES), level_ids[0])
        rooms.append((_room_label(chosen, len(level_ids)), chosen))
    return tuple(sorted(rooms, key=lambda item: item[1]))


def _room_label(level_id: int, slots: int) -> str:
    name = LEVEL_NAMES.get(level_id, 'Level')
    label = f'${level_id:03X}  {name}'
    if slots > 1:
        label += f'  ·  {slots} slots'
    return label


def read_level(rom: RomImage, level_id: int = 0x105) -> SMWLevel:
    if not recognized(rom):
        raise ValueError('SMW level inspection requires the verified USA v1.0 ROM')
    if not 0 <= level_id <= 0x1FF:
        raise ValueError('SMW level numbers run from $000 through $1FF')

    layer1_address = int.from_bytes(rom.slice(lorom_to_pc(LAYER1_POINTERS) + 3 * level_id, 3), 'little')
    layer2_pointer = int.from_bytes(rom.slice(lorom_to_pc(LAYER2_POINTERS) + 3 * level_id, 3), 'little')
    sprite_address = 0x070000 | int.from_bytes(
        rom.slice(lorom_to_pc(SPRITE_POINTERS) + 2 * level_id, 2), 'little')
    header = rom.slice(lorom_to_pc(layer1_address), 5)
    block_columns, block_rows = _placement_blocks(header[1] & 0x1F)
    return SMWLevel(level_id, LEVEL_NAMES.get(level_id, f'Level ${level_id:03X}'), (header[0] & 0x1F) + 1,
                    layer2_pointer, _read_stream(rom, layer1_address, objects=True),
                    _read_stream(rom, sprite_address, objects=False),
                    rom.path.name, rom.copier_header_size, block_columns, block_rows)


def _placement_blocks(mode: int) -> tuple[int, int]:
    """Blocks per screen, then block rows, for a level mode this reader has identified.

    Horizontal mode 0 is one screen of 16 blocks across a level 27 blocks tall.
    Other modes are refused until their own grid has been identified.
    """
    if mode == 0:
        return 16, 27
    raise ValueError('This level inspector only supports horizontal level mode 0')
