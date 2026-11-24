# Retroserv handoff for Cursor

Snapshot from November 9, 2026. The desktop folder is named `RetroServ`, the app and source folder are named `Retroserv`, and the Python package is `retroserv`.

## Start here

Open this entire `RetroServ` folder in Cursor. The working source is in [Retroserv/](Retroserv/). Use [the app README](Retroserv/README.md) for setup and feature instructions. [history/](history/) contains earlier snapshots and the folder reference. [verification/](verification/) contains the scripts used to reproduce the foreground comparison.

From the Cursor terminal:

```bash
cd "$HOME/Desktop/RetroServ/Retroserv"
./Setup-Fedora.sh
./Start-Retroserv.sh
.venv/bin/python -m pytest -q
```

On Bazzite, run `./Setup-Bazzite.sh` in place of `./Setup-Fedora.sh`. It selects a Fedora Distrobox and creates `.venv-distrobox`; setup runs the tests inside the box. The Fedora native route was tested on Fedora 44 KDE. The Bazzite route still needs a live test. Setup needs Python 3.11 or later, Tkinter and pip, and fetches Pillow and pytest. MCP is optional.

The existing desktop shortcut created during recovery points to the original working copy at `$HOME/Documents/ChatGPT/RetroServe/Retroserv`. The copy on the Desktop is independent. After testing it, run `./Install-Desktop-Shortcut.sh` from this copy if you want the existing desktop and application-menu shortcuts to launch this copy instead.

## Purpose and direction

Retroserv is a read-only cartridge inspection, asset extraction, and level reconstruction workbench. Super Mario World for SNES is the first game adapter. The longer-term plan is to edit levels, support selected NES games, and eventually bring the work into another project. Keep game-specific ROM interpretation separate from the view and future editor. A second game should inform shared editor behavior before deciding on a common editing and save format.

## What happened

| Stage | Result |
| --- | --- |
| Original local builds | Source snapshots for 0.1.2 and 0.2 Alpha 2 were present in the home directory. The 0.2 Alpha 2 baseline passed 41 tests and extracted all 50 documented SMW graphics groups from the local ROM. |
| 0.3 Alpha 1 recovery | The earlier conversation described an official 0.3 Alpha 1 ZIP and TAR.GZ and 53 passing tests. Its files and original icon could not be recovered. The local 0.2 Alpha 2 source became the basis for the explicitly labeled `0.3.0a1+recovery.1`. |
| Fedora desktop recovery | Restored SMW graphics names, external palette import and provenance, color-group selection, and 4× default zoom. Recreated the NES controller and 386 PC badge. Added the executable KDE desktop and application-menu launchers. Updated the optional MCP wrapper to work with the official Python SDK v1 and verified it over local stdio. The recovery suite reached 44 tests. |
| Level inspection | Added the Yoshi’s Island 1 main area ($105) and bonus room ($1CB). Implemented a scrollable placement map and record table, JSON export, a CLI command, and an MCP tool. Verified both areas, copier-header handling, and byte-for-byte preservation of the source streams. The suite reached 47 tests. |
| Opening foreground | Reconstructed the static Layer 1 foreground for screen $00 of level $105. Ported the three required object routines, applied vanilla Map16 definitions and the ROM's character graphics and palette, and linked every drawn cell to the record that last wrote it. The suite reached 49 tests. |
| Folder icon | Used the supplied Fedora folder shape as a reference and made [Retroserv-Folder.svg](Retroserv-Folder.svg), a standalone transparent SVG with the Retroserv badge on a black folder. The badge used by the application remains at [retroserv.png](Retroserv/retroserv/retroserv.png). |

The preserved recovery tarball predates the level work. Use the source directory in this handoff for the current foreground milestone. Package metadata still reports `0.3.0a1+recovery.1`. The foreground milestone has no separate release number.

## What works now

- **ROM Inspector** identifies likely LoROM, HiROM or ExHiROM headers, reports hashes and file metadata, and handles a 512-byte copier header. Hex and ASCII views expose raw data. Printable runs are not necessarily dialogue.
- **Tile / Palette Viewer** reads 2, 3, 4 and 8 bpp SNES planar tiles, supports manual offsets and optional ROM BGR555 palettes, and exports PNGs and provenance. Candidate scanning is heuristic.
- **SMW Graphics** supports exactly the vanilla USA v1.0 cartridge fingerprint. It reads the documented GFX00–GFX31 pointer tables and decodes bounded LC_LZ2 streams. It exported 50 BINs and 49 PNGs from the user's ROM. GFX27 is Mode 7 raw data. GFX32 and GFX33 have separate formats and are outside this extraction path.
- **Palette import** accepts a 512-byte CGRAM dump or a 768-byte Lunar Magic RGB palette. Select a starting color. Export JSON records the palette filename, format, SHA-256, and color index. Imported palettes use the colors the user selects. The level foreground has its own ROM-derived palette loader.
- **SMW Levels** displays the main area (20 screens, 88 object placements, 34 sprite records, three screen jumps, and one exit record) and the bonus room (two screens, 15 object placements, one exit record, and zero sprite records). Screen exits retain the destination byte and secondary-exit flag. In vanilla SMW the overworld context supplies the destination bank.
- **Opening foreground** renders the 16 × 27 Map16 cells in the opening column of the main level. The surface is 256 × 432 pixels before 2× desktop display scaling. Click an occupied cell to select its source record and outline the visible cells owned by that object. The current test ROM has 74 occupied cells. The preview uses static terrain and decorative blocks. Animated tiles, backgrounds, sprite artwork, other foreground screens, and live play are future work.
- **CLI and MCP** provide headless access. The MCP launcher serves local stdio using the official Python SDK v1. A local SDK client was used to verify graphics and level inspection. Cursor's own UI integration still needs a live check.

### ROM used for verification

Local reference path on the original machine:

`$HOME/Desktop/Super Mario World (USA)/Super Mario World (USA).sfc`

Headerless cartridge SHA-256:

`0838e531fe22c077528febe14cb3ff7c492f1f5fa8de354192bdff7137c27f5b`

The commercial ROM and generated emulator data are outside this handoff. [The included sample ROM](Retroserv/samples/retroserv_test.sfc) is synthetic and nonplayable. It works for generic inspection and tests, and will be rejected by the SMW adapter. Verification left the original ROM hash unchanged.

## Entry points and code map

| Area | Where to start |
| --- | --- |
| Fedora, Bazzite, desktop and MCP launchers | [Setup-Fedora.sh](Retroserv/Setup-Fedora.sh), [Setup-Bazzite.sh](Retroserv/Setup-Bazzite.sh), [Start-Retroserv.sh](Retroserv/Start-Retroserv.sh), [Install-Desktop-Shortcut.sh](Retroserv/Install-Desktop-Shortcut.sh), [scripts/run.sh](Retroserv/scripts/run.sh) |
| Generic SNES decoding and exports | [rom.py](Retroserv/retroserv/rom.py), [graphics.py](Retroserv/retroserv/graphics.py), [palettes.py](Retroserv/retroserv/palettes.py), [textscan.py](Retroserv/retroserv/textscan.py), [export.py](Retroserv/retroserv/export.py) |
| SMW graphics tables and decompression | [smw.py](Retroserv/retroserv/smw.py), [lc_lz2.py](Retroserv/retroserv/lc_lz2.py) |
| Game-specific level model | [smw_level.py](Retroserv/retroserv/smw_level.py). The versioned `retroserv-smw-level-v1` JSON includes ROM identity, pointer addresses, offsets relative to cartridge data, headers, ordered source records, placements, and terminator offsets. Add the copier-header size for file offsets. |
| Game-specific foreground reconstruction | [smw_foreground.py](Retroserv/retroserv/smw_foreground.py). The long ledge ($21), long bush ($3F) and left diagonal platform ($3A) follow the vanilla object routines. The renderer uses the Map16 common/tileset tables, GFX slots, color tables, and tile flips. It produces a PIL image and a cell-to-source hit map without Tk dependencies. |
| Desktop controls | [gui.py](Retroserv/retroserv/gui.py) hosts the tabs. [level_view.py](Retroserv/retroserv/level_view.py) handles scrolling, mode switches, selection, highlighting, and export. |
| Automation | [cli.py](Retroserv/retroserv/cli.py) exposes `smw-level`. [mcp_server.py](Retroserv/retroserv/mcp_server.py) exposes `inspect_smw_level`. Both reuse the decoder. Foreground viewing is a GUI feature with a Python renderer. |
| Tests | [tests/](Retroserv/tests/) has 49 passing tests, including synthetic palette, level-stream, and object-footprint regressions. |

To get JSON from the CLI:

```bash
rom="$HOME/Desktop/Super Mario World (USA)/Super Mario World (USA).sfc"
./Retroserv-CLI.sh smw-level "$rom" --level 0x105 --output "$HOME/smw-105.json"
```

For Cursor, run `./Install-MCP.sh` and merge a `retroserv` entry into your existing MCP configuration. Set the command to the absolute path of this copy's `Run-Retroserv-MCP.sh`. See [Cursor MCP setup](Retroserv/docs/CURSOR_MCP.md).

### Fedora KDE and the XWayland window

The Tkinter GUI used KDE's regular XWayland display at `:0` during testing. The CLI and MCP run headless. A separate windowed XWayland instance at `:24` was observed during the session. Its parent was Codex, and its startup path pointed to an NES+ test. That instance was separate from Retroserv's launcher. The display numbers describe what was observed at the time.

In Dolphin, the SVG can be selected through **Properties → folder icon → Browse**. The Desktop destination's existing folder metadata was preserved during this handoff.

## Reproduce the Snes9x foreground comparison

The comparison checked all 432 Map16 cells against Snes9x 1.63 WRAM. It compared visible tile attributes with BG1 VRAM and rendered the reference foreground using the emulator's 4bpp character data and CGRAM. There were zero differences in the isolated foreground. A separate comparison with the composed emulator frame used the one-line SNES scroll offset and a two-RGB-level tolerance for color conversion. It matched 13,938 of 13,962 opaque visible pixels, with the other 24 at the Rex sprite overlay.

To repeat the check, obtain the [Snes9x 1.63 source](https://github.com/snes9xgit/snes9x/releases/tag/1.63) and unpack it to a scratch directory. Append the provided read-only memory probe to an unmodified `libretro/libretro.cpp` once. Compile the Linux libretro core using `make` and a C/C++ toolchain. Example from the handoff folder:

```bash
root="$HOME/Desktop/RetroServ"
snes9x=/absolute/path/to/snes9x-1.63
cat "$root/verification/snes9x-memory-probe.inc" >> "$snes9x/libretro/libretro.cpp"
make -C "$snes9x/libretro" -j4
rom="$HOME/Desktop/Super Mario World (USA)/Super Mario World (USA).sfc"
scratch="$(mktemp -d)"
cd "$scratch"
python3 "$root/verification/opening.py" "$rom" "$snes9x/libretro/snes9x_libretro.so"
PYTHONPATH="$root/Retroserv" "$root/Retroserv/.venv/bin/python" "$root/verification/compare.py" "$rom"
```

The scripts write captures in the scratch folder. The GUI check requires an active desktop session:

```bash
PYTHONPATH="$root/Retroserv" "$root/Retroserv/.venv/bin/python" "$root/verification/check_gui.py" "$rom"
```

Sources used for the game-specific work include the SMWDisX [level loader and Map16 setup](https://github.com/IsoFrieze/SMWDisX/blob/master/bank_05.asm), [object routines and Map16 data](https://github.com/IsoFrieze/SMWDisX/blob/master/bank_0D.asm), [graphics and palettes](https://github.com/IsoFrieze/SMWDisX/blob/master/bank_00.asm), [sprite decoding](https://github.com/IsoFrieze/SMWDisX/blob/master/bank_02.asm), and [graphics group names](https://github.com/IsoFrieze/SMWDisX/blob/master/constants.asm).

## Picture references

These pages are for course titles and for comparing a render after the ROM decode is already faithful. They are not a pixel source, and their images stay outside the repository. Snes9x running the same cartridge remains the pixel check.

- Course maps: https://www.mariouniverse.com/maps-snes-smw/
- Sprite, object, tile, and background sheets: https://www.mariouniverse.com/sprites-snes-smw/

The sprite index has two halves. The first half is Super Mario World: enemies, Mario, Luigi, Yoshi, pipes, objects, tiles, backgrounds, and a palette page. The second half is labeled Custom and includes characters and tiles that are not in the USA cartridge. Use only the first half when checking this ROM.

The SMW Levels tab has **Check maps…**. File → Assistant settings chooses who matches the rooms. Picture match compares the drawings directly. Cursor is asked to match the foreground layouts to the course list and to record glitches; it does not repaint the ROM. A room is renamed only when the chosen assistant returns one catalog title for that room. The result is `<rom name>-assistant.json` in the same folder as the ROM. Opening that ROM loads the file. An older hash-named copy under `~/.local/share/retroserv/assistants/` is read only when the file beside the ROM is missing. Corrections live in that file. The grass diagonal-pipe pointers are the first one, in `retroserv/assistants/smw-usa-v1.0.json`; the level view does not know about them.

## Where to continue

1. **Add the first NES adapter before building edit/save.** The SNES milestone already has an emulator-verified screen. Pick one NES game and one level with a verified ROM and reliable format references. Read placements, render one opening screen, and compare it with an emulator. No NES game has been selected or implemented in Retroserv.
2. **Extract shared viewer behavior once two adapters exist.** Keep selection, scrolling, zoom, and image hit-testing reusable. Keep cartridge identities, object expansion, palette rules, and serialization in the adapters. Preserve immutable source records and final tile-to-record ownership as separate data from future editable state.
3. **Expand SMW foreground coverage in emulator-verified slices.** Preserve stream order, handle objects that cross screen boundaries or write backwards across them, and compare generated Map16 IDs before checking pixels. The current renderer intentionally supports level $105 screen $00 and only the three object routines needed there. Backgrounds, animation, and sprite artwork are separate milestones.
4. **Add editor operations after both read-only examples work.** Start with move or resize and an undoable in-memory edit model. Prove byte-identical round trips for unchanged streams. Treat re-encoding, pointer relocation, exit links, ROM checksums, and emulator playtesting as game-specific. Export patches or a separate ROM copy when writing support is ready.
5. **Merge deliberately.** The intended destination project and its interfaces have not been specified. Keep Retroserv usable independently until there is a target for the shared model and view.

The installed build is a preservation and reconstruction tool. It currently has no level editor, playable ROM rebuild path, automatic scene palette matching for generic graphics, or audio, music, and dialogue extraction.
