"""Ledges, ledge edges, and ground slopes for the SMW foreground."""
from __future__ import annotations

from .smw_pen import EMPTY_TILE, _Pen, _replace

def _ledge(pen: _Pen, origin_x: int, origin_y: int, width: int, fills: int) -> None:
    for column in range(width):
        pen.x, pen.y = origin_x + column, origin_y
        pen.high = 1
        pen.put(0x00)
        pen.high = 0
        for depth in range(1, fills + 1):
            pen.y = origin_y + depth
            pen.put(0x3F)

def _ledge_edge(pen: _Pen, rows: int, kind: int) -> None:
    if kind > 14:
        raise ValueError(f'Unsupported ledge edge ${kind:X}')
    top = bytes.fromhex('404106454b484c0103b6b7454b484c')
    body = bytes.fromhex('4041064b4b4c4c40414b4c4b4b4c4c')
    foot = bytes.fromhex('ffffffffffffffffffffff e2e2e4e4'.replace(' ', ''))
    top_found = bytes.fromhex('7d7e82839b9ca0a1aaabafb0d8dcdee0e2e4')
    top_used = bytes.fromhex('b8b9babbbcbdbebfc0c1c2c3d9dddf e1e3e5'.replace(' ', ''))
    body_found = bytes.fromhex('6e6f737478797d7e828387888c8d919296979b9ca0a1a5a6aaabafb0e2e4')
    body_used = bytes.fromhex('707075757a7a7f7f848489898e8e939398989d9da2a2a7a7acacb1b1e9ea')

    def top_tile(tile: int) -> int:
        if 0x09 <= kind < 0x0B or kind == 2:
            return tile
        found = _replace(pen.low(), top_found, top_used)
        if found is not None:
            pen.high = 1
            return found
        if pen.low() != 0x25 and tile in (0x01, 0x03, 0x45, 0x48):
            return tile + 1
        return tile

    def body_tile(tile: int) -> int:
        if kind >= 9 or 3 <= kind < 7 or kind == 2:
            return tile
        found = _replace(pen.low(), body_found, body_used)
        if found is not None:
            pen.high = 1
            return found
        return tile

    def body_page() -> None:
        pen.high = 1 if kind >= 9 or 3 <= kind < 7 else 0

    pen.high = 0 if kind < 3 else 1
    pen.put(top_tile(top[kind]))
    pen.down()
    rows -= 1
    if rows < 0:
        _edge_foot(pen, kind, foot)
        return
    body_page()
    pen.put(body_tile(body[kind]))
    pen.down()
    rows -= 1
    while rows >= 0:
        body_page()
        pen.put(body_tile(body[kind]))
        pen.down()
        rows -= 1
    _edge_foot(pen, kind, foot)

def _edge_foot(pen: _Pen, kind: int, foot: bytes) -> None:
    if kind >= 0x0B:
        pen.high = 1
        pen.put(foot[kind])

def _ground_slope(pen: _Pen, settings: int) -> None:
    """OBJSlopes. Shapes 0, 1 and 2 step left; 3, 4 and 5 stay put and fill right;
    6 and 8 step right. The row origin follows the bank 0D cursor."""
    kind = settings & 15
    while kind >= 10:
        kind -= 10
    high = settings >> 4
    if kind == 0:
        _slope_left(pen, high, 2, (0x96, 0x9B), (0xDE, 0xE6), -2)
    elif kind == 1:
        _slope_lip(pen, high, (0xAA,), (0xE2,), -1)
    elif kind == 2:
        _slope_left(pen, high, 4, (0x6E, 0x73, 0x78, 0x7D), (0xD8, 0xDA, 0xE6, 0xE6), -4)
    elif kind == 3:
        _slope_right(pen, high, (0xA0, 0xA5), (0xE6, 0xE0))
    elif kind == 4:
        _slope_right(pen, high, (0xAF,), (0xE4,))
    elif kind == 5:
        _slope_right(pen, high, (0x82, 0x87, 0x8C, 0x91), (0xE6, 0xE6, 0xDB, 0xDC))
    elif kind == 6:
        _slope_steep(pen, high, 2, (0xEE, 0xF0), (0xC6, 0xC7), 4, 0x65)
    elif kind == 7:
        _slope_inner(pen, high, 2, 4, (0xF0, 0xEF), (0xC8, 0xC9), 0x65)
    elif kind == 8:
        _slope_steep(pen, high, 1, (0xEC,), (0xC4,), 2, 0x65)
    else:
        _slope_inner(pen, high, 1, 2, (0xED,), (0xC5,), 0x65)

def _slope_adjust(pen: _Pen, column: int, row: int, tile: int) -> None:
    pen.x, pen.y = column, row
    pen.high = 1
    pen.put(tile + {0x3F: 1, 0x01: 3, 0x03: 4}.get(pen.low(), 0))

def _slope_put(pen: _Pen, column: int, row: int, tile: int, page: int) -> None:
    pen.x, pen.y = column, row
    pen.high = page
    pen.put(tile)

def _slope_left(pen: _Pen, high: int, width: int, surfaces: tuple[int, ...],
                lips: tuple[int, ...], step: int, *, adjust: bool = True,
                dirt: int = 0x3F, dirt_page: int = 0) -> None:
    count = high + 1
    origin_x, origin_y = pen.x, pen.y
    span = width - 1
    while True:
        column = origin_x
        for tile in surfaces:
            if adjust:
                _slope_adjust(pen, column, origin_y, tile)
            else:
                _slope_put(pen, column, origin_y, tile, 1)
            column += 1
        entered = span - width
        if entered >= 0:
            _slope_under(pen, column, origin_y, lips, entered, dirt, dirt_page)
        span += width
        count -= 1
        if count == 0:
            _slope_under(pen, origin_x, origin_y + 1, lips, span - width, dirt, dirt_page)
            return
        origin_x += step
        origin_y += 1

def _slope_under(pen: _Pen, column: int, row: int, lips: tuple[int, ...], entered: int,
                 dirt: int = 0x3F, dirt_page: int = 0) -> None:
    for tile in lips:
        _slope_put(pen, column, row, tile, 1)
        column += 1
    entered -= 1
    while True:
        entered -= 1
        if entered < 0:
            return
        _slope_put(pen, column, row, dirt, dirt_page)
        column += 1

def _slope_lip(pen: _Pen, high: int, surfaces: tuple[int, ...], lips: tuple[int, ...], step: int, *,
               adjust: bool = True, dirt: int = 0x3F, dirt_page: int = 0) -> None:
    """Shape 1: one surface tile, then an under-tile and dirt on the rows below."""
    count = high + 1
    origin_x, origin_y = pen.x, pen.y
    span = 0
    while True:
        column = origin_x
        for tile in surfaces:
            if adjust:
                _slope_adjust(pen, column, origin_y, tile)
            else:
                _slope_put(pen, column, origin_y, tile, 1)
            column += 1
        reg = span - 1
        if reg >= 0:
            for tile in lips:
                _slope_put(pen, column, origin_y, tile, 1)
                column += 1
                reg -= 1
            while reg >= 0:
                _slope_put(pen, column, origin_y, dirt, dirt_page)
                column += 1
                reg -= 1
        span += 1
        count -= 1
        if count == 0:
            column = origin_x
            reg = span - 1
            row = origin_y + 1
            for tile in lips:
                _slope_put(pen, column, row, tile, 1)
                column += 1
                reg -= 1
            while reg >= 0:
                _slope_put(pen, column, row, dirt, dirt_page)
                column += 1
                reg -= 1
            return
        origin_x += step
        origin_y += 1

def _slope_right(pen: _Pen, high: int, surfaces: tuple[int, ...], lips: tuple[int, ...], *,
                 adjust: bool = True, dirt: int = 0x3F, dirt_page: int = 0) -> None:
    count = high + 1
    origin_x, origin_y = pen.x, pen.y
    column, row = origin_x, origin_y
    span = len(surfaces) - 1
    while True:
        if count == 0:
            return
        for tile in surfaces:
            if adjust:
                _slope_adjust(pen, column, row, tile)
            else:
                _slope_put(pen, column, row, tile, 1)
            column += 1
        row += 1
        column = origin_x
        span += len(surfaces)
        count -= 1
        if count < 0:
            return
        reg = span
        while reg != len(surfaces) * 2 - 1:
            _slope_put(pen, column, row, dirt, dirt_page)
            column += 1
            reg -= 1
        for tile in lips:
            _slope_put(pen, column, row, tile, 1)
            column += 1
        if count == 0:
            return

def _slope_steep(pen: _Pen, high: int, step: int, upper: tuple[int, ...], lower: tuple[int, ...],
                 dirt_at: int, dirt: int) -> None:
    origin_x, origin_y = pen.x, pen.y
    span = high * step - (step - 1)
    started = False
    while True:
        column = origin_x
        reg = span
        if started:
            for tile in lower:
                _slope_put(pen, column, origin_y, tile, 1)
                column += 1
                reg -= 1
            if reg < 0:
                lower_done = True
            else:
                lower_done = False
            if not lower_done:
                for tile in upper:
                    _slope_put(pen, column, origin_y, tile, 1)
                    column += 1
                    reg -= 1
        else:
            for tile in upper:
                _slope_put(pen, column, origin_y, tile, 1)
                column += 1
                reg -= 1
        while reg >= 0:
            _slope_put(pen, column, origin_y, dirt, 1)
            column += 1
            reg -= 1
        if not started:
            started = True
            origin_y += 1
        else:
            span -= step
            origin_x += step
            origin_y += 1
        high -= 1
        if high < 0:
            return

def _slope_inner(pen: _Pen, high: int, step: int, wide: int, edge: tuple[int, ...],
                 core: tuple[int, ...], dirt: int) -> None:
    origin_x, origin_y = pen.x, pen.y
    span = high * step + (step - 1)
    first = True
    while True:
        column, reg = origin_x, span
        while reg >= wide:
            _slope_put(pen, column, origin_y, dirt, 1)
            column += 1
            reg -= 1
        if reg >= step:
            for tile in edge:
                _slope_put(pen, column, origin_y, tile, 1)
                column += 1
        if not first:
            for tile in core:
                _slope_put(pen, column, origin_y, tile, 1)
                column += 1
        first = False
        span -= step
        origin_y += 1
        high -= 1
        if high < 0:
            return

def _left_diagonal(pen: _Pen, x: int, y: int, high: int, low: int) -> None:
    def previous(column, row):
        placed = pen.tiles.get((column, row))
        return (placed.map16_id if placed else EMPTY_TILE) & 0xFF

    def slope(column, row, tile):
        pen.x, pen.y = column, row
        pen.high = 1
        pen.put(tile + {0x3F: 1, 0x01: 3, 0x03: 4}.get(previous(column, row), 0))

    def right_edge(column, row, tile):
        pen.x, pen.y = column, row
        seen = previous(column, row)
        pen.high = 0
        pen.put(tile + (0 if seen == EMPTY_TILE else (1 if seen == 0x3F else 2)))

    slope(x, y, 0xAA)
    right_edge(x + 1, y, 0xA1)
    for step in range(1, low + 1):
        column, row = x - step, y + step
        slope(column, row, 0xAA)
        pen.x, pen.y = column + 1, row
        pen.high = 1
        pen.put(0xE2)
        pen.high = 0
        for interior in range(column + 2, x + step + 1):
            pen.x = interior
            pen.put(0x3F)
        right_edge(x + step + 1, row, 0xA6)
    for depth in range(high + 1):
        column, row = x - low + depth, y + low + 1 + depth
        if depth == 0:
            slope(column, row, 0xF7)
        else:
            right_edge(column, row, 0xA3)
        pen.high = 0
        for interior in range(column + 1, column + 2 * low + 2):
            pen.x, pen.y = interior, row
            pen.put(0x3F)
        right_edge(column + 2 * low + 2, row, 0xA6)
