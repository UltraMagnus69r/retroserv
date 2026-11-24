"""The Yoshi's Island sky is the background list in bank $0C, drawn behind the ground."""
from pathlib import Path

import pytest
from PIL import Image

from retroserv.rom import RomImage
from retroserv.smw_background import background_tiles, place_background
from retroserv.smw_foreground import render_opening_foreground
from retroserv.smw_level import read_level
from retroserv.smw_snapshot import inspect_level

ROM = Path.home() / 'Desktop/Super Mario World (USA)/Super Mario World (USA).sfc'


@pytest.mark.skipif(not ROM.exists(), reason='requires the local SMW cartridge')
def test_yoshis_island_background_is_two_screens_behind_the_ground():
    rom = RomImage(ROM)
    level = read_level(rom, 0x105)
    tiles, page = background_tiles(rom, level.layer2_pointer)
    assert level.layer2_pointer == 0xFFD900
    assert page == 0
    assert len(tiles) == 16 * 27 * 2
    assert tiles[0] == 0

    foreground = render_opening_foreground(rom, 0x105)
    snapshot = inspect_level(rom, 0x105)
    shown = snapshot.surface.image
    assert shown.getpixel((4, 4))[:3] == (0, 99, 189)
    ground = foreground.tiles[1, 25]
    opaque = next(
        (dx, dy) for dy in range(16) for dx in range(16)
        if foreground.image.getpixel((16 + dx, 25 * 16 + dy))[3])
    assert shown.getpixel((16 + opaque[0], 25 * 16 + opaque[1])) == foreground.image.getpixel(
        (16 + opaque[0], 25 * 16 + opaque[1]))
    assert snapshot.surface.cells[1, 25].caption == f'Map16 ${ground.map16_id:03X}'


def test_a_second_level_does_not_read_the_background_list():
    assert background_tiles(None, 0x06ABCD) is None


@pytest.mark.skipif(not ROM.exists(), reason='requires the local SMW cartridge')
def test_backdrop_shows_through_an_empty_foreground_pixel():
    rom = RomImage(ROM)

    class Header:
        header_hex = '3340088027'

    class Level:
        layer1 = Header()
        layer2_pointer = 0x06ABCD

    image = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    image.putpixel((1, 1), (9, 8, 7, 255))
    placed = place_background(rom, Level(), image)
    assert placed.getpixel((0, 0)) == (0, 99, 189, 255)
    assert placed.getpixel((1, 1)) == (9, 8, 7, 255)
