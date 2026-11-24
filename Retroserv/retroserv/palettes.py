"""Imported SNES CGRAM and Lunar Magic RGB palettes."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .graphics import read_palette


@dataclass(frozen=True)
class ImportedPalette:
    name: str
    format: str
    sha256: str
    colors: tuple[tuple[int, int, int], ...]

    def group(self, start: int, bpp: int) -> list[tuple[int, int, int]]:
        end = start + (1 << bpp)
        if start < 0 or end > len(self.colors):
            raise ValueError(f'{bpp}bpp palette group must fit in color indices 0–255')
        return list(self.colors[start:end])


def load_palette(filename: str | Path) -> ImportedPalette:
    path = Path(filename)
    with path.open('rb') as file:
        raw = file.read(769)
    if len(raw) == 512:
        format_name = 'SNES CGRAM BGR555'
        colors = tuple(read_palette(raw, 256))
    elif len(raw) == 768:
        format_name = 'Lunar Magic RGB'
        colors = tuple((raw[i], raw[i + 1], raw[i + 2]) for i in range(0, 768, 3))
    else:
        raise ValueError('Expected a 512-byte CGRAM dump or a 768-byte Lunar Magic .pal file')
    return ImportedPalette(path.name, format_name, sha256(raw).hexdigest(), colors)
