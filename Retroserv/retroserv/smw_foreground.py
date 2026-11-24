"""Static Layer 1 reconstruction for the supported SMW rooms.

Object routines follow SMWDisX bank 0D. Pipes, ledges, and tileset objects live
in their own modules. This module decides which routine runs, then the Map16
loader paints the cells. All art comes from the loaded cartridge.
"""
from __future__ import annotations

from functools import cache
from hashlib import sha256

from PIL import Image

from .assistant import load_for_rom
from .graphics import decode_tile
from .rom import RomImage
from .smw import decoded_gfx
from .smw_ledges import (
    _ground_slope, _ledge, _ledge_edge, _left_diagonal,
)
from .smw_level import LevelRecord, read_level
from .smw_map16 import _apply_map16_pointers, _map16_words, _palette, _read
from .smw_pen import (
    CELL_PIXELS, EMPTY_TILE, GRASS_TILESETS, UNDERGROUND_TILESETS, ForegroundTile,
    OpeningForeground, _COMMON_OBJECTS, _EXTRA, _FAMILY, _GRASS_OBJECTS, _OTHER_EXTENDED,
    _Pen, _REP_TILE, _SINGLE_EXTENDED, _UNDERGROUND_OBJECTS,
)
from .smw_pipes import _diagonal_pipe, _horizontal_pipe, _vertical_pipe
from .smw_tileset import (
    _banded, _bush_stamp, _canvas_block, _ceiling, _ceiling_edge, _cloud_fringe,
    _donut_bridge, _draw_added, _goal_post, _horizontal_skinny, _mushroom_ledge,
    _mushroom_support, _rep_tile, _solid_dirt, _stamp,
)

__all__ = [
    'CELL_PIXELS', 'EMPTY_TILE', 'ForegroundTile', 'OpeningForeground',
    'foreground_supported', 'render_opening_foreground',
]

def _draw_object(record: LevelRecord, tiles: dict[tuple[int, int], ForegroundTile],
                 bush_table: bytes, tileset: int = 7) -> None:
    assert record.x is not None and record.y is not None
    settings = bytes.fromhex(record.raw_hex)[2]
    high, low = settings >> 4, settings & 15
    pen = _Pen(record, tiles)
    if record.kind == 'extended_object':
        _draw_extended(pen, record.type_id)
        return
    _draw_standard(pen, record.type_id, settings, high, low, bush_table, tileset)

def _draw_extended(pen: _Pen, type_id: int) -> None:
    if type_id == 0x41:  # ExtOBJDragonCoin, shown before it is collected
        pen.put(0x2D)
        pen.down()
        pen.put(0x2E)
        return
    if type_id in _SINGLE_EXTENDED:  # ExtOBJSingleTile, shown before it is collected
        single = bytes.fromhex(
            '1f222442432729256e6f70717245464748363711121415161718191a1b1c291d'
            '1f20212223252627282adee0e2e4eced2c252d')
        index = type_id - 0x10
        pen.high = 0 if index < 0x13 else 1
        pen.put(single[index])
        return
    if type_id == 0x46:  # ExtOBJMidwayTape, shown before the midway is hit
        pen.x -= 1
        pen.put(0x35, advance=True)
        pen.put(0x38)
        return
    if type_id == 0x86:  # ExtOBJArrowSign
        for tile in (0x66, 0x67, 0x68, 0x69):
            pen.put(tile, advance=True)
            if tile & 1:
                pen.x -= 2
                pen.down()
        return
    if type_id in (0x47, 0x48):  # ExtOBJDoor
        index = type_id - 0x47
        pen.put((0x1F, 0x27)[index])
        pen.down()
        pen.put((0x20, 0x28)[index])
        return
    if type_id == 0x17:  # ExtOBJGreenStarBlock, shown before it is collected
        pen.high = 1
        pen.put(0x2D)
        return
    if 0x44 <= type_id <= 0x45:  # ExtOBJPurpleTriangle
        pen.put((0xB4, 0xB5)[type_id - 0x44])
        pen.down()
        pen.high = 1
        pen.put(0xEB)
        return
    if 0x57 <= type_id <= 0x5E:  # ExtOBJSingleTile2
        pen.put(bytes.fromhex('7374757693949596')[type_id - 0x57])
        return
    if type_id in (0x82, 0x83):  # ExtOBJBigBush, ExtOBJMediumBush
        _bush_stamp(pen, type_id)
        return
    if type_id == 0x90:  # ExtOBJBossDoor
        _stamp(pen, pen.x, pen.y, 2, 3, bytes.fromhex('98999a9b9c9c'), 0)
        return
    if 0x8A <= type_id <= 0x8D:  # ExtOBJPalaceSwitch, shown before the switch is pressed
        tiles = bytes.fromhex('ecedeeeff0f1f2f3f4f5f6f7f8f9fafb')
        _stamp(pen, pen.x, pen.y, 2, 2, tiles[(type_id - 0x8A) * 4:(type_id - 0x89) * 4], 0)
        return
    if type_id == 0x97:  # ExtOBJPalaceOuterCorner
        pen.high = 1
        pen.put(0x10)
        return
    if type_id == 0x4A:  # ExtOBJClimbingNetDoor
        _stamp(pen, pen.x, pen.y, 4, 4, bytes.fromhex('10111112130b0b15130b0b1516171718'), 0)
        return
    if type_id in (0x4B, 0x4C):  # ExtOBJEscalatorEnd
        pen.high = 1
        pen.put((0x07, 0x08)[type_id - 0x4B])
        return
    if 0x4D <= type_id <= 0x50:  # ExtOBJGuideLineBigCircle
        tiles = bytes.fromhex('7a7b7c257e7f257d8225808125838485')
        _stamp(pen, pen.x, pen.y, 2, 2, tiles[(type_id - 0x4D) * 4:(type_id - 0x4C) * 4], 0)
        return
    if 0x51 <= type_id <= 0x54:  # ExtOBJGuideLineSmallCircle
        pen.put(bytes.fromhex('76777879')[type_id - 0x51])
        return
    if type_id == 0x55:  # ExtOBJGuideLineHorizEnd
        pen.put(0x96)
        pen.down()
        pen.put(0x97)
        return
    if type_id == 0x56:  # ExtOBJGuideLineVertEnd
        pen.put(0x98, advance=True)
        pen.put(0x99)
        return
    if type_id in (0x64, 0x65):  # ExtOBJCobweb
        tiles = bytes.fromhex('8c8d258e90918f25fcfdfeff')
        _stamp(pen, pen.x, pen.y, 2, 2, tiles[(type_id - 0x64) * 4:(type_id - 0x63) * 4], 0)
        return
    if type_id == 0x7F:  # ExtOBJTorpedoLauncher
        _stamp(pen, pen.x, pen.y, 2, 2, bytes.fromhex('66676869'), 1)
        return
    if type_id in (0x88, 0x89):  # ExtOBJTreeBranch
        pen.put((0xC1, 0xC2)[type_id - 0x88])
        return
    if type_id == 0x60:  # ExtOBJCaveLavaInnerCorner
        pen.high = 1
        pen.put(0xFE)
        return
    if 0x72 <= type_id <= 0x74:  # ExtOBJCanvas
        _canvas_block(pen, pen.x, pen.y, (0x00, 0x13, 0x26, 0x39)[type_id - 0x71])
        return
    if 0x75 <= type_id <= 0x78:  # ExtOBJCanvasTiles
        pen.put(bytes.fromhex('7d7e7f80818283')[type_id - 0x75])
        return
    if 0x7C <= type_id <= 0x7E:  # ExtOBJCanvasPairs
        index = type_id - 0x7C
        pen.put((0x81, 0x82, 0x83)[index])
        pen.down()
        pen.put((0x84, 0x85, 0x86)[index])
        return
    if type_id == 0x85:  # ExtOBJYoshisHouse
        _stamp(pen, pen.x, pen.y, 16, 10, bytes.fromhex(
            '2525252525252525252525cbcc25252525cdcecfcfcfcfcfcfcfcfcfcfd0d125'
            '25d2ebd3d3d3ebd3d3d3d3ebd3d3d42525d5d3ebd3d3d3d3d3ebd3d3d3ebd625'
            '25d5d3d3d3d3d3ebd3d3d3d3d3d3d62525d7d8d9d8d8d9d8d8d9d8dadbd8dc25'
            '252525dd2525dd2525dd25cbcc2525252525dedd2525dd2525dd25cbcc252525'
            '25dfe0e12525dd2525dd25e2e3e42525e5e5e6dde5e5dde5e5dde5e7e8e9e5e5'), 0)
        return
    if type_id == 0x87:  # ExtOBJGreenSwitchBlock, shown before the switch is pressed
        pen.put(0x6A)
        return
    if type_id == 0x8E:  # ExtOBJYellowSwitchBlock, shown before the switch is pressed
        pen.put(0x6B)
        return
    raise ValueError(f'Unsupported extended foreground object ${type_id:02X}')

def _draw_standard(pen: _Pen, type_id: int, settings: int, high: int, low: int,
                   bush_table: bytes, tileset: int) -> None:
    origin_x, origin_y = pen.x, pen.y
    family = _FAMILY.get(tileset, '')
    if type_id in _REP_TILE.get(family, ()):  # OBJRepTileWithTop
        _rep_tile(pen, origin_x, origin_y, type_id - 0x18, high, low)
    elif type_id == 0x1C:  # OBJDonutBridge
        _donut_bridge(pen, origin_x, origin_y, low)
    elif type_id == 0x20:  # OBJHorizontalSkinny
        _horizontal_skinny(pen, low)
    elif 0x01 <= type_id <= 0x0E:  # OBJSingleRepTile, uncollected
        single = bytes.fromhex('0221232a2b3f03131e242e2f303265')
        index = type_id - 1
        pen.high = 1 if index >= 7 else 0
        tile = single[index]
        for row in range(high + 1):
            for column in range(low + 1):
                pen.x, pen.y = origin_x + column, origin_y + row
                pen.put(tile)
    elif type_id == 0x0F:  # OBJVerticalPipes
        _vertical_pipe(pen, high, low)
    elif type_id == 0x10:  # OBJHorizontalPipes
        _horizontal_pipe(pen, settings)
    elif type_id == 0x12:  # OBJSlopes, the one shape used by these rooms
        _ground_slope(pen, settings)
    elif type_id == 0x13:  # OBJLedgeEdges
        _ledge_edge(pen, high, low)
    elif type_id == 0x14:  # OBJLedge
        _ledge(pen, origin_x, origin_y, low + 1, high)
    elif type_id == 0x15:  # OBJMidwayGoalPosts
        _goal_post(pen, high, low)
    elif type_id == 0x17:  # OBJRopeClouds
        if high > 1:
            raise ValueError('Unsupported rope settings')
        pen.high = 1
        for _column in range(low + 1):
            pen.put(0x05 + high, advance=True)
    elif type_id == 0x1F:  # OBJVerticalSkinny
        if high == 0:
            raise ValueError('Unsupported vertical rope settings')
        pen.high = 1
        pen.put(0x53)
        for _row in range(high - 1):
            pen.down()
            pen.put(0x54)
        pen.down()
        pen.put(0x55)
    elif type_id == 0x21:  # OBJLongLedge
        _ledge(pen, origin_x, origin_y, settings + 1, 3)
    elif type_id == 0x39:  # OBJDiagonalPipe
        _diagonal_pipe(pen, high)
    elif type_id == 0x3A:  # OBJLeftDiagonalPlat
        _left_diagonal(pen, origin_x, origin_y, high, low)
    elif type_id == 0x3C and family == 'castle':  # OBJStoneBlock
        _banded(pen, low, high, ((0x5D, 0x5E, 0x5F), (0x60, 0x61, 0x62), (0x63, 0x64, 0x65)))
    elif type_id == 0x3C and family == 'rope':  # OBJMushroomLedge
        _mushroom_ledge(pen, low)
    elif type_id == 0x3D and family == 'rope':  # OBJMushroomSupport
        _mushroom_support(pen, origin_x, high, low)
    elif type_id == 0x3D and tileset in GRASS_TILESETS:  # OBJHorizCloudFringe
        _cloud_fringe(pen, high, low)
    elif type_id == 0x36 and family == 'under':  # OBJRectangleLedge
        _banded(pen, low, high, ((0x45, 0x00, 0x48), (0x50, 0xF0, 0x51), (0x4D, 0x4E, 0x4F)))
    elif type_id == 0x3D and tileset in UNDERGROUND_TILESETS:  # OBJCeiling
        _ceiling(pen, origin_x, origin_y, high, low)
    elif type_id == 0x3E and tileset in UNDERGROUND_TILESETS:  # OBJCeilingEdges
        _ceiling_edge(pen, high, low)
    elif type_id == 0x3F and tileset in UNDERGROUND_TILESETS:  # OBJSolidDirt
        _solid_dirt(pen, origin_x, origin_y, high, low)
    elif type_id == 0x3F and tileset in GRASS_TILESETS:  # OBJLongBushes
        if low == 0 or high >= 5:
            raise ValueError('Unsupported long bush settings')
        pen.put(bush_table[high])
        for column in range(origin_x + 1, origin_x + low):
            pen.x = column
            pen.put(bush_table[5 + high])
        pen.x = origin_x + low
        pen.put(bush_table[10 + high])
    elif _draw_added(pen, type_id, high, low, family, origin_x, origin_y):
        return
    else:
        raise ValueError(f'Unsupported foreground object ${type_id:02X}')

def foreground_supported(level) -> bool:
    """True when every object in this horizontal level uses a routine this renderer has."""
    header = bytes.fromhex(level.layer1.header_hex)
    tileset = header[4] & 15 if len(header) > 4 else 0
    family = _FAMILY.get(tileset, '')
    allowed = set(_COMMON_OBJECTS)
    allowed.update(_REP_TILE.get(family, ()))
    if tileset in GRASS_TILESETS:
        allowed.update(_GRASS_OBJECTS)
    if family == 'castle':
        allowed.add(0x3C)
    if family == 'rope':
        allowed.update({0x3C, 0x3D})
    if tileset in UNDERGROUND_TILESETS:
        allowed.update(_UNDERGROUND_OBJECTS)
    allowed.update(_EXTRA.get(family, ()))
    for record in level.layer1.records:
        if record.kind not in ('object', 'extended_object'):
            continue
        settings = bytes.fromhex(record.raw_hex)[2]
        if record.kind == 'extended_object':
            if record.type_id not in _SINGLE_EXTENDED | _OTHER_EXTENDED:
                return False
            continue
        if record.type_id not in allowed:
            return False
        low, high = settings & 15, settings >> 4
        if record.type_id == 0x0F and low > 5:
            return False
        if record.type_id == 0x10 and high > 3:
            return False
        if record.type_id == 0x13 and low > 14:
            return False
        if record.type_id == 0x17 and high > 1:
            return False
        if record.type_id == 0x1E and (high == 0 or low > 1):
            return False
        if record.type_id == 0x1F and high == 0:
            return False
        if record.type_id == 0x20 and low == 0:
            return False
        if record.type_id == 0x3C and low == 0 and family in ('castle', 'rope', 'grass'):
            return False
        if record.type_id == 0x3D and family == 'rope' and low == 0:
            return False
        if record.type_id == 0x3D and tileset in GRASS_TILESETS and high > 1:
            return False
        if record.type_id == 0x36 and family == 'under' and low == 0:
            return False
        if record.type_id == 0x3E and tileset in UNDERGROUND_TILESETS and low > 3:
            return False
        if family == 'castle' and record.type_id == 0x34 and high == 0:
            return False
        if family == 'castle' and record.type_id == 0x37 and high > 1:
            return False
        if family == 'castle' and record.type_id == 0x38 and low > 2:
            return False
        if family == 'rope' and record.type_id == 0x35 and low > 3:
            return False
        if family == 'rope' and record.type_id == 0x38 and high > 1:
            return False
        if family == 'rope' and record.type_id == 0x39 and low > 2:
            return False
        if family == 'rope' and record.type_id == 0x3A and low > 5:
            return False
        if family == 'rope' and record.type_id == 0x3E and low == 0:
            return False
        if family == 'rope' and record.type_id == 0x3F and high == 0:
            return False
        if family == 'grass' and record.type_id == 0x3E and low > 7:
            return False
        if family == 'under' and record.type_id == 0x38 and low > 1:
            return False
        if record.type_id == 0x3F and tileset in GRASS_TILESETS and (low == 0 or high >= 5):
            return False
        if family == 'ghost' and record.type_id == 0x34 and high == 0:
            return False
        if family == 'ghost' and record.type_id == 0x37 and (low == 0 or high > 2):
            return False
        if family == 'ghost' and record.type_id in (0x38, 0x3B) and low == 0:
            return False
        if family == 'ghost' and record.type_id == 0x39 and low > 2:
            return False
        if family == 'ghost' and record.type_id == 0x3A and low > 3:
            return False
        if family == 'grass' and record.type_id == 0x34 and low > 3:
            return False
        if family == 'grass' and record.type_id == 0x37 and low > 1:
            return False
        if family == 'grass' and record.type_id == 0x3C and low == 0:
            return False
        if family == 'castle' and record.type_id == 0x3E and high > 1:
            return False
        if family == 'castle' and record.type_id == 0x3F and low > 2:
            return False
    return True

def render_opening_foreground(rom: RomImage, level_id: int = 0x105, assistant=None) -> OpeningForeground:
    """Render one supported room with static graphics and provenance for every drawn cell."""
    level = read_level(rom, level_id)
    columns = level.screen_count * level.block_columns
    rows = level.block_rows
    header = bytes.fromhex(level.layer1.header_hex)
    tileset = header[4] & 15
    bush_table = _read(rom, 0x0DB5A8, 15)
    drawn = {}
    for record in level.layer1.records:
        if record.kind in ('object', 'extended_object'):
            _draw_object(record, drawn, bush_table, tileset)
    tiles = {(x, y): tile for (x, y), tile in drawn.items() if 0 <= x < columns and 0 <= y < rows}

    if assistant is None:
        assistant = load_for_rom(sha256(rom.data).hexdigest(), rom.path)
    definitions = _map16_words(rom, tileset, assistant)
    colors = _palette(rom, header)
    slots = _read(rom, 0x00A92B + 4 * tileset, 4)
    graphics = [decoded_gfx(rom, number, enforce_identity=False)[1].data for number in slots]

    @cache
    def character(word: int) -> Image.Image:
        number = word & 0x3FF
        slot, index = divmod(number, 128)
        if slot >= len(graphics):
            raise ValueError(f'Opening foreground uses an unsupported character: ${number:03X}')
        data = graphics[slot][index * 24:(index + 1) * 24]
        pixels = decode_tile(data, 3)
        if slots[slot] == 0x17 and index in (0, 1, 16, 17):
            pixels = [pixel | 8 if pixel else 0 for pixel in pixels]
        start = ((word >> 10) & 7) * 16
        tile = Image.new('RGBA', (8, 8))
        tile.putdata([(*colors[start + pixel], 255 if pixel else 0) for pixel in pixels])
        if word & 0x4000:
            tile = tile.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if word & 0x8000:
            tile = tile.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        return tile

    surface = Image.new('RGBA', (columns * CELL_PIXELS, rows * CELL_PIXELS))
    for (x, y), tile in tiles.items():
        for quadrant, word in enumerate(definitions[tile.map16_id]):
            # Map16 definitions are stored TL, BL, TR, BR.
            surface.paste(character(word), (x * 16 + (quadrant // 2) * 8,
                                            y * 16 + (quadrant % 2) * 8))
    return OpeningForeground(surface, tiles, columns, rows)
