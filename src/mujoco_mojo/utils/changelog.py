"""
Fetches and parses mujoco-mojo's `CHANGELOG.md` into structured version entries, for Dojo's "What's Changed" footer button and for `scripts/verify_changelog_by_tag.py`'s pre-push check - one parser, so the two can't drift apart.

The changelog is read live from GitHub. `fetch_and_parse_changelog` raises when that fails, and `load_changelog` is the caller that never leaves Dojo empty-handed: it falls back to the last copy it fetched successfully (saved under `~/.mujoco-mojo`), then to the changelog that ships inside the package, and says which one it used.
"""

from __future__ import annotations

import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from mujoco_mojo.meta import DOCS_SOURCE_DIR, MUJOCO_MOJO_DIR
from mujoco_mojo.utils.log import get_logger

__all__ = [
    "BUNDLED_CHANGELOG_FILE",
    "CHANGELOG_CACHE_FILE",
    "CHANGELOG_URL",
    "ChangelogEntry",
    "ChangelogSource",
    "ChangelogUnavailable",
    "LoadedChangelog",
    "fetch_and_parse_changelog",
    "load_changelog",
    "parse_changelog",
    "read_last_seen_version",
    "version_tuple",
    "write_last_seen_version",
]

logger = get_logger(__name__)

CHANGELOG_URL = "https://raw.githubusercontent.com/Hydrowelder/mujoco-mojo/refs/heads/master/CHANGELOG.md"

LAST_SEEN_VERSION_FILE = MUJOCO_MOJO_DIR / "last_seen_changelog_version.txt"
"""The latest changelog version the user has explicitly acknowledged (by closing the What's Changed modal on it). Read fresh on every `GET /changelog/data` request, not cached in memory, so a mark-seen write takes effect immediately - both for a later page load in the same Dojo process and across a full restart of it."""

CHANGELOG_CACHE_FILE = MUJOCO_MOJO_DIR / "changelog_cache.md"
"""The last changelog fetched successfully from GitHub, kept as the raw text so a later parser change still reads it. `load_changelog` falls back to it, marked as possibly out of date, when GitHub can't be reached."""

BUNDLED_CHANGELOG_FILE = DOCS_SOURCE_DIR / "docs" / "changelog.md"
"""The changelog that ships inside the package, as of the installed version. The last resort for a host that has never reached GitHub, so it can't know about any newer release."""

_FETCH_TIMEOUT_SECONDS = 5.0
_CACHE_TTL_SECONDS = 30 * 60.0
"""How long a successful fetch is reused before refetching - long enough that several tabs opened in one sitting don't each hit GitHub, short enough to notice a same-day release without restarting Dojo."""
_RETRY_AFTER_SECONDS = 5 * 60.0
"""How long a failed fetch is waited out before `fetch_and_parse_changelog` tries GitHub again, so a host that can't reach it doesn't spend the full timeout (and log a failure) on every page load."""

ChangelogSource = Literal["remote", "cache", "bundled"]
"""Where `load_changelog`'s entries came from: GitHub just now, the copy saved from an earlier fetch, or the changelog that ships with the installed package."""

_HEADING_RE = re.compile(
    r"^##\s+Version\s+(?P<version>\d+\.\d+\.\d+)\s*\((?P<date>[^)]*)\)",
    re.MULTILINE,
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VERSION_PREFIX_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


class ChangelogEntry(BaseModel):
    """One `## Version X.Y.Z (YYYY-MM-DD)` section of the changelog."""

    version: str
    date: str | None
    bullets: list[str]
    """Each top-level `- ` bullet, its marker included, with any of its indented sub-bullets appended as-is - a small, self-contained (possibly nested) markdown list per entry."""


def version_tuple(v: str) -> tuple[int, int, int]:
    """The leading `X.Y.Z` as an int triple, for `>` comparison. A dev-build suffix (e.g. `2.6.11.dev3+g1234abc`) is ignored past the prefix; a string with no such prefix degrades to `(0, 0, 0)` rather than raising, since this never needs to be exact, only ordered."""
    m = _VERSION_PREFIX_RE.match(v)
    if not m:
        return (0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def parse_changelog(text: str) -> list[ChangelogEntry]:
    """Splits `text` into one `ChangelogEntry` per `## Version X.Y.Z (date)` heading, newest first (the file's own order). A malformed date (this repo's own `CHANGELOG.md` has one, a typo'd 5-digit year) does not fail the entry - it becomes `date=None`, with the version and bullets unaffected."""
    headings = list(_HEADING_RE.finditer(text))
    entries: list[ChangelogEntry] = []
    for i, m in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        raw_date = m.group("date").strip()
        entries.append(
            ChangelogEntry(
                version=m.group("version"),
                date=raw_date if _DATE_RE.match(raw_date) else None,
                bullets=_parse_bullets(text[m.end() : end]),
            )
        )
    return entries


def _parse_bullets(body: str) -> list[str]:
    bullets: list[str] = []
    for line in body.splitlines():
        if line.startswith("- "):
            bullets.append(line)
        elif bullets and line[:1].isspace() and line.strip().startswith("-"):
            bullets[-1] += "\n" + line
        # blank lines and stray prose between headings are dropped
    return bullets


def _read_url(context: ssl.SSLContext | None) -> str:
    req = urllib.request.Request(
        CHANGELOG_URL, headers={"User-Agent": "mujoco-mojo-dojo"}
    )
    with urllib.request.urlopen(
        req, timeout=_FETCH_TIMEOUT_SECONDS, context=context
    ) as resp:
        if resp.status != 200:
            raise ValueError(f"Fetching {CHANGELOG_URL} returned status {resp.status}")
        body: bytes = resp.read()
        return body.decode("utf-8")


def _certifi_context() -> ssl.SSLContext | None:
    """A context that trusts certifi's CA bundle, or `None` when certifi isn't installed (it is not a dependency of Mojo itself, only of the extras)."""
    try:
        import certifi
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _fetch_remote_text() -> str:
    """Reads the changelog with the interpreter's own trust store, and only if that can't verify GitHub's certificate, once more with certifi's. The system store goes first so a host behind a TLS-intercepting proxy, whose CA lives there, keeps working. `SSL_CERT_FILE` and `SSL_CERT_DIR` are honored by the default context already."""
    try:
        return _read_url(None)
    except urllib.error.URLError as exc:
        if not isinstance(exc.reason, ssl.SSLCertVerificationError):
            raise
        context = _certifi_context()
        if context is None:
            raise
        logger.info(
            "The interpreter's certificates did not verify GitHub, retrying with certifi's"
        )
        return _read_url(context)


def _describe(exc: BaseException) -> str:
    """One line for a log or an error message: a network error's reason (`certificate verify failed ...`) rather than urllib's wrapper around it."""
    if isinstance(exc, urllib.error.URLError) and not isinstance(
        exc, urllib.error.HTTPError
    ):
        return str(exc.reason)
    return str(exc) or type(exc).__name__


class ChangelogUnavailable(RuntimeError):
    """Raised by `fetch_and_parse_changelog`, without a network request, while a recent failure is still being waited out. The message is that failure's own."""


_cache: tuple[float, list[ChangelogEntry]] | None = None
_failure: tuple[float, str] | None = None
_cache_lock = threading.Lock()


def fetch_and_parse_changelog(*, force_refresh: bool = False) -> list[ChangelogEntry]:
    """
    Fetches `CHANGELOG_URL` and parses it, reusing a successful result for `_CACHE_TTL_SECONDS`.

    Synchronous by design, so it and everything it calls stay plain-function testable with no async test infra (this repo has none); call it from an async endpoint via `starlette.concurrency.run_in_threadpool`.

    Raises on any failure - a network error, a timeout, a non-200 response, or a 200 that parses to zero entries (a captive-portal page would otherwise look like an empty changelog instead of a failure). After a failure the next calls raise `ChangelogUnavailable` for `_RETRY_AFTER_SECONDS` without touching the network, unless `force_refresh` is set. A success also saves the text to `CHANGELOG_CACHE_FILE` for `load_changelog`'s fallback.
    """
    global _cache, _failure
    now = time.monotonic()
    with _cache_lock:
        if (
            not force_refresh
            and _cache is not None
            and now - _cache[0] < _CACHE_TTL_SECONDS
        ):
            return _cache[1]
        if (
            not force_refresh
            and _failure is not None
            and now - _failure[0] < _RETRY_AFTER_SECONDS
        ):
            raise ChangelogUnavailable(_failure[1])
        try:
            text = _fetch_remote_text()
            entries = parse_changelog(text)
            if not entries:
                raise ValueError(
                    "Remote changelog fetched successfully but parsed to zero entries"
                )
        except Exception as exc:
            _failure = (time.monotonic(), _describe(exc))
            raise
        _failure = None
        _cache = (now, entries)
        _save_cache_text(text)
        return entries


def _save_cache_text(text: str) -> None:
    """Best effort: a read-only home just means no saved copy, never a failed request. Written to a sibling file and moved into place, so a second Dojo process never reads half a file."""
    tmp = CHANGELOG_CACHE_FILE.with_name(CHANGELOG_CACHE_FILE.name + ".tmp")
    try:
        CHANGELOG_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(CHANGELOG_CACHE_FILE)
    except OSError:
        logger.debug("Couldn't save the changelog copy", exc_info=True)


def _parse_file(path: Path) -> list[ChangelogEntry]:
    """The entries in `path`, or none if it's missing, unreadable or has no version headings."""
    try:
        return parse_changelog(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return []


class LoadedChangelog(BaseModel):
    entries: list[ChangelogEntry]
    source: ChangelogSource


def load_changelog() -> LoadedChangelog | None:
    """
    The changelog from the best place available, newest entry first: GitHub (`fetch_and_parse_changelog`), else the copy saved by the last successful fetch, else the changelog that ships in the package. `source` says which, so a caller can tell the user a copy may be out of date. Returns `None` only if none of the three has an entry.

    A network failure is one warning line, not a traceback, and a failure still being waited out is not logged again. Any other failure (a bad status, a page with no versions) keeps its traceback.
    """
    try:
        return LoadedChangelog(entries=fetch_and_parse_changelog(), source="remote")
    except ChangelogUnavailable:
        pass
    except OSError as exc:
        logger.warning(
            "Couldn't fetch the remote changelog (%s), using a saved copy",
            _describe(exc),
        )
    except Exception:
        logger.warning(
            "Failed to fetch/parse the remote changelog, using a saved copy",
            exc_info=True,
        )
    entries = _parse_file(CHANGELOG_CACHE_FILE)
    if entries:
        return LoadedChangelog(entries=entries, source="cache")
    entries = _parse_file(BUNDLED_CHANGELOG_FILE)
    if entries:
        return LoadedChangelog(entries=entries, source="bundled")
    return None


def read_last_seen_version() -> str | None:
    """The version last written by `write_last_seen_version`, or `None` if the user has never acknowledged one (a first-ever launch of this feature, or a fresh `~/.mujoco-mojo`)."""
    try:
        text = LAST_SEEN_VERSION_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return text or None


def write_last_seen_version(version: str) -> None:
    """Persists `version` as acknowledged, so it (and everything older) stops being flagged `is_new` and stops triggering the modal's auto-open, on this and every future launch, until a genuinely newer version appears."""
    LAST_SEEN_VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_SEEN_VERSION_FILE.write_text(version.strip() + "\n", encoding="utf-8")
