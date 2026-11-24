import json
import os
from io import BytesIO

import pytest
from pathlib import Path

from PIL import Image

from retroserv.assistant import (
    AssistantChange, AssistantFile, apply_room_labels, apply_snapshot, load_for_rom,
    merge_assistant, read_assistant, save_for_rom, write_assistant,
)
from retroserv.inspection import FORMAT, InspectionSnapshot
from retroserv.map_source import course_maps
from retroserv.smw import SMW_USA_V10_SHA256
from retroserv.smw_foreground import _apply_map16_pointers
from retroserv.assistant_settings import AssistantSettings, load_settings, save_api_key, save_settings
from retroserv.cursor_match import BrainDecision, cursor_requirement, layout_brief, parse_match_response
from retroserv.smw_map_check import CheckProgress, check_course_maps

PAGE = 'https://maps.example/smw/'
HTML = '''
<html><body>
<a href="world-map.png">World Map</a>
<a href="notes.zip">Notes</a>
<a href="https://maps.example/smw/yoshis-island-1.png">Yoshi&#8217;s Island 1</a>
<a href="donut-plains-1.png">Donut Plains 1</a>
<a href="yoshis-island-1.png">Yoshi&#8217;s Island 1</a>
</body></html>
'''


def _png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, 'png')
    return buffer.getvalue()


def _snapshot():
    return InspectionSnapshot(
        FORMAT, 'snes', 'smw-usa-v1.0', '$001', 'Level', 'abc', 'fixture.sfc', 0,
        '1 screens   •   1 objects   •   0 sprite records', 'legend', 'room.json',
        16, 27, 16, True, (), (), (), None)


def test_course_page_keeps_level_maps_and_skips_world_maps():
    maps = course_maps(HTML, PAGE)
    assert [(item.title, item.url) for item in maps] == [
        ("Yoshi's Island 1", 'https://maps.example/smw/yoshis-island-1.png'),
        ('Donut Plains 1', 'https://maps.example/smw/donut-plains-1.png'),
    ]


def test_assistant_file_round_trip_and_room_label(tmp_path):
    change = AssistantChange('note-1', 'note', 'Remember this room', '1', {'kept': True})
    original = AssistantFile('a' * 64, PAGE, 2, {}, (change,))
    path = write_assistant(original, tmp_path / 'assistant.json')
    loaded = read_assistant(path)
    assert loaded == original
    assert json.loads(path.read_text(encoding='utf-8'))['format'] == 'retroserv-assistant-v1'


def _room():
    from retroserv.assistant import AssistantRoom
    return AssistantRoom('$001', 'Donut Plains 1', 'https://maps.example/donut.png')


def test_accepted_title_replaces_the_room_label_and_the_snapshot():
    from retroserv.assistant import AssistantRoom
    assistant = AssistantFile('a' * 64, PAGE, 1, {
        '1': AssistantRoom('$001', 'Donut Plains 1', 'https://maps.example/donut.png'),
    })
    labels = apply_room_labels((('$001  Level  ·  4 slots', 1),), assistant)
    assert labels == (('$001  Donut Plains 1  ·  4 slots', 1),)
    snapshot = apply_snapshot(_snapshot(), assistant, '1')
    assert snapshot.name == 'Donut Plains 1'
    assert snapshot.summary.startswith('1 screens')


def test_check_names_one_unique_picture_and_keeps_earlier_changes():
    matched = Image.new('RGB', (32, 16), (20, 140, 40))
    other = Image.new('RGB', (32, 16), (180, 40, 40))
    plain = Image.new('RGB', (32, 16), (8, 8, 8))
    images = {
        'https://maps.example/smw/yoshis-island-1.png': matched,
        'https://maps.example/smw/donut-plains-1.png': other,
    }

    def fetch(url):
        if url in images:
            return _png(images[url])
        return HTML.encode()

    def render(_rom, level_id, assistant=None):
        picture = matched if level_id == 1 else other if level_id == 2 else plain
        return type('Rendered', (), {'image': picture})()

    existing = AssistantFile(SMW_USA_V10_SHA256, '', 0, {}, (
        AssistantChange('grass-diagonal-pipe-edges', 'map16-pointers', 'Pipes', '*',
                        {'tilesets': [7]}),
    ))
    report = check_course_maps(
        None, PAGE, existing, fetch=fetch,
        rooms_for=lambda _rom: (('$001  Level', 1), ('$002  Level', 2), ('$003  Level', 3)),
        render=render)
    assert report.rooms['1'].title == "Yoshi's Island 1"
    assert report.rooms['2'].title == 'Donut Plains 1'
    assert report.rooms['3'].title is None
    assert report.changes[0].id == 'grass-diagonal-pipe-edges'
    assert report.source_map_count == 2


def test_check_progress_counts_every_level():
    picture = Image.new('RGB', (32, 16), (20, 140, 40))
    seen = []

    def fetch(url):
        if url.endswith('.png'):
            return _png(picture)
        return HTML.encode()

    def render(_rom, _level_id, assistant=None):
        return type('Rendered', (), {'image': picture})()

    check_course_maps(
        None, PAGE, AssistantFile('b' * 64), progress=seen.append, fetch=fetch,
        rooms_for=lambda _rom: (('$001  Level', 1), ('$002  Level', 2)),
        render=render)
    levels = [item for item in seen if item.total and item.message.startswith('Level ')]
    assert [(item.completed, item.total, item.message) for item in levels] == [
        (0, 2, 'Level 1 of 2 · $001'),
        (1, 2, 'Level 1 of 2 · $001'),
        (1, 2, 'Level 2 of 2 · $002'),
        (2, 2, 'Level 2 of 2 · $002'),
    ]
    assert all(isinstance(item, CheckProgress) for item in seen)
    assert seen[0].total == 0


def test_cursor_names_only_a_catalog_title_once_and_keeps_a_finding():
    text = '''```json
    {"names":[{"key":"1","title":"Yoshi's Island 1"},{"key":"2","title":"Yoshi's Island 1"},
              {"key":"3","title":"Not a course"},{"key":"9","title":"Donut Plains 1"}],
     "findings":[{"key":"1","summary":"The question block is a small yellow mark."}]}
    ```'''
    decision = parse_match_response(text, {"Yoshi's Island 1", 'Donut Plains 1'}, {'1', '2', '3'})
    assert decision.names == {'1': "Yoshi's Island 1"}
    assert decision.findings[0].summary.startswith('The question block')
    assert decision.findings[0].kind == 'finding'

    picture = Image.new('RGB', (64, 32), (20, 140, 40))
    other = Image.new('RGB', (64, 32), (180, 40, 40))

    def fetch(url):
        if url.endswith('yoshis-island-1.png'):
            return _png(picture)
        if url.endswith('.png'):
            return _png(other)
        return HTML.encode()

    def render(_rom, level_id, assistant=None):
        return type('Rendered', (), {'image': picture if level_id == 1 else other})()

    def decide(briefs, titles):
        assert "Yoshi's Island 1" in titles
        assert briefs[0]['profile']
        return BrainDecision({'1': "Yoshi's Island 1", '2': "Yoshi's Island 1"}, decision.findings)

    existing = AssistantFile('b' * 64, '', 0, {}, (
        AssistantChange('grass-diagonal-pipe-edges', 'map16-pointers', 'Pipes', '*', {}),
        AssistantChange('cursor-finding-1', 'finding', 'old note', '1'),
    ))
    report = check_course_maps(
        None, PAGE, existing, fetch=fetch, decide=decide,
        rooms_for=lambda _rom: (('$001  Level', 1), ('$002  Level', 2)),
        render=render)
    assert report.rooms['1'].title == "Yoshi's Island 1"
    assert report.rooms['2'].title is None
    assert [change.id for change in report.changes] == ['grass-diagonal-pipe-edges', 'cursor-finding-1']
    assert report.changes[1].summary.startswith('The question block')


def test_assistant_settings_round_trip_and_key_file(tmp_path, monkeypatch):
    monkeypatch.delenv('CURSOR_API_KEY', raising=False)
    save_settings(AssistantSettings('picture', 'composer-2.5'), tmp_path)
    assert load_settings(tmp_path).provider == 'picture'
    assert cursor_requirement(AssistantSettings('cursor', 'composer-2.5'), tmp_path)
    save_api_key('cursor_test_key', tmp_path)
    assert key_is_private(tmp_path)
    assert load_settings(tmp_path).provider == 'picture'


def key_is_private(directory):
    from retroserv.assistant_settings import key_path
    return key_path(directory).stat().st_mode & 0o777 == 0o600


def test_error_log_records_the_run_without_the_reply(tmp_path):
    from retroserv.cursor_match import MatchError
    from retroserv.error_log import write_error_log
    exc = MatchError('Cursor replied in prose instead of a JSON object',
                     reply='I will compare the levels next.', status='finished',
                     run_id='run-1', model='composer-2.5')
    path = write_error_log(exc, context='Map check', directory=tmp_path)
    text = path.read_text(encoding='utf-8')
    assert path.name.startswith('Retroserv-error-')
    assert path.stat().st_mode & 0o777 == 0o600
    assert 'I will compare the levels next.' not in text
    assert 'Traceback' not in text
    assert 'run_id: run-1' in text
    assert 'composer-2.5' in text
    assert 'Map check' in text
    with pytest.raises(ValueError, match='without a reply'):
        parse_match_response('', set(), set())


def test_layout_brief_uses_the_room_key():
    brief = layout_brief(0x105, '$105', Image.new('RGB', (512, 64), (10, 80, 20)))
    assert brief['key'] == '261' and brief['subject'] == '$105'
    assert len(brief['profile']) == 32


def test_two_rooms_with_the_same_picture_stay_unnamed():
    picture = Image.new('RGB', (32, 16), (20, 140, 40))

    def fetch(url):
        if url.endswith('.png'):
            return _png(picture)
        return HTML.encode()

    def render(_rom, _level_id, assistant=None):
        return type('Rendered', (), {'image': picture})()

    report = check_course_maps(
        None, PAGE, AssistantFile('b' * 64), fetch=fetch,
        rooms_for=lambda _rom: (('$001  Level', 1), ('$002  Level', 2)),
        render=render)
    assert all(room.title is None for room in report.rooms.values())
    assert report.rooms['1'].candidates


def test_assistant_file_is_named_for_the_rom_and_saved_beside_it(tmp_path):
    rom = tmp_path / 'Super Mario World (USA).sfc'
    rom.write_bytes(b'not a cartridge')
    saved = save_for_rom(AssistantFile('c' * 64, PAGE, 3), rom)
    assert saved == tmp_path / 'Super Mario World (USA)-assistant.json'
    loaded = load_for_rom('c' * 64, rom)
    assert loaded is not None and loaded.source_map_count == 3
    assert load_for_rom('d' * 64, rom) is None


def test_bundled_pipe_correction_loads_for_this_cartridge_and_merges(tmp_path):
    rom = tmp_path / 'Game.sfc'
    rom.write_bytes(b'x')
    loaded = load_for_rom(SMW_USA_V10_SHA256, rom)
    assert loaded is not None
    assert loaded.changes[0].id == 'grass-diagonal-pipe-edges'
    pointers = [0] * 512
    _apply_map16_pointers(pointers, 7, loaded)
    assert pointers[0x1C4] == 0x0D8A70
    assert pointers[0x1EC] == 0x0D8A90
    assert pointers[0x1C4] != pointers[0x1EC]
    underground = [0] * 512
    _apply_map16_pointers(underground, 3, loaded)
    assert underground[0x1C4] == 0
    report = AssistantFile(SMW_USA_V10_SHA256, PAGE, 4, {'261': _room()}, ())
    merged = merge_assistant(loaded, report)
    assert merged.changes[0].id == 'grass-diagonal-pipe-edges'
    assert merged.rooms['261'].title == 'Donut Plains 1'
    assert not (tmp_path / 'Game-assistant.json').exists()


@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires a display')
def test_status_bar_advances_with_each_level():
    from retroserv.gui import RetroservGUI

    app = RetroservGUI()
    app.update()
    assert app.progress.winfo_manager() == ''
    assert app.progress.master.winfo_height() > 20
    app._apply_check_progress(CheckProgress('Map 1 of 3 · Yoshi\'s Island 1'))
    app.update()
    assert app.progress.winfo_manager() == 'pack'
    assert app.progress.winfo_height() > 10
    assert str(app.progress.cget('mode')) == 'indeterminate'
    assert app.status.get().startswith('Map 1 of 3')
    app._apply_check_progress(CheckProgress('Level 1 of 4 · $103', 0, 4))
    app.update()
    assert str(app.progress.cget('mode')) == 'determinate'
    assert app.progress['maximum'] == 4
    assert app.progress['value'] == 0
    app._apply_check_progress(CheckProgress('Level 2 of 4 · $105', 2, 4))
    app.update()
    assert app.progress['value'] == 2
    assert '$105' in app.status.get()
    app._hide_check_progress()
    app.update()
    assert app.progress.winfo_manager() == ''
    app.destroy()
