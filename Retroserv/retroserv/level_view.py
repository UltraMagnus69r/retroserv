"""Scrollable inspection view. It draws an inspection snapshot and does not import game adapters."""
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from collections.abc import Callable, Sequence

from PIL import Image, ImageTk

from .export import save_json
from .inspection import InspectionSnapshot, InspectionSurface

CELL = 14
TOP = 25
FOREGROUND_ZOOM = 2
PLACEMENT_HINT = 'Placement anchors'
FOREGROUND_HINT = 'Static foreground • Click a tile to inspect its source record'
OVERLAY_HINT = ('Foreground with placement overlay • Click a circle for its anchor, '
                'or a tile for the record that painted it')
SQUARE = '#71c6a2'
DOT = '#ffc277'
OVERLAY_GRID = '#e8eef4'
OVERLAY_GUIDE = '#f2c14e'


def _oval_box(x, y, shape, cell, origin_y):
    pad = 4 if shape == 'dot' else 2
    return (x * cell + pad, origin_y + y * cell + pad,
            (x + 1) * cell - pad, origin_y + (y + 1) * cell - pad)


class LevelView(ttk.Frame):
    def __init__(self, parent, handle, rooms: Sequence[tuple[str, int]],
                 load_snapshot: Callable[[int, bool], InspectionSnapshot],
                 on_check: Callable[[], None] | None = None,
                 on_rebuild: Callable[[], None] | None = None):
        super().__init__(parent, padding=10)
        self.handle = handle
        self.load_snapshot = load_snapshot
        self.room_keys = dict(rooms)
        self.snapshot: InspectionSnapshot | None = None
        self.records_by_id = {}
        self.surface: InspectionSurface | None = None
        self.foreground_photo = None
        self.picked_cell = None
        self.overlay = tk.BooleanVar(value=False)

        controls = ttk.Frame(self)
        controls.pack(fill='x')
        self.room = ttk.Combobox(controls, values=[label for label, _key in rooms], state='readonly', width=42)
        self.room.current(0)
        self.room.pack(side='left', padx=(0, 8))
        self.room.bind('<<ComboboxSelected>>', lambda _: self.clear())
        ttk.Button(controls, text='Read level', command=self.load).pack(side='left')
        self.export_button = ttk.Button(controls, text='Export level JSON…',
                                        command=self.export, state='disabled')
        self.export_button.pack(side='left', padx=8)
        self.view_button = ttk.Button(controls, text='Opening foreground', command=self.toggle_foreground,
                                      state='disabled')
        self.view_button.pack(side='left')
        self.overlay_button = ttk.Checkbutton(controls, text='Placement overlay', variable=self.overlay,
                                              command=self._apply_overlay, state='disabled')
        self.overlay_button.pack(side='left', padx=(8, 0))
        if on_check is not None:
            self.check_button = ttk.Button(controls, text='Check maps…', command=on_check)
            self.check_button.pack(side='left', padx=(8, 0))
        if on_rebuild is not None:
            self.rebuild_button = ttk.Button(controls, text='Rebuild from ROM', command=on_rebuild)
            self.rebuild_button.pack(side='left', padx=(8, 0))
        self.summary = ttk.Label(self)
        self.summary.pack(anchor='w', pady=(7, 1))
        self.hint = ttk.Label(self, text=PLACEMENT_HINT)
        self.hint.pack(anchor='w')

        map_frame = ttk.Frame(self)
        map_frame.pack(fill='both', expand=True, pady=(4, 0))
        map_frame.columnconfigure(0, weight=1)
        map_frame.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(map_frame, height=420,
                                background='#18232f', highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        horizontal = ttk.Scrollbar(map_frame, orient='horizontal', command=self.canvas.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        vertical = ttk.Scrollbar(map_frame, orient='vertical', command=self.canvas.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        self.canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        self.canvas.bind('<Button-1>', self.select_marker)

        table = ttk.Frame(self)
        table.pack(fill='x', pady=(6, 0))
        columns = ('label', 'detail', 'offset', 'bytes')
        self.rows = ttk.Treeview(table, columns=columns, show='headings', height=6, selectmode='browse')
        for key, title, width in zip(columns, ('Record', 'Location', 'ROM offset', 'Source bytes'),
                                     (160, 220, 90, 140)):
            self.rows.heading(key, text=title)
            self.rows.column(key, width=width)
        self.rows.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(table, command=self.rows.yview)
        scroll.pack(side='right', fill='y')
        self.rows.configure(yscrollcommand=scroll.set)
        self.rows.bind('<<TreeviewSelect>>', self.highlight_record)
        self.clear()

    def set_rooms(self, rooms: Sequence[tuple[str, int]], *, selected: int | None = None) -> None:
        self.room_keys = dict(rooms)
        labels = [label for label, _key in rooms]
        self.room.configure(values=labels)
        chosen = next((label for label, key in rooms if key == selected), labels[0] if labels else '')
        self.room.set(chosen)
        self.clear()

    def show_note(self, text: str) -> None:
        self.summary.configure(text=text)

    def clear(self):
        self.snapshot = None
        self.records_by_id = {}
        self.surface = None
        self.foreground_photo = None
        self.picked_cell = None
        self.canvas.delete('all')
        self.canvas.configure(scrollregion=(0, 0, 0, 0))
        self.rows.delete(*self.rows.get_children())
        self.summary.configure(text='Choose a room and click Read level.')
        self.export_button.configure(state='disabled')
        self.view_button.configure(text='Opening foreground', state='disabled')
        self.overlay.set(False)
        self.overlay_button.configure(state='disabled')
        self.hint.configure(text=PLACEMENT_HINT)

    def load(self):
        def read():
            snapshot = self.load_snapshot(self.room_keys[self.room.get()], False)
            self.clear()
            self.snapshot = snapshot
            self._fill_records(snapshot)
            self._show_placement()
            self.export_button.configure(state='normal')
            if snapshot.supports_surface:
                self.view_button.configure(state='normal')
            self.hint.configure(text=snapshot.legend)
        self.handle(read)

    def _fill_records(self, snapshot: InspectionSnapshot):
        self.records_by_id = {record.id: record for record in snapshot.records}
        for record in snapshot.records:
            self.rows.insert('', 'end', iid=record.id, values=(
                record.label, record.detail, f'0x{record.offset:05X}', record.raw_hex))
        self.summary.configure(text=snapshot.summary)

    def _show_placement(self):
        snapshot = self.snapshot
        self.surface = None
        self.foreground_photo = None
        self.picked_cell = None
        self.canvas.delete('all')
        width = snapshot.grid_columns * CELL
        height = TOP + snapshot.grid_rows * CELL
        self.canvas.configure(scrollregion=(0, 0, width, height))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        for row in range(snapshot.grid_rows + 1):
            y = TOP + row * CELL
            self.canvas.create_line(0, y, width, y, fill='#253544', tags=('grid',))
        for column in range(snapshot.grid_columns + 1):
            x = column * CELL
            self.canvas.create_line(x, TOP, x, height, fill='#253544', tags=('grid',))
        for guide in snapshot.guides:
            x = guide.x * CELL
            self.canvas.create_line(x, 0, x, height, fill='#536d83', tags=('guide',))
            self.canvas.create_text(x + 8, 11, anchor='w', fill='#c9d8e3', text=guide.label)
        for marker in snapshot.markers:
            self._draw_marker(marker, CELL, TOP)
        self.overlay_button.configure(state='disabled')

    def _draw_marker(self, marker, cell, origin_y):
        left, top, right, bottom = _oval_box(marker.x, marker.y, marker.shape, cell, origin_y)
        fill = DOT if marker.shape == 'dot' else SQUARE
        self.canvas.create_oval(left, top, right, bottom, fill=fill, outline='',
                                tags=(f'record-{marker.record_id}',))

    def _show_surface(self, surface: InspectionSurface, *, scroll_to_ground=True):
        xview, yview = self.canvas.xview(), self.canvas.yview()
        self.surface = surface
        if scroll_to_ground:
            self.picked_cell = None
        width, height = surface.image.size
        size = (width * FOREGROUND_ZOOM, height * FOREGROUND_ZOOM)
        self.foreground_photo = ImageTk.PhotoImage(surface.image.resize(size, Image.Resampling.NEAREST))
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, anchor='nw', image=self.foreground_photo)
        if self.overlay.get():
            self._draw_surface_overlay(surface)
        self.canvas.configure(scrollregion=(0, 0, *size))
        self.overlay_button.configure(state='normal')
        if scroll_to_ground:
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(1)
        else:
            self.canvas.xview_moveto(xview[0])
            self.canvas.yview_moveto(yview[0])

    def _draw_surface_overlay(self, surface: InspectionSurface):
        cell = surface.cell_pixels * FOREGROUND_ZOOM
        width = surface.columns * cell
        height = surface.rows * cell
        for row in range(surface.rows + 1):
            y = row * cell
            self.canvas.create_line(0, y, width, y, fill=OVERLAY_GRID, tags=('grid',))
        for column in range(surface.columns + 1):
            x = column * cell
            self.canvas.create_line(x, 0, x, height, fill=OVERLAY_GRID, tags=('grid',))
        for guide in self.snapshot.guides:
            if guide.x < 0 or guide.x > surface.columns:
                continue
            x = guide.x * cell
            self.canvas.create_line(x, 0, x, height, fill=OVERLAY_GUIDE, width=2, tags=('guide',))
            at_end = guide.x == surface.columns
            self.canvas.create_text(x + (-8 if at_end else 6), 12, anchor='e' if at_end else 'w',
                                    fill=OVERLAY_GUIDE, text=guide.label)
        for marker in self.snapshot.markers:
            if 0 <= marker.x < surface.columns and 0 <= marker.y < surface.rows:
                self._draw_marker(marker, cell, 0)

    def _apply_overlay(self):
        if self.surface is None:
            return
        picked = self.picked_cell
        selected = self.rows.selection()
        self._show_surface(self.surface, scroll_to_ground=False)
        self.picked_cell = picked
        if selected:
            self.rows.selection_set(selected)
        self.highlight_record(None)

    def _foreground_hint(self):
        return OVERLAY_HINT if self.overlay.get() else FOREGROUND_HINT

    def _marker_at(self, canvas_x, canvas_y, cell):
        if not self.overlay.get() or self.snapshot is None or self.surface is None:
            return None
        for marker in self.snapshot.markers:
            if not (0 <= marker.x < self.surface.columns and 0 <= marker.y < self.surface.rows):
                continue
            left, top, right, bottom = _oval_box(marker.x, marker.y, marker.shape, cell, 0)
            if left <= canvas_x <= right and top <= canvas_y <= bottom:
                return marker
        return None

    def toggle_foreground(self):
        if self.surface is not None:
            self._show_placement()
            self.view_button.configure(text='Opening foreground')
            self.hint.configure(text=self.snapshot.legend)
            return

        def show():
            snapshot = self.load_snapshot(self.room_keys[self.room.get()], True)
            if snapshot.surface is None:
                raise ValueError('This room has no rendered surface')
            self.snapshot = snapshot
            self.records_by_id = {record.id: record for record in snapshot.records}
            self._show_surface(snapshot.surface)
            self.view_button.configure(text='Placement map')
            self.hint.configure(text=self._foreground_hint())
            self.highlight_record(None)
        self.handle(show)

    def select_marker(self, event):
        if self.surface is not None:
            cell_px = self.surface.cell_pixels * FOREGROUND_ZOOM
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            marker = self._marker_at(canvas_x, canvas_y, cell_px)
            if marker is not None:
                self.picked_cell = None
                self.rows.selection_set(marker.record_id)
                self.rows.see(marker.record_id)
                self.highlight_record(None)
                return
            x = int(canvas_x // cell_px)
            y = int(canvas_y // cell_px)
            cell = self.surface.cells.get((x, y))
            self.picked_cell = (x, y) if cell is not None else None
            if cell is None:
                self.rows.selection_remove(*self.rows.selection())
            else:
                self.rows.selection_set(cell.record_id)
                self.rows.see(cell.record_id)
            self.highlight_record(None)
            return

        for tag in self.canvas.gettags('current'):
            if tag.startswith('record-'):
                key = tag.removeprefix('record-')
                self.rows.selection_set(key)
                self.rows.see(key)

    def highlight_record(self, _event):
        self.canvas.delete('selection')
        selected = self.rows.selection()
        if self.surface is not None:
            self.hint.configure(text=self._foreground_hint())
            if selected:
                record_id = selected[0]
                record = self.records_by_id[record_id]
                if self.picked_cell is not None:
                    cell = self.surface.cells[self.picked_cell]
                    if cell.record_id == record_id:
                        x, y = self.picked_cell
                        self.hint.configure(text=f'{cell.caption} at {x}, {y}'
                                                 f'  •  {record.label}'
                                                 f'  •  ROM offset 0x{record.offset:05X}')
                    else:
                        self.picked_cell = None
                if self.picked_cell is None and self.overlay.get() and self.snapshot is not None:
                    marker = next((item for item in self.snapshot.markers
                                   if item.record_id == record_id
                                   and 0 <= item.x < self.surface.columns
                                   and 0 <= item.y < self.surface.rows), None)
                    if marker is not None:
                        self.hint.configure(text=f'Anchor at {marker.x}, {marker.y}'
                                                 f'  •  {record.label}'
                                                 f'  •  ROM offset 0x{record.offset:05X}')
                cell_px = self.surface.cell_pixels * FOREGROUND_ZOOM
                for (x, y), cell in self.surface.cells.items():
                    if cell.record_id == record_id:
                        left, top = x * cell_px, y * cell_px
                        self.canvas.create_rectangle(left, top, left + cell_px - 1,
                                                     top + cell_px - 1, outline='#ffffff',
                                                     tags=('selection',))
                if self.overlay.get() and self.snapshot is not None:
                    for marker in self.snapshot.markers:
                        if marker.record_id != record_id:
                            continue
                        if not (0 <= marker.x < self.surface.columns and 0 <= marker.y < self.surface.rows):
                            continue
                        left, top, right, bottom = _oval_box(marker.x, marker.y, marker.shape, cell_px, 0)
                        self.canvas.create_rectangle(left - 2, top - 2, right + 2, bottom + 2,
                                                     outline='#ffffff', width=2, tags=('selection',))
            return
        if not selected or self.snapshot is None:
            return
        marker = self.canvas.bbox(f'record-{selected[0]}')
        if marker:
            x1, y1, x2, y2 = marker
            self.canvas.create_rectangle(x1 - 3, y1 - 3, x2 + 3, y2 + 3, outline='#ffffff', tags=('selection',))
            top = self.canvas.canvasy(0)
            visible_height = self.canvas.winfo_height()
            board_height = TOP + self.snapshot.grid_rows * CELL
            if y1 < top or y2 > top + visible_height:
                self.canvas.yview_moveto((y1 - visible_height / 2) / board_height)
            left = self.canvas.canvasx(0)
            visible_width = self.canvas.winfo_width()
            board_width = self.snapshot.grid_columns * CELL
            if x1 < left or x2 > left + visible_width:
                self.canvas.xview_moveto((x1 - visible_width / 2) / board_width)

    def export(self):
        snapshot = self.snapshot
        if snapshot is None:
            return
        filename = filedialog.asksaveasfilename(parent=self, title='Save level data',
                           initialfile=snapshot.export_name,
                           defaultextension='.json', filetypes=[('JSON', '*.json')])
        if filename:
            self.handle(lambda: save_json(Path(filename), snapshot.to_dict()))
