"""Tests for saving a plot profile through the Dojo's mosaic router, in particular when a save would replace one that is already stored."""

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mujoco_mojo.utils.layers.dojo.routers import mosaic

PROFILE: dict[str, Any] = {"version": 2, "tabs": [{}]}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A client for the mosaic router with the profiles stored under a temporary directory."""
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    monkeypatch.setattr(mosaic, "_get_profiles_dir", lambda: profiles)
    app = FastAPI()
    app.include_router(mosaic.router, prefix="/mosaic")
    return TestClient(app)


def _save(client: TestClient, name: str, **params: str) -> Any:
    return client.post(f"/mosaic/api/profiles/{name}", json=PROFILE, params=params)


def test_a_save_stores_the_profile_under_its_sanitized_name(
    client: TestClient,
) -> None:
    response = _save(client, "My Plots/arm.v2")
    assert response.status_code == 200
    assert response.json() == {"name": "My_Plots/armv2"}
    assert client.get("/mosaic/api/profiles/My_Plots/armv2").status_code == 200


def test_a_save_replaces_a_stored_profile_by_default(client: TestClient) -> None:
    assert _save(client, "p1").status_code == 200
    again = _save(client, "p1")
    assert again.status_code == 200
    assert again.json() == {"name": "p1"}


def test_a_save_that_must_not_overwrite_goes_through_when_nothing_is_stored(
    client: TestClient,
) -> None:
    response = _save(client, "fresh", overwrite="false")
    assert response.status_code == 200
    assert response.json() == {"name": "fresh"}


def test_a_save_that_must_not_overwrite_is_refused_with_the_stored_name(
    client: TestClient,
) -> None:
    _save(client, "p1")
    response = _save(client, "p1", overwrite="false")
    assert response.status_code == 409
    assert response.json() == {"detail": {"name": "p1"}}


@pytest.mark.parametrize(
    ("stored", "typed"),
    [
        ("ab", "a.b"),
        ("my_plots", "my plots"),
        ("my_plots", "  my   plots  "),
        ("folder/p", "folder//p"),
        ("folder/p", "/folder/ p /"),
        ("p", "p!?"),
    ],
)
def test_a_name_that_sanitizes_to_a_stored_one_is_a_conflict(
    client: TestClient, stored: str, typed: str
) -> None:
    _save(client, stored)
    response = _save(client, typed, overwrite="false")
    assert response.status_code == 409
    assert response.json() == {"detail": {"name": stored}}


def test_a_refused_save_leaves_the_stored_profile_as_it_was(
    client: TestClient,
) -> None:
    original: dict[str, Any] = {**PROFILE, "vsEnabled": True}
    client.post("/mosaic/api/profiles/p1", json=original)
    _save(client, "p1", overwrite="false")
    assert client.get("/mosaic/api/profiles/p1").json()["vsEnabled"] is True


def test_a_name_that_sanitizes_to_a_different_profile_is_not_a_conflict(
    client: TestClient,
) -> None:
    _save(client, "ab")
    response = _save(client, "a-b", overwrite="false")
    assert response.status_code == 200
    assert response.json() == {"name": "a-b"}


def test_an_invalid_payload_is_rejected_before_the_conflict_check(
    client: TestClient,
) -> None:
    _save(client, "p1")
    response = client.post(
        "/mosaic/api/profiles/p1",
        json={"tabs": "not a list"},
        params={"overwrite": "false"},
    )
    assert response.status_code == 422
