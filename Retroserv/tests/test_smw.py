"""Synthetic inputs only. No commercial ROM content in the test suite."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import json
import pytest
from retroserv.lc_lz2 import decompress, LZ2Error
from retroserv.graphics import decode_tile, render_tiles
from retroserv.smw import (SMW_USA_V10_SHA256, lorom_to_pc, gfx_entry,
                           decoded_gfx, export_gfx, require_smw, gfx_bpp)


def test_profile_fingerprint_is_documented_sha():
    assert SMW_USA_V10_SHA256 == '0838e531fe22c077528febe14cb3ff7c492f1f5fa8de354192bdff7137c27f5b'


def test_3bpp_planes_and_rendering():
    raw = bytearray(24)
    raw[0], raw[1], raw[16] = 0b10000000, 0b01000000, 0b00100000
    assert decode_tile(bytes(raw), 3)[:8] == [1, 2, 4, 0, 0, 0, 0, 0]
    im = render_tiles(bytes(raw), 0, 3, 1)
    assert im.size == (128, 8)
    assert im.getpixel((0,0)) != im.getpixel((1,0))


def test_lz2_literal_byte_word_inc_and_repeat():
    # direct 3 bytes 'ABC', fill 2 x 'x', alternate 3 'YZ', incremental 3 starting 1,
    # reference first three bytes at output index 0, terminate.
    stream = bytes([2, 65, 66, 67, 0x21, 120, 0x42, 89, 90,
                    0x62, 1, 0x82, 0, 0, 0xFF])
    result = decompress(stream)
    assert result.data == b'ABCxxYZY\x01\x02\x03ABC'
    assert result.consumed == len(stream)
    assert result.commands == {'0':1,'1':1,'2':1,'3':1,'4':1}


def test_lz2_long_header_and_overlap():
    # Long direct copy length 34, header E0 21 (length-1 = 33)
    stream = bytes([0xE0, 33]) + b'A' * 34 + bytes([0x84,0,0,0xFF])
    assert decompress(stream).data == b'A'*39
    # Repeat first byte 4 more times with overlapping source
    assert decompress(bytes([0, ord('Z'), 0x83,0,0,0xFF])).data == b'ZZZZZ'


def test_lz2_fail_closed():
    invalid = [b'\xFF\x00', b'\x00', b'\x80\x00\x00\xff', b'\xE8\x00\xff', b'\x00\x2A']
    for stream in invalid[1:]:
        with pytest.raises(LZ2Error):
            decompress(stream)
    with pytest.raises(LZ2Error):
        decompress(bytes([0x7F, 0x00, 0xFF]), max_output=3)
    with pytest.raises(LZ2Error):
        decompress(bytes([0, 33, 0xFF]), max_input=1)
    with pytest.raises(LZ2Error):
        decompress(bytes([0xFF]), offset=1)


def test_lorom_offsets():
    assert lorom_to_pc(0x00B992) == 0x3992
    assert lorom_to_pc(0x088000) == 0x40000
    with pytest.raises(ValueError):
        lorom_to_pc(0x000200)
    with pytest.raises(ValueError):
        lorom_to_pc(0x7E8000)


class FakeRom:
    def __init__(self, path):
        self.path = Path(path)
        self.copier_header_size = 0
        raw = bytearray(0x80000)
        # Synthetic pointer to $088000 => PC 0x40000
        raw[0x3992] = 0x00
        raw[0x39C4] = 0x80
        raw[0x39F6] = 0x08
        # One synthetic 3bpp tile with pixel index 7 at (0,0)
        tile = bytearray(24)
        tile[0] = tile[1] = tile[16] = 0x80
        raw[0x40000:0x40000+26] = bytes([23]) + tile + b'\xff'
        self.data = bytes(raw)


def test_smw_pointer_and_export(tmp_path):
    rom = FakeRom(tmp_path/'synthetic.sfc')
    entry = gfx_entry(rom, 0, enforce_identity=False)
    assert (entry.snes_address, entry.data_offset, entry.bpp) == (0x088000, 0x40000, 3)
    info, data = decoded_gfx(rom, 0, enforce_identity=False)
    assert data.data[0] == 0x80 and len(data.data) == 24 and data.consumed == 26
    out = export_gfx(rom, 0, tmp_path/'export', enforce_identity=False)
    assert Path(out['png']).is_file() and Path(out['binary']).read_bytes() == data.data
    meta = json.loads(Path(out['manifest']).read_text())
    assert meta['source_rom_offset_hex'] == '0x40000'
    assert meta['source_snes_address'] == '$088000'
    assert meta['palette'].startswith('synthetic grayscale')
    with pytest.raises(FileExistsError):
        export_gfx(rom, 0, tmp_path/'export', enforce_identity=False)
    with pytest.raises(ValueError):
        require_smw(rom)
    assert gfx_bpp(0x27)[0] is None
    assert gfx_bpp(0x28)[0] == 2
    assert gfx_bpp(0x02)[0] == 3
