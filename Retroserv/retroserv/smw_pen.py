"""Shared cursor and tile sets for the SMW foreground routines."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .smw_level import LevelRecord

CELL_PIXELS = 16
EMPTY_TILE = 0x025
GRASS_TILESETS = frozenset({0, 7, 12})
UNDERGROUND_TILESETS = frozenset({3, 9, 10, 11, 14})
_COMMON_OBJECTS = set(range(0x01, 0x0F)) | {0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x17, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x21}
_GRASS_OBJECTS = {0x39, 0x3A, 0x3D, 0x3F}
_UNDERGROUND_OBJECTS = {0x36, 0x3D, 0x3E, 0x3F}
_FAMILY = {0: 'grass', 7: 'grass', 12: 'grass', 1: 'castle', 2: 'rope', 6: 'rope', 8: 'rope',
           3: 'under', 9: 'under', 10: 'under', 11: 'under', 14: 'under', 4: 'ghost', 5: 'ghost', 13: 'ghost'}
_REP_TILE = {
    'grass': set(range(0x18, 0x1C)) | set(range(0x22, 0x30)),
    'castle': set(range(0x18, 0x1C)) | set(range(0x22, 0x34)),
    'rope': set(range(0x18, 0x1C)) | set(range(0x22, 0x32)),
    'under': set(range(0x18, 0x1C)) | set(range(0x22, 0x34)),
    'ghost': set(range(0x18, 0x1C)) | set(range(0x22, 0x2E)),
}
# Bank 0D at $0DB3DB. The four published bytes continue into the following bytes;
# higher object indexes read those, which is what the routine does.
_REP_BYTES = bytes.fromhex(
    '000104080203050ba457a559290f85008502a5594a4a4a4a85018a38e917aa20')
_EXTRA = {
    'grass': {0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x3B, 0x3C, 0x3E},
    'castle': {0x34, 0x37, 0x38, 0x39, 0x3A, 0x3D, 0x3E, 0x3F},
    'rope': {0x32, 0x33, 0x34, 0x35, 0x38, 0x39, 0x3A, 0x3E, 0x3F},
    'under': {0x34, 0x35, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C},
    'ghost': {0x2F, 0x30} | set(range(0x34, 0x40)),
}
_SWITCH = {
    ('grass', 0x32): 0x6C, ('grass', 0x38): 0x6D,
    ('castle', 0x39): 0x6C, ('castle', 0x3A): 0x6D,
    ('rope', 0x33): 0x6C, ('rope', 0x34): 0x6D,
    ('under', 0x34): 0x6C, ('under', 0x35): 0x6D,
}
_SINGLE_EXTENDED = set(range(0x10, 0x17)) | set(range(0x18, 0x41))
_OTHER_EXTENDED = (
    {0x17, 0x41, 0x44, 0x45, 0x46, 0x47, 0x48, 0x4A, 0x55, 0x56, 0x60, 0x64, 0x65, 0x7F, 0x82, 0x83, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8E, 0x90, 0x97}
    | set(range(0x72, 0x79)) | set(range(0x7C, 0x7F))
    | set(range(0x4B, 0x55)) | set(range(0x57, 0x5F)) | set(range(0x8A, 0x8E))
)


@dataclass(frozen=True)
class ForegroundTile:
    map16_id: int
    source: LevelRecord


@dataclass(frozen=True)
class OpeningForeground:
    image: Image.Image
    tiles: dict[tuple[int, int], ForegroundTile]
    columns: int
    rows: int


class _Pen:
    """Map16 cursor. Right and down follow the bank 0D object cursor."""

    def __init__(self, record: LevelRecord, tiles: dict[tuple[int, int], ForegroundTile]):
        self.record = record
        self.tiles = tiles
        self.x = record.x
        self.y = record.y
        self.high = 0

    def put(self, tile: int, *, advance: bool = False) -> None:
        self.tiles[self.x, self.y] = ForegroundTile((self.high << 8) | (tile & 0xFF), self.record)
        if advance:
            self.x += 1

    def down(self) -> None:
        self.y += 1

    def low(self) -> int:
        previous = self.tiles.get((self.x, self.y))
        return (previous.map16_id if previous else EMPTY_TILE) & 0xFF


def _replace(existing: int, found: bytes, replacement: bytes) -> int | None:
    for index in range(len(found) - 1, -1, -1):
        if existing == found[index]:
            return replacement[index]
    return None


