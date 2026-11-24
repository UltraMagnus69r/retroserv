"""Path limits, private logs, durable assistant files, and the map signature cache."""
import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from retroserv.access_paths import require_export_path, require_palette_path, require_rom_path
from retroserv.assistant import AssistantFile, read_assistant, write_assistant
from retroserv.smw_map_check import check_course_maps, fetch_bytes, map_signature


def _config(tmp_path: Path, roms: Path, exports: Path) -> Path:
    config = tmp_path / 'cfg'
    config.mkdir()
    (config / 'paths.json').write_text(json.dumps({
        'rom_directories': [str(roms)],
        'export_directory': str(exports),
    }), encoding='utf-8')
    return config


def test_mcp_paths_stay_inside_the_named_folders(tmp_path):
    roms = tmp_path / 'roms'
    exports = tmp_path / 'exports'
    roms.mkdir()
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    config = _config(tmp_path, roms, exports)
    rom = require_rom_path(str(roms / 'game.sfc'), config)
    assert rom == (roms / 'game.sfc').resolve()
    exported = require_export_path(str(exports / 'shot.png'), config)
    assert exported == (exports / 'shot.png').resolve()
    palette = require_palette_path(str(exports / 'level.pal'), config)
    assert palette.parent == exports.resolve()
    with pytest.raises(ValueError, match='outside'):
        require_rom_path(str(elsewhere / 'game.sfc'), config)
    with pytest.raises(ValueError, match='outside'):
        require_rom_path(str(roms / '..' / 'elsewhere' / 'game.sfc'), config)
    with pytest.raises(ValueError, match='outside'):
        require_export_path(str(elsewhere / 'shot.png'), config)


def test_a_symlink_cannot_leave_the_rom_folder(tmp_path):
    roms = tmp_path / 'roms'
    exports = tmp_path / 'exports'
    roms.mkdir()
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    (roms / 'outside').symlink_to(elsewhere)
    config = _config(tmp_path, roms, exports)
    with pytest.raises(ValueError, match='outside'):
        require_rom_path(str(roms / 'outside' / 'game.sfc'), config)


def test_room_score_must_be_a_number(tmp_path):
    path = tmp_path / 'assistant.json'
    path.write_text(json.dumps({
        'format': 'retroserv-assistant-v1',
        'rom_sha256': 'a' * 64,
        'rooms': {'1': {'subject': '$001', 'candidates': [
            {'title': 'Yoshi', 'url': 'https://example/a.png', 'score': 'high'},
        ]}},
    }), encoding='utf-8')
    with pytest.raises(ValueError, match='not a number'):
        read_assistant(path)
    path.write_text(json.dumps({
        'format': 'retroserv-assistant-v1',
        'rom_sha256': 'a' * 64,
        'rooms': {'1': {'subject': '$001', 'candidates': [
            {'title': 'Yoshi', 'url': 'https://example/a.png', 'score': True},
        ]}},
    }), encoding='utf-8')
    with pytest.raises(ValueError, match='not a number'):
        read_assistant(path)


def test_assistant_file_is_replaced_as_a_whole(tmp_path):
    path = tmp_path / 'Game-assistant.json'
    write_assistant(AssistantFile('b' * 64, '', 0, {}, ()), path)
    assert path.is_file()
    assert not path.with_name(path.name + '.tmp').exists()
    assert path.with_name(path.name + '.lock').is_file()
    assert read_assistant(path).rom_sha256 == 'b' * 64


def _png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, 'png')
    return buffer.getvalue()


def test_an_unchanged_map_reuses_its_signature(tmp_path):
    picture = Image.new('RGB', (32, 16), (20, 140, 40))
    calls = []

    def retrieve(url, etag):
        calls.append(etag)
        if etag == '"abc"':
            return 304, b'', '"abc"'
        return 200, _png(picture), '"abc"'

    url = 'https://maps.example/smw/yoshis-island-1.png'
    first = map_signature(url, fetch_bytes, tmp_path, retrieve=retrieve)
    second = map_signature(url, fetch_bytes, tmp_path, retrieve=retrieve)
    assert second == first
    assert calls == ['', '"abc"']


def test_an_injected_fetch_does_not_fill_the_map_cache(tmp_path, monkeypatch):
    cache = tmp_path / 'cache'
    monkeypatch.setattr('retroserv.smw_map_check.default_map_cache', lambda: cache)
    picture = Image.new('RGB', (8, 8), (10, 20, 30))

    def fetch(url):
        if url.endswith('.png'):
            return _png(picture)
        return b'<a href="level.png">Level 1</a>'

    check_course_maps(
        None, 'https://maps.example/page', fetch=fetch,
        rooms_for=lambda _rom: (), render=lambda *_args: None)
    assert not cache.exists()


def test_foreground_routines_and_jobs_are_split():
    root = Path(__file__).resolve().parents[1] / 'retroserv'
    foreground = (root / 'smw_foreground.py').read_text(encoding='utf-8')
    window = (root / 'gui.py').read_text(encoding='utf-8')
    assert 'def _vertical_pipe' not in foreground
    assert 'def _ledge(' not in foreground
    assert 'def _palette' not in foreground
    assert 'def render_opening_foreground' in foreground
    assert 'def check_course_maps' not in window
    assert 'run_map_check' in window and 'run_rebuild' in window
    assert '_same_rom' in window
