"""Tests for how the Dojo's templates choose between the built frontend files and the sources a Vite dev server serves."""

import json
import re

import pytest

from mujoco_mojo.utils.layers.dojo import shared

TEMPLATES_DIR = shared.HERE / "templates"
DIST_DIR = TEMPLATES_DIR / "static" / "dist"
ENTRIES: dict[str, str] = json.loads((shared.TS_DIR / "entries.json").read_text())


def test_built_files_are_served_from_dist_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shared, "VITE_DEV", False)
    assert shared.asset_url("trial-viewer.js") == "/mojo-static/dist/trial-viewer.js"
    assert shared.asset_url("main.css") == "/mojo-static/dist/main.css"


def test_dev_mode_points_at_the_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shared, "VITE_DEV", True)
    assert shared.asset_url("trial-viewer.js") == "/src/trial-viewer.ts"
    assert shared.asset_url("main.js") == "/src/store.ts"
    assert shared.asset_url("main.css") == "/src/styles/main.css"


def test_dev_mode_rejects_a_name_that_is_not_an_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shared, "VITE_DEV", True)
    with pytest.raises(KeyError):
        shared.asset_url("nope.js")


@pytest.mark.parametrize("name", sorted(ENTRIES))
def test_every_entry_has_a_source_and_a_built_file(name: str) -> None:
    assert (shared.TS_DIR / ENTRIES[name]).is_file()
    assert (DIST_DIR / name).is_file()


def test_every_asset_a_template_asks_for_is_an_entry() -> None:
    # not rglob over the whole templates folder, which would walk static/ts/node_modules
    pages = [
        *TEMPLATES_DIR.glob("*.html"),
        *(TEMPLATES_DIR / "partials").rglob("*.html"),
    ]
    asked = {
        name
        for path in pages
        for name in re.findall(r"asset\('([^']+)'\)", path.read_text())
    }
    assert asked
    assert asked <= ENTRIES.keys()
