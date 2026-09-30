"""Changelog API for the Dojo footer's "What's Changed" button."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

import mujoco_mojo.utils.layers.dojo.shared as shared
from mujoco_mojo.__about__ import __version__
from mujoco_mojo.settings import MujocoMojoSettings
from mujoco_mojo.utils.changelog import (
    ChangelogEntry,
    fetch_and_parse_changelog,
    read_last_seen_version,
    version_tuple,
    write_last_seen_version,
)
from mujoco_mojo.utils.log import get_logger

router = APIRouter()

logger = get_logger(__name__)


class ChangelogEntryOut(ChangelogEntry):
    is_new: bool
    """Whether this entry's version is newer than the last version the user explicitly acknowledged (see `POST /mark-seen`)."""


class ChangelogResponse(BaseModel):
    entries: list[ChangelogEntryOut]
    installed_version: str
    latest_version: str | None
    """The newest version named in the changelog, or None if it couldn't be fetched."""
    update_available: bool
    """Whether `latest_version` is newer than `installed_version` - independent of `is_new`/acknowledgment, and true across restarts until the user actually upgrades."""
    show_whats_changed: bool
    is_localhost: bool
    """Whether this request came from the machine running Dojo - the What's Changed toggle only writes to settings.toml when this is true, same restriction as the Settings panel."""
    error: str | None = None


@router.get("/data")
async def get_changelog_data(request: Request) -> ChangelogResponse:
    try:
        entries_in = await run_in_threadpool(fetch_and_parse_changelog)
        error = None
    except Exception:
        logger.warning("Failed to fetch/parse the remote changelog", exc_info=True)
        entries_in, error = [], "Couldn't load the changelog from GitHub right now."

    # read fresh every request, not cached in memory: a mark-seen write
    # (below) then takes effect immediately, for a later page load in this
    # same Dojo process and across a full restart of it, with no separate
    # per-session bookkeeping needed on either end
    seen = await run_in_threadpool(read_last_seen_version)
    baseline = version_tuple(seen or __version__)
    entries = [
        ChangelogEntryOut(
            **entry.model_dump(), is_new=version_tuple(entry.version) > baseline
        )
        for entry in entries_in
    ]
    latest_version = entries_in[0].version if entries_in else None  # newest-first
    return ChangelogResponse(
        entries=entries,
        installed_version=__version__,
        latest_version=latest_version,
        update_available=latest_version is not None
        and version_tuple(latest_version) > version_tuple(__version__),
        show_whats_changed=MujocoMojoSettings().dojo.show_whats_changed,
        is_localhost=shared.is_localhost(request),
        error=error,
    )


class MarkSeenRequest(BaseModel):
    version: str


@router.post("/mark-seen")
async def mark_changelog_seen(body: MarkSeenRequest) -> dict[str, str]:
    """Acknowledges `body.version` (the modal's own `latest_version`, echoed back on close), so it and everything older stop being flagged `is_new` and stop triggering the auto-open, on this launch and every future one, until a genuinely newer version appears."""
    await run_in_threadpool(write_last_seen_version, body.version)
    return {"status": "ok"}
