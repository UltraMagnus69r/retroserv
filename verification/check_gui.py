from pathlib import Path
import sys
from unittest.mock import patch

from retroserv.gui import RetroservGUI
from retroserv.level_view import FOREGROUND_ZOOM

rom = Path(sys.argv[1])
app = RetroservGUI()
app.geometry('850x580')
with patch('retroserv.gui.messagebox.showerror', side_effect=AssertionError), patch(
    'retroserv.gui.filedialog.askopenfilename', return_value=str(rom)):
    app.open_rom()
    view = app.level_view
    app.notebook.select(view)
    app.update()
    view.load()
    assert len(view.rows.get_children()) == 126
    view.view_button.invoke()
    app.update()
    assert view.surface.image.size == (5120, 432)
    assert view.surface.columns == 320 and view.surface.rows == 27
    assert len(view.surface.cells) > 195
    cell = view.surface.cell_pixels * FOREGROUND_ZOOM
    x, y = 1, 25
    view.canvas.event_generate('<Button-1>',
        x=int((x+.5)*cell-view.canvas.canvasx(0)),
        y=int((y+.5)*cell-view.canvas.canvasy(0)))
    app.update()
    assert view.rows.selection() == (view.surface.cells[x, y].record_id,)
    assert 'Map16 $03F at 1, 25' in view.hint.cget('text')
    record_id = view.surface.cells[x, y].record_id
    footprint = sum(cell.record_id == record_id for cell in view.surface.cells.values())
    assert len(view.canvas.find_withtag('selection')) == footprint > 144
    assert view.overlay_button.instate(['!disabled'])
    assert view.overlay.get() is False
    assert view.canvas.find_withtag('grid') == ()
    view.overlay_button.invoke()
    app.update()
    columns, rows = view.surface.columns, view.surface.rows
    assert view.overlay.get() is True
    assert len(view.canvas.find_withtag('grid')) == columns + rows + 2
    visible_guides = [guide for guide in view.snapshot.guides if 0 <= guide.x <= columns]
    assert len(view.canvas.find_withtag('guide')) == len(visible_guides) == 20
    visible = [marker for marker in view.snapshot.markers
               if 0 <= marker.x < columns and 0 <= marker.y < rows]
    hidden = [marker for marker in view.snapshot.markers if marker not in visible]
    assert visible
    for marker in visible:
        assert view.canvas.find_withtag(f'record-{marker.record_id}')
    for marker in hidden:
        assert not view.canvas.find_withtag(f'record-{marker.record_id}')
    marker = max(visible, key=lambda item: (item.y, item.x))
    view.canvas.event_generate('<Button-1>',
        x=int((marker.x + 0.5) * cell - view.canvas.canvasx(0)),
        y=int((marker.y + 0.5) * cell - view.canvas.canvasy(0)))
    app.update()
    assert view.picked_cell is None
    assert view.rows.selection() == (marker.record_id,)
    assert f'Anchor at {marker.x}, {marker.y}' in view.hint.cget('text')
    occupied = {(item.x, item.y) for item in visible}
    painted = max((xy for xy in view.surface.cells if xy not in occupied), key=lambda xy: (xy[1], xy[0]))
    view.canvas.event_generate('<Button-1>',
        x=int((painted[0] + 0.5) * cell - view.canvas.canvasx(0)),
        y=int((painted[1] + 0.5) * cell - view.canvas.canvasy(0)))
    app.update()
    assert view.picked_cell == painted
    assert view.surface.cells[painted].caption in view.hint.cget('text')
    view.overlay_button.invoke()
    app.update()
    assert view.overlay.get() is False and view.canvas.find_withtag('grid') == ()
    view.view_button.invoke()
    app.update()
    assert view.surface is None and len(view.rows.get_children()) == 126
    bonus = next(label for label, number in view.room_keys.items() if number == 0x1CB)
    view.room.set(bonus)
    view.room.event_generate('<<ComboboxSelected>>')
    app.update()
    view.load()
    assert view.view_button.instate(['!disabled']) and len(view.rows.get_children()) == 16
    view.view_button.invoke()
    app.update()
    assert view.surface.image.size == (512, 432)
    assert view.surface.columns == 32 and view.surface.rows == 27
    assert view.surface.cells
app.destroy()
print('Opening foreground, placement overlay, tile hit testing, source highlighting, mode switch, and room scope passed.')
