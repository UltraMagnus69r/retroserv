"""Build a synthetic 256KiB LoROM-shaped fixture. NOT an executable game.

All text, shapes, and generated data here are original. The test ROM is useful to
exercise the inspector/decoder without shipping any third-party game content.
"""
from __future__ import annotations
from pathlib import Path

DEMO_TILE_OFFSET = 0x12000
DEMO_PALETTE_OFFSET = 0x13000
DEMO_TEXT_OFFSET = 0x14000


def _encode_4bpp(pixels):
    output = bytearray(32)
    for y in range(8):
        for x in range(8):
            c = pixels[y][x]
            for pair in range(2):
                for part in (0, 1):
                    plane = pair*2 + part
                    if (c >> plane) & 1:
                        output[pair*16 + y*2 + part] |= (1 << (7-x))
    return bytes(output)


def create_demo(filename: str | Path):
    output = Path(filename)
    if output.exists():
        raise FileExistsError(f'Will not overwrite existing file: {output}')
    raw = bytearray([0xff]) * (256 * 1024)
    # The boot location is filled with a 65816 SEI instruction for header scoring;
    # this file deliberately DOES NOT contain a functional SNES program.
    raw[0] = 0x78
    title = b'RETROSERV TEST DATA  '
    assert len(title) == 21
    pos = 0x7fc0
    raw[pos:pos+21] = title
    raw[pos+0x15:pos+0x1c] = bytes([0x20, 0x00, 0x08, 0x00, 0x01, 0x00, 0x00])
    raw[pos+0x3c:pos+0x3e] = (0x8000).to_bytes(2, 'little')
    for n in range(64):
        pixels = [[0]*8 for _ in range(8)]
        for y in range(8):
            for x in range(8):
                # Original geometric patterns in a sparse grid.
                if x in (0,7) or y in (0,7):
                    pixels[y][x] = (n % 6) + 1
                elif ((x+y+n) % 5) == 0:
                    pixels[y][x] = ((n//3) % 6) + 8
                else:
                    pixels[y][x] = (n % 4) + 2
        start = DEMO_TILE_OFFSET + n*32
        raw[start:start+32] = _encode_4bpp(pixels)
    values = [0x0000, 0x001f, 0x03e0, 0x7c00, 0x03ff, 0x7fe0, 0x7c1f, 0x7fff,
              0x4210, 0x14a5, 0x28aa, 0x39ce, 0x56b5, 0x6318, 0x421f, 0x0210]
    for i, value in enumerate(values):
        raw[DEMO_PALETTE_OFFSET+i*2:DEMO_PALETTE_OFFSET+i*2+2] = value.to_bytes(2, 'little')
    msg = b'RETROSERV ORIGINAL SAMPLE TEXT FOR SCANNER TESTING\x00'
    raw[DEMO_TEXT_OFFSET:DEMO_TEXT_OFFSET+len(msg)] = msg
    # Checksum field pair follows the standard SNES complement relationship.
    raw[pos+0x1c:pos+0x1e] = b'\xff\xff'
    raw[pos+0x1e:pos+0x20] = b'\x00\x00'
    checksum = sum(raw) & 0xffff
    raw[pos+0x1c:pos+0x1e] = (checksum ^ 0xffff).to_bytes(2, 'little')
    raw[pos+0x1e:pos+0x20] = checksum.to_bytes(2, 'little')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    return output

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('output')
    args = ap.parse_args()
    create_demo(args.output)
