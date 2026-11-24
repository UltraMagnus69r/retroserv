"""Map16 words and the level foreground palette, read from the cartridge."""
from __future__ import annotations

from struct import unpack

from .graphics import read_palette
from .rom import RomImage
from .smw import lorom_to_pc

def _read(rom: RomImage, address: int, length: int) -> bytes:
    return rom.slice(lorom_to_pc(address), length)

def _apply_map16_pointers(pointers: list[int], tileset: int, assistant) -> None:
    """Apply map16-pointers changes from the assistant file. Other kinds stay untouched."""
    if assistant is None:
        return
    for change in assistant.changes:
        if change.kind != 'map16-pointers':
            continue
        tilesets = change.data.get('tilesets')
        if tilesets is not None and tileset not in tilesets:
            continue
        for key, address in change.data.get('pointers', {}).items():
            index = int(str(key), 16)
            if 0 <= index < len(pointers):
                pointers[index] = int(str(address), 16)

def _map16_words(rom: RomImage, tileset: int, assistant=None) -> list[tuple[int, ...]]:
    mask = _read(rom, 0x0581BB, 64)
    common = 0x0D8000
    specific = 0x0D0000 | int.from_bytes(_read(rom, 0x058000 + 2 * tileset, 2), 'little')
    pointers = []
    for tile in range(512):
        if mask[tile // 8] & (0x80 >> (tile % 8)):
            pointers.append(common)
            common += 8
        else:
            pointers.append(specific)
            specific += 8
    _apply_map16_pointers(pointers, tileset, assistant)
    return [unpack('<4H', _read(rom, address, 8)) for address in pointers]

def _palette(rom: RomImage, header: bytes) -> list[tuple[int, int, int]]:
    palette = [(0, 0, 0)] * 128
    for row in range(8):
        palette[row * 16 + 1] = read_palette(b'\xdd\x7f', 1)[0]
    for address, row, index, length, rows in (
        (0x00B0B0 + (header[0] >> 5) * 24, 0, 2, 6, 2),  # BG palettes
        (0x00B170, 0, 8, 8, 2),                          # status bar
        (0x00B190 + (header[3] & 7) * 24, 2, 2, 6, 2),  # FG palettes
        (0x00B250, 4, 2, 6, 4),                          # common BG colors
        (0x00B674, 2, 9, 7, 3),                          # berries
    ):
        for step in range(rows):
            start = (row + step) * 16 + index
            palette[start:start + length] = read_palette(_read(rom, address + step * length * 2, length * 2), length)
    # RegularLevelNMI writes one frame of FlashingColors over CGRAM $64 after LoadPalette.
    # The first frame is EffFrame masked with #$1C, which lands on $00B60C.
    palette[0x64] = read_palette(_read(rom, 0x00B60C, 2), 1)[0]
    return palette
