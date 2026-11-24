"""Bounded, strict LC_LZ2 decompression for ROM preservation.

Format reference: https://sneslab.net/wiki/LC_LZ2
Source offsets and consumed sizes are tracked so results can be audited.
No decompressed content is shipped with Retroserv.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass


class LZ2Error(ValueError):
    """A malformed or unsupported LC_LZ2 stream."""


@dataclass(frozen=True)
class LZ2Result:
    data: bytes
    consumed: int  # includes the terminating FF header
    commands: dict[str, int]


def decompress(data: bytes, offset: int = 0, *, max_output: int = 262144,
               max_input: int = 262144) -> LZ2Result:
    """Decompress a terminated LC_LZ2 stream, bounded by input/output sizes.

    The length in a command header represents length minus one. Long headers
    are `111CCCLL LLLLLLLL`, except 0xFF which terminates a stream.
    Repeat source addresses are absolute output-buffer indices, big-endian.
    Overlapping backreferences are allowed.
    """
    if not (0 <= offset < len(data)):
        raise LZ2Error('Stream offset outside input')
    if not (1 <= max_input <= 16 * 1024 * 1024 and 1 <= max_output <= 16 * 1024 * 1024):
        raise LZ2Error('Invalid LZ2 input/output limits')
    cursor, end = offset, min(len(data), offset + max_input)
    output = bytearray()
    commands = Counter()

    def take(n: int) -> bytes:
        nonlocal cursor
        if cursor + n > end:
            raise LZ2Error(f'Truncated LC_LZ2 stream at 0x{cursor:X}')
        value = data[cursor:cursor + n]
        cursor += n
        return value

    while cursor < end:
        header = take(1)[0]
        if header == 0xFF:
            return LZ2Result(bytes(output), cursor - offset, dict(commands))
        if header >= 0xE0:
            command = (header >> 2) & 7
            length = (((header & 3) << 8) | take(1)[0]) + 1
        else:
            command = header >> 5
            length = (header & 31) + 1
        if command > 4:
            raise LZ2Error(f'Unsupported LC_LZ2 command {command} at 0x{cursor:X}')
        if len(output) + length > max_output:
            raise LZ2Error(f'LC_LZ2 output exceeds {max_output} bytes')
        commands[str(command)] += 1
        if command == 0:  # direct copy
            output.extend(take(length))
        elif command == 1:  # byte fill
            output.extend(take(1) * length)
        elif command == 2:  # word fill
            word = take(2)
            output.extend((word * ((length + 1) // 2))[:length])
        elif command == 3:  # increasing fill
            initial = take(1)[0]
            output.extend(((initial + i) & 0xFF) for i in range(length))
        else:  # output-buffer repeat, including overlapping repeats
            pointer = take(2)
            source = (pointer[0] << 8) | pointer[1]
            for j in range(length):
                at = source + j
                if at >= len(output):
                    raise LZ2Error(f'Invalid LC_LZ2 repeat source 0x{at:X}')
                output.append(output[at])
    raise LZ2Error('LC_LZ2 stream has no FF terminator within input limit')
