"""Read-only extraction of documented vanilla Super Mario World (USA v1.0) GFX.

Only the exact published 512-KiB cartridge-data SHA-256 is accepted. This is
NOT a general ROM hacking/reconstruction engine, and does not reconstruct the
correct in-game color palettes. It never modifies a ROM.

GFX pointer tables: $00B992/$00B9C4/$00B9F6 (parallel arrays, GFX00-31).
Sources: https://pipedream.nexus/bank/lm-contract.html
         https://pipedream.nexus/bank/00.html
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
from PIL import Image
from .rom import RomImage
from .lc_lz2 import decompress, LZ2Error, LZ2Result
from .graphics import render_tiles
from .export import save_json
from .palettes import ImportedPalette

SMW_USA_V10_SHA256 = '0838e531fe22c077528febe14cb3ff7c492f1f5fa8de354192bdff7137c27f5b'
SMW_USA_V10_CRC32 = 'B19ED489'
SMW_GFX_COUNT = 0x32   # GFX00..GFX31 (GFX32/33 stored separately)
TABLE_LOW = 0x00B992
TABLE_HIGH = 0x00B9C4
TABLE_BANK = 0x00B9F6

# Graphics file IDs in https://github.com/IsoFrieze/SMWDisX/blob/master/constants.asm
GFX_GROUPS = (
    'Powerups', 'Koopa and Goomba', 'Spiny and Lakitu', 'Thwomp and Magikoopa',
    'Buzzy Beetle and Blargg', 'Chainsaw', 'Urchin and Dolphin', 'Ghost House',
    "Yoshi's House", 'Sumo Bro and Pokey', 'Wendy and Lemmy', 'Roy, Morton and Ludwig',
    'Underground', 'Princess Peach', 'Ninji and Disco Shell', 'Mario Start',
    'Overworld sprites', 'Big Boo and Eerie', 'Dry Bones and Grinder', 'Hammer Bro and Chuck',
    'Overworld animation', 'Grass tiles', 'Rope tiles', 'Diagonal pipe',
    'Castle tiles', 'Forest and hill backgrounds', 'Cave tiles', 'Castle pillar background',
    'Overworld tiles 1', 'Overworld tiles 2', 'Overworld level icons', 'Forest tiles',
    'Rex and Mega Mole', 'Bowser', 'Boss background', 'Dino Rhino',
    'Mechakoopa', 'Iggy, Larry and Reznor', 'Credits Yoshi', 'Iggy and Reznor platform',
    'HUD tiles', 'Title screen', 'Message tiles', 'Castle destruction',
    'Cutscene tiles', 'Cutscene sprites', 'Thank You', 'Credits lettering',
    'The End', 'Special enemies',
)


def lorom_to_pc(snes_address: int) -> int:
    bank, addr = (snes_address >> 16) & 255, snes_address & 0xFFFF
    if addr < 0x8000 or bank in (0x7E, 0x7F):
        raise ValueError(f'Not a LoROM ROM address: ${snes_address:06X}')
    return ((bank & 0x7F) << 15) | (addr & 0x7FFF)


def recognized(rom: RomImage) -> bool:
    return (len(rom.data) == 524288 and
            sha256(rom.data).hexdigest() == SMW_USA_V10_SHA256)


def require_smw(rom: RomImage):
    if not recognized(rom):
        raise ValueError('SMW GFX extractor requires the exact headerless cartridge SHA-256 '
                         f'{SMW_USA_V10_SHA256} (USA v1.0). Other versions/hacks are not yet supported.')


@dataclass(frozen=True)
class GfxEntry:
    number: int
    snes_address: int
    data_offset: int
    bpp: int | None
    note: str

    def to_dict(self) -> dict:
        return {'number': self.number, 'name': f'GFX{self.number:02X}',
                'snes_address': f'${self.snes_address:06X}',
                'rom_data_offset': f'0x{self.data_offset:X}',
                'bpp': self.bpp, 'group': GFX_GROUPS[self.number], 'note': self.note}


def gfx_bpp(number: int) -> tuple[int | None, str]:
    if number == 0x27:
        return None, 'Mode 7 graphics; 8bpp linear format not yet rendered'
    if number in (0x28, 0x29, 0x2A, 0x2B, 0x2F):
        return 2, 'Layer 3 (2bpp)'
    return 3, 'Native 3bpp tiles; grayscale preview is not the game palette'


def gfx_entry(rom: RomImage, number: int, *, enforce_identity: bool = True) -> GfxEntry:
    if enforce_identity:
        require_smw(rom)
    if not 0 <= number < SMW_GFX_COUNT:
        raise ValueError('SMW GFX number must be 0x00..0x31; GFX32/33 use separate structures')
    data = rom.data
    lo = data[lorom_to_pc(TABLE_LOW) + number]
    hi = data[lorom_to_pc(TABLE_HIGH) + number]
    bank = data[lorom_to_pc(TABLE_BANK) + number]
    address = (bank << 16) | (hi << 8) | lo
    offset = lorom_to_pc(address)
    if offset >= len(data):
        raise ValueError(f'GFX{number:02X} points outside cartridge data: ${address:06X}')
    bpp, note = gfx_bpp(number)
    return GfxEntry(number, address, offset, bpp, note)


def list_gfx(rom: RomImage, *, enforce_identity: bool = True) -> list[GfxEntry]:
    if enforce_identity:
        require_smw(rom)
    return [gfx_entry(rom, number, enforce_identity=False) for number in range(SMW_GFX_COUNT)]


def decoded_gfx(rom: RomImage, number: int, *, enforce_identity: bool = True) -> tuple[GfxEntry, LZ2Result]:
    entry = gfx_entry(rom, number, enforce_identity=enforce_identity)
    result = decompress(rom.data, entry.data_offset, max_output=262144,
                        max_input=min(262144, len(rom.data) - entry.data_offset))
    return entry, result


def gfx_preview(entry: GfxEntry, result: LZ2Result, *, columns: int = 16,
                palette: ImportedPalette | None = None, palette_start: int = 0) -> Image.Image:
    if entry.bpp is None:
        raise ValueError(f'GFX{entry.number:02X} is Mode 7 and has no tile renderer in this release')
    tile_bytes = entry.bpp * 8
    tile_count = len(result.data) // tile_bytes
    if not (1 <= tile_count <= 8192):
        raise ValueError('No complete planar tiles or too many tiles')
    colors = palette.group(palette_start, entry.bpp) if palette is not None else None
    return render_tiles(result.data, 0, entry.bpp, tile_count, columns, colors, transparent_zero=True)


def export_gfx(rom: RomImage, number: int, output_dir: str | Path, *, overwrite: bool = False,
               enforce_identity: bool = True, palette: ImportedPalette | None = None,
               palette_start: int = 0) -> dict:
    entry, result = decoded_gfx(rom, number, enforce_identity=enforce_identity)
    folder = Path(output_dir).resolve()
    if folder == rom.path:
        raise ValueError('Refusing to overwrite input ROM')
    basename = f'GFX{entry.number:02X}'
    binary = folder / f'{basename}.bin'
    png = folder / f'{basename}.png' if entry.bpp is not None else None
    metadata = folder / f'{basename}.retroserv.json'
    paths = [binary, metadata] + ([png] if png is not None else [])
    if any(path == rom.path for path in paths):
        raise ValueError('Refusing to overwrite input ROM')
    if not overwrite and any(path.exists() for path in paths):
        raise FileExistsError(f'{basename} output exists; pass --overwrite explicitly')
    # Validate rendering before writing anything.
    image = gfx_preview(entry, result, palette=palette, palette_start=palette_start) if png else None
    palette_details = None
    if png:
        palette_details = 'synthetic grayscale; original in-game colors NOT reconstructed'
        if palette is not None:
            palette_details = {'file': palette.name, 'format': palette.format,
                               'sha256': palette.sha256, 'start_index': palette_start}
    folder.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(result.data)
    if image and png:
        image.save(png)
    manifest = {
        'format': 'retroserv-smw-gfx-v1', 'profile': 'Super Mario World USA v1.0',
        'game_version_verified_by_sha256': bool(enforce_identity),
        'source_filename': rom.path.name,
        'source_cartridge_sha256': sha256(rom.data).hexdigest(),
        'source_rom_offset_hex': f'0x{entry.data_offset:X}',
        'source_file_offset_hex': f'0x{entry.data_offset + rom.copier_header_size:X}',
        'source_snes_address': f'${entry.snes_address:06X}',
        'compressed_bytes_including_terminator': result.consumed,
        'decompressed_bytes': len(result.data),
        'decompressed_sha256': sha256(result.data).hexdigest(),
        'decompressor': 'LC_LZ2', 'commands': result.commands,
        'gfx_number': number, 'bpp': entry.bpp,
        'tile_count': len(result.data) // (8 * entry.bpp) if entry.bpp else None,
        'palette': palette_details,
        'exported_files': [p.name for p in paths], 'warning': entry.note,
        'notice': 'For private preservation/research. This tool does not grant rights to redistribute game assets.'
    }
    save_json(metadata, manifest, overwrite=True)
    return {'name': basename, 'binary': str(binary), 'png': str(png) if png else None,
            'manifest': str(metadata), 'compressed_bytes': result.consumed,
            'decompressed_bytes': len(result.data)}
