"""Bitmap rendering of text + icons for the LED badge.

The renderer turns a message string with optional ``:icon:`` tokens into a
DISPLAY_HEIGHT (=11) row monochrome bitmap.

Font selection (in order of preference):
  1. DejaVu Sans Mono (TTF) at a size that gets us close to 11 px,
     scaled to exactly 11 px height afterwards.
  2. PIL.ImageFont.load_default(size=10)  (recent Pillow).
  3. PIL.ImageFont.load_default()         (legacy Pillow).

Icon resolution:
  1. Built-in icons from :mod:`.icons`.
  2. /config/led_badge_icons/<name>.png  (rescaled to 11 px height).
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from .const import DISPLAY_HEIGHT
from .icons import BUILTIN_ICONS

_LOGGER = logging.getLogger(__name__)

ICON_RE = re.compile(r":([a-zA-Z0-9_]+):")
USER_ICON_PATH = "/config/led_badge_icons"

# Common font locations on HAOS / Debian / Alpine. We try sizes that
# typically come out roughly 11 px tall on these fonts; the final rendering
# always re-fits to exactly DISPLAY_HEIGHT pixels.
_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 11),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 11),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11),
    ("/usr/share/fonts/dejavu/DejaVuSansMono-Bold.ttf", 11),
    ("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 11),
]

_cached_font = None
_cached_font_is_default = False


def _get_font():
    """Return a Pillow font object plus a flag indicating fallback usage."""
    global _cached_font, _cached_font_is_default
    if _cached_font is not None:
        return _cached_font, _cached_font_is_default

    from PIL import ImageFont  # noqa: PLC0415

    for path, size in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                _cached_font = ImageFont.truetype(path, size)
                _LOGGER.debug("led_badge: using TTF font %s @ %d", path, size)
                _cached_font_is_default = False
                return _cached_font, _cached_font_is_default
            except OSError as err:
                _LOGGER.debug("led_badge: cannot load %s: %s", path, err)

    # Fallbacks
    try:
        _cached_font = ImageFont.load_default(size=10)
    except TypeError:
        _cached_font = ImageFont.load_default()
    _cached_font_is_default = True
    _LOGGER.warning(
        "led_badge: no DejaVu TTF found, falling back to PIL default font"
    )
    return _cached_font, _cached_font_is_default


def _fit_to_height(img, target_h: int = DISPLAY_HEIGHT):
    """Crop or pad an image vertically to exactly target_h pixels (centered)."""
    from PIL import Image  # noqa: PLC0415

    if img.height == target_h:
        return img
    if img.height > target_h:
        # Resize down preserving aspect ratio, then re-threshold afterwards
        ratio = target_h / img.height
        new_w = max(1, round(img.width * ratio))
        return img.resize((new_w, target_h), resample=Image.NEAREST)
    # smaller → pad symmetrically
    new = Image.new("L", (img.width, target_h), 0)
    new.paste(img, (0, (target_h - img.height) // 2))
    return new


def _render_text_block(text: str) -> list[list[int]]:
    """Render plain text (no icon tokens) into a DISPLAY_HEIGHT-row bitmap."""
    if not text:
        return [[] for _ in range(DISPLAY_HEIGHT)]

    from PIL import Image, ImageDraw  # noqa: PLC0415

    font, _is_default = _get_font()

    # Probe text bounds
    tmp = Image.new("L", (1, 1), 0)
    draw = ImageDraw.Draw(tmp)
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
    except AttributeError:
        # very old Pillow
        w, h = draw.textsize(text, font=font)
        bbox = (0, 0, w, h)

    tw = max(1, bbox[2] - bbox[0])
    th = max(1, bbox[3] - bbox[1])

    img = Image.new("L", (tw + 4, th + 4), 0)
    draw = ImageDraw.Draw(img)
    draw.text((-bbox[0] + 2, -bbox[1] + 2), text, fill=255, font=font)

    # Trim to actual ink bounds, then fit to 11 px tall
    ink = img.getbbox()
    if ink is None:
        return [[0] * 1 for _ in range(DISPLAY_HEIGHT)]
    img = img.crop(ink)
    img = _fit_to_height(img, DISPLAY_HEIGHT)

    px = img.load()
    return [
        [1 if px[x, y] >= 128 else 0 for x in range(img.width)]
        for y in range(DISPLAY_HEIGHT)
    ]


def _load_user_icon(name: str) -> list[list[int]] | None:
    """Try to load a user-supplied icon from /config/led_badge_icons/."""
    base = Path(USER_ICON_PATH)
    if not base.exists():
        return None
    for ext in (".png", ".bmp", ".gif"):
        path = base / f"{name}{ext}"
        if not path.exists():
            continue
        try:
            from PIL import Image  # noqa: PLC0415

            img = Image.open(path).convert("L")
            img = _fit_to_height(img, DISPLAY_HEIGHT)
            px = img.load()
            return [
                [1 if px[x, y] >= 128 else 0 for x in range(img.width)]
                for y in range(DISPLAY_HEIGHT)
            ]
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("led_badge: failed to load icon %s: %s", path, err)
    return None


def _resolve_icon(name: str) -> list[list[int]] | None:
    if name in BUILTIN_ICONS:
        return [list(row) for row in BUILTIN_ICONS[name]]
    return _load_user_icon(name)


def _spacer(width: int = 1) -> list[list[int]]:
    return [[0] * width for _ in range(DISPLAY_HEIGHT)]


def _concat(*blocks: list[list[int]]) -> list[list[int]]:
    out: list[list[int]] = [[] for _ in range(DISPLAY_HEIGHT)]
    for block in blocks:
        for row_idx, row in enumerate(block):
            out[row_idx].extend(row)
    return out


def render(message: str) -> list[list[int]]:
    """Render full message (text + ``:icon:`` tokens) into 11-row bitmap."""
    parts: list[list[list[int]]] = []
    last_end = 0

    for match in ICON_RE.finditer(message):
        if match.start() > last_end:
            parts.append(_render_text_block(message[last_end:match.start()]))

        icon = _resolve_icon(match.group(1))
        if icon is not None:
            parts.append(_spacer(1))
            parts.append(icon)
            parts.append(_spacer(1))
        else:
            # Render the literal token so typos are visible on the badge
            parts.append(_render_text_block(match.group(0)))

        last_end = match.end()

    if last_end < len(message):
        parts.append(_render_text_block(message[last_end:]))

    if not parts:
        parts = [_spacer(1)]

    return _concat(*parts)
