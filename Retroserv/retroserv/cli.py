"""Command-line entry points. Works via `python -m retroserv ...`."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from . import __version__
from .palettes import load_palette
from .smw_snapshot import inspect_level
from .rom import RomImage, RomError, parse_offset
from .graphics import scan_graphics
from .textscan import scan_ascii, hex_dump
from .export import graphics_export, binary_export, save_json
from .smw import list_gfx, export_gfx, recognized, gfx_bpp


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='retroserv', description='Retroserv: read-only SNES ROM preservation and extraction tools')
    p.add_argument('--version', action='version', version=f'Retroserv {__version__}')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('gui', help='Start the graphical ROM workbench')
    sub.add_parser('demo', help='Generate original, NONPLAYABLE, synthetic test data').add_argument('output')
    inspect = sub.add_parser('inspect', help='Identify ROM and print a JSON inspection report')
    inspect.add_argument('rom')
    inspect.add_argument('--output', help='Write JSON report to file')
    strings = sub.add_parser('strings', help='Search for printable ASCII runs (not script decoding)')
    strings.add_argument('rom')
    strings.add_argument('--min-length', type=int, default=8)
    strings.add_argument('--contains', default='')
    strings.add_argument('--limit', type=int, default=200)
    strings.add_argument('--output')
    scan = sub.add_parser('scan', help='Heuristically rank possible raw tile offsets')
    scan.add_argument('rom')
    scan.add_argument('--bpp', type=int, choices=(2,3,4,8), default=4)
    scan.add_argument('--step', type=int, default=512)
    scan.add_argument('--sample-tiles', type=int, default=16)
    scan.add_argument('--limit', type=int, default=20)
    scan.add_argument('--output')
    tiles = sub.add_parser('tiles', help='Render raw SNES planar tiles as a PNG')
    tiles.add_argument('rom')
    tiles.add_argument('--offset', required=True, type=parse_offset,
                       help='Data offset, e.g. 0x12000 (hex) or 73728 (decimal)')
    tiles.add_argument('--bpp', type=int, choices=(2,3,4,8), required=True)
    tiles.add_argument('--count', type=int, default=128)
    tiles.add_argument('--columns', type=int, default=16)
    tiles.add_argument('--palette-offset', type=parse_offset)
    tiles.add_argument('--transparent-zero', action='store_true')
    tiles.add_argument('--output', required=True)
    tiles.add_argument('--overwrite', action='store_true')
    cut = sub.add_parser('extract', help='Copy a raw data range with provenance JSON')
    cut.add_argument('rom')
    cut.add_argument('--offset', required=True, type=parse_offset)
    cut.add_argument('--length', required=True, type=parse_offset)
    cut.add_argument('--output', required=True)
    cut.add_argument('--overwrite', action='store_true')
    smw_list = sub.add_parser('smw-gfx-list', help='List GFX00..GFX31 pointers in verified SMW USA v1.0 ROM')
    smw_list.add_argument('rom')
    smw_list.add_argument('--output', help='Write a JSON list of documented GFX pointers')
    smw_out = sub.add_parser('smw-gfx-export', help='Decompress and export verified SMW GFX tiles')
    smw_out.add_argument('rom')
    choice = smw_out.add_mutually_exclusive_group(required=True)
    choice.add_argument('--number', type=parse_offset, help='GFX index: $0F, 0x0F or decimal 15')
    choice.add_argument('--all', action='store_true', help='Attempt all 50 documented GFX files')
    smw_out.add_argument('--output-dir', required=True)
    smw_out.add_argument('--palette', help='512-byte CGRAM or 768-byte Lunar Magic palette')
    smw_out.add_argument('--palette-start', type=parse_offset, default=0, help='Starting color index')
    smw_out.add_argument('--overwrite', action='store_true')
    level = sub.add_parser('smw-level', help='Inspect a supported SMW room as a game-neutral snapshot')
    level.add_argument('rom')
    level.add_argument('--level', type=parse_offset, default=0x105,
                       help='Horizontal SMW level number, $000 through $1FF')
    level.add_argument('--output', help='Write a new level JSON file')
    view = sub.add_parser('hex', help='View bytes from a cartridge data offset')
    view.add_argument('rom')
    view.add_argument('--offset', type=parse_offset, default=0)
    view.add_argument('--length', type=int, default=256)
    return p


def output_report(data: object, filename: str | None = None):
    if filename:
        save_json(Path(filename), data)
        print(f'Saved {filename}')
    else:
        print(json.dumps(data, indent=2))


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == 'gui':
            from .gui import launch
            launch()
            return 0
        if args.command == 'demo':
            from .demo import create_demo
            create_demo(args.output)
            print(f'Created synthetic nonplayable ROM: {args.output}')
            return 0
        rom = RomImage(args.rom)
        if args.command == 'inspect':
            output_report(rom.info(), args.output)
        elif args.command == 'strings':
            rows = [r.to_dict() for r in scan_ascii(rom.data, args.min_length, args.limit, args.contains)]
            output_report({'source_sha256':rom.info()['sha256_original_file'], 'findings':rows,
                           'warning':'ASCII runs may be incidental binary data, not dialogue.'}, args.output)
        elif args.command == 'scan':
            rows = [r.to_dict() for r in scan_graphics(rom.data, args.bpp, args.step,
                                                       args.sample_tiles, args.limit)]
            output_report({'bpp':args.bpp, 'candidates':rows,
                           'warning':'Heuristic rankings only; no graphics identity guaranteed.'}, args.output)
        elif args.command == 'smw-level':
            output_report(inspect_level(rom, args.level).to_dict(), args.output)
        elif args.command == 'smw-gfx-list':
            rows = [entry.to_dict() for entry in list_gfx(rom)]
            output_report({'profile': 'SMW USA v1.0', 'verified': recognized(rom),
                           'entries': rows, 'notes': 'GFX32 and GFX33 require separate handling.'}, args.output)
        elif args.command == 'smw-gfx-export':
            numbers = range(0x32) if args.all else [args.number]
            palette = load_palette(args.palette) if args.palette else None
            if not palette and args.palette_start:
                raise ValueError('--palette-start requires --palette')
            if palette:
                palette.group(args.palette_start, 3 if args.all else (gfx_bpp(args.number)[0] or 3))
            results, errors = [], []
            for num in numbers:
                try:
                    results.append(export_gfx(rom, num, args.output_dir, overwrite=args.overwrite,
                                              palette=palette, palette_start=args.palette_start))
                except (ValueError, OSError) as exc:
                    if not args.all:
                        raise
                    errors.append({'gfx_number': num, 'error': str(exc)})
            output_report({'results': results, 'errors': errors,
                           'note': 'PNG colors use the imported palette.' if palette else 'PNG uses synthetic grayscale.'})
            return 2 if errors else 0
        elif args.command == 'tiles':
            result = graphics_export(rom, args.output, args.offset, args.bpp, args.count,
                                     args.columns, args.palette_offset, args.transparent_zero, args.overwrite)
            output_report(result)
        elif args.command == 'extract':
            output_report(binary_export(rom, args.output, args.offset, args.length, args.overwrite))
        elif args.command == 'hex':
            print(hex_dump(rom.data, args.offset, args.length))
        return 0
    except (ValueError, RomError, OSError, ImportError) as exc:
        print(f'Retroserv error: {exc}', file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
