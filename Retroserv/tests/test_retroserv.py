from __future__ import annotations
import json
from hashlib import sha256
import pytest
from PIL import Image
from retroserv.demo import create_demo, DEMO_TILE_OFFSET, DEMO_PALETTE_OFFSET, DEMO_TEXT_OFFSET
from retroserv.rom import RomImage, RomError, parse_offset
from retroserv.graphics import decode_tile, read_palette, render_tiles, scan_graphics, bgr555_rgb
from retroserv.textscan import scan_ascii, hex_dump
from retroserv.export import graphics_export, binary_export


@pytest.fixture
def demo(tmp_path):
    path = tmp_path / 'retroserv_test.sfc'
    create_demo(path)
    return path


def test_demo_internal_header(demo):
    rom = RomImage(demo)
    assert rom.header
    assert rom.header.mapping == 'LoROM'
    assert rom.header.title == 'RETROSERV TEST DATA'
    assert rom.header.checksum_pair_valid
    assert rom.header.reset_vector == 0x8000
    assert rom.copier_header_size == 0
    assert rom.info()['sha256_original_file'] == sha256(demo.read_bytes()).hexdigest()


def test_copier_header_handling(demo, tmp_path):
    p = tmp_path / 'copier.smc'
    p.write_bytes(b'X'*512 + demo.read_bytes())
    rom = RomImage(p)
    assert rom.copier_header_size == 512
    assert rom.header.mapping == 'LoROM'
    assert rom.data == demo.read_bytes()


def test_bounds_safety_and_bad_data(tmp_path, demo):
    with pytest.raises(RomError):
        RomImage(tmp_path / 'absent.sfc')
    p = tmp_path / 'tiny.sfc'
    p.write_bytes(b'0' * 16)
    with pytest.raises(RomError):
        RomImage(p)
    rom = RomImage(demo)
    with pytest.raises(ValueError):
        rom.slice(len(rom.data) - 4, 10)
    with pytest.raises(ValueError):
        rom.slice(-1, 1)
    with pytest.raises(ValueError):
        rom.slice(0, 0)
    with pytest.raises(ValueError):
        parse_offset('-1')
    assert parse_offset('$A000') == 0xA000
    assert parse_offset('0xA000') == 0xA000
    assert parse_offset('40960') == 40960


def test_2bpp_planes():
    raw = bytearray(16)
    raw[0] = 0b10000000
    raw[1] = 0b01000000
    assert decode_tile(bytes(raw), 2)[:8] == [1,2,0,0,0,0,0,0]


def test_4bpp_planes():
    raw = bytearray(32)
    raw[0] = 0x80
    raw[1] = 0x80
    raw[16] = 0x80
    raw[17] = 0x80
    assert decode_tile(bytes(raw), 4)[0] == 15


def test_8bpp_planes():
    raw = bytearray(64)
    for plane in range(8):
        raw[(plane//2)*16 + (plane%2)] = 0x80
    assert decode_tile(bytes(raw), 8)[0] == 255


def test_bgr555_conversion():
    assert bgr555_rgb(0x001f) == (255,0,0)
    assert bgr555_rgb(0x03e0) == (0,255,0)
    assert bgr555_rgb(0x7c00) == (0,0,255)
    assert read_palette(b'\x1f\x00\xe0\x03', 2) == [(255,0,0),(0,255,0)]


def test_synthetic_tiles_and_palette(demo):
    rom = RomImage(demo)
    pal = read_palette(rom.slice(DEMO_PALETTE_OFFSET, 32),16)
    assert pal[1] == (255,0,0)
    img = render_tiles(rom.data, DEMO_TILE_OFFSET,4,64,8,pal,transparent_zero=True)
    assert img.size == (64,64)
    assert img.getpixel((0,0)) == (255,0,0,255)
    assert img.getpixel((3,3))[3] == 255
    assert img.getpixel((4,4))[3] in (0,255)


def test_strings_and_hex(demo):
    rom = RomImage(demo)
    rows = scan_ascii(rom.data, 12)
    assert any('RETROSERV ORIGINAL SAMPLE TEXT' in s.text and s.offset == DEMO_TEXT_OFFSET for s in rows)
    assert '00012000' in hex_dump(rom.data, DEMO_TILE_OFFSET, 16)


def test_export_with_sidecars(demo, tmp_path):
    rom = RomImage(demo)
    target = tmp_path / 'tiles.png'
    result = graphics_export(rom,target,DEMO_TILE_OFFSET,4,64,8,DEMO_PALETTE_OFFSET,True)
    assert target.exists()
    with Image.open(target) as image:
        assert image.size == (64,64)
    metadata = json.loads((tmp_path / 'tiles.retroserv.json').read_text())
    assert metadata['data_offset_hex'] == f'0x{DEMO_TILE_OFFSET:X}'
    assert metadata['verified_game_asset'] is False
    assert metadata['source_sha256'] == sha256(demo.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        graphics_export(rom,target,DEMO_TILE_OFFSET,4,64)
    dest = tmp_path / 'slice.bin'
    binary_export(rom,dest,DEMO_TEXT_OFFSET,10)
    assert dest.read_bytes() == b'RETROSERV '
    with pytest.raises(ValueError):
        binary_export(rom, demo, 0, 64, overwrite=True)


def test_scan_contract(demo):
    rom = RomImage(demo)
    candidates = scan_graphics(rom.data,4,512,16,20)
    assert len(candidates) <= 20
    assert all(0 <= c.offset < len(rom.data) and 0 < c.score <= 1 for c in candidates)
    assert candidates == sorted(candidates, key=lambda c: c.score, reverse=True)


def test_no_rom_mutation(demo, tmp_path):
    rom = RomImage(demo)
    original_hash = sha256(demo.read_bytes()).hexdigest()
    graphics_export(rom,tmp_path/'tiles.png', DEMO_TILE_OFFSET,4,64)
    binary_export(rom,tmp_path/'raw.bin',DEMO_TILE_OFFSET,128)
    assert sha256(demo.read_bytes()).hexdigest() == original_hash

@pytest.mark.parametrize('mapping,pos,mode,bytes_total,boot',[
    ('HiROM',0xFFC0,0x21,128*1024,0x8000),
    ('ExHiROM',0x40FFC0,0x25,5*1024*1024,0x408000),
])
def test_other_header_layouts(tmp_path, mapping, pos, mode, bytes_total, boot):
    img = bytearray([0xff]) * bytes_total
    img[boot] = 0x78
    img[pos:pos+21] = b'ORIGINAL TEST CART   '
    img[pos+0x15:pos+0x1c] = bytes([mode, 0, 0x0d, 0, 1, 0, 0])
    img[pos+0x3c:pos+0x3e] = (0x8000).to_bytes(2,'little')
    img[pos+0x1c:pos+0x1e] = b'\xff\xff'
    img[pos+0x1e:pos+0x20] = b'\x00\x00'
    checksum = sum(img) & 0xffff
    img[pos+0x1c:pos+0x1e] = (checksum ^ 0xffff).to_bytes(2,'little')
    img[pos+0x1e:pos+0x20] = checksum.to_bytes(2,'little')
    file = tmp_path / (mapping + '.sfc')
    file.write_bytes(img)
    parsed = RomImage(file)
    assert parsed.header is not None
    assert parsed.header.mapping == mapping
    assert parsed.header.checksum_pair_valid
