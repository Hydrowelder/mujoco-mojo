import logging
import ssl
import urllib.error
from pathlib import Path

import pytest

import mujoco_mojo.utils.changelog as changelog_module
from mujoco_mojo.utils.changelog import (
    ChangelogUnavailable,
    fetch_and_parse_changelog,
    load_changelog,
    parse_changelog,
    read_last_seen_version,
    version_tuple,
    write_last_seen_version,
)


REMOTE_TEXT = "# Changelog\n\n## Version 9.0.0 (2030-01-01)\n\n- from github\n"
CACHED_TEXT = "# Changelog\n\n## Version 8.0.0 (2029-01-01)\n\n- from the cache\n"


@pytest.fixture(autouse=True)
def isolated_changelog_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """No memory of an earlier fetch or failure, and the saved copy in a temp folder instead of the real home. Returns the saved copy's path."""
    cache_file = tmp_path / "changelog_cache.md"
    monkeypatch.setattr(changelog_module, "_cache", None)
    monkeypatch.setattr(changelog_module, "_failure", None)
    monkeypatch.setattr(changelog_module, "CHANGELOG_CACHE_FILE", cache_file)
    return cache_file


def _fetch_fails(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> list[int]:
    """Makes every fetch raise `exc`, and returns a list that gets one item per attempt."""
    attempts: list[int] = []

    def _boom() -> str:
        attempts.append(1)
        raise exc

    monkeypatch.setattr(changelog_module, "_fetch_remote_text", _boom)
    return attempts


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
    """`fetch_and_parse_changelog` itself has no fallback: a fetch failure raises, and is not cached as a result."""

    def _boom() -> str:
        raise TimeoutError("simulated network failure")

    monkeypatch.setattr("mujoco_mojo.utils.changelog._fetch_remote_text", _boom)
    with pytest.raises(TimeoutError):
        fetch_and_parse_changelog(force_refresh=True)

    assert changelog_module._cache is None


def test_failed_fetch_is_waited_out_instead_of_retried_on_every_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = _fetch_fails(monkeypatch, TimeoutError("simulated network failure"))
    with pytest.raises(TimeoutError):
        fetch_and_parse_changelog()
    with pytest.raises(ChangelogUnavailable, match="simulated network failure"):
        fetch_and_parse_changelog()
    assert len(attempts) == 1
    # an explicit refresh always goes to the network
    with pytest.raises(TimeoutError):
        fetch_and_parse_changelog(force_refresh=True)
    assert len(attempts) == 2


def test_failed_fetch_is_retried_once_the_wait_is_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = _fetch_fails(monkeypatch, TimeoutError("simulated network failure"))
    with pytest.raises(TimeoutError):
        fetch_and_parse_changelog()
    monkeypatch.setattr(changelog_module, "_RETRY_AFTER_SECONDS", 0.0)
    with pytest.raises(TimeoutError):
        fetch_and_parse_changelog()
    assert len(attempts) == 2


def test_successful_fetch_saves_the_text_and_clears_the_failure(
    monkeypatch: pytest.MonkeyPatch, isolated_changelog_state: Path
) -> None:
    monkeypatch.setattr(changelog_module, "_failure", (0.0, "old failure"))
    monkeypatch.setattr(changelog_module, "_fetch_remote_text", lambda: REMOTE_TEXT)
    entries = fetch_and_parse_changelog(force_refresh=True)
    assert [e.version for e in entries] == ["9.0.0"]
    assert isolated_changelog_state.read_text(encoding="utf-8") == REMOTE_TEXT
    assert changelog_module._failure is None


def test_fetch_succeeds_when_the_copy_cannot_be_saved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # a file where the folder should be, so the save fails
    blocker = tmp_path / "blocker"
    blocker.write_text("")
    monkeypatch.setattr(
        changelog_module, "CHANGELOG_CACHE_FILE", blocker / "changelog_cache.md"
    )
    monkeypatch.setattr(changelog_module, "_fetch_remote_text", lambda: REMOTE_TEXT)
    assert fetch_and_parse_changelog(force_refresh=True)[0].version == "9.0.0"


def test_zero_entry_page_is_a_failure_and_is_not_saved(
    monkeypatch: pytest.MonkeyPatch, isolated_changelog_state: Path
) -> None:
    monkeypatch.setattr(
        changelog_module, "_fetch_remote_text", lambda: "<html>captive portal</html>"
    )
    with pytest.raises(ValueError, match="zero entries"):
        fetch_and_parse_changelog(force_refresh=True)
    assert not isolated_changelog_state.exists()


def test_load_changelog_prefers_github(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(changelog_module, "_fetch_remote_text", lambda: REMOTE_TEXT)
    loaded = load_changelog()
    assert loaded is not None
    assert loaded.source == "remote"
    assert [e.version for e in loaded.entries] == ["9.0.0"]


def test_load_changelog_falls_back_to_the_saved_copy(
    monkeypatch: pytest.MonkeyPatch, isolated_changelog_state: Path
) -> None:
    isolated_changelog_state.write_text(CACHED_TEXT, encoding="utf-8")
    _fetch_fails(monkeypatch, TimeoutError("simulated network failure"))
    loaded = load_changelog()
    assert loaded is not None
    assert loaded.source == "cache"
    assert [e.version for e in loaded.entries] == ["8.0.0"]


def test_load_changelog_falls_back_to_the_bundled_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fetch_fails(monkeypatch, TimeoutError("simulated network failure"))
    loaded = load_changelog()
    assert loaded is not None
    assert loaded.source == "bundled"
    expected = parse_changelog(
        changelog_module.BUNDLED_CHANGELOG_FILE.read_text(encoding="utf-8")
    )
    assert loaded.entries == expected
    assert loaded.entries


def test_load_changelog_skips_an_empty_saved_copy(
    monkeypatch: pytest.MonkeyPatch, isolated_changelog_state: Path
) -> None:
    isolated_changelog_state.write_text("not a changelog", encoding="utf-8")
    _fetch_fails(monkeypatch, TimeoutError("simulated network failure"))
    loaded = load_changelog()
    assert loaded is not None
    assert loaded.source == "bundled"


def test_load_changelog_is_none_when_nothing_has_an_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        changelog_module, "BUNDLED_CHANGELOG_FILE", tmp_path / "missing.md"
    )
    _fetch_fails(monkeypatch, TimeoutError("simulated network failure"))
    assert load_changelog() is None


def test_load_changelog_serves_the_fallback_during_the_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = _fetch_fails(monkeypatch, TimeoutError("simulated network failure"))
    assert load_changelog() is not None
    loaded = load_changelog()
    assert loaded is not None
    assert loaded.source == "bundled"
    assert len(attempts) == 1


def test_load_changelog_logs_a_network_failure_as_one_line_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    reason = ssl.SSLCertVerificationError("certificate verify failed")
    _fetch_fails(monkeypatch, urllib.error.URLError(reason))
    with caplog.at_level(logging.DEBUG, logger=changelog_module.logger.name):
        load_changelog()
        load_changelog()
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].exc_info is None
    assert "certificate verify failed" in warnings[0].getMessage()


def test_load_changelog_keeps_the_traceback_for_a_parse_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(changelog_module, "_fetch_remote_text", lambda: "no versions")
    with caplog.at_level(logging.DEBUG, logger=changelog_module.logger.name):
        load_changelog()
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].exc_info is not None


def _cert_error() -> urllib.error.URLError:
    return urllib.error.URLError(
        ssl.SSLCertVerificationError("certificate verify failed")
    )


def test_fetch_retries_with_certifi_when_the_certificate_does_not_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    certifi_context = ssl.create_default_context()
    contexts: list[ssl.SSLContext | None] = []

    def _read(context: ssl.SSLContext | None) -> str:
        contexts.append(context)
        if context is None:
            raise _cert_error()
        return REMOTE_TEXT

    monkeypatch.setattr(changelog_module, "_read_url", _read)
    monkeypatch.setattr(changelog_module, "_certifi_context", lambda: certifi_context)
    assert changelog_module._fetch_remote_text() == REMOTE_TEXT
    assert contexts == [None, certifi_context]


def test_fetch_raises_the_certificate_error_when_certifi_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _read(context: ssl.SSLContext | None) -> str:
        raise _cert_error()

    monkeypatch.setattr(changelog_module, "_read_url", _read)
    monkeypatch.setattr(changelog_module, "_certifi_context", lambda: None)
    with pytest.raises(urllib.error.URLError):
        changelog_module._fetch_remote_text()


def test_fetch_does_not_retry_other_network_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contexts: list[ssl.SSLContext | None] = []

    def _read(context: ssl.SSLContext | None) -> str:
        contexts.append(context)
        raise urllib.error.URLError(OSError("network is unreachable"))

    monkeypatch.setattr(changelog_module, "_read_url", _read)
    monkeypatch.setattr(
        changelog_module, "_certifi_context", lambda: ssl.create_default_context()
    )
    with pytest.raises(urllib.error.URLError):
        changelog_module._fetch_remote_text()
    assert contexts == [None]


def test_certifi_context_loads_the_certifi_bundle() -> None:
    pytest.importorskip("certifi")
    context = changelog_module._certifi_context()
    assert context is not None
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.cert_store_stats()["x509_ca"] > 0
