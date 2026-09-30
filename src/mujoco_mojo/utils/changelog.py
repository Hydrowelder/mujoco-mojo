"""
Fetches and parses mujoco-mojo's `CHANGELOG.md` into structured version entries, for Dojo's "What's Changed" footer button and for `scripts/verify_changelog_by_tag.py`'s pre-push check - one parser, so the two can't drift apart.

The changelog is always read live from GitHub; there is no local-file fallback, so a fetch failure is just an error the caller surfaces, the same way any other failed request already is.
"""

from __future__ import annotations

import re
import threading
import time
import urllib.request

from pydantic import BaseModel

from mujoco_mojo.meta import MUJOCO_MOJO_DIR
from mujoco_mojo.utils.log import get_logger

__all__ = [
    "CHANGELOG_URL",
    "ChangelogEntry",
    "fetch_and_parse_changelog",
    "parse_changelog",
    "read_last_seen_version",
    "version_tuple",
    "write_last_seen_version",
]

logger = get_logger(__name__)

CHANGELOG_URL = "https://raw.githubusercontent.com/Hydrowelder/mujoco-mojo/refs/heads/master/CHANGELOG.md"

LAST_SEEN_VERSION_FILE = MUJOCO_MOJO_DIR / "last_seen_changelog_version.txt"
"""The latest changelog version the user has explicitly acknowledged (by closing the What's Changed modal on it). Read fresh on every `GET /changelog/data` request, not cached in memory, so a mark-seen write takes effect immediately - both for a later page load in the same Dojo process and across a full restart of it."""

_FETCH_TIMEOUT_SECONDS = 5.0
_CACHE_TTL_SECONDS = 30 * 60.0
"""How long a successful fetch is reused before refetching - long enough that several tabs opened in one sitting don't each hit GitHub, short enough to notice a same-day release without restarting Dojo."""

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


def _fetch_remote_text() -> str:
    req = urllib.request.Request(
        CHANGELOG_URL, headers={"User-Agent": "mujoco-mojo-dojo"}
    )
    with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT_SECONDS) as resp:
        if resp.status != 200:
            raise ValueError(f"Fetching {CHANGELOG_URL} returned status {resp.status}")
        return resp.read().decode("utf-8")


_cache: tuple[float, list[ChangelogEntry]] | None = None
_cache_lock = threading.Lock()


def fetch_and_parse_changelog(*, force_refresh: bool = False) -> list[ChangelogEntry]:
    """
    Fetches `CHANGELOG_URL` and parses it, reusing a successful result for `_CACHE_TTL_SECONDS`.

    Synchronous by design, so it and everything it calls stay plain-function testable with no async test infra (this repo has none); call it from an async endpoint via `starlette.concurrency.run_in_threadpool`.

    Raises on any failure - a network error, a timeout, a non-200 response, or a 200 that parses to zero entries (a captive-portal page would otherwise look like an empty changelog instead of a failure). A failure is not cached, so the next call retries.
    """
    global _cache
    now = time.monotonic()
    with _cache_lock:
        if (
            not force_refresh
            and _cache is not None
            and now - _cache[0] < _CACHE_TTL_SECONDS
        ):
            return _cache[1]
        entries = parse_changelog(_fetch_remote_text())
        if not entries:
            raise ValueError(
                "Remote changelog fetched successfully but parsed to zero entries"
            )
        _cache = (now, entries)
        return entries


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
