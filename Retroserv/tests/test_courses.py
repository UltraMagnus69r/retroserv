from pathlib import Path

import pytest

from retroserv.assistant import AssistantChange, AssistantFile
from retroserv.map_source import CourseMap
from retroserv.rom import RomImage
from retroserv.smw_courses import room_titles
from retroserv.smw_rebuild import rebuild_from_rom

ROM = Path.home() / 'Desktop/Super Mario World (USA)/Super Mario World (USA).sfc'


@pytest.mark.skipif(not ROM.exists(), reason='requires the local SMW cartridge')
def test_overworld_names_yoshis_island_and_the_bonus_room():
    rom = RomImage(ROM)
    titles = room_titles(rom)
    assert titles['261'] == "Yoshi's Island 1"
    assert titles['21'] == 'Donut Plains 1'
    assert titles['459'] == "Yoshi's Island 1 bonus room"
    assert titles.get('257') != "Yoshi's Island 1"
    assert titles['8'] == 'Green Switch Palace'
    assert titles['20'] == 'Yellow Switch Palace 3'
    assert titles['33'] == 'Chocolate Ghost House'


@pytest.mark.skipif(not ROM.exists(), reason='requires the local SMW cartridge')
def test_rebuild_drops_a_guessed_title_and_keeps_the_pipe_change():
    rom = RomImage(ROM)
    guessed = AssistantFile('0' * 64, 'https://example.test/maps', 75, {
        '257': type('Room', (), {})(),
    }, (
        AssistantChange('grass-diagonal-pipe-edges', 'map16-pointers', 'Pipes', '*', {}),
        AssistantChange('cursor-finding-257', 'finding', 'old guess', '257'),
    ))
    # The hash is replaced from the ROM. A mismatched hash must not block the pipe change.
    guessed = AssistantFile(guessed.rom_sha256, guessed.source, guessed.source_map_count, {},
                            guessed.changes)
    maps = (CourseMap("Yoshi's Island 1", 'https://example.test/yi1.png'),)
    report = rebuild_from_rom(rom, guessed, maps)
    assert report.rooms['261'].title == "Yoshi's Island 1"
    assert report.rooms['261'].map_url == 'https://example.test/yi1.png'
    assert report.rooms['257'].title != "Yoshi's Island 1"
    assert any(change.kind == 'map16-pointers' for change in report.changes)
    assert all(change.id != 'cursor-finding-257' for change in report.changes)
    assert any(change.id == 'rom-finding-261' for change in report.changes)
