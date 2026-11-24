"""Layer 2 backgrounds stored beside a horizontal SMW level.

A pointer whose bank byte is $FF is not a second level. The game reads the
low address from bank $0C, expands the run-length list into a 16 by 27
screen, and draws those Map16 tiles behind the foreground. The sky color is
the backdrop selected by the level header.
"""
from __future__ import annotations

from struct import unpack

from PIL import Image

from .graphics import bgr555_rgb, decode_tile
from .rom import RomImage
from .smw import decoded_gfx, lorom_to_pc
from .smw_map16 import _palette, _read

SCREEN_COLUMNS = 16
SCREEN_ROWS = 27
SCREEN_CELLS = SCREEN_COLUMNS * SCREEN_ROWS
_BUFFER = 0x400
_MAP16 = 0x0D9100
_BACKDROP = 0x00B0A0
_PAGE_SPLIT = 0xE8FE


def background_tiles(rom: RomImage, pointer: int) -> tuple[bytes, int] | None:
    """Low Map16 bytes and the Map16 page, or None when layer 2 is another level."""
    if (pointer >> 16) & 0xFF != 0xFF:
        return None
    offset = pointer & 0xFFFF
    if offset < 0x8000:
        raise ValueError(f'Background pointer ${pointer:06X} is not a bank $0C address')
    data = rom.data[lorom_to_pc(0x0C0000 | offset):]
    return _expand(data), 1 if offset >= _PAGE_SPLIT else 0


def place_background(rom: RomImage, level, foreground: Image.Image) -> Image.Image:
    """Draw the backdrop and any background screens behind the foreground."""
    header = bytes.fromhex(level.layer1.header_hex)
    backdrop = bgr555_rgb(int.from_bytes(
        rom.slice(lorom_to_pc(_BACKDROP) + (header[1] >> 5) * 2, 2), 'little'))
    image = Image.new('RGBA', foreground.size, (*backdrop, 255))
    decoded = background_tiles(rom, level.layer2_pointer)
    if decoded is not None:
        tiles, page = decoded
        _paint(rom, header, tiles, page, image)
    image.paste(foreground, (0, 0), foreground)
    return image


def _expand(data: bytes) -> bytes:
    """The run-length list from CODE_058126, stopped at $FF $FF or the RAM buffer."""
    output = bytearray()
    cursor = 0
    while cursor < len(data) and len(output) < _BUFFER:
        if cursor + 1 < len(data) and data[cursor] == 0xFF and data[cursor + 1] == 0xFF:
            break
        control = data[cursor]
        cursor += 1
        if control & 0x80:
            count = (control & 0x7F) + 1
            if cursor >= len(data):
                break
            output.extend([data[cursor]] * count)
            cursor += 1
        else:
            count = control + 1
            output.extend(data[cursor:cursor + count])
            cursor += count
    return bytes(output[:_BUFFER])


def _paint(rom: RomImage, header: bytes, tiles: bytes, page: int, image: Image.Image) -> None:
    colors = _palette(rom, header)
    tileset = header[4] & 15
    slots = _read(rom, 0x00A92B + 4 * tileset, 4)
    graphics = [decoded_gfx(rom, number, enforce_identity=False)[1].data for number in slots]
    table = rom.slice(lorom_to_pc(_MAP16), 0x200 * 8)
    definitions = [unpack('<4H', table[index * 8:(index + 1) * 8]) for index in range(0x200)]
    screens = len(tiles) // SCREEN_CELLS
    for screen in range(screens):
        origin = screen * SCREEN_COLUMNS * 16
        if origin >= image.width:
            break
        block = tiles[screen * SCREEN_CELLS:(screen + 1) * SCREEN_CELLS]
        for index, low in enumerate(block):
            x, y = index % SCREEN_COLUMNS, index // SCREEN_COLUMNS
            _paste(image, definitions[(page << 8) | low], colors, slots, graphics,
                   origin + x * 16, y * 16)


def _paste(image, words, colors, slots, graphics, left: int, top: int) -> None:
    for quadrant, word in enumerate(words):
        number = word & 0x3FF
        slot, index = divmod(number, 128)
        if slot >= len(graphics):
            continue
        data = graphics[slot][index * 24:(index + 1) * 24]
        if len(data) < 24:
            continue
        pixels = decode_tile(data, 3)
        start = ((word >> 10) & 7) * 16
        ox = left + (quadrant // 2) * 8
        oy = top + (quadrant % 2) * 8
        for py in range(8):
            sy = 7 - py if word & 0x8000 else py
            for px in range(8):
                sx = 7 - px if word & 0x4000 else px
                pixel = pixels[sy * 8 + sx]
                if pixel and 0 <= ox + px < image.width and 0 <= oy + py < image.height:
                    image.putpixel((ox + px, oy + py), (*colors[start + pixel], 255))
