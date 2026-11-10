from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import mujoco_mojo.utils.layers.dojo.routers.changelog as changelog_router
from mujoco_mojo.utils.changelog import ChangelogEntry, LoadedChangelog


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        "mujoco_mojo.utils.changelog.LAST_SEEN_VERSION_FILE", tmp_path / "seen.txt"
    )
    app = FastAPI()
    app.include_router(changelog_router.router, prefix="/changelog")
    return TestClient(app)


def _loaded(source: str) -> LoadedChangelog:
    entry = ChangelogEntry(version="99.0.0", date="2030-01-01", bullets=["- a change"])
    return LoadedChangelog.model_validate({"entries": [entry], "source": source})


@pytest.mark.parametrize("source", ["remote", "cache", "bundled"])
def test_the_response_says_where_the_entries_came_from(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    monkeypatch.setattr(changelog_router, "load_changelog", lambda: _loaded(source))
    body = client.get("/changelog/data").json()
    assert body["source"] == source
    assert body["error"] is None
    assert body["latest_version"] == "99.0.0"
    assert body["update_available"] is True
    assert [e["version"] for e in body["entries"]] == ["99.0.0"]


def test_the_response_reports_an_error_only_when_nothing_could_be_loaded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(changelog_router, "load_changelog", lambda: None)
    body = client.get("/changelog/data").json()
    assert body["source"] is None
    assert body["error"]
    assert body["entries"] == []
    assert body["latest_version"] is None
    assert body["update_available"] is False
