import importlib.abc
import importlib.machinery
import logging
import sys
from pathlib import Path
from types import ModuleType
from collections.abc import Sequence

import pytest

from mujoco_mojo.utils.layers.dojo import favicons


def _write_logo(static_dir: Path) -> None:
    static_dir.mkdir()
    (static_dir / "light-logo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>'
    )


@pytest.mark.parametrize("error", [ImportError, OSError])
def test_cairo_available_is_false_when_the_import_fails(
    error: type[Exception], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing libcairo surfaces as `OSError` (cairocffi dlopens it on import), a missing cairosvg as `ImportError`; both mean no favicons."""

    class FailingFinder(importlib.abc.MetaPathFinder):
        def find_spec(
            self,
            fullname: str,
            path: Sequence[str] | None,
            target: ModuleType | None = None,
        ) -> importlib.machinery.ModuleSpec | None:
            if fullname == "cairosvg":
                raise error("no library called cairo-2 was found")
            return None

    # drop any already-imported cairosvg so the import actually re-runs and hits the finder
    monkeypatch.delitem(sys.modules, "cairosvg", raising=False)
    monkeypatch.setattr(sys, "meta_path", [FailingFinder(), *sys.meta_path])
    assert favicons._cairo_available() is False


def test_ensure_favicons_skips_with_a_warning_when_cairo_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The icons are cosmetic, so a missing Cairo must neither raise nor generate anything."""
    static_dir = tmp_path / "static"
    cache_dir = tmp_path / "cache"
    _write_logo(static_dir)
    monkeypatch.setattr(favicons, "_cairo_available", lambda: False)

    with caplog.at_level(logging.WARNING, logger=favicons.logger.name):
        favicons.ensure_favicons(static_dir, cache_dir)

    assert not cache_dir.exists()
    assert "Cairo" in caplog.text


def test_ensure_favicons_skips_with_a_warning_when_the_cache_dir_cannot_be_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An unwritable cache location must not take down startup over a cosmetic asset."""
    static_dir = tmp_path / "static"
    _write_logo(static_dir)
    blocker = tmp_path / "blocker"
    blocker.write_text("")
    monkeypatch.setattr(favicons, "_cairo_available", lambda: True)

    with caplog.at_level(logging.WARNING, logger=favicons.logger.name):
        favicons.ensure_favicons(static_dir, blocker / "cache")

    assert "could not create" in caplog.text


def test_ensure_favicons_generates_every_asset_when_cairo_is_available(
    tmp_path: Path,
) -> None:
    if not favicons._cairo_available():
        pytest.skip("the Cairo system library is not installed")

    static_dir = tmp_path / "static"
    cache_dir = tmp_path / "cache"
    _write_logo(static_dir)

    favicons.ensure_favicons(static_dir, cache_dir)

    for filename in (
        "apple-touch-icon.png",
        "favicon-32x32.png",
        "favicon-16x16.png",
        "favicon.ico",
    ):
        assert (cache_dir / filename).stat().st_size > 0
