from pathlib import Path

import pytest

from retroserv.rom import RomImage
from retroserv.smw_level import _read_stream, read_level


def synthetic_rom(tmp_path, offset, stream):
    data = bytearray((Path(__file__).resolve().parents[1] / 'samples/retroserv_test.sfc').read_bytes())
    data[offset:offset + len(stream)] = stream
    path = tmp_path / 'fixture.sfc'
    path.write_bytes(data)
    return RomImage(path)


def test_object_stream_keeps_screen_commands_and_ff_exit_destination(tmp_path):
    raw = bytes.fromhex('13 00 00 00 00 58 10 bf 03 00 01 92 14 ff 07 02 00 ff ff')
    rom = synthetic_rom(tmp_path, 0, raw)
    stream = _read_stream(rom, 0x008000, objects=True)

    first, jump, next_screen, exit_record = stream.records
    assert (first.type_id, first.x, first.y) == (33, 0, 24)
    assert (jump.kind, jump.screen, jump.x) == ('screen_jump', 3, None)
    assert (next_screen.screen, next_screen.x, next_screen.y) == (4, 68, 18)
    assert (exit_record.kind, exit_record.screen, exit_record.exit_destination_byte) == ('screen_exit', 7, 255)
    assert exit_record.secondary_exit
    assert stream.terminator_offset == len(raw) - 1
    assert bytes.fromhex(stream.header_hex + ' ' + ' '.join(r.raw_hex for r in stream.records) + ' ff') == raw


def test_sprite_stream_decodes_high_coordinate_bits(tmp_path):
    rom = synthetic_rom(tmp_path, 0, bytes.fromhex('04 3b f2 ab ff'))
    stream = _read_stream(rom, 0x008000, objects=False)
    sprite, = stream.records
    assert (sprite.screen, sprite.x, sprite.y, sprite.type_id) == (18, 303, 19, 0xAB)
    assert sprite.sprite_extra_bits == 2
    assert stream.terminator_offset == 4


def test_stream_stops_at_bank_boundary_and_rejects_unverified_rom(tmp_path):
    rom = synthetic_rom(tmp_path, 0x7FFD, bytes.fromhex('04 01 00 ff ff'))
    with pytest.raises(ValueError, match='terminator'):
        _read_stream(rom, 0x00FFFD, objects=False)
    with pytest.raises(ValueError, match='verified USA'):
        read_level(rom)
