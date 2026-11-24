"""Tileset objects for the SMW foreground."""
from __future__ import annotations

from .smw_ledges import _slope_adjust, _slope_left, _slope_lip, _slope_put, _slope_right
from .smw_pen import (
    EMPTY_TILE, GRASS_TILESETS, UNDERGROUND_TILESETS, _EXTRA, _FAMILY, _Pen, _REP_BYTES,
    _REP_TILE, _SWITCH, _replace,
)

def _replace(existing: int, found: bytes, replacement: bytes) -> int | None:
    for index in range(len(found) - 1, -1, -1):
        if existing == found[index]:
            return replacement[index]
    return None

def _rep_tile(pen: _Pen, origin_x: int, origin_y: int, index: int, high: int, low: int) -> None:
    pen.high = 0
    for row in range(high + 1):
        tile = _REP_BYTES[index] if row == 0 else _REP_BYTES[4 + index]
        for column in range(low + 1):
            pen.x, pen.y = origin_x + column, origin_y + row
            pen.put(tile)

def _donut_bridge(pen: _Pen, origin_x: int, origin_y: int, low: int) -> None:
    for row, (page, tile) in enumerate(((0, 0x26), (1, 0x44))):
        pen.high = page
        pen.y = origin_y + row
        for column in range(low + 1):
            pen.x = origin_x + column
            pen.put(tile)

def _horizontal_skinny(pen: _Pen, low: int) -> None:
    if low == 0:
        raise ValueError('Unsupported horizontal rope settings')
    pen.high = 1
    pen.put(0x56, advance=True)
    for _column in range(low - 1):
        pen.put(0x57, advance=True)
    pen.put(0x58)

def _banded(pen: _Pen, low: int, high: int, tiles: tuple[tuple[int, int, int], ...]) -> None:
    if low == 0:
        raise ValueError('Unsupported empty band')
    kinds = (0,) if high == 0 else (0,) + (1,) * (high - 1) + (2,)
    origin_x, origin_y = pen.x, pen.y
    pen.high = 1
    for row, kind in enumerate(kinds):
        left, middle, right = tiles[kind]
        pen.y = origin_y + row
        pen.x = origin_x
        pen.put(left, advance=True)
        for _column in range(low - 1):
            pen.put(middle, advance=True)
        pen.put(right)

def _mushroom_cap(pen: _Pen, plain: int, joined: int) -> None:
    seen = pen.low()
    pen.put(joined if 0x73 <= seen <= 0x75 else plain, advance=True)

def _mushroom_ledge(pen: _Pen, low: int) -> None:
    if low == 0:
        raise ValueError('Unsupported mushroom ledge settings')
    pen.high = 1
    _mushroom_cap(pen, 0x07, 0x0A)
    for _column in range(low - 1):
        pen.put(0x08, advance=True)
    _mushroom_cap(pen, 0x09, 0x0B)

def _mushroom_support(pen: _Pen, origin_x: int, high: int, low: int) -> None:
    if low == 0:
        raise ValueError('Unsupported mushroom stem settings')
    pen.high = 0
    for _row in range(high + 1):
        pen.x = origin_x
        pen.put(0x73, advance=True)
        for _column in range(low - 1):
            pen.put(0x74, advance=True)
        pen.put(0x75, advance=True)
        pen.y += 1

def _cloud_fringe(pen: _Pen, high: int, low: int) -> None:
    if high > 1:
        raise ValueError('Unsupported cloud fringe settings')
    pen.high = 0
    for _column in range(low + 1):
        pen.put((0x93, 0x9C)[high], advance=True)

def _solid_dirt(pen: _Pen, origin_x: int, origin_y: int, high: int, low: int) -> None:
    _filled(pen, origin_x, origin_y, high, low, 0x65, 1)

def _filled(pen: _Pen, origin_x: int, origin_y: int, high: int, low: int, tile: int, page: int) -> None:
    pen.high = page
    for row in range(high + 1):
        for column in range(low + 1):
            pen.x, pen.y = origin_x + column, origin_y + row
            pen.put(tile)

def _capped_row(pen: _Pen, low: int, left: int, middle: int, right: int, page: int) -> None:
    if low == 0:
        raise ValueError('Unsupported empty capped row')
    pen.high = page
    pen.put(left, advance=True)
    for _column in range(low - 1):
        pen.put(middle, advance=True)
    pen.put(right)

def _column(pen: _Pen, high: int, tile: int, page: int) -> None:
    pen.high = page
    for _row in range(high + 1):
        pen.put(tile)
        pen.down()

def _cap_then_body(pen: _Pen, origin_x: int, origin_y: int, high: int, low: int,
                   cap: int, body: int, cap_page: int, body_page: int) -> None:
    width = low + 1
    pen.high = cap_page
    for column in range(width):
        pen.x, pen.y = origin_x + column, origin_y
        pen.put(cap)
    pen.high = body_page
    for row in range(1, high + 1):
        for column in range(width):
            pen.x, pen.y = origin_x + column, origin_y + row
            pen.put(body)

def _stamp(pen: _Pen, origin_x: int, origin_y: int, width: int, height: int, tiles: bytes, page: int) -> None:
    pen.high = page
    index = 0
    for row in range(height):
        for column in range(width):
            pen.x, pen.y = origin_x + column, origin_y + row
            pen.put(tiles[index])
            index += 1

def _bush_stamp(pen: _Pen, type_id: int) -> None:
    if type_id == 0x82:
        width, height = 9, 5
        tiles = bytes.fromhex(
            '2525254b4d4e25252525255449495f6325252525574949524a5d25255a494950514a60255a494949534a4a4a63')
    else:
        width, height = 6, 4
        tiles = bytes.fromhex('25254b4c25252554495f6325255749524a5d5a4949494f60')
    index = 0
    origin_x, origin_y = pen.x, pen.y
    for row in range(height):
        pen.y = origin_y + row
        pen.x = origin_x
        for _column in range(width):
            _bush_tile(pen, tiles[index])
            index += 1

def _bush_tile(pen: _Pen, tile: int) -> None:
    pen.high = 0
    if tile == 0x25:
        pen.x += 1
        return
    if 0x49 <= tile < 0x54:
        seen = pen.low()
        if seen != 0x25:
            tile += 1 if seen == 0x49 else 2
    pen.put(tile, advance=True)

def _net_edge(pen: _Pen, origin_x: int, origin_y: int, high: int, low: int) -> None:
    if high == 0 or low > 1:
        raise ValueError('Unsupported climbing net')
    plain = (0x0A, 0x0C)[low]
    for row in range(high + 1):
        pen.x, pen.y = origin_x, origin_y + row
        pen.high = 0
        tile = plain
        seen = pen.low()
        if row == 0 and seen == 0x08:
            tile = (0x07, 0x09)[low]
        elif row == 0 and seen == 0x0E:
            tile = (0x1A, 0x19)[low]
        elif row == high and seen == 0x0E:
            tile = (0x0D, 0x0F)[low]
        elif row == high and seen == 0x08:
            tile = (0x1C, 0x1B)[low]
        pen.put(tile)

def _guide(pen: _Pen, type_id: int, high: int, low: int, family: str, origin_x: int, origin_y: int) -> bool:
    if family == 'castle' and type_id == 0x34:  # OBJSpecialVertPipe
        if high == 0:
            raise ValueError('Unsupported special pipe')
        for row in range(high + 1):
            left, right, page = ((0x33, 0x34, 1) if row in (0, high) else (0x9D, 0x9E, 0))
            pen.high = page
            pen.x, pen.y = origin_x, origin_y + row
            pen.put(left, advance=True)
            pen.put(right)
        return True
    if (family == 'castle' and type_id == 0x37) or (family == 'rope' and type_id == 0x38):
        if high > 1:
            raise ValueError('Unsupported horizontal guide')
        pen.high = 0
        for _step in range(low + 1):
            pen.put((0x92, 0x93)[high], advance=True)
        return True
    if (family == 'castle' and type_id == 0x38) or (family == 'rope' and type_id == 0x39):
        if low > 2:
            raise ValueError('Unsupported vertical guide')
        _column(pen, high, (0x90, 0x91, 0xA2)[low], 0)
        return True
    if family == 'rope' and type_id == 0x32:  # OBJLogBridge
        for row, (page, tile) in enumerate(((0, 0xA3), (1, 0x0E))):
            pen.high = page
            for column in range(low + 1):
                pen.x, pen.y = origin_x + column, origin_y + row
                pen.put(tile)
        return True
    if family == 'rope' and type_id == 0x35:  # OBJPlantPillar
        _plant(pen, origin_x, origin_y, high, low)
        return True
    if family == 'rope' and type_id == 0x3A:  # OBJSlopedGuideLines
        _sloped_guide(pen, origin_x, origin_y, high, low)
        return True
    if family == 'rope' and type_id == 0x3E:  # OBJHorizontalPost
        _capped_row(pen, low, 0x59, 0x5A, 0x5B, 1)
        return True
    if family == 'rope' and type_id == 0x3F:  # OBJVerticalPost
        if high == 0:
            raise ValueError('Unsupported vertical post')
        pen.x, pen.y = origin_x, origin_y
        pen.high = 1
        pen.put(0x5C)
        for depth in range(1, high):
            pen.y = origin_y + depth
            pen.put(0x5D)
        pen.y = origin_y + high
        pen.put(0x5E)
        return True
    if family == 'grass' and type_id == 0x3E:  # OBJVertCloudFringe
        if low > 7:
            raise ValueError('Unsupported cloud fringe')
        top = bytes.fromhex('948f9d9895909e99')[low]
        body = bytes.fromhex('8f8f989890909999')[low]
        pen.high = 0
        for row in range(high + 1):
            pen.x, pen.y = origin_x, origin_y + row
            pen.put(top if row == 0 else body)
        return True
    if family == 'under' and type_id in (0x3A, 0x3B):  # OBJCaveLava
        tile = 0x59 if type_id == 0x3A else 0xFF
        pen.high = 1
        for row in range(high + 1):
            for column in range(low + 1):
                pen.x, pen.y = origin_x + column, origin_y + row
                pen.put(tile if row == 0 else 0xFF)
        return True
    if family == 'under' and type_id == 0x3C:  # OBJSteepSlopes
        _steep_slope(pen, origin_x, origin_y, high, low)
        return True
    if family == 'under' and type_id == 0x38:  # OBJCaveLavaEdge
        if low > 1:
            raise ValueError('Unsupported lava edge')
        pen.high = 1
        for row in range(high + 1):
            pen.x, pen.y = origin_x, origin_y + row
            pen.put((0x5A, 0x5B)[low] if row == 0 else 0x5B)
        return True
    if family == 'ghost' and type_id == 0x2F:  # OBJHorizLogBackground
        _filled(pen, origin_x, origin_y, high, low, 0x82, 0)
        return True
    if family == 'ghost' and type_id == 0x30:  # OBJYoshiHouseGrass
        _cap_then_body(pen, origin_x, origin_y, high, low, 0x0F, 0xEA, 1, 0)
        return True
    if family == 'grass' and type_id == 0x3B:  # OBJRightDiagonalPlat
        _right_diagonal(pen, origin_x, origin_y, high, low)
        return True
    if family == 'grass' and type_id == 0x3C:  # OBJArches
        _arches(pen, origin_x, origin_y, low)
        return True
    if family == 'under' and type_id == 0x39:  # OBJCaveLavaSlopes
        _lava_slopes(pen, origin_x, origin_y, high, low)
        return True
    if family == 'under' and type_id == 0x37:  # OBJCanvasGrid
        _canvas_grid(pen)
        return True
    if family == 'castle' and type_id == 0x3D:  # OBJSlopedConveyors
        _conveyor(pen, origin_x, origin_y, high, low)
        return True
    return False

def _steep_slope(pen: _Pen, origin_x: int, origin_y: int, high: int, low: int) -> None:
    caps = (0xCA, 0xCB, 0xF1) if high % 2 == 0 else (0xCC, 0xCD, 0xF2)
    step = -1 if high % 2 == 0 else 1
    for piece in range(low + 1):
        column, row = origin_x, origin_y
        for tile in caps:
            _slope_put(pen, column, row, tile, 1)
            row += 1
        for _dirt in range((low - piece) * 2):
            _slope_put(pen, column, row, 0x3F, 0)
            row += 1
        origin_x += step
        origin_y += 2

def _edge_tile(pen: _Pen, column: int, row: int, tile: int, page: int) -> None:
    pen.x, pen.y = column, row
    pen.high = page
    seen = pen.low()
    if seen != 0x25:
        tile += 1 if seen == 0x3F else 2
    pen.put(tile)

def _right_diagonal(pen: _Pen, origin_x: int, origin_y: int, high: int, low: int) -> None:
    _edge_tile(pen, origin_x, origin_y, 0xAF, 0)
    _slope_adjust(pen, origin_x + 1, origin_y, 0xAF)
    span = 3
    for _row in range(low):
        origin_x -= 1
        origin_y += 1
        _edge_tile(pen, origin_x, origin_y, 0xA9, 0)
        column = origin_x + 1
        for _dirt in range(span - 2):
            _slope_put(pen, column, origin_y, 0x3F, 0)
            column += 1
        _slope_put(pen, column, origin_y, 0xE4, 1)
        _slope_adjust(pen, column + 1, origin_y, 0xAF)
        span += 2
    origin_x -= 1
    origin_y += 1
    span -= 1
    for _row in range(high + 1):
        _edge_tile(pen, origin_x, origin_y, 0xA9, 0)
        column = origin_x + 1
        for _dirt in range(span - 1):
            _slope_put(pen, column, origin_y, 0x3F, 0)
            column += 1
        _edge_tile(pen, column, origin_y, 0xF9 if _row == 0 else 0xAC, 1 if _row == 0 else 0)
        origin_x -= 1
        origin_y += 1

def _arches(pen: _Pen, origin_x: int, origin_y: int, low: int) -> None:
    if low == 0:
        raise ValueError('Unsupported arch settings')
    tiles = bytes.fromhex('070a0a080a0a09818283818283818125848125848181258481258481')
    index = 0
    for row in range(4):
        pen.high = 1 if row == 0 else 0
        column = origin_x
        for offset in range(3):
            pen.x, pen.y = column, origin_y + row
            pen.put(tiles[index + offset])
            column += 1
        for _middle in range(low - 1):
            for offset in range(3):
                pen.x, pen.y = column, origin_y + row
                pen.put(tiles[index + 3 + offset])
                column += 1
        pen.x, pen.y = column, origin_y + row
        pen.put(tiles[index + 6])
        index += 7

def _lava_slopes(pen: _Pen, origin_x: int, origin_y: int, high: int, low: int) -> None:
    pen.x, pen.y = origin_x, origin_y
    shape = low & 3
    if shape == 0:
        _slope_left(pen, high, 2, (0xD2, 0xD3), (0xFB, 0xFF), -2, adjust=False, dirt=0xFF, dirt_page=1)
    elif shape == 1:
        _slope_lip(pen, high, (0xD6,), (0xFD,), -1, adjust=False, dirt=0xFF, dirt_page=1)
    elif shape == 2:
        _slope_right(pen, high, (0xD4, 0xD5), (0xFF, 0xFC), adjust=False, dirt=0xFF, dirt_page=1)
    else:
        _slope_right(pen, high, (0xD7,), (0xFE,), adjust=False, dirt=0xFF, dirt_page=1)

def _conveyor(pen: _Pen, origin_x: int, origin_y: int, high: int, low: int) -> None:
    surface = (0xCE, 0xD1, 0xCF, 0xD0)[low & 3]
    lip = (0xF3, 0xF6, 0xF4, 0xF5)[low & 3]
    if (low & 2) == 0:
        _slope_lip(pen, high, (surface,), (lip,), -1, adjust=False)
        return
    count = high + 1
    column, row = origin_x, origin_y
    span = 0
    while True:
        if count == 0:
            return
        _slope_put(pen, column, row, surface, 1)
        column += 1
        row += 1
        column = origin_x
        span += 1
        reg = span
        count -= 1
        while reg != 1:
            _slope_put(pen, column, row, 0x3F, 0)
            column += 1
            reg -= 1
        _slope_put(pen, column, row, lip, 1)
        column += 1

def _canvas_block(pen: _Pen, origin_x: int, origin_y: int, start: int) -> None:
    tiles = bytes.fromhex(
        '5c5d5e607374757374757374757374757676765c5d5e607778797a7b7c777879'
        '7a7b7c7676765c5d5e60737d75737e757374757f74757676765c5d5e60778283'
        '7a8586817879847b7c767676')
    index = start
    for row, width, page in ((0, 4, 1), (1, 3, 0), (2, 3, 0), (3, 3, 0), (4, 3, 0), (5, 3, 0)):
        for column in range(width):
            pen.x, pen.y = origin_x + column, origin_y + row
            pen.high = page
            pen.put(tiles[index])
            index += 1
        if row == 4:
            pen.x, pen.y = origin_x + 3, origin_y + 4
            pen.high = 1
            pen.put(0x5F)

def _canvas_grid(pen: _Pen) -> None:
    for line in range(5):
        for column in range(16):
            pen.x, pen.y = column, 5 + 4 * line
            pen.high = 1
            pen.put(0x61)
    pattern = bytes.fromhex('5c5d5e607374756263645f767676')
    for column, row in ((0, 5), (8, 5), (4, 9), (12, 9), (0, 13), (8, 13), (4, 17), (12, 17)):
        for offset in range(4):
            pen.x, pen.y = column + offset, row
            pen.high = 1
            pen.put(pattern[offset])
        for band in range(1, 4):
            for offset in range(3):
                pen.x, pen.y = column + offset, row + band
                pen.high = 0
                pen.put(pattern[4 + offset])
        for offset in range(4):
            pen.x, pen.y = column + offset, row + 4
            pen.high = 1
            pen.put(pattern[7 + offset])
        for offset in range(3):
            pen.x, pen.y = column + offset, row + 5
            pen.high = 0
            pen.put(pattern[11 + offset])

def _plant(pen: _Pen, origin_x: int, origin_y: int, high: int, low: int) -> None:
    if low > 3:
        raise ValueError('Unsupported plant pillar')
    pen.high = 0
    pen.x, pen.y = origin_x, origin_y
    pen.put(bytes.fromhex('9a9c9ea0')[low], advance=True)
    pen.put(bytes.fromhex('9b9d9fa1')[low])
    if high == 0:
        return
    pen.high = 1
    pen.x, pen.y = origin_x, origin_y + 1
    pen.put(0x5F, advance=True)
    pen.put(0x60)
    pairs = bytes.fromhex('616263646566')
    index = 0
    for row in range(2, high + 1):
        pen.high = 1
        pen.x, pen.y = origin_x, origin_y + row
        pen.put(pairs[index], advance=True)
        pen.put(pairs[index + 1])
        index = (index + 2) % 6

def _sloped_guide(pen: _Pen, origin_x: int, origin_y: int, high: int, low: int) -> None:
    if low > 5:
        raise ValueError('Unsupported sloped guide')
    if low == 0:
        tiles, step = (0x8C, 0x8D), -2
    elif low == 2:
        tiles, step = (0x8E, 0x8F), 2
    elif low in (1, 4):
        tiles, step = ((0x94 if low == 4 else 0x86),), -1
    else:
        tiles, step = ((0x95 if low == 5 else 0x87),), 1
    for _step in range(high + 1):
        pen.high = 0
        for offset, tile in enumerate(tiles):
            pen.x, pen.y = origin_x + offset, origin_y
            pen.put(tile)
        origin_x += step
        origin_y += 1

def _draw_added(pen: _Pen, type_id: int, high: int, low: int, family: str,
                origin_x: int, origin_y: int) -> bool:
    if type_id == 0x11:  # OBJBulletCannon
        pen.high = 1
        pen.x, pen.y = origin_x, origin_y
        pen.put(0x41)
        if high >= 1:
            pen.down()
            pen.put(0x42)
        for _row in range(max(0, high - 1)):
            pen.down()
            pen.put(0x43)
        return True
    if type_id == 0x1D:  # OBJRepTileWithBottom
        _cap_then_body(pen, origin_x, origin_y, high, low, 0x0B, 0x0B, 0, 0)
        _filled(pen, origin_x, origin_y + high, 0, low, 0x0E, 0)
        return True
    if type_id == 0x1E:  # OBJClimbingNetEdge
        _net_edge(pen, origin_x, origin_y, high, low)
        return True
    if _guide(pen, type_id, high, low, family, origin_x, origin_y):
        return True
    switch = _SWITCH.get((family, type_id))
    if switch is not None:
        _filled(pen, origin_x, origin_y, high, low, switch, 0)
        return True
    if family == 'grass' and type_id == 0x30:  # OBJIcyPipe
        for row in range(high + 1):
            left, right = (0x61, 0x62) if row == 0 else (0x63, 0x64)
            pen.high = 1
            pen.x, pen.y = origin_x, origin_y + row
            pen.put(left, advance=True)
            pen.put(right)
        return True
    if family == 'grass' and type_id == 0x31:  # OBJIcyTurnBlocks, single-rep index $0E
        pen.high = 1
        for row in range(high + 1):
            for column in range(low + 1):
                pen.x, pen.y = origin_x + column, origin_y + row
                pen.put(0x65)
        return True
    if family == 'grass' and type_id == 0x33:  # OBJForestCanopy
        pattern = bytes.fromhex(
            'b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4'
            'b4b4b4b4b5b3b5b3b3b4b4b5b3b4b4b4b4b5b3b5b6b1b6b1b1b3b5b6b1b3b5b3b5b6b1b6'
            '2525252525b1b62525b1b6b1b625252525252525')
        copies = (high << 4 | low) + 1
        for copy in range(copies):
            _stamp(pen, origin_x, origin_y + 11 * copy, 16, 6, pattern, 0)
        return True
    if family == 'grass' and type_id == 0x34:  # OBJForestLedgeEdges
        if low > 3:
            raise ValueError('Unsupported forest edge')
        _column(pen, 0, bytes.fromhex('5f5e100f')[low], 1)
        pen.y = origin_y
        for _row in range(high):
            pen.down()
            pen.put(bytes.fromhex('605dc5c4')[low])
        return True
    if family == 'grass' and type_id == 0x35:  # OBJForestLedge
        _cap_then_body(pen, origin_x, origin_y, high, low, 0x0E, 0xB8, 1, 0)
        return True
    if family == 'grass' and type_id == 0x36:  # OBJBigTreeTrunk
        _big_tree(pen, origin_x, origin_y, high)
        return True
    if family == 'grass' and type_id == 0x37:  # OBJSmallTreeTrunk
        _small_tree(pen, origin_x, origin_y, high, low)
        return True
    if family == 'castle' and type_id == 0x3E:  # OBJHorizontalSpikes
        if high > 1:
            raise ValueError('Unsupported horizontal spikes')
        pen.high = 1
        for _step in range(low + 1):
            pen.put((0x5A, 0x59)[high], advance=True)
        return True
    if family == 'castle' and type_id == 0x3F:  # OBJVerticalSpikes
        if low > 2:
            raise ValueError('Unsupported vertical spikes')
        _column(pen, high, (0x5B, 0x5C, 0x53)[low], 1)
        return True
    if family != 'ghost':
        return False
    if type_id == 0x34:  # OBJWoodPlatWithSupport
        _wood_support(pen, origin_x, origin_y, high, low)
    elif type_id in (0x35, 0x36):  # OBJGhostHouseRepTiles
        page = type_id - 0x35
        _filled(pen, origin_x, origin_y, high, low, (0x92, 0x5E)[page], page)
    elif type_id == 0x37:  # OBJGhostHouseHoriz
        if low == 0 or high > 2:
            raise ValueError('Unsupported ghost house line')
        _capped_row(pen, low, (0x82, 0x89, 0x88)[high], (0x82, 0x8A, 0x88)[high], (0x82, 0x8B, 0x88)[high], 0)
    elif type_id == 0x38:  # OBJWoodPlatNoSupport
        _capped_row(pen, low, 0x0A, 0x0B, 0x0C, 1)
    elif type_id == 0x39:  # OBJVertLogBackground
        if low > 2:
            raise ValueError('Unsupported log background')
        _column(pen, high, (0x83, 0x78, 0x79)[low], 0)
    elif type_id == 0x3A:  # OBJGhostHouseVertSolid
        if low > 3:
            raise ValueError('Unsupported ghost house column')
        _column(pen, high, (0x5F, 0x60, 0x5A, 0x5B)[low], 1)
    elif type_id == 0x3B:  # OBJBonusPlatform
        _capped_row(pen, low, 0x07, 0x08, 0x09, 1)
    elif type_id == 0x3C:  # OBJPalaceCeiling
        _cap_then_body(pen, origin_x, origin_y, 0, low, 0x54, 0x54, 1, 1)
        if high:
            _filled(pen, origin_x, origin_y, high - 1, low, 0x53, 1)
            _cap_then_body(pen, origin_x, origin_y + high, 0, low, 0x54, 0x54, 1, 1)
    elif type_id == 0x3D:  # OBJPalaceFloor
        _cap_then_body(pen, origin_x, origin_y, high, low, 0x5D, 0x53, 1, 1)
    elif type_id == 0x3E:  # OBJPalaceLeftWall
        for row in range(high + 1):
            pen.y = origin_y + row
            pen.x = origin_x
            pen.high = 1
            for _step in range(low):
                pen.put(0x53, advance=True)
            pen.put(0x55)
    elif type_id == 0x3F:  # OBJPalaceRightWall
        for row in range(high + 1):
            pen.y = origin_y + row
            pen.x = origin_x
            pen.high = 1
            pen.put(0x5C, advance=True)
            for _step in range(low + 1 if low else 0):
                pen.put(0x53, advance=True)
    else:
        return False
    return True

def _big_tree(pen: _Pen, origin_x: int, origin_y: int, high: int) -> None:
    row = 0
    while row < high + 1:
        pen.x, pen.y = origin_x, origin_y + row
        pen.high = 0
        first = 0x0B if pen.low() == 0x0E else 0xB9
        pen.high = 1 if first == 0x0B else 0
        pen.put(first, advance=True)
        pen.put(first + 1)
        row += 1
        if row >= high + 1:
            return
        pen.high = 0
        pen.x, pen.y = origin_x, origin_y + row
        pen.put(0xBB, advance=True)
        pen.put(0xBC)
        row += 1

def _small_tree(pen: _Pen, origin_x: int, origin_y: int, high: int, low: int) -> None:
    if low > 1:
        raise ValueError('Unsupported small tree')
    row = 0
    while row < high + 1:
        pen.x, pen.y = origin_x, origin_y + row
        pen.high = 0
        tile = (0xBD, 0xBF)[low]
        if low == 1 and pen.low() in (0xB1, 0xB6):
            tile = pen.low() + 1
        elif low != 1 and pen.low() == 0x0E:
            pen.high = 1
            tile = 0x0D
        pen.put(tile)
        row += 1
        if row >= high + 1:
            return
        pen.high = 0
        pen.y = origin_y + row
        pen.put((0xBE, 0xC0)[low])
        row += 1

def _wood_support(pen: _Pen, origin_x: int, origin_y: int, high: int, low: int) -> None:
    if high == 0:
        raise ValueError('Unsupported supported platform')
    pen.x, pen.y = origin_x, origin_y
    _capped_row(pen, low * 4 + 3, 0x0A, 0x0B, 0x0C, 1)
    pen.high = 0
    for stem in range(low + 1):
        column = origin_x + 1 + 4 * stem
        pen.x, pen.y = column, origin_y + 1
        pen.put(0x78)
        for depth in range(1, high):
            pen.y = origin_y + 1 + depth
            pen.put(0x79)

def _goal_post(pen: _Pen, rows: int, kind: int) -> None:
    plain = (bytes.fromhex('2f2532'), bytes.fromhex('302533'), bytes.fromhex('313534'))
    tape = (bytes.fromhex('39253c'), bytes.fromhex('3a253d'), bytes.fromhex('3b253e'))
    tiles = tape if kind else plain
    for column in range(3):
        pen.x, pen.y = pen.record.x + column, pen.record.y
        pen.high = 0
        pen.put(tiles[0][column])
        left = rows
        left -= 1
        while left > 0:
            pen.down()
            pen.put(tiles[1][column])
            left -= 1
        pen.down()
        pen.put(tiles[2][column])

def _ceiling(pen: _Pen, origin_x: int, origin_y: int, rows: int, width: int) -> None:
    pen.high = 1
    for row in range(rows):
        for column in range(width + 1):
            pen.x, pen.y = origin_x + column, origin_y + row
            pen.put(0x65)
    for column in range(width + 1):
        pen.x, pen.y = origin_x + column, origin_y + rows
        pen.put(0x4E)

def _ceiling_edge(pen: _Pen, rows: int, kind: int) -> None:
    if kind > 3:
        raise ValueError(f'Unsupported ceiling edge ${kind:X}')
    shaft = bytes.fromhex('50505151')
    lip = bytes.fromhex('4d504f51')
    pen.high = 1
    for _row in range(rows):
        pen.put(shaft[kind])
        pen.down()
    pen.put(lip[kind], advance=True)
