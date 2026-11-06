import ipaddress
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from mujoco_mojo.settings import MujocoMojoSettings
from mujoco_mojo.utils.statusing import JOB_STATUS_FNAME, JobStatus, JobType

__all__ = [
    "CURRENT_JOB",
    "HERE",
    "VITE_DEV",
    "asset_url",
    "is_localhost",
    "set_globals",
    "static",
    "template_globals",
    "templates",
]

HERE = Path(__file__).parent
TS_DIR = HERE / "templates" / "static" / "ts"
WORKDIR: Path | None = None
CURRENT_JOB: JobStatus | None = None
AUTH_PASSWORD: str | None = None

# the env var MOJO_DOJO_DEV (set by scripts/dev_dojo.sh) points the templates at the
# TypeScript sources a running Vite dev server serves instead of the built files, so a
# frontend edit needs no rebuild. read once at import: whether it is set can't change
# without a process restart.
VITE_DEV = os.environ.get("MOJO_DOJO_DEV", "").lower() in {"1", "true", "yes"}

# Chime sound comes from https://mixkit.co/free-sound-effects/win/
templates = Jinja2Templates(directory=HERE / "templates")
static = StaticFiles(directory=HERE / "templates" / "static")

# the same dict as `templates.env.globals`, typed for what it holds: jinja2 builds that dict from
# an unannotated literal of its own helpers, so a type checker infers a value type that
# rejects every global registered here
template_globals: dict[str, Any] = templates.env.globals

# base.html reads this on every page (not just the routes that already build
# their own per-route context, e.g. mosaic.py's get_trial_viewer) to seed
# store.ts's isFullscreen default - registered as a callable, not a plain
# `update()` value like the ones in set_globals() below, since those are
# fixed once at job startup while this must reflect the current
# settings.toml on every render (e.g. right after the settings panel saves
# a change, with no server restart in between).
template_globals["default_to_fullscreen"] = lambda: (
    MujocoMojoSettings().dojo.default_to_fullscreen
)

# same rationale as default_to_fullscreen above - read live on every render,
# only ever seed a browser's localStorage value the first time (see
# store.ts/trial-viewer.ts's own comments on the window.__mojoDefault*
# fallback pattern for why a value the user already set always wins).
template_globals["default_hide_invalid_profiles"] = lambda: (
    MujocoMojoSettings().dojo.hide_invalid_profiles
)
template_globals["default_profile_sort_mode"] = lambda: (
    MujocoMojoSettings().dojo.profile_sort_mode.value
)
template_globals["default_profile_sort_dir"] = lambda: (
    MujocoMojoSettings().dojo.profile_sort_dir.value
)
template_globals["default_hide_invalid_labs"] = lambda: (
    MujocoMojoSettings().dojo.hide_invalid_labs
)
template_globals["default_lab_sort_mode"] = lambda: (
    MujocoMojoSettings().dojo.lab_sort_mode.value
)
template_globals["default_lab_sort_dir"] = lambda: (
    MujocoMojoSettings().dojo.lab_sort_dir.value
)


def asset_url(name: str) -> str:
    """The URL a template loads a built frontend file from: `/mojo-static/dist/<name>`, or the TypeScript or CSS source Vite serves for it when `MOJO_DOJO_DEV` is set. `name` is a key of `ts/entries.json`, the list `vite.config.ts` builds from too, so an unknown name raises `KeyError` in dev."""
    if not VITE_DEV:
        return f"/mojo-static/dist/{name}"
    entries: dict[str, str] = json.loads((TS_DIR / "entries.json").read_text())
    return f"/{entries[name]}"


# base.html and the page templates build their <script>/<link> URLs with asset(), and
# add Vite's client (what reloads the page on an edit) when vite_dev is set
template_globals["asset"] = asset_url
template_globals["vite_dev"] = VITE_DEV


def is_localhost(request: Request) -> bool:
    """Whether the request's direct TCP peer is the loopback interface, regardless of which interface the server itself is bound to. Shared by every router that gates a write behind "only from the machine running Dojo" (settings, and the What's Changed toggle)."""
    host = request.client.host if request.client else None
    if host is None:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def set_globals(workdir: Path, owner: str, job_type: JobType) -> None:
    global WORKDIR

    workdir = workdir.resolve()
    WORKDIR = workdir

    template_globals.update(current_year=datetime.now().year)
    template_globals.update(workdir_path=str(workdir))
    template_globals.update(workdir_name=workdir.name)
    template_globals.update(job_status_path=str(workdir / JOB_STATUS_FNAME))
    template_globals.update(owner=owner)
    template_globals.update(job_type=job_type)
    template_globals.update(JobType=JobType)
