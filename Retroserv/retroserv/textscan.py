"""Conservative printable-ASCII run discovery (not a dialogue script decompiler)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class TextRun:
    offset: int
    text: str

    def to_dict(self):
        return {'offset': self.offset, 'offset_hex': f'0x{self.offset:06X}', 'text': self.text}


def scan_ascii(data: bytes, min_length: int = 8, limit: int = 2000,
               contains: str = '') -> list[TextRun]:
    if not 3 <= min_length <= 256 or not 1 <= limit <= 100000:
        raise ValueError('Invalid minimum length or limit')
    findings: list[TextRun] = []
    start = None
    for i in range(len(data) + 1):
        printable = i < len(data) and 32 <= data[i] <= 126
        if printable:
            if start is None:
                start = i
        elif start is not None:
            if i - start >= min_length:
                snippet = data[start:i].decode('ascii')
                if not contains or contains.casefold() in snippet.casefold():
                    findings.append(TextRun(start, snippet))
                    if len(findings) >= limit:
                        break
            start = None
    return findings


def hex_dump(data: bytes, offset: int, length: int = 256) -> str:
    if offset < 0 or length < 1 or length > 65536 or offset > len(data):
        raise ValueError('Invalid hexadecimal viewer request')
    blob = data[offset:offset + length]
    lines = []
    for i in range(0, len(blob), 16):
        chunk = blob[i:i+16]
        hexes = ' '.join(f'{c:02X}' for c in chunk)
        ascii_part = ''.join(chr(c) if 32 <= c <= 126 else '.' for c in chunk)
        lines.append(f'{offset+i:08X}  {hexes:<47}  |{ascii_part}|')
    return '\n'.join(lines)
