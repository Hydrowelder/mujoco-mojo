"""
Derives raster favicon assets from light-logo.svg, for browser/OS chrome that can't use an SVG favicon at all.

Mirrors the approach used by the (separate) flask-website project for the
same problem:

* Safari's tab bar, bookmarks, and iOS's "Add to Home Screen" only read a
  raster ``apple-touch-icon``, never an SVG favicon.
* ``GET /favicon.ico`` at the site root is still probed by a lot of
  browser/OS UI (bookmarks, tab switchers) independent of any ``<link
  rel="icon">`` in the page at all.
* Some browser chrome still only understands PNG favicons, at the
  conventional 32x32/16x16 sizes.

Rendered from ``light-logo.svg`` specifically, not ``dark-logo.svg`` -- these
derivatives are static files and can't respond to Dojo's manual dark-mode
toggle the way the primary SVG `<link>` does (see base.html), so they mirror
that link's own default, pre-toggle state instead of trying to track it.

:func:`ensure_favicons` regenerates each derivative once, only when the
source SVG has actually changed since the last time it ran (see ``main.py``
for where this gets called, and ``CACHE_DIR`` for where the results land).
"""

import hashlib
import io
import logging
from pathlib import Path

import cairosvg
from PIL import Image

from mujoco_mojo.meta import MUJOCO_MOJO_DIR

logger = logging.getLogger(__name__)

# Not inside the installed package's own static folder -- that may not be
# writable (e.g. a wheel install under site-packages), and generated files
# shouldn't be committed to git the way the source SVGs are.
CACHE_DIR = MUJOCO_MOJO_DIR / "cache"

_SOURCE_SVG = "light-logo.svg"

# (output filename, size in pixels) for every PNG derived from light-logo.svg.
# No flattening onto an opaque background here -- outside the hexagon mark is
# transparent in the source SVG, and it should stay that way in the
# derivatives too.
_FAVICON_TARGETS: list[tuple[str, int]] = [
    ("apple-touch-icon.png", 180),
    ("favicon-32x32.png", 32),
    ("favicon-16x16.png", 16),
]

# favicon.ico embeds both of these sizes; it isn't just another entry in
# _FAVICON_TARGETS since it's assembled from two renders via Pillow, not
# saved directly from cairosvg's own output.
_FAVICON_ICO_SIZES = (16, 32)


def _rasterize(svg_bytes: bytes, size: int) -> bytes:
    """Renders svg_bytes to a square PNG at size x size."""
    rendered = cairosvg.svg2png(
        bytestring=svg_bytes, output_width=size, output_height=size
    )
    # cairosvg ships no type stubs; the omitted `write_to` param is what
    # actually guarantees `bytes` back at runtime (vs. `None` when writing
    # straight to a file instead) -- this narrows that for pyright.
    assert isinstance(rendered, bytes)
    return rendered


def _generate_if_stale(
    cache_dir: Path, filename: str, size: int, svg_bytes: bytes, source_hash: str
) -> None:
    """
    Regenerates one derived PNG if it's missing or its recorded source hash doesn't match.

    The "recorded source hash" lives in a sidecar file (``<filename>.sha256``)
    written the last time this PNG was generated, rather than relying on file
    mtimes -- a fresh git checkout gives the source SVG the same mtime as
    everything else, which would make mtime comparison useless here.

    The render is written to a temp file and moved into place with
    `Path.replace` (atomic on the same filesystem) so a request racing a
    regeneration always sees a complete PNG, old or new, never a partial one.
    """
    png_path = cache_dir / filename
    hash_path = png_path.with_name(png_path.name + ".sha256")
    if (
        png_path.exists()
        and hash_path.exists()
        and hash_path.read_text().strip() == source_hash
    ):
        return

    png_bytes = _rasterize(svg_bytes, size)
    tmp_path = png_path.with_name(png_path.name + ".tmp")
    tmp_path.write_bytes(png_bytes)
    tmp_path.replace(png_path)
    hash_path.write_text(source_hash)
    logger.debug(f"Regenerated {filename} from {_SOURCE_SVG} ({source_hash[:12]})")


def _generate_ico_if_stale(cache_dir: Path, svg_bytes: bytes, source_hash: str) -> None:
    """
    Regenerates favicon.ico (embedding both 16x16 and 32x32) if it's missing or stale.

    Renders each size in `_FAVICON_ICO_SIZES` independently via cairosvg
    (rather than letting Pillow's ICO writer downscale a single larger
    bitmap) so every embedded size is a crisp, purpose-rendered image, not a
    blurrier resample.
    """
    ico_path = cache_dir / "favicon.ico"
    hash_path = ico_path.with_name(ico_path.name + ".sha256")
    if (
        ico_path.exists()
        and hash_path.exists()
        and hash_path.read_text().strip() == source_hash
    ):
        return

    # Largest first: Pillow's ICO writer bounds-checks every requested size
    # against the *base* image (the one .save() is called on, not the
    # largest of `append_images`) and silently drops anything bigger --
    # saving from the smallest image here would silently produce a
    # 16x16-only .ico despite `sizes` asking for 32x32 too.
    images = sorted(
        (
            Image.open(io.BytesIO(_rasterize(svg_bytes, size)))
            for size in _FAVICON_ICO_SIZES
        ),
        key=lambda img: img.size,
        reverse=True,
    )
    tmp_path = ico_path.with_name(ico_path.name + ".tmp")
    images[0].save(
        tmp_path,
        format="ICO",
        sizes=[img.size for img in images],
        append_images=images[1:],
    )
    tmp_path.replace(ico_path)
    hash_path.write_text(source_hash)
    logger.debug(f"Regenerated favicon.ico from {_SOURCE_SVG} ({source_hash[:12]})")


def ensure_favicons(static_dir: Path, cache_dir: Path = CACHE_DIR) -> None:
    """
    (Re)generates every favicon derivative that's missing or stale.

    Covers every PNG in `_FAVICON_TARGETS` plus favicon.ico. Each is handled
    independently -- one failing to render (a corrupt SVG, a read-only cache
    directory) is logged and skipped rather than raised, so it can't block
    the others or take down app startup over what's ultimately a cosmetic
    asset.

    Args:
        static_dir: Dojo's `templates/static` directory, where light-logo.svg lives.
        cache_dir: Where derived PNG/ICO files are written. Defaults to `CACHE_DIR`.

    """
    svg_path = static_dir / _SOURCE_SVG
    if not svg_path.exists():
        return

    try:
        svg_bytes = svg_path.read_bytes()
    except OSError:
        logger.warning("Failed to read %s", _SOURCE_SVG, exc_info=True)
        return

    cache_dir.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(svg_bytes).hexdigest()

    for filename, size in _FAVICON_TARGETS:
        try:
            _generate_if_stale(cache_dir, filename, size, svg_bytes, source_hash)
        except Exception:
            logger.warning(
                "Failed to (re)generate %s from %s",
                filename,
                _SOURCE_SVG,
                exc_info=True,
            )

    try:
        _generate_ico_if_stale(cache_dir, svg_bytes, source_hash)
    except Exception:
        logger.warning(
            "Failed to (re)generate favicon.ico from %s", _SOURCE_SVG, exc_info=True
        )
