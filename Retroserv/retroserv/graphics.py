"""SNES 2/3/4/8bpp planar tile decoding and BGR555 palettes."""
from __future__ import annotations
from dataclasses import dataclass
from math import ceil
from PIL import Image


def bgr555_rgb(value: int) -> tuple[int, int, int]:
    r, g, b = value & 31, (value >> 5) & 31, (value >> 10) & 31
    return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))


def read_palette(raw: bytes, count: int) -> list[tuple[int, int, int]]:
    if len(raw) < count * 2:
        raise ValueError(f"Need {count * 2} bytes for {count} palette entries")
    return [bgr555_rgb(int.from_bytes(raw[i*2:i*2+2], 'little')) for i in range(count)]


def default_palette(bpp: int) -> list[tuple[int, int, int]]:
    n = 1 << bpp
    return [(round(i * 255 / (n-1)),) * 3 for i in range(n)]


def decode_tile(raw: bytes, bpp: int) -> list[int]:
    """Return 64 indexed pixels in row-major order."""
    if bpp not in (2, 3, 4, 8):
        raise ValueError('SNES planar bpp must be 2, 3, 4, or 8')
    if len(raw) != 8 * bpp:
        raise ValueError(f'Expected exactly {8*bpp} tile bytes')
    result = []
    for y in range(8):
        for x in range(8):
            bit = 7 - x
            idx = 0
            for plane_pair in range(bpp // 2):
                base = 16 * plane_pair + 2*y
                idx |= ((raw[base] >> bit) & 1) << (plane_pair * 2)
                idx |= ((raw[base + 1] >> bit) & 1) << (plane_pair * 2 + 1)
            if bpp == 3:
                idx |= ((raw[16 + y] >> bit) & 1) << 2
            result.append(idx)
    return result


def render_tiles(rom_data: bytes, offset: int, bpp: int, tile_count: int = 128,
                 columns: int = 16, palette: list[tuple[int,int,int]] | None = None,
                 transparent_zero: bool = False) -> Image.Image:
    if bpp not in (2, 3, 4, 8):
        raise ValueError('BPP must be 2, 3, 4, or 8')
    if not 1 <= tile_count <= 8192:
        raise ValueError('Tile count must be in range 1..8192')
    if not 1 <= columns <= 64:
        raise ValueError('Columns must be in range 1..64')
    if offset < 0 or offset + tile_count * bpp * 8 > len(rom_data):
        raise ValueError('Tile data exceeds ROM bounds')
    colors = palette if palette is not None else default_palette(bpp)
    if len(colors) < (1 << bpp):
        raise ValueError(f'{bpp}bpp requires {1 << bpp} palette entries')
    width, height = columns * 8, ceil(tile_count / columns) * 8
    out = Image.new('RGBA', (width, height), (0, 0, 0, 0) if transparent_zero else (0,0,0,255))
    pixels = out.load()
    tile_bytes = bpp * 8
    for tile_index in range(tile_count):
        start = offset + tile_index * tile_bytes
        tile = decode_tile(rom_data[start:start + tile_bytes], bpp)
        dx, dy = tile_index % columns * 8, tile_index // columns * 8
        for y in range(8):
            for x in range(8):
                c = tile[y*8+x]
                pixels[dx+x, dy+y] = (*colors[c], 0 if (transparent_zero and c == 0) else 255)
    return out


@dataclass(frozen=True)
class Candidate:
    offset: int
    bpp: int
    score: float
    distinct_colors: int
    adjacent_pixel_match: float

    def to_dict(self):
        return {'offset': self.offset, 'bpp': self.bpp,
                'score': round(self.score, 4), 'distinct_colors': self.distinct_colors,
                'adjacent_pixel_match': round(self.adjacent_pixel_match, 4)}


def scan_graphics(data: bytes, bpp: int = 4, step: int = 512,
                  sample_tiles: int = 16, limit: int = 20) -> list[Candidate]:
    """Rank potential planar tile regions by local color smoothness.

    Heuristic ONLY: these regions are not verified sprites, backgrounds, or tiles.
    Compressed data and game code can score; legitimate complex graphics can score poorly.
    """
    if bpp not in (2, 3, 4, 8):
        raise ValueError('BPP must be 2, 3, 4, or 8')
    if step < 32 or step > 65536 or sample_tiles < 2 or sample_tiles > 256 or not 1 <= limit <= 100:
        raise ValueError('Invalid step, sample_tiles, or limit')
    tilebytes = bpp * 8
    needed = tilebytes * sample_tiles
    if len(data) < needed:
        return []
    ranked: list[Candidate] = []
    for offset in range(0, len(data) - needed + 1, step):
        block = data[offset:offset + needed]
        # Dismiss almost blank input, common in unfilled ROM regions.
        if max(block.count(0), block.count(255)) > int(0.85 * needed):
            continue
        tiles = [decode_tile(block[i*tilebytes:(i+1)*tilebytes], bpp) for i in range(sample_tiles)]
        present = set(c for tile in tiles for c in tile)
        if len(present) < 3:
            continue
        edges = 0
        matching = 0
        for tile in tiles:
            for y in range(8):
                for x in range(7):
                    edges += 1
                    matching += tile[y*8+x] == tile[y*8+x+1]
            for y in range(7):
                for x in range(8):
                    edges += 1
                    matching += tile[y*8+x] == tile[(y+1)*8+x]
        smooth = matching / edges
        if smooth < 0.35 or smooth > 0.975:
            continue
        # Rank approximate coherence; never frame as definitive detection.
        score = smooth * (1.0 - abs(smooth - 0.71) * 0.1)
        ranked.append(Candidate(offset, bpp, score, len(present), smooth))
    ranked.sort(key=lambda c: c.score, reverse=True)
    return ranked[:limit]
