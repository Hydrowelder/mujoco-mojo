from datetime import datetime
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from mujoco_mojo.settings import MujocoMojoSettings
from mujoco_mojo.utils.statusing import JOB_STATUS_FNAME, JobStatus, JobType

__all__ = ["CURRENT_JOB", "HERE", "set_globals", "static", "templates"]

HERE = Path(__file__).parent
WORKDIR: Path | None = None
CURRENT_JOB: JobStatus | None = None
AUTH_PASSWORD: str | None = None

# Chime sound comes from https://mixkit.co/free-sound-effects/win/
templates = Jinja2Templates(directory=HERE / "templates")
static = StaticFiles(directory=HERE / "templates" / "static")

# base.html reads this on every page (not just the routes that already build
# their own per-route context, e.g. mosaic.py's get_trial_viewer) to seed
# store.ts's isFullscreen default - registered as a callable, not a plain
# `update()` value like the ones in set_globals() below, since those are
# fixed once at job startup while this must reflect the current
# settings.toml on every render (e.g. right after the settings panel saves
# a change, with no server restart in between).
templates.env.globals["default_to_fullscreen"] = lambda: (
    MujocoMojoSettings().dojo.default_to_fullscreen
)

# same rationale as default_to_fullscreen above - read live on every render,
# only ever seed a browser's localStorage value the first time (see
# store.ts/trial-viewer.ts's own comments on the window.__mojoDefault*
# fallback pattern for why a value the user already set always wins).
templates.env.globals["default_hide_invalid_profiles"] = lambda: (
    MujocoMojoSettings().dojo.hide_invalid_profiles
)
templates.env.globals["default_profile_sort_mode"] = lambda: (
    MujocoMojoSettings().dojo.profile_sort_mode.value
)
templates.env.globals["default_profile_sort_dir"] = lambda: (
    MujocoMojoSettings().dojo.profile_sort_dir.value
)
templates.env.globals["default_hide_invalid_labs"] = lambda: (
    MujocoMojoSettings().dojo.hide_invalid_labs
)
templates.env.globals["default_lab_sort_mode"] = lambda: (
    MujocoMojoSettings().dojo.lab_sort_mode.value
)
templates.env.globals["default_lab_sort_dir"] = lambda: (
    MujocoMojoSettings().dojo.lab_sort_dir.value
)


def set_globals(workdir: Path, owner: str, job_type: JobType) -> None:
    global WORKDIR

    workdir = workdir.resolve()
    WORKDIR = workdir

    templates.env.globals.update(current_year=datetime.now().year)
    templates.env.globals.update(workdir_path=str(workdir))
    templates.env.globals.update(workdir_name=workdir.name)
    templates.env.globals.update(job_status_path=str(workdir / JOB_STATUS_FNAME))
    templates.env.globals.update(owner=owner)
    templates.env.globals.update(job_type=job_type)
    templates.env.globals.update(JobType=JobType)
