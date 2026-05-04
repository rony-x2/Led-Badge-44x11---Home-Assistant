"""LED Badge BLE protocol: header + bitmap encoding.

Spec is reverse-engineered (see Nilhcem's blog post and
https://github.com/fossasia/led-name-badge-ls32 for the USB/HID variant
of the same protocol — the data format is identical, only the wire chunk
size differs: 16 bytes over BLE vs. 64 bytes over USB).

Header layout (64 bytes, sent first as 4 BLE chunks):
    0..3   "wang" magic
    4      reserved (0x00)
    5      brightness flag: 0x00=100%, 0x10=75%, 0x20=50%, 0x30=25%
    6      blink  flags, bit i = blink for message i
    7      marquee flags, bit i = marquee for message i
    8..15  speed (high nibble, 0..7) | mode (low nibble, 0..8) per message
    16..31 length per message in byte-columns, big-endian (8 * 2 bytes)
    32..37 reserved (0)
    38..43 timestamp YY MM DD HH MM SS
    44..63 reserved (0)

Bitmap layout (concatenated after the header, then split into 16-byte BLE
chunks, last one zero-padded):
    For each 8-pixel-wide "byte-column" of the rendered scene we emit
    DISPLAY_HEIGHT bytes (one per row, MSB = leftmost pixel).
    `length` in the header is the number of those byte-columns.
"""
from __future__ import annotations

import datetime as dt
from typing import Iterable

from .const import CHUNK_SIZE, DISPLAY_HEIGHT


def _pad(seq, default, n: int = 8) -> list:
    s = list(seq) + [default] * n
    return s[:n]


def build_header(
    lengths: list[int],
    speeds: list[int],
    modes: list[int],
    blinks: list[bool],
    marquees: list[bool],
    brightness: int,
    timestamp: dt.datetime | None = None,
) -> bytes:
    """Build the 64-byte protocol header."""
    if timestamp is None:
        timestamp = dt.datetime.now()

    lengths = _pad(lengths, 0)
    speeds = _pad(speeds, 4)
    modes = _pad(modes, 0)
    blinks = _pad(blinks, False)
    marquees = _pad(marquees, False)

    h = bytearray(64)
    h[0:4] = b"wang"

    # Brightness: 4 discrete levels
    b = max(0, min(100, int(brightness)))
    if b >= 88:
        h[5] = 0x00
    elif b >= 63:
        h[5] = 0x10
    elif b >= 38:
        h[5] = 0x20
    else:
        h[5] = 0x30

    h[6] = sum(1 << i for i, v in enumerate(blinks) if v) & 0xFF
    h[7] = sum(1 << i for i, v in enumerate(marquees) if v) & 0xFF

    for i in range(8):
        sp = max(1, min(8, int(speeds[i]))) - 1   # encoded 0..7
        md = max(0, min(8, int(modes[i])))
        h[8 + i] = (sp << 4) | md

    for i in range(8):
        ln = max(0, min(0xFFFF, int(lengths[i])))
        h[16 + i * 2] = (ln >> 8) & 0xFF
        h[16 + i * 2 + 1] = ln & 0xFF

    h[38] = timestamp.year % 100
    h[39] = timestamp.month
    h[40] = timestamp.day
    h[41] = timestamp.hour
    h[42] = timestamp.minute
    h[43] = timestamp.second

    return bytes(h)


def bitmap_to_bytes(rows: list[list[int]]) -> tuple[bytes, int]:
    """Convert a DISPLAY_HEIGHT-row pixel bitmap into the byte-column stream.

    `rows` must be exactly DISPLAY_HEIGHT rows of equal width,
    each entry 0 (off) or 1 (on).

    Returns (data_bytes, length_in_byte_columns).
    """
    if len(rows) != DISPLAY_HEIGHT:
        raise ValueError(f"expected {DISPLAY_HEIGHT} rows, got {len(rows)}")

    # Make defensive copies so we can pad without surprising callers
    rows = [list(r) for r in rows]

    width = len(rows[0])
    if any(len(r) != width for r in rows):
        raise ValueError("rows have inconsistent widths")

    # Pad to multiple of 8 pixel columns
    pad = (-width) % 8
    if pad:
        for r in rows:
            r.extend([0] * pad)
        width += pad

    n_cols = width // 8
    out = bytearray()
    for col in range(n_cols):
        for row in range(DISPLAY_HEIGHT):
            byte = 0
            for bit in range(8):
                if rows[row][col * 8 + bit]:
                    byte |= 1 << (7 - bit)
            out.append(byte)

    return bytes(out), n_cols


def chunkify(payload: bytes, size: int = CHUNK_SIZE) -> Iterable[bytes]:
    """Yield zero-padded `size`-byte chunks of `payload`."""
    for i in range(0, len(payload), size):
        chunk = payload[i:i + size]
        if len(chunk) < size:
            chunk = chunk + b"\x00" * (size - len(chunk))
        yield chunk
