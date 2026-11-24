"""Compare Retroserv with the Snes9x memory and frame captured by opening.py."""
from collections import Counter
import sys
from pathlib import Path
from struct import unpack_from
from PIL import Image
from retroserv.graphics import decode_tile, read_palette
from retroserv.rom import RomImage
from retroserv.smw_foreground import render_opening_foreground, _map16_words

d = Path.cwd()
rom = RomImage(sys.argv[1])
r = render_opening_foreground(rom)
w = (d/'opening4.wram').read_bytes()
v = (d/'opening4.vram').read_bytes()
palette = read_palette((d/'opening4.cgram').read_bytes(), 256)
defs = _map16_words(rom, 7)
sc_base, hscroll, vscroll, bg_size, char_base, sc_size = unpack_from('<6H', (d/'opening4.bg').read_bytes())
assert (sc_base, hscroll, vscroll, bg_size, char_base, sc_size) == (0x2000, 0, 192, 0, 0, 3)
reference = Image.new('RGBA', (256, 432))
map_diffs, word_diffs = [], []
for y in range(27):
    for x in range(16):
        p = 0xC800 + y*16 + x
        map_id = w[p] + 256*w[p+0x10000]
        if map_id != (r.tiles[x, y].map16_id if (x, y) in r.tiles else 0x025):
            map_diffs.append((x,y,map_id))
        for i in range(4):
            tx, ty = x*2+i//2, y*2+i%2
            # The game uploads tile rows around the camera to a circular tilemap.
            # For off-camera rows, use the verified WRAM tile ID to look up its character.
            word = defs[map_id][i]
            if vscroll <= ty*8 < vscroll + 224:
                ppu_address = sc_base + (ty // 32)*0x800 + (ty % 32)*32 + tx
                actual_word = unpack_from('<H', v, 2*ppu_address)[0]
                if actual_word != word:
                    word_diffs.append((tx, ty, hex(actual_word), hex(word)))
                word = actual_word
            char = word & 0x3FF
            pattern = v[32*char:32*(char+1)]
            pixels = decode_tile(pattern, 4)
            row = ((word >> 10) & 7) * 16
            for py in range(8):
                for px in range(8):
                    a = pixels[(7-py if word & 0x8000 else py)*8 + (7-px if word & 0x4000 else px)]
                    if a:
                        reference.putpixel((tx*8+px, ty*8+py), (*palette[row+a], 255))
screen = r.image.crop((0, 0, 256, r.image.height))
pixels = screen.tobytes()
expected = reference.tobytes()
pixel_diffs = [(i // 4 % 256, i // 4 // 256) for i in range(0, len(pixels), 4)
               if pixels[i:i+4] != expected[i:i+4]]
print('Map16 ID diffs:',len(map_diffs),map_diffs[:10])
print('Visible character word diffs:',len(word_diffs),word_diffs[:15])
print('RGBA diffs:',len(pixel_diffs),pixel_diffs[:12])
reference.save(d/'reference.png')
shot = Image.open(d/'opening4.ppm').convert('RGB')
comparison = Counter()
for y in range(224):
    for x in range(256):
        rgba=r.image.getpixel((x,y+vscroll+1))
        if rgba[3]:
            comparison[max(abs(a-b) for a, b in zip(rgba[:3], shot.getpixel((x,y)))) <= 2] += 1
print('Visible opaque pixels matching composite screenshot within two RGB levels (sprite overlap included):',comparison)
assert not map_diffs and not word_diffs and not pixel_diffs
