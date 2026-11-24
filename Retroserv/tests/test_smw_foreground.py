from pathlib import Path

import pytest

from PIL import Image

from retroserv.rom import RomImage
from retroserv.smw_foreground import (
    ForegroundTile, OpeningForeground, _draw_object, foreground_supported,
    render_opening_foreground,
)
from retroserv.smw_map16 import _palette
from retroserv.smw_rebuild import left_screen_differences
from retroserv.smw import lorom_to_pc
from retroserv.smw_level import LevelRecord, level_catalog, read_level

ROM = Path.home() / 'Desktop/Super Mario World (USA)/Super Mario World (USA).sfc'


BUSH_TABLE = bytes(range(15))


def test_ledge_and_bush_dimensions_and_provenance():
    ledge = LevelRecord('object', 10, '58 10 03', 0, 0x21, 0, 24)
    bush = LevelRecord('object', 13, '78 f1 02', 0, 0x3F, 1, 24)
    tiles = {}
    _draw_object(ledge, tiles, BUSH_TABLE)
    assert len(tiles) == 16
    assert tiles[0, 24] == ForegroundTile(0x100, ledge)
    assert tiles[3, 27] == ForegroundTile(0x03F, ledge)

    _draw_object(bush, tiles, BUSH_TABLE)
    assert [tiles[x, 24] for x in range(1, 4)] == [ForegroundTile(tile, bush) for tile in (0, 5, 10)]
    assert tiles[1, 25].source is ledge


def test_left_diagonal_platform_uses_preceding_tile_and_keeps_source():
    ledge = LevelRecord('object', 10, '42 10 03', 0, 0x21, 0, 2)
    diagonal = LevelRecord('object', 13, '63 a2 11', 0, 0x3A, 2, 3)
    tiles = {}
    _draw_object(ledge, tiles, BUSH_TABLE)
    _draw_object(diagonal, tiles, BUSH_TABLE)
    assert tiles[2, 3] == ForegroundTile(0x1AB, diagonal)
    assert tiles[1, 4] == ForegroundTile(0x1AB, diagonal)
    assert tiles[2, 4] == ForegroundTile(0x1E2, diagonal)
    assert tiles[1, 5] == ForegroundTile(0x1F8, diagonal)
    assert tiles[2, 6] == ForegroundTile(0x0A3, diagonal)


def test_new_ground_pipes_and_bonus_ceiling_keep_their_source():
    ledge = LevelRecord('object', 1, '00 00 21', 0, 0x14, 0, 4)
    edge = LevelRecord('object', 2, '00 00 0b', 0, 0x13, 4, 4)
    pipe = LevelRecord('object', 3, '00 00 20', 0, 0x0F, 8, 4)
    horizontal = LevelRecord('object', 4, '00 00 12', 1, 0x10, 16, 4)
    ceiling = LevelRecord('object', 5, '00 00 d0', 0, 0x3E, 0, 0)
    tiles = {}
    _draw_object(ledge, tiles, BUSH_TABLE)
    assert tiles[0, 4] == ForegroundTile(0x100, ledge)
    assert tiles[1, 6] == ForegroundTile(0x03F, ledge)
    assert (0, 7) not in tiles
    _draw_object(edge, tiles, BUSH_TABLE)
    assert tiles[4, 4].map16_id == 0x145
    assert tiles[4, 5].map16_id == 0x1E2
    _draw_object(pipe, tiles, BUSH_TABLE)
    assert [tiles[8, row].map16_id for row in range(4, 7)] == [0x133, 0x135, 0x135]
    assert tiles[9, 4].map16_id == 0x134
    _draw_object(horizontal, tiles, BUSH_TABLE)
    assert [tiles[column, 4].map16_id for column in range(16, 19)] == [0x13B, 0x13D, 0x13D]
    assert [tiles[column, 5].map16_id for column in range(16, 19)] == [0x13F, 0x13E, 0x13E]
    _draw_object(ceiling, tiles, BUSH_TABLE, tileset=3)
    assert [tiles[0, row].map16_id for row in range(13)] == [0x150] * 13
    assert tiles[0, 13].map16_id == 0x14D


def test_slope_shapes_follow_the_row_cursor():
    gentle = LevelRecord('object', 1, '00 00 14', 0, 0x12, 0, 0)
    steep = LevelRecord('object', 2, '00 00 00', 0, 0x12, 8, 0)
    tiles = {}
    _draw_object(gentle, tiles, BUSH_TABLE)
    assert tiles[0, 0].map16_id == 0x1AF
    assert tiles[0, 1].map16_id == 0x1E4
    assert tiles[1, 1].map16_id == 0x1AF
    assert tiles[0, 2].map16_id == 0x03F
    assert tiles[1, 2].map16_id == 0x1E4
    _draw_object(steep, tiles, BUSH_TABLE)
    assert tiles[8, 0].map16_id == 0x196
    assert tiles[9, 0].map16_id == 0x19B
    assert tiles[8, 1].map16_id == 0x1DE
    assert tiles[9, 1].map16_id == 0x1E6


def test_shared_ground_routines_keep_width_and_source():
    topped = LevelRecord('object', 1, '00 00 11', 0, 0x18, 0, 0)
    donut = LevelRecord('object', 2, '00 00 01', 0, 0x1C, 4, 0)
    rope = LevelRecord('object', 3, '00 00 02', 0, 0x20, 8, 0)
    stone = LevelRecord('object', 4, '00 00 21', 1, 0x3C, 12, 0)
    tiles = {}
    _draw_object(topped, tiles, BUSH_TABLE)
    assert [tiles[column, 0].map16_id for column in range(2)] == [0x000, 0x000]
    assert [tiles[column, 1].map16_id for column in range(2)] == [0x002, 0x002]
    _draw_object(donut, tiles, BUSH_TABLE)
    assert [tiles[column, 0].map16_id for column in range(4, 6)] == [0x026, 0x026]
    assert tiles[5, 1].map16_id == 0x144
    _draw_object(rope, tiles, BUSH_TABLE)
    assert [tiles[column, 0].map16_id for column in range(8, 11)] == [0x156, 0x157, 0x158]
    _draw_object(stone, tiles, BUSH_TABLE, tileset=1)
    assert [tiles[12, row].map16_id for row in range(3)] == [0x15D, 0x160, 0x163]
    assert tiles[13, 2].map16_id == 0x165


def test_dragon_coin_stacks_two_tiles_from_its_anchor():
    coin = LevelRecord('extended_object', 21, '10 01 41', 1, 0x41, 17, 16)
    tiles = {}
    _draw_object(coin, tiles, BUSH_TABLE)
    assert tiles == {
        (17, 16): ForegroundTile(0x02D, coin),
        (17, 17): ForegroundTile(0x02E, coin),
    }


@pytest.mark.skipif(not ROM.exists(), reason='requires the local SMW cartridge')
def test_both_supported_rooms_draw_every_object():
    rom = RomImage(ROM)
    for level_id, size in ((0x105, (5120, 432)), (0x1CB, (512, 432))):
        foreground = render_opening_foreground(rom, level_id)
        level = read_level(rom, level_id)
        assert foreground.image.size == size
        assert foreground.columns == level.screen_count * level.block_columns
        sources = {tile.source.offset for tile in foreground.tiles.values()}
        for record in level.layer1.records:
            if record.kind in ('object', 'extended_object'):
                assert record.offset in sources
    opening = render_opening_foreground(rom, 0x105)
    assert opening.tiles[1, 25].map16_id == 0x03F


@pytest.mark.skipif(not ROM.exists(), reason='requires the local SMW cartridge')
def test_horizontal_levels_come_from_the_rom_and_known_ones_render():
    rom = RomImage(ROM)
    catalog = level_catalog(rom)
    by_id = dict((level_id, label) for label, level_id in catalog)
    assert len(catalog) == len(by_id) == 152
    assert '$105  Yoshi\'s Island 1' == by_id[0x105]
    assert 0x1CB in by_id
    rendered = 0
    unsupported = 0
    for _label, level_id in catalog:
        level = read_level(rom, level_id)
        if not foreground_supported(level):
            unsupported += 1
            continue
        foreground = render_opening_foreground(rom, level_id)
        rendered += 1
        assert foreground.tiles
        header = bytes.fromhex(level.layer1.header_hex)
        tileset = header[4] & 15
        bush = rom.slice(lorom_to_pc(0x0DB5A8), 15)
        for record in level.layer1.records:
            if record.kind not in ('object', 'extended_object'):
                continue
            alone = {}
            _draw_object(record, alone, bush, tileset)
            assert alone, record
    assert rendered == 152
    assert unsupported == 0


@pytest.mark.skipif(not ROM.exists(), reason='requires the local SMW cartridge')
def test_level_display_uses_the_flashing_coin_color():
    rom = RomImage(ROM)
    header = bytes.fromhex(read_level(rom, 0x105).layer1.header_hex)
    palette = _palette(rom, header)
    assert palette[0x64] == (255, 181, 0)
    assert palette[0x65] == (222, 165, 57)
    rendered = render_opening_foreground(rom, 0x105)
    coin = next(xy for xy, tile in rendered.tiles.items() if tile.map16_id == 0x02D)
    colors = {
        rendered.image.getpixel((coin[0] * 16 + dx, coin[1] * 16 + dy))
        for dy in range(16) for dx in range(16)
    }
    assert (255, 181, 0, 255) in colors
    assert (255, 8, 255, 255) not in colors


def test_left_screen_compare_names_the_changed_cell():
    record = LevelRecord('object', 1, '00 00 09', 0, 0x09, 0, 0)
    image = Image.new('RGBA', (32, 16), (0, 0, 0, 0))
    image.putpixel((1, 1), (10, 20, 30, 255))
    shot = Image.new('RGB', (256, 32), (0, 0, 0))
    rendered = OpeningForeground(image, {(0, 0): ForegroundTile(0x11E, record)}, 2, 1)
    assert left_screen_differences(rendered, shot) == ['differs: 0,0 Map16 $11E object $09']
    shot.putpixel((1, 1), (11, 21, 31))
    assert left_screen_differences(rendered, shot) == []
