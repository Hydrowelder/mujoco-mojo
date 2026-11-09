"""Tests for how the Dojo's templates choose between the built frontend files and the sources a Vite dev server serves."""

import json
import re

import pytest
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from mujoco_mojo.meta import DOCS_ASSETS_DIR
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


class TestTheLogos:
    """The Dojo's logos are the docs' own, in the docs source that ships with the package, so there is one copy of each in the package. `/mojo-static` serves them after its own folder."""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(Starlette(routes=[Mount("/mojo-static", app=shared.static)]))

    @pytest.mark.parametrize("name", ["light-logo.svg", "dark-logo.svg"])
    def test_the_logo_is_served_from_the_docs_source(
        self, client: TestClient, name: str
    ) -> None:
        response = client.get(f"/mojo-static/{name}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/svg+xml"
        assert response.content == (DOCS_ASSETS_DIR / name).read_bytes()

    def test_the_dojos_own_files_are_still_served(self, client: TestClient) -> None:
        assert client.get("/mojo-static/chime.mp3").status_code == 200
        assert client.get("/mojo-static/dist/main.css").status_code == 200

    def test_a_file_that_is_in_neither_folder_is_not_found(
        self, client: TestClient
    ) -> None:
        assert client.get("/mojo-static/nope.svg").status_code == 404

    def test_every_logo_a_template_asks_for_is_served(self, client: TestClient) -> None:
        pages = [
            *TEMPLATES_DIR.glob("*.html"),
            *(TEMPLATES_DIR / "partials").rglob("*.html"),
        ]
        asked = {
            name
            for path in pages
            for name in re.findall(r"/mojo-static/([\w.-]+\.svg)", path.read_text())
        }

        assert {"light-logo.svg", "dark-logo.svg"} <= asked
        for name in sorted(asked):
            assert client.get(f"/mojo-static/{name}").status_code == 200, name

    def test_the_dojo_keeps_no_copy_of_a_docs_logo(self) -> None:
        """A second copy is what this replaced: the two would drift, and the wheel would carry both."""
        logos = {path.read_bytes() for path in DOCS_ASSETS_DIR.glob("*.svg")}
        copies = [
            path.name
            for path in (TEMPLATES_DIR / "static").glob("*.svg")
            if path.read_bytes() in logos
        ]

        assert copies == []
