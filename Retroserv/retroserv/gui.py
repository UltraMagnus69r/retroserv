"""Cross-platform Tk desktop ROM inspector; Fedora Linux is the primary target."""
from __future__ import annotations
import json
import sys
import threading
import tkinter as tk
from hashlib import sha256
from tkinter import simpledialog, ttk, filedialog, messagebox
from pathlib import Path
from PIL import Image, ImageTk
from . import __version__
from .assistant import (
    apply_room_labels, bundled_assistants, closest_text, load_for_rom, merge_assistant,
    read_assistant, save_for_rom, sidecar_path, write_assistant,
)
from .palettes import ImportedPalette, load_palette
from .rom import RomImage, parse_offset
from .graphics import read_palette, render_tiles, scan_graphics
from .textscan import scan_ascii, hex_dump
from .export import graphics_export, binary_export
from .smw import list_gfx, decoded_gfx, gfx_preview, export_gfx, recognized, GFX_GROUPS
from .level_view import LevelView
from .map_source import DEFAULT_MAP_PAGE
from .level_jobs import run_map_check, run_rebuild
from .smw_map_check import CheckProgress
from .smw_snapshot import inspect_level, rooms
from .desktop_paths import default_rom_directory
from .error_log import write_error_log


class RetroservGUI(tk.Tk):
    def __init__(self):
        super().__init__(className='Retroserv')
        self.title(f'Retroserv {__version__} — SNES Preservation Workbench')
        self.window_icon = tk.PhotoImage(file=Path(__file__).with_name('retroserv.png'))
        self.iconphoto(True, self.window_icon)
        self.geometry('1130x800')
        self.minsize(850, 580)
        self.rom: RomImage | None = None
        self.assistant = None
        self._checking = False
        self.preview_photo = None
        self.smw_preview_photo = None
        self.offset = tk.StringVar(value='0x12000')
        self.bpp = tk.StringVar(value='4')
        self.count = tk.StringVar(value='128')
        self.columns = tk.StringVar(value='16')
        self.palette_offset = tk.StringVar(value='')
        self.transparency = tk.BooleanVar(value=False)
        self.zoom = tk.StringVar(value='4')
        self.smw_zoom = tk.StringVar(value='4')
        self.smw_palette: ImportedPalette | None = None
        self.smw_palette_name = tk.StringVar(value='Grayscale')
        self.smw_palette_start = tk.StringVar(value='0')
        self.min_ascii = tk.StringVar(value='8')
        self.contains = tk.StringVar(value='')
        self.hex_offset = tk.StringVar(value='0x0')
        self.hex_length = tk.StringVar(value='256')

        self.ui_font = 'DejaVu Sans' if sys.platform.startswith('linux') else 'Segoe UI'
        self.mono_font = 'DejaVu Sans Mono' if sys.platform.startswith('linux') else 'Consolas'
        self.configure(background='#181e26')
        style = ttk.Style(self)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('TNotebook', background='#212936', borderwidth=0)
        style.configure('TNotebook.Tab', padding=(16, 9), font=(self.ui_font, 10))
        style.configure('TButton', padding=(9, 6))
        style.configure('TLabel', font=(self.ui_font, 10))
        style.configure('Header.TLabel', font=(self.ui_font, 13, 'bold'))
        style.configure('Treeview', rowheight=25)
        style.configure('Check.Horizontal.TProgressbar', thickness=18)
        self._make_menu()
        toolbar = ttk.Frame(self, padding=(14, 10))
        toolbar.pack(fill='x')
        ttk.Label(toolbar, text='RETROSERV', style='Header.TLabel').pack(side='left')
        self.open_button = ttk.Button(toolbar, text='Open ROM…', command=self.open_rom)
        self.open_button.pack(side='left', padx=16)
        self.file_label = ttk.Label(toolbar, text='No ROM loaded — open a .sfc or .smc file')
        self.file_label.pack(side='left', padx=4)
        status_row = ttk.Frame(self, padding=(12, 6))
        status_row.pack(side='bottom', fill='x')
        self.status = tk.StringVar(value='Ready. The original ROM is never edited.')
        ttk.Label(status_row, textvariable=self.status).pack(side='left', fill='x', expand=True)
        self.progress = ttk.Progressbar(status_row, style='Check.Horizontal.TProgressbar',
                                        length=260, mode='determinate', maximum=1)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=12, pady=(2,8))
        self.tab_info, self.tab_gfx, self.tab_smw, self.tab_text, self.tab_hex = [ttk.Frame(self.notebook) for _ in range(5)]
        for tab, name in [(self.tab_info,'ROM Inspector'), (self.tab_gfx,'Tile / Palette Viewer'),
                          (self.tab_smw,'SMW Graphics'),
                          (self.tab_text,'ASCII Finder'), (self.tab_hex,'Hex Viewer')]:
            self.notebook.add(tab, text=name)
        self.level_view = LevelView(
            self.notebook, self._handle, rooms(),
            lambda key, include_surface: inspect_level(
                self._require_rom(), key, include_surface=include_surface, assistant=self.assistant),
            self.check_maps, self.rebuild_from_rom)
        self.notebook.insert(3, self.level_view, text='SMW Levels')
        self._info_tab()
        self._graphics_tab()
        self._smw_tab()
        self._text_tab()
        self._hex_tab()

    def _make_menu(self):
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        self.file_menu = file_menu
        file_menu.add_command(label='Open ROM…', command=self.open_rom)
        file_menu.add_command(label='Load assistant file…', command=self.load_assistant)
        file_menu.add_command(label='Save assistant file as…', command=self.save_assistant)
        file_menu.add_command(label='Assistant settings…', command=self.assistant_settings)
        file_menu.add_command(label='Export inspection JSON…', command=self.export_info)
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=self.destroy)
        menu.add_cascade(label='File', menu=file_menu)
        self.config(menu=menu)

    def _info_tab(self):
        ttk.Label(self.tab_info, text='Read-only ROM fingerprint and cartridge header',
                  style='Header.TLabel').pack(anchor='w', padx=12, pady=12)
        self.info_text = tk.Text(self.tab_info, wrap='none', font=(self.mono_font, 10), borderwidth=0,
                                 background='#111821', foreground='#d9e2eb', insertbackground='#d9e2eb')
        self.info_text.pack(fill='both', expand=True, padx=12, pady=(0,12))
        self.info_text.insert('1.0', 'Open a ROM to inspect internal headers, hashes, and source size.\n\n'
                              'Header detection is heuristic; uncertain candidates are marked.')
        self.info_text.configure(state='disabled')

    def _graphics_tab(self):
        top = ttk.Frame(self.tab_gfx, padding=10)
        top.pack(fill='x')
        values = [("Data offset", self.offset, 12), ("BPP", self.bpp, 4),
                  ("Tiles", self.count, 7), ("Columns", self.columns, 6),
                  ("Palette offset", self.palette_offset, 12), ("Zoom", self.zoom, 4)]
        for title, var, width in values:
            group = ttk.Frame(top)
            group.pack(side='left', padx=(0,12))
            ttk.Label(group, text=title).pack(anchor='w')
            if title in ('BPP','Zoom'):
                values_option = ('2','3','4','8') if title == 'BPP' else ('1','2','3','4','5','6')
                ttk.Combobox(group, width=width, textvariable=var, values=values_option,
                             state='readonly').pack()
            else:
                ttk.Entry(group, width=width, textvariable=var).pack()
        actions = ttk.Frame(self.tab_gfx, padding=(10,1))
        actions.pack(fill='x')
        ttk.Checkbutton(actions, text='Transparent index 0', variable=self.transparency).pack(side='left', padx=(0,12))
        ttk.Button(actions, text='Preview tiles', command=self.preview).pack(side='left', padx=5)
        ttk.Button(actions, text='Export PNG + provenance…', command=self.export_tiles).pack(side='left', padx=5)
        ttk.Button(actions, text='Scan candidate offsets', command=self.scan_candidates).pack(side='left', padx=5)
        ttk.Label(self.tab_gfx, text='All ROM offsets are data-relative. Scanned offsets are guesses, not verified sprite locations.',
                  foreground='#93500a').pack(anchor='w', padx=10, pady=4)
        splitter = ttk.Panedwindow(self.tab_gfx, orient='horizontal')
        splitter.pack(fill='both', expand=True, padx=10, pady=(0,10))
        left = ttk.Frame(splitter)
        right = ttk.Frame(splitter, width=235)
        splitter.add(left, weight=4)
        splitter.add(right, weight=1)
        self.canvas = tk.Canvas(left, background='#1b212b', highlightthickness=0)
        self.cv_x = ttk.Scrollbar(left, orient='horizontal', command=self.canvas.xview)
        self.cv_y = ttk.Scrollbar(left, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.cv_x.set, yscrollcommand=self.cv_y.set)
        self.canvas.grid(row=0,column=0,sticky='nsew')
        self.cv_x.grid(row=1,column=0,sticky='ew')
        self.cv_y.grid(row=0,column=1,sticky='ns')
        left.grid_rowconfigure(0,weight=1)
        left.grid_columnconfigure(0,weight=1)
        ttk.Label(right, text='Candidate regions', style='Header.TLabel').pack(anchor='w', pady=7)
        ttk.Label(right, text='Double-click to preview\n(heuristic guesses only)').pack(anchor='w', pady=(0,4))
        self.candidates = tk.Listbox(right, font=(self.mono_font,10), activestyle='dotbox')
        self.candidates.pack(fill='both', expand=True)
        self.candidates.bind('<Double-Button-1>', self._open_candidate)

    def _smw_tab(self):
        bar = ttk.Frame(self.tab_smw, padding=10)
        bar.pack(fill='x')
        ttk.Label(bar, text='Super Mario World USA v1.0 — exact SHA-256 profile',
                  style='Header.TLabel').pack(side='left', padx=(0, 14))
        ttk.Button(bar, text='Discover GFX', command=self.smw_discover).pack(side='left', padx=4)
        ttk.Button(bar, text='Preview', command=self.smw_preview).pack(side='left', padx=4)
        ttk.Button(bar, text='Export selected…', command=self.smw_export_one).pack(side='left', padx=4)
        ttk.Button(bar, text='Export all…', command=self.smw_export_all).pack(side='left', padx=4)
        controls = ttk.Frame(self.tab_smw, padding=(10, 0))
        controls.pack(fill='x')
        ttk.Button(controls, text='Load .pal / CGRAM…', command=self.smw_load_palette).pack(side='left')
        ttk.Button(controls, text='Grayscale', command=self.smw_clear_palette).pack(side='left', padx=5)
        ttk.Label(controls, text='Start color').pack(side='left', padx=(10, 4))
        start = ttk.Entry(controls, width=6, textvariable=self.smw_palette_start)
        start.pack(side='left')
        start.bind('<Return>', self.smw_refresh_preview)
        ttk.Label(controls, text='Zoom').pack(side='left', padx=(10, 4))
        zoom = ttk.Combobox(controls, width=4, textvariable=self.smw_zoom,
                            values=('1', '2', '3', '4', '5', '6'), state='readonly')
        zoom.pack(side='left')
        zoom.bind('<<ComboboxSelected>>', self.smw_refresh_preview)
        ttk.Label(controls, textvariable=self.smw_palette_name, width=26).pack(side='left', padx=10)
        ttk.Label(self.tab_smw,
                  text='Choose a starting color for the imported palette. GFX27 exports as raw data.', foreground='#93500a').pack(anchor='w', padx=10, pady=4)
        pane = ttk.Panedwindow(self.tab_smw, orient='horizontal')
        pane.pack(fill='both', expand=True, padx=10, pady=8)
        left, right = ttk.Frame(pane), ttk.Frame(pane)
        pane.add(left, weight=2)
        pane.add(right, weight=3)
        self.smw_tree = ttk.Treeview(left, columns=('name','offset','bpp','note'), show='headings', height=25)
        for col, label, width in [('name','GFX',75),('offset','ROM offset',110),('bpp','BPP',45),('note','Graphics group',230)]:
            self.smw_tree.heading(col, text=label)
            self.smw_tree.column(col, width=width, stretch=(col == 'note'))
        self.smw_tree.pack(fill='both', expand=True)
        self.smw_tree.bind('<Double-Button-1>', lambda _: self.smw_preview())
        self.smw_canvas = tk.Canvas(right, background='#1b212b', highlightthickness=0)
        scroll_y = ttk.Scrollbar(right, orient='vertical', command=self.smw_canvas.yview)
        scroll_x = ttk.Scrollbar(right, orient='horizontal', command=self.smw_canvas.xview)
        self.smw_canvas.configure(xscrollcommand=scroll_x.set, yscrollcommand=scroll_y.set)
        self.smw_canvas.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

    def smw_discover(self):
        def do():
            rom = self._require_rom()
            entries = list_gfx(rom)
            for item in self.smw_tree.get_children():
                self.smw_tree.delete(item)
            for entry in entries:
                self.smw_tree.insert('', 'end', iid=str(entry.number),
                    values=(f'GFX{entry.number:02X}', f'0x{entry.data_offset:05X}',
                            entry.bpp if entry.bpp else 'Mode7', GFX_GROUPS[entry.number]))
            self.status.set(f'{len(entries)} documented SMW GFX pointers found; content not yet validated')
        self._handle(do)

    def _smw_selected(self):
        picked = self.smw_tree.selection()
        if not picked:
            raise ValueError('Click Discover GFX and select a graphics entry')
        return int(picked[0])

    def smw_refresh_preview(self, _event=None):
        if self.smw_tree.selection():
            self.smw_preview()

    def smw_load_palette(self):
        filename = filedialog.askopenfilename(title='Load SNES palette',
                       filetypes=[('Palette dumps', '*.pal *.cgram *.bin *.dmp'), ('All files', '*.*')])
        if not filename:
            return

        def do():
            self.smw_palette = load_palette(filename)
            self.smw_palette_name.set(self.smw_palette.name)
            self.smw_palette_start.set('0')
            self.smw_refresh_preview()
        self._handle(do)

    def smw_clear_palette(self):
        self.smw_palette = None
        self.smw_palette_name.set('Grayscale')
        self.smw_palette_start.set('0')
        self.smw_refresh_preview()

    def smw_palette_index(self):
        return parse_offset(self.smw_palette_start.get()) if self.smw_palette is not None else 0

    def smw_preview(self):
        def do():
            entry, result = decoded_gfx(self._require_rom(), self._smw_selected())
            start = self.smw_palette_index()
            image = gfx_preview(entry, result, palette=self.smw_palette, palette_start=start)
            zoom = int(self.smw_zoom.get())
            enlarged = image.resize((image.width * zoom, image.height * zoom), Image.Resampling.NEAREST)
            self.smw_preview_photo = ImageTk.PhotoImage(enlarged)
            self.smw_canvas.delete('all')
            self.smw_canvas.create_image(0, 0, anchor='nw', image=self.smw_preview_photo)
            self.smw_canvas.configure(scrollregion=(0, 0, enlarged.width, enlarged.height))
            colors = f'{self.smw_palette.format} from color {start}' if self.smw_palette else 'Grayscale'
            self.status.set(f'GFX{entry.number:02X} • {len(result.data)} decoded bytes • {colors} • {zoom}×')
        self._handle(do)

    def smw_export_one(self):
        def do():
            rom = self._require_rom()
            number = self._smw_selected()
            folder = filedialog.askdirectory(title='Choose directory for SMW GFX export')
            if not folder: return
            result = export_gfx(rom, number, folder, palette=self.smw_palette,
                                palette_start=self.smw_palette_index())
            self.status.set(f'Exported {result["name"]} with provenance: {folder}')
            messagebox.showinfo('Retroserv', f'Exported {result["name"]} to {folder}')
        self._handle(do)

    def smw_export_all(self):
        def do():
            rom = self._require_rom()
            if not recognized(rom):
                raise ValueError('Exact SMW USA v1.0 ROM fingerprint required')
            folder = filedialog.askdirectory(title='Choose empty output folder for all GFX')
            if not folder: return
            output = Path(folder)
            # Avoid accidental overwrite, and warn before generating many files.
            if any(output.glob('GFX*')):
                raise ValueError('Output contains GFX files; choose an empty output directory')
            start = self.smw_palette_index()
            if self.smw_palette:
                self.smw_palette.group(start, 3)
            if not messagebox.askyesno('Retroserv', 'Export 50 GFX entries to this folder?', parent=self):
                return
            successes, failures = 0, []
            for number in range(0x32):
                try:
                    export_gfx(rom, number, output, palette=self.smw_palette, palette_start=start)
                    successes += 1
                except (ValueError, OSError) as exc:
                    failures.append(f'GFX{number:02X}: {exc}')
            self.status.set(f'Exported {successes}/50 SMW GFX entries; {len(failures)} failures')
            messagebox.showinfo('Retroserv', f'Exported {successes}/50 GFX entries. '
                    + ('Errors: '+ '; '.join(failures[:5]) if failures else 'No errors.'), parent=self)
        self._handle(do)

    def _text_tab(self):
        bar = ttk.Frame(self.tab_text, padding=10)
        bar.pack(fill='x')
        ttk.Label(bar, text='Min length').pack(side='left')
        ttk.Entry(bar, textvariable=self.min_ascii, width=6).pack(side='left', padx=8)
        ttk.Label(bar, text='Contains').pack(side='left')
        ttk.Entry(bar, textvariable=self.contains, width=32).pack(side='left', padx=8)
        ttk.Button(bar, text='Find ASCII runs', command=self.find_strings).pack(side='left')
        ttk.Label(self.tab_text, text='These are printable byte sequences, not decoded dialogue or verified scripts.',
                  foreground='#93500a').pack(anchor='w', padx=10, pady=6)
        columns = ('offset','text')
        self.string_tree = ttk.Treeview(self.tab_text, columns=columns, show='headings')
        self.string_tree.heading('offset', text='ROM data offset')
        self.string_tree.heading('text', text='ASCII text')
        self.string_tree.column('offset', width=160, stretch=False)
        self.string_tree.column('text', width=700)
        self.string_tree.pack(fill='both', expand=True, padx=10,pady=8)
        self.string_tree.bind('<Double-Button-1>', self._string_hex_jump)

    def _hex_tab(self):
        bar = ttk.Frame(self.tab_hex, padding=10)
        bar.pack(fill='x')
        ttk.Label(bar, text='Data offset').pack(side='left')
        ttk.Entry(bar, textvariable=self.hex_offset, width=16).pack(side='left', padx=8)
        ttk.Label(bar, text='Length (1–65536)').pack(side='left')
        ttk.Entry(bar, textvariable=self.hex_length, width=12).pack(side='left', padx=8)
        ttk.Button(bar, text='View bytes', command=self.show_hex).pack(side='left', padx=6)
        ttk.Button(bar, text='Export raw slice…', command=self.export_slice).pack(side='left')
        self.hex_text = tk.Text(self.tab_hex, wrap='none', font=(self.mono_font,11), background='#111821',
                                foreground='#d9e2eb', insertbackground='#d9e2eb', borderwidth=0)
        self.hex_text.pack(fill='both', expand=True, padx=10,pady=8)

    def _require_rom(self):
        if self.rom is None:
            raise ValueError('Open a ROM before using this action')
        return self.rom

    def _report_error(self, exc: BaseException, context: str) -> None:
        path = write_error_log(exc, context=context)
        message = str(exc)
        if path is not None:
            message += f'\n\nLog: {path.name}'
        messagebox.showerror('Retroserv', message, parent=self)
        self.status.set(f'Error: {exc}')

    def _handle(self, action):
        try:
            return action()
        except (OSError, ValueError, RuntimeError) as exc:
            self._report_error(exc, 'Retroserv')
            return None

    def open_rom(self):
        if self._checking:
            return
        filename = filedialog.askopenfilename(title='Select SNES ROM',
                     initialdir=str(default_rom_directory()),
                     filetypes=[('SNES ROM images','*.sfc *.smc *.fig *.bin'),('All files','*.*')])
        if not filename: return
        def do():
            self.rom = RomImage(filename)
            info = self.rom.info()
            self.file_label.configure(text=f'{Path(filename).name}  •  {len(self.rom.data):,} data bytes')
            self.info_text.configure(state='normal')
            self.info_text.delete('1.0','end')
            self.info_text.insert('1.0', json.dumps(info, indent=2))
            self.info_text.configure(state='disabled')
            self.candidates.delete(0,'end')
            for item in self.string_tree.get_children(): self.string_tree.delete(item)
            self.canvas.delete('all')
            self.preview_photo = None
            for item in self.smw_tree.get_children(): self.smw_tree.delete(item)
            self.smw_canvas.delete('all')
            self.smw_preview_photo = None
            digest = sha256(self.rom.data).hexdigest()
            self.assistant = load_for_rom(digest, self.rom.path)
            self.level_view.set_rooms(apply_room_labels(rooms(self.rom), self.assistant), selected=0x105)
            sidecar = sidecar_path(self.rom.path)
            if sidecar.is_file():
                self.status.set(f'Loaded {Path(filename).name} (READ ONLY). Assistant file: {sidecar.name}')
            else:
                self.status.set(f'Loaded {Path(filename).name} (READ ONLY)')
            self.notebook.select(self.tab_info)
        self._handle(do)

    def _refresh_rooms(self, selected: int | None = None) -> None:
        current = selected
        if current is None:
            current = self.level_view.room_keys.get(self.level_view.room.get())
        self.level_view.set_rooms(apply_room_labels(rooms(self.rom), self.assistant), selected=current)

    def load_assistant(self):
        if self.rom is None:
            messagebox.showinfo('Retroserv', 'Open a ROM first', parent=self)
            return
        filename = filedialog.askopenfilename(title='Load assistant file', parent=self,
                     filetypes=[('Assistant file', '*.json'), ('All files', '*.*')])
        if not filename:
            return
        def do():
            loaded = read_assistant(Path(filename))
            digest = sha256(self.rom.data).hexdigest()
            if loaded.rom_sha256 != digest:
                raise ValueError('That assistant file belongs to a different ROM')
            base = next((item for item in bundled_assistants() if item.rom_sha256 == digest), None)
            self.assistant = merge_assistant(base, loaded)
            path = save_for_rom(self.assistant, self.rom.path)
            self._refresh_rooms(0x105)
            self.status.set(f'Assistant file applied and saved: {path}')
        self._handle(do)

    def save_assistant(self):
        if self.assistant is None:
            messagebox.showinfo('Retroserv', 'Open a ROM first. The assistant file is stored per cartridge.',
                                parent=self)
            return
        filename = filedialog.asksaveasfilename(title='Save a copy of the assistant file', parent=self,
                     defaultextension='.json', filetypes=[('Assistant file', '*.json')])
        if not filename:
            return
        def do():
            write_assistant(self.assistant, Path(filename))
            self.status.set(f'Assistant file copied: {filename}')
        self._handle(do)

    def assistant_settings(self):
        from .assistant_settings import (
            PROVIDERS, AssistantSettings, api_key, clear_api_key, load_settings, save_api_key,
            save_settings,
        )
        current = load_settings()
        dialog = tk.Toplevel(self)
        dialog.title('Assistant settings')
        dialog.transient(self)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Assistant').grid(row=0, column=0, sticky='w')
        labels = [label for _key, label in PROVIDERS]
        by_label = {label: key for key, label in PROVIDERS}
        by_key = dict(PROVIDERS)
        provider = tk.StringVar(value=by_key.get(current.provider, labels[0]))
        ttk.Combobox(frame, textvariable=provider, values=labels, state='readonly', width=28).grid(
            row=0, column=1, sticky='ew', pady=4)
        ttk.Label(frame, text='Cursor model').grid(row=1, column=0, sticky='w')
        model = tk.StringVar(value=current.model)
        ttk.Entry(frame, textvariable=model, width=30).grid(row=1, column=1, sticky='ew', pady=4)
        ttk.Label(frame, text='Cursor API key').grid(row=2, column=0, sticky='w')
        key = tk.StringVar()
        ttk.Entry(frame, textvariable=key, show='*', width=30).grid(row=2, column=1, sticky='ew', pady=4)
        saved = 'A key is saved. Leave this blank to keep it.' if api_key() else (
            'No key is saved. CURSOR_API_KEY is used when this is blank.')
        ttk.Label(frame, text=saved, wraplength=360).grid(row=3, column=0, columnspan=2, sticky='w', pady=(0, 8))
        ttk.Label(frame, text='Snes9x shots').grid(row=4, column=0, sticky='w')
        shots = tk.StringVar(value=current.screenshot_folder)
        ttk.Entry(frame, textvariable=shots, width=30).grid(row=4, column=1, sticky='ew', pady=4)

        def browse_shots():
            folder = filedialog.askdirectory(title='Folder of Snes9x screenshots', parent=dialog)
            if folder:
                shots.set(folder)

        ttk.Button(frame, text='Browse…', command=browse_shots).grid(row=5, column=1, sticky='w')
        ttk.Label(frame, text='Name a shot $105.png to compare that room. '
                  'Rebuild from ROM reads course names from the cartridge. '
                  'Cursor can describe one room. It does not repaint it.',
                  wraplength=360).grid(row=6, column=0, columnspan=2, sticky='w', pady=(8, 12))

        def store():
            save_settings(AssistantSettings(by_label[provider.get()], model.get(), shots.get()))
            typed = key.get().strip()
            if typed:
                save_api_key(typed)
            dialog.destroy()

        def forget():
            clear_api_key()
            key.set('')
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, columnspan=2, sticky='e')
        ttk.Button(buttons, text='Clear saved key', command=forget).pack(side='left', padx=(0, 8))
        ttk.Button(buttons, text='Cancel', command=dialog.destroy).pack(side='left', padx=(0, 8))
        ttk.Button(buttons, text='Save', command=store).pack(side='left')
        dialog.grab_set()
        dialog.wait_window()

    def check_maps(self):
        if self.rom is None:
            messagebox.showinfo('Retroserv', 'Open a ROM first', parent=self)
            return
        if self._checking:
            return
        from .assistant_settings import load_settings
        from .cursor_match import cursor_requirement
        settings = load_settings()
        if settings.provider == 'cursor':
            problem = cursor_requirement(settings)
            if problem:
                messagebox.showerror('Retroserv', problem, parent=self)
                self.assistant_settings()
                return
        url = simpledialog.askstring(
            'Check maps',
            'Compare every horizontal room with every course map on this page.',
            initialvalue=self.assistant.source if self.assistant and self.assistant.source else DEFAULT_MAP_PAGE,
            parent=self)
        if not url or not url.strip():
            return
        rom_path = self._begin_job()
        selected = self.level_view.room_keys.get(self.level_view.room.get())
        digest = sha256(self.rom.data).hexdigest()
        assistant = self.assistant or load_for_rom(digest, self.rom.path)
        rom = self.rom

        def work():
            try:
                result = run_map_check(
                    rom, url.strip(), assistant, settings,
                    lambda update: self.after(0, self._apply_check_progress, update))
            except Exception as exc:
                self.after(0, lambda exc=exc: self._check_failed(exc))
                return
            self.after(0, lambda result=result: self._check_finished(result, selected, rom_path))

        threading.Thread(target=work, daemon=True).start()

    def _apply_check_progress(self, update: CheckProgress) -> None:
        self.status.set(update.message)
        if not self.progress.winfo_ismapped():
            self.progress.pack(side='right', padx=(12, 0))
        if update.total <= 0:
            if str(self.progress.cget('mode')) != 'indeterminate':
                self.progress.stop()
                self.progress.configure(mode='indeterminate', maximum=100)
                self.progress.start(12)
        else:
            if str(self.progress.cget('mode')) != 'determinate':
                self.progress.stop()
                self.progress.configure(mode='determinate')
            self.progress.configure(maximum=update.total, value=update.completed)
        self.update_idletasks()

    def _hide_check_progress(self) -> None:
        self.progress.stop()
        self.progress.configure(mode='determinate', value=0, maximum=1)
        if self.progress.winfo_ismapped():
            self.progress.pack_forget()

    def _set_level_buttons(self, state: str) -> None:
        for name in ('check_button', 'rebuild_button'):
            button = getattr(self.level_view, name, None)
            if button is not None:
                button.configure(state=state)

    def _set_rom_actions(self, state: str) -> None:
        self.open_button.configure(state=state)
        self.file_menu.entryconfig('Open ROM…', state=state)

    def _begin_job(self):
        self._checking = True
        self._set_level_buttons('disabled')
        self._set_rom_actions('disabled')
        return self.rom.path

    def _end_job(self) -> None:
        self._checking = False
        self._set_level_buttons('normal')
        self._set_rom_actions('normal')
        self._hide_check_progress()

    def _same_rom(self, rom_path) -> bool:
        return self.rom is not None and self.rom.path == rom_path

    def rebuild_from_rom(self):
        if self.rom is None:
            messagebox.showinfo('Retroserv', 'Open a ROM first', parent=self)
            return
        if self._checking:
            return
        from .assistant_settings import load_settings
        settings = load_settings()
        rom_path = self._begin_job()
        selected = self.level_view.room_keys.get(self.level_view.room.get())
        digest = sha256(self.rom.data).hexdigest()
        assistant = self.assistant or load_for_rom(digest, self.rom.path)
        rom = self.rom

        def work():
            try:
                result, note = run_rebuild(
                    rom, assistant, settings,
                    lambda update: self.after(0, self._apply_check_progress, update))
            except Exception as exc:
                self.after(0, lambda exc=exc: self._check_failed(exc))
                return
            self.after(0, lambda result=result, note=note: self._rebuild_finished(
                result, selected, note, rom_path))

        threading.Thread(target=work, daemon=True).start()

    def _check_failed(self, exc: Exception) -> None:
        self._end_job()
        self._report_error(exc, 'Map check')

    def _check_finished(self, result, selected, rom_path) -> None:
        self._end_job()
        if not self._same_rom(rom_path):
            self.status.set('The ROM changed before the map check finished, so nothing was saved.')
            return
        path = save_for_rom(result, self.rom.path)
        self.assistant = result
        self._refresh_rooms(selected if selected is not None else 0x105)
        note = closest_text(result.rooms.get(str(selected)) if selected is not None else None)
        if note:
            self.level_view.show_note(note)
        named = sum(room.title is not None for room in result.rooms.values())
        self.status.set(
            f'Checked {len(result.rooms)} rooms against {result.source_map_count} maps. '
            f'Named {named}. Assistant file: {path}')

    def _rebuild_finished(self, result, selected, note: str, rom_path) -> None:
        self._end_job()
        if not self._same_rom(rom_path):
            self.status.set('The ROM changed before the rebuild finished, so nothing was saved.')
            return
        path = save_for_rom(result, self.rom.path)
        self.assistant = result
        self._refresh_rooms(selected if selected is not None else 0x105)
        named = sum(room.title is not None for room in result.rooms.values())
        status = f'Named {named} of {len(result.rooms)} rooms from the ROM. Assistant file: {path}'
        if note:
            status += f' Cursor: {note}'
        self.status.set(status)

    def export_info(self):
        if self.rom is None:
            messagebox.showinfo('Retroserv', 'Open a ROM first')
            return
        name = filedialog.asksaveasfilename(title='Save inspection JSON',
                          defaultextension='.json', filetypes=[('JSON','*.json')])
        if not name: return
        def do():
            from .export import save_json
            save_json(Path(name), self.rom.info())
            self.status.set(f'Inspection saved: {name}')
        self._handle(do)

    def _graphics_parameters(self):
        rom = self._require_rom()
        off = parse_offset(self.offset.get())
        bpp, count, columns = int(self.bpp.get()), int(self.count.get()), int(self.columns.get())
        pal = parse_offset(self.palette_offset.get()) if self.palette_offset.get().strip() else None
        return rom, off, bpp, count, columns, pal

    def preview(self):
        def do():
            rom, off, bpp, count, columns, pal = self._graphics_parameters()
            colors = read_palette(rom.slice(pal, 2*(1<<bpp)),1<<bpp) if pal is not None else None
            bitmap = render_tiles(rom.data,off,bpp,count,columns,colors,self.transparency.get())
            mult = int(self.zoom.get())
            resized = bitmap.resize((bitmap.width*mult,bitmap.height*mult),resample=0)
            self.preview_photo = ImageTk.PhotoImage(resized)
            self.canvas.delete('all')
            self.canvas.create_image(0,0,anchor='nw',image=self.preview_photo)
            self.canvas.configure(scrollregion=(0,0,resized.width,resized.height))
            self.status.set(f'Preview: 0x{off:X}, {bpp}bpp, {count} tiles, {bitmap.width}×{bitmap.height} logical pixels')
        self._handle(do)

    def export_tiles(self):
        if self.rom is None:
            self._handle(self._require_rom); return
        filename = filedialog.asksaveasfilename(title='Export decoded PNG', defaultextension='.png',
                      filetypes=[('PNG image','*.png')])
        if not filename: return
        def do():
            rom, off, bpp, count, columns, pal = self._graphics_parameters()
            result = graphics_export(rom,filename,off,bpp,count,columns,pal,self.transparency.get())
            self.status.set(f"PNG saved with provenance: {result['png']}")
            messagebox.showinfo('Retroserv',f"Saved PNG and provenance JSON:\n{result['png']}\n{result['sidecar']}")
        self._handle(do)

    def scan_candidates(self):
        def do():
            rom = self._require_rom()
            self.status.set('Scanning ROM for plausible tile patterns…')
            self.update_idletasks()
            rows = scan_graphics(rom.data, int(self.bpp.get()), limit=40)
            self._candidate_rows = rows
            self.candidates.delete(0,'end')
            for candidate in rows:
                self.candidates.insert('end',f'0x{candidate.offset:06X}  score {candidate.score:.2f}')
            self.status.set(f'Ranked {len(rows)} heuristic candidates. No asset identities verified.')
        self._handle(do)

    def _open_candidate(self,_event):
        sel = self.candidates.curselection()
        if sel and getattr(self,'_candidate_rows',None):
            self.offset.set(f'0x{self._candidate_rows[sel[0]].offset:X}')
            self.preview()

    def find_strings(self):
        def do():
            rom = self._require_rom()
            rows = scan_ascii(rom.data,int(self.min_ascii.get()),2000,self.contains.get())
            for item in self.string_tree.get_children(): self.string_tree.delete(item)
            for row in rows:
                self.string_tree.insert('', 'end',values=(f'0x{row.offset:06X}',row.text[:500]))
            self.status.set(f'{len(rows)} printable ASCII runs (max 2,000); game-specific encodings not decoded')
        self._handle(do)

    def _string_hex_jump(self,_event):
        selected = self.string_tree.selection()
        if selected:
            self.hex_offset.set(self.string_tree.item(selected[0], 'values')[0])
            self.notebook.select(self.tab_hex)
            self.show_hex()

    def show_hex(self):
        def do():
            rom = self._require_rom()
            result = hex_dump(rom.data,parse_offset(self.hex_offset.get()),int(self.hex_length.get()))
            self.hex_text.delete('1.0','end')
            self.hex_text.insert('1.0',result)
            self.status.set('Hexadecimal ROM data viewer (read only)')
        self._handle(do)

    def export_slice(self):
        if self.rom is None: self._handle(self._require_rom); return
        filename = filedialog.asksaveasfilename(title='Export raw bytes', defaultextension='.bin',
                                                 filetypes=[('Binary','*.bin'),('All files','*.*')])
        if not filename: return
        def do():
            result = binary_export(self.rom,filename,parse_offset(self.hex_offset.get()),
                                   parse_offset(self.hex_length.get()))
            self.status.set(f"Copied bytes with provenance: {result['binary']}")
        self._handle(do)


def launch():
    app = RetroservGUI()
    app.mainloop()

if __name__ == '__main__':
    launch()
