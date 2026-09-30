from pathlib import Path

import pytest

from mujoco_mojo.utils.changelog import (
    fetch_and_parse_changelog,
    parse_changelog,
    read_last_seen_version,
    version_tuple,
    write_last_seen_version,
)


def test_parse_changelog_extracts_version_date_and_bullets() -> None:
    text = "# Changelog\n\n## Version 1.2.3 (2026-01-05)\n\n- Did a thing\n- Did another thing\n"
    entries = parse_changelog(text)
    assert len(entries) == 1
    assert entries[0].version == "1.2.3"
    assert entries[0].date == "2026-01-05"
    assert entries[0].bullets == ["- Did a thing", "- Did another thing"]


def test_parse_changelog_handles_malformed_year_without_crashing() -> None:
    """Regression for the real '20206-09-11' heading in this repo's own CHANGELOG.md."""
    text = "## Version 2.6.10 (20206-09-11)\n\n- Some change\n"
    entries = parse_changelog(text)
    assert entries[0].version == "2.6.10"
    assert entries[0].date is None
    assert entries[0].bullets == ["- Some change"]


def test_parse_changelog_folds_nested_sub_bullets_into_parent() -> None:
    text = (
        "## Version 1.0.0 (2026-01-01)\n\n"
        "- Parent change\n"
        "    - Sub detail\n"
        "        - Sub-sub detail\n"
        "- Second top-level change\n"
    )
    entries = parse_changelog(text)
    assert len(entries[0].bullets) == 2
    assert "Sub detail" in entries[0].bullets[0]
    assert "Sub-sub detail" in entries[0].bullets[0]
    assert entries[0].bullets[1] == "- Second top-level change"


def test_parse_changelog_empty_text_returns_empty_list() -> None:
    assert parse_changelog("") == []


def test_parse_changelog_matches_real_repo_changelog() -> None:
    """Loose regression guard against a future format drift in the real file."""
    repo_changelog = Path(__file__).resolve().parents[2] / "CHANGELOG.md"
    entries = parse_changelog(repo_changelog.read_text(encoding="utf-8"))
    assert len(entries) > 10
    assert all(e.version.count(".") == 2 for e in entries)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2.6.11", (2, 6, 11)),
        ("2.6.11.dev3+g1234abc", (2, 6, 11)),
        ("0.0.0-dev", (0, 0, 0)),
        ("not-a-version", (0, 0, 0)),
    ],
)
def test_version_tuple(raw: str, expected: tuple[int, int, int]) -> None:
    assert version_tuple(raw) == expected


def test_read_last_seen_version_missing_file_returns_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "mujoco_mojo.utils.changelog.LAST_SEEN_VERSION_FILE", tmp_path / "nope.txt"
    )
    assert read_last_seen_version() is None


def test_write_then_read_last_seen_version_roundtrips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "nested" / "last_seen_changelog_version.txt"
    monkeypatch.setattr("mujoco_mojo.utils.changelog.LAST_SEEN_VERSION_FILE", path)
    write_last_seen_version("2.6.11")
    assert read_last_seen_version() == "2.6.11"
    # acknowledging a later version overwrites the earlier one, not append
    write_last_seen_version("2.6.12")
    assert read_last_seen_version() == "2.6.12"


def test_fetch_and_parse_changelog_propagates_remote_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No silent fallback: a fetch failure raises, and the failure isn't cached, so the next call retries."""
    monkeypatch.setattr("mujoco_mojo.utils.changelog._cache", None)

    def _boom() -> str:
        raise TimeoutError("simulated network failure")

    monkeypatch.setattr("mujoco_mojo.utils.changelog._fetch_remote_text", _boom)
    with pytest.raises(TimeoutError):
        fetch_and_parse_changelog(force_refresh=True)

    import mujoco_mojo.utils.changelog as changelog_module

    assert changelog_module._cache is None
