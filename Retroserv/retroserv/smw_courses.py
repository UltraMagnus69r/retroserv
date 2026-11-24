"""Course names stored in the USA overworld, plus the rooms a course opens.

The cartridge has no ASCII title list. Each overworld level tile is numbered in
scan order ($04D7F2), and that number picks a three-part string ($04A0FC into
$049AC5). Tiles $56–$80 are the courses. A tile on the submap half ($400 and
up) loads a level in the $100 bank ($05D8A2). A screen exit keeps that bank.
"""
from __future__ import annotations

from collections import deque

from .smw import lorom_to_pc
from .smw_level import LAYER1_POINTERS, level_catalog, read_level

TILEMAP = 0x0CF7DF
NAME_WORDS = 0x04A0FC
NAME_STRINGS = 0x049AC5
PART_A = 0x049C91
PART_B = 0x049CCF
PART_C = 0x049CED
_ILLUSION = (0x32, 0x33, 0x34, 0x35, 0x36, 0x37)
_YELLOW = (0x38, 0x39, 0x3A, 0x3B, 0x3C)


def room_titles(rom) -> dict[str, str]:
    """Catalog room key -> name. Courses come from the overworld. Exits extend them."""
    pointers = _catalog_pointers(rom)
    titles: dict[str, str] = {}
    roots: dict[int, str] = {}
    for level_id, name in _overworld_courses(rom).items():
        key = pointers.get(_layer1_pointer(rom, level_id))
        if key is None:
            continue
        # Several level numbers can share one level. The number the room list uses keeps its own name.
        if key in roots and level_id != key:
            continue
        titles[str(key)] = name
        roots[key] = name
    named = set(roots)
    pending: deque[tuple[int, str]] = deque(roots.items())
    opened = {name: 0 for name in set(roots.values())}
    while pending:
        key, root = pending.popleft()
        try:
            level = read_level(rom, key)
        except ValueError:
            continue
        destinations = []
        for dest in _exit_levels(level):
            dest_key = pointers.get(_layer1_pointer(rom, dest))
            if dest_key is None or dest_key in named or dest_key in destinations:
                continue
            destinations.append(dest_key)
        for dest_key in destinations:
            opened[root] += 1
            count = opened[root]
            titles[str(dest_key)] = f'{root} bonus room' if count == 1 else f'{root} room {count}'
            named.add(dest_key)
            pending.append((dest_key, root))
    return titles


def _overworld_courses(rom) -> dict[int, str]:
    tilemap = _read(rom, TILEMAP, 0x800)
    words = _words(_read(rom, NAME_WORDS, 0xC0))
    part_a = _words(_read(rom, PART_A, PART_B - PART_A))
    part_b = _words(_read(rom, PART_B, PART_C - PART_B))
    part_c = _words(_read(rom, PART_C, 0x1A))
    strings = _read(rom, NAME_STRINGS, 0x400)
    courses = {}
    translevel = 1
    for index, tile in enumerate(tilemap):
        if not 0x56 <= tile <= 0x80:
            continue
        word = words[translevel] if translevel < len(words) else 0
        low_byte = translevel if translevel < 0x25 else translevel - 0x24
        level_id = low_byte | (0x100 if index >= 0x400 else 0)
        courses[level_id] = _present(_decode_word(word, strings, part_a, part_b, part_c))
        translevel += 1
    return courses


def _decode_word(word: int, strings: bytes, part_a, part_b, part_c) -> str:
    low, high = word & 0xFF, (word >> 8) & 0xFF
    codes: list[int] = []
    for table, index in ((part_a, high & 0x7F), (part_b, (low >> 4) & 0xF), (part_c, low & 0xF)):
        if index >= len(table):
            continue
        part = _string_at(strings, table[index])
        if part == [0x1F]:
            continue
        codes.extend(part)
    return _glyphs(codes)


def _string_at(strings: bytes, offset: int) -> list[int]:
    codes = []
    while offset < len(strings):
        byte = strings[offset]
        codes.append(byte & 0x7F)
        offset += 1
        if byte & 0x80:
            break
    return codes


def _glyphs(codes: list[int]) -> str:
    text = []
    index = 0
    while index < len(codes):
        if tuple(codes[index:index + 6]) == _ILLUSION:
            # "FOREST OF " plus these six tiles plus "ON" is the one illusion word.
            text.append('ILLUSI')
            index += 6
            continue
        if tuple(codes[index:index + 5]) == _YELLOW:
            # Green, red, and blue are spelled with ordinary letters. This run is the other switch color.
            text.append('YELLOW')
            index += 5
            continue
        text.append(_glyph(codes[index]))
        index += 1
    return ''.join(text)


def _glyph(code: int) -> str:
    if code == 0x1F:
        return ' '
    if code == 0x5D:
        return "'"
    if code == 0x5A:
        return '#'
    if code == 0x1C:
        # Sits between the shared prefix CHOCO and GHOST HOUSE. CHOCOLATE is the full word beside it.
        return 'LATE '
    if code <= 0x19:
        return chr(ord('A') + code)
    if 0x64 <= code <= 0x6A:
        return chr(ord('1') + code - 0x64)
    return ''


def _present(text: str) -> str:
    words = []
    for word in ' '.join(text.split()).split(' '):
        if not word or word.startswith('#'):
            words.append(word)
            continue
        head, separator, tail = word.partition("'")
        shown = head.capitalize()
        if separator:
            shown += "'" + tail.lower()
        words.append(shown)
    return ' '.join(words)


def _exit_levels(level) -> list[int]:
    bank = level.level_id & 0x100
    destinations = []
    for record in level.layer1.records:
        if record.kind == 'screen_exit' and record.exit_destination_byte is not None:
            destinations.append(record.exit_destination_byte | bank)
    return destinations


def _catalog_pointers(rom) -> dict[int, int]:
    pointers = {}
    for _label, key in level_catalog(rom):
        pointers[_layer1_pointer(rom, key)] = key
    return pointers


def _layer1_pointer(rom, level_id: int) -> int:
    base = lorom_to_pc(LAYER1_POINTERS)
    return int.from_bytes(rom.slice(base + 3 * level_id, 3), 'little')


def _words(raw: bytes) -> list[int]:
    return [int.from_bytes(raw[index:index + 2], 'little') for index in range(0, len(raw) - 1, 2)]


def _read(rom, snes_address: int, size: int) -> bytes:
    return rom.slice(lorom_to_pc(snes_address), size)
