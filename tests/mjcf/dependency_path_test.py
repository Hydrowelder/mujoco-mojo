import os
from pathlib import Path

import pytest

from mujoco_mojo.mjcf.dependency_path import copy_asset

requires_posix = pytest.mark.skipif(
    os.name != "posix", reason="unprivileged symlink creation requires POSIX"
)


def test_copy_asset_ignores_prefer_symlinks_on_non_posix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """prefer_symlinks is silently ignored off POSIX; a normal copy is made instead."""
    monkeypatch.setattr("mujoco_mojo.mjcf.dependency_path.os.name", "nt")

    source = tmp_path / "source.txt"
    source.write_text("hello")
    dest = tmp_path / "bundle" / "source.txt"

    copy_asset(source, dest, prefer_symlinks=True)

    assert dest.exists()
    assert not dest.is_symlink()
    assert dest.read_text() == "hello"


@requires_posix
def test_copy_asset_creates_symlink_when_prefer_symlinks_and_posix(tmp_path: Path):
    """On POSIX, prefer_symlinks links to the source instead of copying its bytes."""
    source = tmp_path / "source.txt"
    source.write_text("hello")
    dest = tmp_path / "bundle" / "source.txt"

    copy_asset(source, dest, prefer_symlinks=True)

    assert dest.is_symlink()
    assert dest.resolve() == source.resolve()


@requires_posix
def test_copy_asset_relinks_when_symlink_target_changes(tmp_path: Path):
    """A symlink already at dest pointing elsewhere is replaced, not left stale."""
    old_source = tmp_path / "old.txt"
    old_source.write_text("old")
    new_source = tmp_path / "new.txt"
    new_source.write_text("new")
    dest = tmp_path / "bundle" / "asset.txt"

    copy_asset(old_source, dest, prefer_symlinks=True)
    copy_asset(new_source, dest, prefer_symlinks=True)

    assert dest.is_symlink()
    assert dest.resolve() == new_source.resolve()


@requires_posix
def test_copy_asset_replaces_real_file_with_symlink(tmp_path: Path):
    """A real, non-symlinked file already at dest (e.g. from a copy-mode bundle) is replaced with a symlink."""
    source = tmp_path / "source.txt"
    source.write_text("hello")
    dest = tmp_path / "bundle" / "source.txt"
    dest.parent.mkdir(parents=True)
    dest.write_text("stale copy")

    copy_asset(source, dest, prefer_symlinks=True)

    assert dest.is_symlink()
    assert dest.resolve() == source.resolve()
