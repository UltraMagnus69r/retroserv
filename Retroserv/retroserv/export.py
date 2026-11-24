"""Non-destructive, provenance-aware data exports."""
from __future__ import annotations
from pathlib import Path
import json
from .rom import RomImage
from .graphics import render_tiles, read_palette


def save_json(path: Path, data: dict | list, overwrite: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = 'w' if overwrite else 'x'
    with path.open(mode, encoding='utf-8') as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
        out.write('\n')


def graphics_export(rom: RomImage, output: str | Path, offset: int, bpp: int,
                    count: int, columns: int = 16, palette_offset: int | None = None,
                    transparent_zero: bool = False, overwrite: bool = False) -> dict:
    output = Path(output).resolve()
    if output == rom.path:
        raise ValueError('Refusing to overwrite source ROM')
    if output.suffix.lower() != '.png':
        raise ValueError('Graphics export requires a .png output path')
    sidecar = output.with_suffix('.retroserv.json')
    if not overwrite and (output.exists() or sidecar.exists()):
        raise FileExistsError('Export or provenance sidecar already exists; use --overwrite explicitly')
    palette = None
    if palette_offset is not None:
        palette = read_palette(rom.slice(palette_offset, 2 * (1 << bpp)), 1 << bpp)
    image = render_tiles(rom.data, offset, bpp, count, columns, palette, transparent_zero)
    provenance = {
        'format': 'retroserv-extraction-v1', 'type': 'raw_snes_planar_tiles',
        'verified_game_asset': False,
        'source_name': rom.path.name,
        'source_sha256': rom.info()['sha256_original_file'],
        'cartridge_sha256': rom.info()['sha256_cartridge_data'],
        'data_offset_hex': f'0x{offset:X}',
        'raw_file_offset_hex': f'0x{offset + rom.copier_header_size:X}',
        'data_length': count * 8 * bpp,
        'bpp': bpp, 'tile_count': count, 'columns': columns,
        'palette_data_offset_hex': f'0x{palette_offset:X}' if palette_offset is not None else None,
        'palette': 'ROM BGR555' if palette_offset is not None else 'synthetic grayscale',
        'transparent_index_0': transparent_zero,
        'output_file': output.name,
        'notice': 'A decoded PNG does not by itself establish that this ROM range contains graphics.'
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format='PNG')
    save_json(sidecar, provenance, overwrite=True)
    return {'png': str(output), 'sidecar': str(sidecar), 'image_size': list(image.size)}


def binary_export(rom: RomImage, output: str | Path, offset: int, length: int,
                  overwrite: bool = False) -> dict:
    output = Path(output).resolve()
    if output == rom.path:
        raise ValueError('Refusing to overwrite source ROM, even with --overwrite')
    sidecar = Path(str(output) + '.retroserv.json')
    if not overwrite and (output.exists() or sidecar.exists()):
        raise FileExistsError('Output exists; use --overwrite explicitly')
    content = rom.slice(offset, length)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    info = {
        'format': 'retroserv-extraction-v1', 'type': 'raw_binary_slice',
        'source_name': rom.path.name, 'source_sha256': rom.info()['sha256_original_file'],
        'data_offset_hex': f'0x{offset:X}',
        'raw_file_offset_hex': f'0x{offset + rom.copier_header_size:X}',
        'data_length': length, 'output_file': output.name,
        'notice': 'Raw bytes are not automatically identified as code, scripts, or assets.'
    }
    save_json(sidecar, info, overwrite=True)
    return {'binary': str(output), 'sidecar': str(sidecar), 'data_length': length}
