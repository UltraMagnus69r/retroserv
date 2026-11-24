from hashlib import sha256

import pytest

from retroserv.lc_lz2 import LZ2Result
from retroserv.palettes import load_palette
from retroserv.smw import GfxEntry, gfx_preview


@pytest.mark.parametrize(('raw', 'format_name'), [
    (bytes(4) + b'\x1f\x00' + bytes(506), 'SNES CGRAM BGR555'),
    (bytes(6) + b'\xff\x00\x00' + bytes(759), 'Lunar Magic RGB'),
])
def test_imported_palette_colors_tile_from_selected_group(tmp_path, raw, format_name):
    path = tmp_path / 'palette.dump'
    path.write_bytes(raw)
    palette = load_palette(path)
    assert palette.format == format_name
    assert palette.sha256 == sha256(raw).hexdigest()
    entry = GfxEntry(0, 0x808000, 0, 3, '')
    result = LZ2Result(b'\x80' + bytes(23), 0, {})
    image = gfx_preview(entry, result, palette=palette, palette_start=1)
    assert image.getpixel((0, 0)) == (255, 0, 0, 255)
    assert image.getpixel((1, 0))[3] == 0
    assert len(palette.group(248, 3)) == 8
    with pytest.raises(ValueError, match='must fit'):
        palette.group(249, 3)


def test_rejects_invalid_palette_size(tmp_path):
    path = tmp_path / 'bad.pal'
    path.write_bytes(bytes(513))
    with pytest.raises(ValueError, match='512-byte CGRAM'):
        load_palette(path)
