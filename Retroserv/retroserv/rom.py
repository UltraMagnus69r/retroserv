"""SNES image loading, hashing, and conservative header identification.

ROM images are never modified. SNES internal header locations and fields follow
https://snes.nesdev.org/wiki/ROM_header .
"""
from __future__ import annotations
from . import __version__

from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
from typing import Any
import zlib

MAX_ROM_BYTES = 64 * 1024 * 1024
HEADER_LOCATIONS = (("LoROM", 0x7FC0, 0), ("HiROM", 0xFFC0, 1),
                    ("ExHiROM", 0x40FFC0, 5))


class RomError(ValueError):
    """Invalid, unreadable, or unsupported input."""


def parse_offset(value: str | int) -> int:
    """Parse offsets: 0x12000, $12000, 12000 (decimal), 12000h (hex)."""
    if isinstance(value, int):
        result = value
    else:
        raw = value.strip().replace('_', '')
        if not raw:
            raise ValueError("Empty offset")
        if raw.startswith('$'):
            result = int(raw[1:], 16)
        elif raw.lower().endswith('h'):
            result = int(raw[:-1], 16)
        else:
            result = int(raw, 0) if raw.lower().startswith(('0x', '0o', '0b')) else int(raw, 10)
    if result < 0:
        raise ValueError("Offsets cannot be negative")
    return result


@dataclass(frozen=True)
class HeaderCandidate:
    mapping: str
    file_offset: int
    score: int
    title: str
    map_byte: int
    cartridge_type: int
    rom_size_code: int
    ram_size_code: int
    region_code: int
    maker_code: int
    revision: int
    checksum: int
    complement: int
    checksum_pair_valid: bool
    reset_vector: int
    plausible_title: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _candidate(blob: bytes, location: tuple[str, int, int], copier: int) -> HeaderCandidate | None:
    name, at, map_kind = location
    pos = at + copier
    if len(blob) < pos + 0x40:
        return None
    raw_title = blob[pos:pos + 21]
    printable = sum(32 <= b < 127 for b in raw_title)
    title_ok = printable >= 17
    title = ''.join(chr(b) if 32 <= b < 127 else '?' for b in raw_title).strip()
    mode, cart, romsz, ramsz, region, maker, rev = blob[pos + 0x15:pos + 0x1c]
    complement = int.from_bytes(blob[pos + 0x1c:pos + 0x1e], 'little')
    checksum = int.from_bytes(blob[pos + 0x1e:pos + 0x20], 'little')
    pair_ok = checksum + complement == 0xffff and (checksum != 0 or complement != 0xffff)
    reset = int.from_bytes(blob[pos + 0x3c:pos + 0x3e], 'little')
    mode_ok = (mode & 0x0f) == map_kind and (mode & 0xe0) in (0x20, 0x30)
    score = 0
    score += 6 if pair_ok else -2
    score += 5 if mode_ok else -3
    score += 4 if title_ok else -3
    score += 2 if reset >= 0x8000 else -3
    score += 1 if 7 <= romsz <= 16 else -1
    score += 1 if ramsz <= 9 else -1
    score += 1 if region <= 20 else -1
    if mode_ok and reset >= 0x8000:
        if name == 'LoROM':
            boot_pos = ((reset & 0x7fff) + copier)
        elif name == 'HiROM':
            boot_pos = (reset + copier)
        else:
            boot_pos = 0x400000 + reset + copier
        if boot_pos < len(blob):
            op = blob[boot_pos]
            if op in (0x78, 0x18, 0x38, 0x9c, 0x4c, 0x5c):
                score += 2
            elif op in (0x00, 0x02, 0xdb, 0x42):
                score -= 2
    return HeaderCandidate(name, pos, score, title, mode, cart, romsz, ramsz,
                           region, maker, rev, checksum, complement, pair_ok,
                           reset, title_ok)


class RomImage:
    """In-memory immutable ROM input; all offsets used by tools are *data* offsets.

    Data offsets exclude an optional 512-byte copier header; we also report raw
    file offsets in sidecars for forensics.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        try:
            size = self.path.stat().st_size
        except OSError as exc:
            raise RomError(f"Cannot read ROM: {exc}") from exc
        if size < 0x8000:
            raise RomError("File too small for an ordinary SNES ROM (minimum 32 KiB)")
        if size > MAX_ROM_BYTES:
            raise RomError(f"ROM exceeds safety limit of {MAX_ROM_BYTES} bytes")
        try:
            self.raw = self.path.read_bytes()
        except OSError as exc:
            raise RomError(f"Cannot read ROM: {exc}") from exc
        guesses = []
        possible_copiers = [0, 512]
        if size % 1024 == 512:
            possible_copiers = [512, 0]
        for copier in possible_copiers:
            for loc in HEADER_LOCATIONS:
                obj = _candidate(self.raw, loc, copier)
                if obj:
                    guesses.append((obj, copier))
        if guesses:
            guesses.sort(key=lambda pair: (pair[0].score, pair[0].checksum_pair_valid,
                                           pair[1] == (512 if size % 1024 == 512 else 0)), reverse=True)
            candidate, header_bytes = guesses[0]
            # If no candidate is compelling, only use filesize heuristic.
            self.header = candidate if candidate.score >= 8 else None
            self.copier_header_size = header_bytes if self.header else (512 if size % 1024 == 512 else 0)
            self.header_candidates = [c for c, _ in guesses]
        else:
            self.header = None
            self.copier_header_size = 512 if size % 1024 == 512 else 0
            self.header_candidates = []
        self.data = self.raw[self.copier_header_size:]

    def slice(self, offset: int, length: int) -> bytes:
        if offset < 0 or length <= 0 or length > 16 * 1024 * 1024:
            raise ValueError("Offset must be nonnegative and length 1..16 MiB")
        if offset + length > len(self.data):
            raise ValueError(f"Requested data range 0x{offset:X}..0x{offset+length:X} exceeds ROM size 0x{len(self.data):X}")
        return self.data[offset:offset + length]

    def info(self) -> dict[str, Any]:
        return {
            'tool': f'Retroserv {__version__}',
            'source_file': self.path.name,
            'size_bytes': len(self.raw),
            'data_bytes': len(self.data),
            'copier_header_bytes': self.copier_header_size,
            'sha256_original_file': sha256(self.raw).hexdigest(),
            'sha256_cartridge_data': sha256(self.data).hexdigest(),
            'crc32_cartridge_data': f'{zlib.crc32(self.data):08X}',
            'internal_header': self.header.to_dict() if self.header else None,
            'header_confidence': ('probable' if self.header and self.header.score >= 16
                                  else 'tentative' if self.header else 'not identified'),
            'notes': [
                'Internal header detection is heuristic, not cartridge authentication.',
                'Checksum pair validity does not establish complete ROM integrity.',
                'All data offsets exclude any 512-byte copier header.'
            ],
        }
