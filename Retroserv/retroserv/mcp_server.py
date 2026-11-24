"""Optional local MCP stdio server (requires mcp>=1.28,<2).

For security, this server is local-only and does not accept network connections.
The tools remain read-only on source ROMs, writing only explicit user exports.
"""
from __future__ import annotations
from .access_paths import require_export_path, require_palette_path, require_rom_path
from .rom import RomImage, parse_offset
from .graphics import scan_graphics
from .textscan import scan_ascii
from .export import graphics_export, binary_export
from .smw import list_gfx, export_gfx
from .palettes import load_palette
from .smw_snapshot import inspect_level

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:
    raise SystemExit('Install MCP integration: python -m pip install -e ".[mcp]"') from exc

mcp = FastMCP('Retroserv')


def _rom(rom_path: str) -> RomImage:
    return RomImage(require_rom_path(rom_path))


@mcp.tool()
def inspect_rom(rom_path: str) -> dict:
    """Inspect and SHA256-hash a local SNES ROM without modifying it."""
    return _rom(rom_path).info()


@mcp.tool()
def find_graphics_candidates(rom_path: str, bpp: int = 4, limit: int = 20) -> dict:
    """Rank raw potential tile regions. Heuristic: NOT verified graphics or sprites."""
    rom = _rom(rom_path)
    return {'candidates':[c.to_dict() for c in scan_graphics(rom.data, bpp=bpp, limit=limit)],
            'warning':'Candidate offsets can refer to code, compressed data, or noise.'}


@mcp.tool()
def find_ascii_strings(rom_path: str, min_length: int = 8, contains: str = '', limit: int = 200) -> dict:
    """Find ASCII strings; cannot decode arbitrary custom SNES script encodings."""
    rom = _rom(rom_path)
    return {'findings':[r.to_dict() for r in scan_ascii(rom.data, min_length, limit, contains)],
            'warning':'Printable runs are not confirmed dialogue scripts.'}


@mcp.tool()
def export_graphics(rom_path: str, output_png: str, offset: str,
                    bpp: int = 4, count: int = 128, columns: int = 16,
                    palette_offset: str = '', transparent_zero: bool = False) -> dict:
    """Export raw 2/3/4/8bpp tile pixels to PNG with provenance JSON; never overwrites."""
    rom = _rom(rom_path)
    p = parse_offset(palette_offset) if palette_offset.strip() else None
    return graphics_export(rom, str(require_export_path(output_png)), parse_offset(offset), bpp, count,
                           columns, p, transparent_zero)


@mcp.tool()
def list_smw_gfx(rom_path: str) -> dict:
    """List GFX00..GFX31 pointers in an exact verified SMW USA v1.0 ROM."""
    rom = _rom(rom_path)
    return {'entries': [e.to_dict() for e in list_gfx(rom)],
            'warning': 'These are documented addresses; decompression/preview is separate.'}


@mcp.tool()
def export_smw_gfx(rom_path: str, number: int, output_dir: str,
                   palette_path: str = '', palette_start: int = 0) -> dict:
    """Extract verified SMW GFX with optional CGRAM or Lunar Magic palette."""
    if palette_start and not palette_path:
        raise ValueError('Palette start requires a palette file')
    palette = load_palette(require_palette_path(palette_path)) if palette_path else None
    return export_gfx(_rom(rom_path), number, str(require_export_path(output_dir)), palette=palette,
                      palette_start=palette_start)


@mcp.tool()
def inspect_smw_level(rom_path: str, level_id: int = 0x105) -> dict:
    """Read a supported SMW room as a game-neutral snapshot. Level $105 includes screens $00 through $02."""
    return inspect_level(_rom(rom_path), level_id).to_dict()


@mcp.tool()
def export_raw_region(rom_path: str, output_file: str, offset: str, length: int) -> dict:
    """Copy a ROM byte region and provenance sidecar; never overwrites."""
    return binary_export(_rom(rom_path), str(require_export_path(output_file)), parse_offset(offset), length)

if __name__ == '__main__':
    mcp.run(transport='stdio')
