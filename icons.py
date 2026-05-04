"""Built-in icons for the LED badge.

Each icon is a list of DISPLAY_HEIGHT (=11) rows, each row a list of 0/1.
Add your own either here or by dropping <name>.png into
/config/led_badge_icons/  (height up to 11 px is rescaled automatically).

Editor convention below: '#' = pixel on, '.' or ' ' = off.
"""
from __future__ import annotations

from .const import DISPLAY_HEIGHT


def _parse(*lines: str) -> list[list[int]]:
    """Parse human-readable rows into a 0/1 bitmap, padded/centered to 11 rows."""
    rows = [[1 if c == "#" else 0 for c in line] for line in lines]
    width = max(len(r) for r in rows)
    for r in rows:
        if len(r) < width:
            r.extend([0] * (width - len(r)))

    if len(rows) < DISPLAY_HEIGHT:
        pad_top = (DISPLAY_HEIGHT - len(rows)) // 2
        pad_bot = DISPLAY_HEIGHT - len(rows) - pad_top
        empty = [0] * width
        rows = [empty[:] for _ in range(pad_top)] + rows + [empty[:] for _ in range(pad_bot)]
    elif len(rows) > DISPLAY_HEIGHT:
        off = (len(rows) - DISPLAY_HEIGHT) // 2
        rows = rows[off:off + DISPLAY_HEIGHT]
    return rows


BUILTIN_ICONS: dict[str, list[list[int]]] = {
    "heart": _parse(
        ".##.##.",
        "#######",
        "#######",
        "#######",
        ".#####.",
        "..###..",
        "...#...",
    ),
    "wifi": _parse(
        ".#######.",
        "#.......#",
        "..#####..",
        ".#.....#.",
        "...###...",
        "..#...#..",
        "....#....",
        "....#....",
    ),
    "bell": _parse(
        "...#...",
        "..###..",
        ".#####.",
        ".#####.",
        ".#####.",
        ".#####.",
        "#######",
        "#######",
        "...#...",
        "..###..",
    ),
    "check": _parse(
        ".......##",
        "......##.",
        ".....##..",
        "....##...",
        "#..##....",
        "###......",
        ".#.......",
    ),
    "cross": _parse(
        "#.....#",
        "##...##",
        ".##.##.",
        "..###..",
        ".##.##.",
        "##...##",
        "#.....#",
    ),
    "warn": _parse(
        "....#....",
        "....#....",
        "...###...",
        "...#.#...",
        "..##.##..",
        "..#...#..",
        ".##.#.##.",
        ".#..#..#.",
        "##..#..##",
        "#########",
    ),
    "home": _parse(
        "....#....",
        "...###...",
        "..#####..",
        ".#######.",
        "#########",
        "#.#####.#",
        "..#####..",
        "..#.#.#..",
        "..#.#.#..",
        "..#####..",
    ),
    "smile": _parse(
        "..#####..",
        ".#.....#.",
        "#..#.#..#",
        "#.......#",
        "#.#...#.#",
        "#..###..#",
        ".#.....#.",
        "..#####..",
    ),
    "arrow_right": _parse(
        "....#....",
        "....##...",
        "....###..",
        "########.",
        "#########",
        "########.",
        "....###..",
        "....##...",
        "....#....",
    ),
    "arrow_left": _parse(
        "....#....",
        "...##....",
        "..###....",
        ".########",
        "#########",
        ".########",
        "..###....",
        "...##....",
        "....#....",
    ),
    "music": _parse(
        "..####.",
        "..#..#.",
        "..#..#.",
        "..#..#.",
        "..#..#.",
        ".##..##",
        "###..##",
        "###..##",
        ".#....#",
    ),
    "key": _parse(
        ".#####...",
        "##...##..",
        "##...##..",
        "##...##..",
        ".#####...",
        "...##....",
        "...########",
        "...##...##",
        "...##....",
    ),
    "battery": _parse(
        ".#########..",
        ".#.......#..",
        ".#.######.##",
        ".#.######.##",
        ".#.######.##",
        ".#.######.##",
        ".#.######.##",
        ".#.######.##",
        ".#.......#..",
        ".#########..",
    ),
}
