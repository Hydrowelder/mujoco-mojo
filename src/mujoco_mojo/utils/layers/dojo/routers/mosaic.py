from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from mujoco_mojo.utils.log import get_logger

from .. import shared

logger = get_logger(__name__)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_mosaic(request: Request):
    """Serves the initial mosiac frame."""
    return shared.templates.TemplateResponse(
        name="mosaic.html", context={"request": request}
    )


@router.get("/api/trials")
async def get_valid_trials():
    """Scans the workdir for folders containing 'telemetry.duckdb'"""
    job = shared.CURRENT_JOB

    if job is None:
        logger.warning("Mosaic accessed but CURRENT_JOB is None.")
        return {"trials": []}

    valid_trials = []

    for tn in job.trial_nums:
        trial_dir = job.trial_num_to_path(tn)

        # if there is a db and the trial is actually done
        if (trial_dir / "telemetry.duckdb").exists() and tn in job._cache:
            valid_trials.append(trial_dir.name)

    valid_trials.sort()

    return {"trials": valid_trials}


@router.get("/{trial_id}", response_class=HTMLResponse)
async def get_trail_viewer(request: Request, trial_id: str):
    """Land here when clicking a trial."""
    return shared.templates.TemplateResponse(
        name="trial_viewer.html", context={"request": request, "trial_id": trial_id}
    )
