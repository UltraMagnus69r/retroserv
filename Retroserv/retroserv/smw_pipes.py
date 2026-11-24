"""Pipe objects for the SMW foreground."""
from __future__ import annotations

from .smw_pen import _Pen

def _vertical_pipe(pen: _Pen, rows: int, kind: int) -> None:
    if kind > 5:
        raise ValueError(f'Unsupported vertical pipe ${kind:X}')
    caps = (0x33, 0x37, 0x39)
    caps_right = (0x34, 0x38, 0x3A)
    bottoms = (None, None, 0x39, 0x33, 0x37)
    bottoms_right = (None, None, 0x3A, 0x34, 0x38)
    origin = pen.x
    pen.high = 1

    def pair(left: int, right: int) -> None:
        pen.x = origin
        pen.put(left, advance=True)
        pen.put(right)

    def stem() -> None:
        pair(0x35, 0x36)

    if kind < 3:
        pair(caps[kind], caps_right[kind])
    elif kind == 5:
        pair(0x68, 0x69)
    else:
        stem()
    while True:
        pen.y += 1
        if kind == 5 or kind < 2:
            rows -= 1
            if rows < 0:
                return
            stem() if kind != 5 else pair(0x68, 0x69)
            continue
        rows -= 1
        if rows != 0:
            stem()
            continue
        pair(bottoms[kind], bottoms_right[kind])
        return

def _horizontal_pipe(pen: _Pen, settings: int) -> None:
    width = settings & 15
    kind = (settings & 0xF0) >> 3
    if kind > 6:
        raise ValueError(f'Unsupported horizontal pipe ${kind:X}')
    ends = bytes.fromhex('3b3c3b3f3b3c3b3f')
    middles = bytes.fromhex('3d3e3d3e3d3e3d3e')
    pen.high = 1
    while True:
        row_x, row_y = pen.x, pen.y
        remaining = width
        pen.put(ends[kind] if kind < 4 else middles[kind], advance=True)
        if kind < 4:
            while remaining >= 0:
                remaining -= 1
                if remaining < 0:
                    break
                pen.put(middles[kind], advance=True)
        else:
            while remaining != 0:
                remaining -= 1
                if remaining == 0:
                    break
                pen.put(middles[kind], advance=True)
            pen.put(ends[kind])
        pen.x, pen.y = row_x, row_y + 1
        kind += 1
        if kind & 1 == 0:
            return

def _diagonal_pipe(pen: _Pen, rows: int) -> None:
    order = bytes.fromhex('c4c5c7ecedc6c7ee595aefc7ee595b5c')
    span = 1
    index = 0
    pen.high = 1

    def band() -> None:
        nonlocal index
        start_x, start_y = pen.x, pen.y
        for _step in range(span + 1):
            pen.put(order[index], advance=True)
            index += 1
        pen.x, pen.y = start_x - 1, start_y + 1

    while True:
        band()
        span += 2
        rows -= 1
        if rows < 0:
            break
        if index != 6:
            continue
        span -= 1
        while True:
            band()
            if index == 0x10:
                index -= 5
            rows -= 1
            if rows < 0:
                break
        break
    pen.x += 1
    pen.put(0xEB)
