from datetime import datetime
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from mujoco_mojo.utils.statusing import JobStatus

__all__ = ["CURRENT_JOB", "HERE", "set_globals", "static", "templates"]

HERE = Path(__file__).parent
WORKDIR: Path | None = None
CURRENT_JOB: JobStatus | None = None

# Chime sound comes from https://mixkit.co/free-sound-effects/win/
templates = Jinja2Templates(directory=HERE / "templates")
static = StaticFiles(directory=HERE / "templates" / "static")


def set_globals(workdir: Path, owner: str) -> None:
    global WORKDIR

    workdir = workdir.resolve()
    WORKDIR = workdir

    templates.env.globals.update(current_year=datetime.now().year)
    templates.env.globals.update(workdir_path=str(workdir))
    templates.env.globals.update(workdir_name=workdir.name)
    templates.env.globals.update(owner=owner)
