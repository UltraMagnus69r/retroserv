# Retroserv 0.3 Alpha 1 Recovery — Fedora and Bazzite

Build version `0.3.0a1+recovery.1`. Rebuilt from the local 0.2 Alpha 2
source with the palette, graphics catalog and zoom features described in the
0.3 Alpha 1 release notes. The original 0.3 Alpha 1 archive and icon were
unavailable. This build includes a replacement NES controller and 386 PC icon.

**Linux-first, aimed at the Fedora family:** Fedora Workstation, Fedora KDE Plasma
Desktop, Fedora Spins, and Fedora Atomic desktops (Bazzite, Silverblue, Kinoite).

Retroserv is an MIT-licensed, source-available Python ROM inspection utility.
It can read SNES ROMs, decode uncompressed graphics plus supported Super Mario World LC_LZ2 graphics and palettes at specified
addresses, generate PNG exports with provenance, scan ASCII, and inspect hex.
**It is not a universal SNES game decompiler or a finished game builder.**

## Default ROM folder

Clicking **Open ROM…** now starts the file chooser in your Desktop folder
(`~/Desktop` on standard Fedora). Retroserv reads the Fedora/XDG
`~/.config/user-dirs.dirs` setting to support renamed or relocated Desktop
folders. If no Desktop directory exists, it opens your home folder.
This affects ROM loading only; it does not move your ROM files or change
export destinations.

## Copy onto another desktop

```bash
git clone https://github.com/UltraMagnus69r/retroserv.git ~/Desktop/RetroServ
cd ~/Desktop/RetroServ/Retroserv
chmod +x ./*.sh scripts/*.sh
./Setup-Fedora.sh
./Start-Retroserv.sh
```

That clone is the whole working folder. `./Setup-Fedora.sh` creates the Python virtual environment on the new machine. The commercial Super Mario World ROM is not in the repository. Keep your own copy on that desktop and open it with **Open ROM…**.

## Getting started on a Fedora laptop (Workstation/KDE/Spin)

1. Clone the repository as shown above, or extract a source archive. The setup commands run inside the `Retroserv` folder.
2. Open a terminal in that folder and run:

```bash
chmod +x ./*.sh scripts/*.sh
./Setup-Fedora.sh --check          # see what the installer will use
./Setup-Fedora.sh                  # on standard Fedora, native install
./Install-Desktop-Shortcut.sh
./Start-Retroserv.sh
```

On standard Fedora this uses `python3`, a **project-local virtual environment**
(`.venv`), and pip. If system Tk/pip are missing it invokes `sudo dnf install -y
python3 python3-pip python3-tkinter` to install the required distro packages.
If those prerequisites are already available, no sudo is needed. The first
install requires internet access for Python packages (Pillow and pytest).

**Do not use `sudo pip` or enable `--break-system-packages`.**

## Bazzite / Silverblue / Kinoite (Fedora Atomic)

The same `./Setup-Fedora.sh` detects `/run/ostree-booted` (or `/run/bootc-booted`)
and selects **Distrobox** instead of layering RPMs on the immutable host.
It requires Distrobox and Podman already installed on the host. If missing,
consult your distribution's Distrobox documentation; setup stops with an error.
It creates/uses container `retroserv-dev` from `registry.fedoraproject.org/fedora-toolbox:44`,
installs Python/pip/Tk there, and installs Retroserv to `.venv-distrobox`
under the project directory.

```bash
./Setup-Fedora.sh --check
./Setup-Fedora.sh
./Install-Desktop-Shortcut.sh
./Start-Retroserv.sh
```

The old `Setup-Bazzite.sh` remains as a compatibility alias which explicitly
selects Distrobox; new users should run `Setup-Fedora.sh`.

### Choosing a mode manually

On Fedora Workstation, the default is **native**. To opt into Distrobox:

```bash
RETROSERV_MODE=distrobox ./Setup-Fedora.sh
```

Or force a native install if you already have a working host Python+Tk setup:

```bash
RETROSERV_MODE=native ./Setup-Fedora.sh
```

Successful setup records your choice in `.retroserv-install-mode` (ignored by
Git and excluded from the release archive); launchers then use that mode.
`RETROSERV_MODE=native|distrobox` can also override the saved choice for a
single launch. Use separate virtual environments to avoid Python ABI conflicts.

## Verify using the included original test ROM

The included `samples/retroserv_test.sfc` is **synthetic nonplayable data**.
Launch the GUI and open it. In Tile / Palette Viewer:

| Setting | Value |
| --- | --- |
| Tile offset | `0x12000` |
| Bits per pixel | `4` |
| Tile count | `64` |
| Columns | `8` |
| Palette offset | `0x13000` |

Click Preview tiles, then try PNG export. None of these operations modifies
source ROMs.

CLI tests after setup:

```bash
./Retroserv-CLI.sh --version
./Retroserv-CLI.sh inspect samples/retroserv_test.sfc
./Retroserv-CLI.sh scan samples/retroserv_test.sfc --bpp 4 --limit 10
./Retroserv-CLI.sh tiles samples/retroserv_test.sfc --offset 0x12000 --bpp 4 --count 64 --columns 8 --palette-offset 0x13000 --output /tmp/retroserv-tiles.png
```

## Super Mario World USA v1.0 (verified SHA-256 only)

The **SMW Graphics** tab discovers the named GFX00–GFX31 groups, uses
bounded LC_LZ2 decompression, and exports decoded BIN files, PNGs and
provenance JSON. Planar previews start at 4×. GFX27 exports raw Mode 7 data.
GFX32 and GFX33 require separate extraction.

Choose **Load .pal / CGRAM…** to import a 768-byte Lunar Magic RGB palette or
a 512-byte SNES CGRAM dump. Enter a starting color index, then select
**Preview** or **Export selected…**. Each planar group uses consecutive
colors from that index. The game scene determines which colors to select.

Only cartridge data with SHA-256
`0838e531fe22c077528febe14cb3ff7c492f1f5fa8de354192bdff7137c27f5b`
(the recognized USA v1.0 ROM) is accepted by this profile. The ROM is never
modified or included in this release.

Launch the GUI and open your SMW ROM, then select **SMW Graphics → Discover GFX**.
Select a file, preview, and export it. Alternatively, via CLI:

```bash
./Retroserv-CLI.sh smw-gfx-list '/path/to/Super Mario World (USA).sfc'
./Retroserv-CLI.sh smw-gfx-export '/path/to/Super Mario World (USA).sfc' \
  --number 0x00 --output-dir "$HOME/Retroserv-Exports"
# After validating one file, optional batch extraction:
./Retroserv-CLI.sh smw-gfx-export '/path/to/Super Mario World (USA).sfc' \
  --all --output-dir "$HOME/Retroserv-Exports-All"
```

Exports include SHA-256, cartridge/file offsets, original SNES address,
LC_LZ2 input consumption and decoded data digest. Imported palettes also
record the file's SHA-256, format and starting color index. For CLI palette
export, pass `--palette /path/to/palette.pal --palette-start 16`.

References (independent published research):
- https://github.com/IsoFrieze/SMWDisX/blob/master/constants.asm
- https://sneslab.net/wiki/LC_LZ2
- https://pipedream.nexus/bank/lm-contract.html
- https://pipedream.nexus/bank/00.html
- https://snescentral.com/article_test.php?id=0000

## Yoshi’s Island 1 level inspection

Open a verified SMW USA v1.0 ROM and go to **SMW Levels**. Choose the
main area ($105) or bonus room ($1CB), then select **Read level**. Scroll the
map and select a marker or a table row to inspect the source record. In
the main area, select **Opening foreground** to see screen $00 drawn from
the ROM's object routines, Map16 definitions, graphics, and palette. Click a
tile to select its last writer in the object table and highlight that object's
visible footprint. **Placement map** switches back to the whole-level overview.

The foreground preview covers the opening screen's 16 by 27 tile area.
It is a static Layer 1 view. Backgrounds, sprites, animation, and other
screens are outside this preview. The opening screen was compared with
Snes9x 1.63 using the verified ROM. All 432 Map16 cells and the foreground
pixels matched the emulator's loaded foreground layer.

**Export level JSON…** saves the two streams' source order, bytes and offsets,
along with the cartridge fingerprint. The JSON keeps SMW-specific records
in the SMW adapter. The GUI, CLI and MCP use the same decoder. This keeps the
format-specific logic separate for future NES importers or integration into
another project.

```bash
./Retroserv-CLI.sh smw-level '/path/to/Super Mario World (USA).sfc' \
  --level 0x105 --output smw-105.json
```

Use `--level 0x1CB` for the bonus room. The MCP tool is `inspect_smw_level`.
See the SMWDisX disassembly for the
[level loader](https://github.com/IsoFrieze/SMWDisX/blob/master/bank_05.asm),
[screen commands](https://github.com/IsoFrieze/SMWDisX/blob/master/bank_0D.asm),
and [sprite loader](https://github.com/IsoFrieze/SMWDisX/blob/master/bank_02.asm).

## Cursor MCP

Run `./Install-MCP.sh`. Copy the full absolute path of
`Run-Retroserv-MCP.sh` into the `command` entry of your Cursor MCP
configuration. More at `docs/CURSOR_MCP.md`.
The MCP server uses the official MCP Python SDK v1 and runs over stdio.

## Supported capabilities

- Read `.sfc` and `.smc` ROMs; identify possible LoROM/HiROM/ExHiROM headers.
- Handle optional 512-byte copier headers and record SHA-256 fingerprints.
- Hex view and export byte ranges without modifying original files.
- Decode 2bpp, 3bpp, 4bpp, 8bpp planar tiles and BGR555 palettes at given offsets.
- Rank potential graphics offsets heuristically; **not automatic asset identification**.
- Find printable ASCII runs; **not generic dialogue/script extraction**.
- GUI, CLI, and optional MCP server.

**Missing:** general-purpose compression scanners (LC_LZ2 exists for verified SMW), game-specific dialogue,
accurate maps and animations, 65816 disassembly/decompilation, automated asset
identification, and building playable SNES cartridges. Other open-source tools
are listed in `docs/OPEN_SOURCE.md` but have not been integrated.

## Testing limits

The recovery build targets Fedora and Bazzite. Native Fedora 44 KDE is
the verified environment. Bazzite and the Distrobox installation route
still require a live test.

Tests: `python -m pytest -q`. Before upgrading an existing install, back up any local modifications.

Only analyze copies of ROMs you have the right to possess and work with.
Exporting data does not authorize distributing another game's copyrighted
assets or code.
