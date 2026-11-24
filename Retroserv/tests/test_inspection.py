import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from retroserv.inspection import (
    FORMAT, InspectionCell, InspectionGuide, InspectionMarker, InspectionRecord,
    InspectionSnapshot, InspectionSurface,
)
from retroserv.smw_foreground import OpeningForeground, _draw_object
from retroserv.smw_level import LevelRecord, LevelStream, SMWLevel
from retroserv.smw_snapshot import snapshot_from_level


def _level(level_id, layer_records, sprites=(), block_columns=16, block_rows=27):
    return SMWLevel(level_id, 'Room', 2, 0x123456,
                    LevelStream(0, 0, '00', 1, tuple(layer_records)),
                    LevelStream(0, 0, '04', 2, tuple(sprites)),
                    'fixture.sfc', 0, block_columns, block_rows)


def test_snapshot_hides_smw_record_fields_and_keeps_provenance():
    ledge = LevelRecord('object', 10, '58 10 03', 0, 0x21, 0, 24)
    sprite = LevelRecord('sprite', 40, '3b f2 ab', 1, 0xAB, 20, 8, sprite_extra_bits=2)
    exit_record = LevelRecord('screen_exit', 21, '07 02 00 ff', 7, 0, exit_destination_byte=255,
                              secondary_exit=True)
    tiles = {}
    _draw_object(ledge, tiles, bytes(range(15)))
    foreground = OpeningForeground(Image.new('RGBA', (256, 432)), tiles, 16, 27)
    snapshot = snapshot_from_level(_level(0x105, (ledge, exit_record), (sprite,)), foreground,
                                   cartridge_sha256='abc')

    assert snapshot.format == FORMAT
    assert snapshot.supports_surface
    assert snapshot.surface.cells[0, 24].caption == 'Map16 $100'
    assert snapshot.surface.cells[0, 24].record_id == snapshot.records[0].id == '10'
    assert [marker.shape for marker in snapshot.markers] == ['square', 'dot']
    assert snapshot.records[1].detail == 'Screen $07 · Secondary $FF'
    payload = snapshot.to_dict()
    encoded = json.dumps(payload)
    assert payload['surface']['width'] == 256
    assert 'layer2' not in encoded
    assert 'map16_id' not in encoded
    assert 'type_id' not in encoded
    assert 'sprite_extra_bits' not in encoded


def test_bonus_room_snapshot_has_records_and_no_surface():
    jump = LevelRecord('screen_jump', 4, '80 01 01', 3, 1)
    snapshot = snapshot_from_level(_level(0x1CB, (jump,)), None, cartridge_sha256='abc')
    assert snapshot.supports_surface is True
    assert snapshot.surface is None
    assert snapshot.markers == ()
    assert snapshot.records[0].label == 'Screen jump $01'
    assert snapshot.to_dict()['surface'] is None


def test_snapshot_grid_comes_from_the_level_read():
    snapshot = snapshot_from_level(_level(0x105, (), block_columns=10, block_rows=12), None,
                                   cartridge_sha256='abc')
    assert snapshot.screen_columns == 10
    assert snapshot.grid_rows == 12
    assert snapshot.grid_columns == 20
    assert [guide.x for guide in snapshot.guides] == [0, 10]
    assert snapshot.to_dict()['screen_columns'] == 10


def test_shell_modules_do_not_import_smw_level_types():
    root = Path(__file__).resolve().parents[1] / 'retroserv'
    view = (root / 'level_view.py').read_text(encoding='utf-8')
    assert 'smw_' not in view
    for name in ('cli.py', 'mcp_server.py'):
        source = (root / name).read_text(encoding='utf-8')
        assert 'from .smw_level' not in source
        assert 'from .smw_foreground' not in source
        assert 'from .smw_snapshot import inspect_level' in source


def _snapshot(surface):
    record = InspectionRecord('10', 'Object $21', 'Screen $00 · 1, 1', 10, '00 00 00')
    return InspectionSnapshot(
        FORMAT, 'snes', 'smw-usa-v1.0', '$105', 'Room', 'abc', 'fixture.sfc', 0,
        '1 screens   •   1 objects   •   0 sprite records', 'legend', 'room.json',
        10, 12, 10, True, (InspectionGuide(0, 'Screen $00'),), (record,),
        (InspectionMarker('10', 1, 1, 'square'),), surface)


@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires a display')
def test_view_selects_snapshot_cell_without_game_types():
    import tkinter as tk
    from retroserv.level_view import FOREGROUND_ZOOM, LevelView

    image = Image.new('RGBA', (32, 32), (20, 40, 60, 255))
    surface = InspectionSurface(image, 16, 2, 2, {(1, 1): InspectionCell('10', 'Map16 $03F')})
    loaded = {'surface': False}

    def load(_key, include_surface):
        loaded['surface'] = include_surface
        base = _snapshot(surface if include_surface else None)
        return replace(base, markers=base.markers + (InspectionMarker('10', 9, 1, 'square'),))

    root = tk.Tk()
    root.geometry('850x580')
    view = LevelView(root, lambda action: action(), [('Room', 1)], load)
    view.pack(fill='both', expand=True)
    view.load()
    root.update()
    assert view.rows.get_children() == ('10',)
    assert len(view.canvas.find_withtag('grid')) == 11 + 13
    assert len(view.canvas.find_withtag('guide')) == 1
    assert loaded['surface'] is False
    assert view.view_button.instate(['!disabled'])
    assert view.overlay_button.instate(['disabled'])
    view.view_button.invoke()
    root.update()
    assert loaded['surface'] is True
    assert view.surface.image.size == (32, 32)
    cell = view.surface.cell_pixels * FOREGROUND_ZOOM
    x, y = 1, 1
    view.canvas.event_generate('<Button-1>', x=int((x + 0.5) * cell - view.canvas.canvasx(0)),
                               y=int((y + 0.5) * cell - view.canvas.canvasy(0)))
    root.update()
    assert view.rows.selection() == ('10',)
    assert 'Map16 $03F at 1, 1' in view.hint.cget('text')
    assert len(view.canvas.find_withtag('selection')) == 1
    assert view.overlay_button.instate(['!disabled'])
    assert view.canvas.find_withtag('grid') == ()
    view.overlay_button.invoke()
    root.update()
    assert view.overlay.get() is True
    assert len(view.canvas.find_withtag('grid')) == 6
    assert len(view.canvas.find_withtag('guide')) == 1
    assert len(view.canvas.find_withtag('record-10')) == 1
    view.canvas.event_generate('<Button-1>', x=int((x + 0.5) * cell - view.canvas.canvasx(0)),
                               y=int((y + 0.5) * cell - view.canvas.canvasy(0)))
    root.update()
    assert view.picked_cell is None
    assert view.rows.selection() == ('10',)
    assert 'Anchor at 1, 1' in view.hint.cget('text')
    assert len(view.canvas.find_withtag('selection')) == 2
    view.canvas.event_generate('<Button-1>', x=int(x * cell + 1 - view.canvas.canvasx(0)),
                               y=int(y * cell + 1 - view.canvas.canvasy(0)))
    root.update()
    assert view.picked_cell == (1, 1)
    assert 'Map16 $03F at 1, 1' in view.hint.cget('text')
    view.overlay_button.invoke()
    root.update()
    assert view.overlay.get() is False
    assert view.canvas.find_withtag('grid') == ()
    assert 'Map16 $03F at 1, 1' in view.hint.cget('text')
    view.view_button.invoke()
    root.update()
    assert view.surface is None
    assert view.overlay_button.instate(['disabled'])
    assert len(view.canvas.find_withtag('grid')) == 11 + 13
    root.destroy()
