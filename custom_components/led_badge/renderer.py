"""Bitmap rendering of text + icons for the LED badge.

The renderer turns a message string with optional ``:icon:`` tokens into a
DISPLAY_HEIGHT (=11) row monochrome bitmap.

Font selection (first match wins):
  1. ``<config>/led_badge_font.ttf`` – a TrueType font supplied by the user.
  2. DejaVu Sans Bold / Sans / Sans Mono Bold / Sans Mono from the usual
     system font directories.
  3. Pillow's built-in default font (no umlauts).

For every font the largest point size is chosen whose vertical extent –
measured from the top of an umlaut capital to the bottom of a descender –
fits into DISPLAY_HEIGHT pixels. All text segments of a message are drawn
on the same baseline, so text before and after an icon lines up, and
spaces keep their real width.

Icon resolution:
  1. Built-in icons from :mod:`.icons`.
  2. ``<config>/led_badge_icons/<name>.png|.bmp|.gif``. Taller images are
     scaled down to DISPLAY_HEIGHT pixels, smaller ones are centred
     vertically. Transparent pixels count as "off".

All functions in this module do blocking file I/O and must be run in the
executor, never in the event loop.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from pathlib import Path
import re
from typing import Any

from .const import DISPLAY_HEIGHT
from .icons import BUILTIN_ICONS

_LOGGER = logging.getLogger(__name__)

ICON_RE = re.compile(r":([a-zA-Z0-9_]+):")
USER_ICON_DIRNAME = "led_badge_icons"
USER_FONT_FILENAME = "led_badge_font.ttf"

# Used to measure the vertical extent a font needs: umlaut capitals at the
# top, descenders at the bottom.
_REFERENCE_TEXT = "HÄÖÜdgjpqy|"

_FONT_DIRS = (
    "/usr/share/fonts/truetype/dejavu",  # Debian / Ubuntu
    "/usr/share/fonts/dejavu",  # Alpine / Fedora
    "/usr/share/fonts/TTF",  # Arch
    "/usr/share/fonts/ttf-dejavu",
)
_FONT_FILES = (
    "DejaVuSans-Bold.ttf",
    "DejaVuSans.ttf",
    "DejaVuSansMono-Bold.ttf",
    "DejaVuSansMono.ttf",
)

Bitmap = list[list[int]]


@dataclass(frozen=True)
class _FittedFont:
    """A font together with the baseline offset that centres it in 11 px."""

    font: Any
    baseline: int  # y coordinate of the baseline inside the 11 px canvas
    supports_anchor: bool


_font_cache: dict[str, _FittedFont] = {}


def _band(font: Any) -> tuple[int, int]:
    """Return (top, bottom) of the reference text's ink relative to baseline."""
    from PIL import Image, ImageDraw  # noqa: PLC0415

    img = Image.new("1", (400, 80), 0)
    draw = ImageDraw.Draw(img)
    draw.fontmode = "1"
    draw.text((4, 40), _REFERENCE_TEXT, font=font, fill=1, anchor="ls")
    bbox = img.getbbox()
    if bbox is None:
        return 0, 0
    return bbox[1] - 40, bbox[3] - 40


def _fit_truetype(loader) -> _FittedFont | None:
    """Pick the largest size whose reference band fits DISPLAY_HEIGHT."""
    best: _FittedFont | None = None
    for size in range(6, 30):
        try:
            font = loader(size)
        except (OSError, TypeError, ValueError):
            return best
        top, bottom = _band(font)
        height = bottom - top
        if height <= 0 or height > DISPLAY_HEIGHT:
            if best is not None:
                break
            continue
        offset = (DISPLAY_HEIGHT - height) // 2
        best = _FittedFont(font=font, baseline=offset - top, supports_anchor=True)
    return best


def _candidate_paths(config_dir: str) -> list[Path]:
    paths = [Path(config_dir) / USER_FONT_FILENAME]
    paths.extend(
        Path(font_dir) / font_file
        for font_file in _FONT_FILES
        for font_dir in _FONT_DIRS
    )
    return paths


def _get_font(config_dir: str) -> _FittedFont:
    """Return a fitted font (cached per config directory)."""
    if (cached := _font_cache.get(config_dir)) is not None:
        return cached

    from PIL import ImageFont  # noqa: PLC0415

    fitted: _FittedFont | None = None
    for path in _candidate_paths(config_dir):
        if not path.is_file():
            continue
        fitted = _fit_truetype(
            lambda size, p=path: ImageFont.truetype(str(p), size)
        )
        if fitted is not None:
            _LOGGER.debug(
                "led_badge: using font %s at %s pt", path, fitted.font.size
            )
            break
        _LOGGER.debug("led_badge: font %s does not fit, skipping", path)

    if fitted is None:
        _LOGGER.warning(
            "led_badge: no DejaVu font found, falling back to Pillow's default "
            "font (no umlauts). Put a TrueType font at %s for better results",
            Path(config_dir) / USER_FONT_FILENAME,
        )
        fitted = _fit_truetype(lambda size: ImageFont.load_default(size=size))
    if fitted is None:
        # Pillow without FreeType: fixed bitmap font, no anchor support
        fitted = _FittedFont(
            font=ImageFont.load_default(), baseline=0, supports_anchor=False
        )

    _font_cache[config_dir] = fitted
    return fitted


def _image_to_bitmap(img) -> Bitmap:
    px = img.load()
    return [
        [1 if px[x, y] else 0 for x in range(img.width)]
        for y in range(DISPLAY_HEIGHT)
    ]


def _render_text_block(text: str, config_dir: str) -> Bitmap:
    """Render plain text (no icon tokens) into a DISPLAY_HEIGHT-row bitmap."""
    if not text:
        return [[] for _ in range(DISPLAY_HEIGHT)]

    from PIL import Image, ImageDraw  # noqa: PLC0415

    fitted = _get_font(config_dir)
    width = max(1, math.ceil(fitted.font.getlength(text)))

    img = Image.new("1", (width, DISPLAY_HEIGHT), 0)
    draw = ImageDraw.Draw(img)
    draw.fontmode = "1"  # no anti-aliasing: crisp pixels for the LED matrix
    if fitted.supports_anchor:
        draw.text((0, fitted.baseline), text, font=fitted.font, fill=1, anchor="ls")
    else:
        draw.text((0, 0), text, font=fitted.font, fill=1)
    return _image_to_bitmap(img)


def _fit_icon(img):
    """Scale an icon down to DISPLAY_HEIGHT or centre it vertically."""
    from PIL import Image  # noqa: PLC0415

    if img.height > DISPLAY_HEIGHT:
        ratio = DISPLAY_HEIGHT / img.height
        new_w = max(1, round(img.width * ratio))
        img = img.resize((new_w, DISPLAY_HEIGHT), resample=Image.Resampling.BOX)
    elif img.height < DISPLAY_HEIGHT:
        canvas = Image.new("L", (img.width, DISPLAY_HEIGHT), 0)
        canvas.paste(img, (0, (DISPLAY_HEIGHT - img.height) // 2))
        img = canvas
    return img.point(lambda v: 255 if v >= 128 else 0)


def _load_user_icon(name: str, config_dir: str) -> Bitmap | None:
    """Try to load a user-supplied icon from <config>/led_badge_icons/."""
    base = Path(config_dir) / USER_ICON_DIRNAME
    if not base.is_dir():
        return None

    from PIL import Image  # noqa: PLC0415

    for ext in (".png", ".bmp", ".gif"):
        path = base / f"{name}{ext}"
        if not path.is_file():
            continue
        try:
            with Image.open(path) as src:
                img = src.convert("RGBA")
            # Transparent areas become black (= LED off)
            background = Image.new("RGBA", img.size, (0, 0, 0, 255))
            img = Image.alpha_composite(background, img).convert("L")
            return _image_to_bitmap(_fit_icon(img))
        except (OSError, ValueError) as err:
            _LOGGER.warning("led_badge: failed to load icon %s: %s", path, err)
    return None


def _resolve_icon(name: str, config_dir: str) -> Bitmap | None:
    if name in BUILTIN_ICONS:
        return [list(row) for row in BUILTIN_ICONS[name]]
    return _load_user_icon(name, config_dir)


def _spacer(width: int = 1) -> Bitmap:
    return [[0] * width for _ in range(DISPLAY_HEIGHT)]


def _concat(*blocks: Bitmap) -> Bitmap:
    out: Bitmap = [[] for _ in range(DISPLAY_HEIGHT)]
    for block in blocks:
        for row_idx, row in enumerate(block):
            out[row_idx].extend(row)
    return out


def render(message: str, config_dir: str = "/config") -> Bitmap:
    """Render full message (text + ``:icon:`` tokens) into an 11-row bitmap."""
    parts: list[Bitmap] = []
    last_end = 0

    for match in ICON_RE.finditer(message):
        if match.start() > last_end:
            parts.append(
                _render_text_block(message[last_end : match.start()], config_dir)
            )

        icon = _resolve_icon(match.group(1), config_dir)
        if icon is not None:
            parts.extend((_spacer(1), icon, _spacer(1)))
        else:
            # Render the literal token so typos are visible on the badge
            parts.append(_render_text_block(match.group(0), config_dir))

        last_end = match.end()

    if last_end < len(message):
        parts.append(_render_text_block(message[last_end:], config_dir))

    bitmap = _concat(*parts) if parts else _spacer(1)
    if not bitmap[0]:
        bitmap = _spacer(1)
    return bitmap
