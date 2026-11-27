"""Tests for where Mojo keeps the user's files (`mujoco_mojo.meta`), and for moving them out of `~/.mujoco-mojo`, where they were all kept before version 2.8.6."""

from pathlib import Path

import pytest

from mujoco_mojo.meta import (
    CACHE_DIR,
    CONFIG_DIR,
    DATA_DIR,
    LEGACY_FILES,
    LEGACY_LEFTOVERS,
    STATE_DIR,
    home_relative,
    move_legacy_files,
)


@pytest.fixture
def legacy(tmp_path: Path) -> Path:
    """An old `~/.mujoco-mojo` with a settings file and its lock, a saved profile and a built docs site."""
    folder = tmp_path / "home" / ".mujoco-mojo"
    (folder / "profiles").mkdir(parents=True)
    (folder / "profiles" / "mine.json").write_text("{}", encoding="utf-8")
    (folder / "docs" / "v2.8.5").mkdir(parents=True)
    (folder / "docs" / "v2.8.5" / "index.html").write_text("site", encoding="utf-8")
    (folder / "settings.toml").write_text("[general]\n", encoding="utf-8")
    (folder / "settings.toml.lock").write_text("", encoding="utf-8")
    return folder


def destinations(tmp_path: Path) -> dict[str, Path]:
    """Where the files of `legacy` go: a config, a data and a cache folder of their own."""
    return {
        "settings.toml": tmp_path / "config" / "settings.toml",
        "profiles": tmp_path / "data" / "profiles",
        "docs": tmp_path / "cache" / "docs",
    }


def move(legacy: Path, tmp_path: Path) -> list[str]:
    return move_legacy_files(
        legacy, destinations(tmp_path), LEGACY_LEFTOVERS, tmp_path / "state"
    )


def test_every_old_file_goes_into_one_of_the_standard_folders() -> None:
    folders = (CONFIG_DIR, DATA_DIR, CACHE_DIR, STATE_DIR)
    for name, destination in LEGACY_FILES.items():
        assert any(destination.is_relative_to(folder) for folder in folders), name


def test_each_file_moves_to_its_place_and_the_old_folder_goes(
    legacy: Path, tmp_path: Path
) -> None:
    left = move(legacy, tmp_path)

    to = destinations(tmp_path)
    assert left == []
    assert not legacy.exists()
    assert to["settings.toml"].read_text(encoding="utf-8") == "[general]\n"
    assert (to["profiles"] / "mine.json").read_text(encoding="utf-8") == "{}"
    assert (to["docs"] / "v2.8.5" / "index.html").is_file()


def test_a_file_whose_new_place_is_taken_is_left_and_nothing_is_overwritten(
    legacy: Path, tmp_path: Path
) -> None:
    newer = destinations(tmp_path)["settings.toml"]
    newer.parent.mkdir(parents=True)
    newer.write_text("[newer]\n", encoding="utf-8")

    left = move(legacy, tmp_path)

    assert left == ["settings.toml"]
    assert newer.read_text(encoding="utf-8") == "[newer]\n"
    assert (legacy / "settings.toml").read_text(encoding="utf-8") == "[general]\n"
    # the rest still moved
    assert (destinations(tmp_path)["profiles"] / "mine.json").is_file()


def test_what_mojo_does_not_know_is_left_where_it_is(
    legacy: Path, tmp_path: Path
) -> None:
    (legacy / "template").mkdir()
    (legacy / "template" / "notes.txt").write_text("mine", encoding="utf-8")

    left = move(legacy, tmp_path)

    assert left == ["template"]
    assert (legacy / "template" / "notes.txt").read_text(encoding="utf-8") == "mine"


def test_nothing_happens_without_the_old_folder(tmp_path: Path) -> None:
    left = move(tmp_path / "home" / ".mujoco-mojo", tmp_path)

    assert left == []
    # not even the lock's folder is made
    assert not (tmp_path / "state").exists()


def test_a_second_run_does_nothing(legacy: Path, tmp_path: Path) -> None:
    move(legacy, tmp_path)
    moved = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    assert move(legacy, tmp_path) == []
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == moved


def test_a_path_in_the_home_folder_is_shown_from_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    assert home_relative(tmp_path / ".config" / "mujoco-mojo") == (
        "~/.config/mujoco-mojo"
    )
    elsewhere = tmp_path.parent / "elsewhere" / "mujoco-mojo"
    assert home_relative(elsewhere) == str(elsewhere)
