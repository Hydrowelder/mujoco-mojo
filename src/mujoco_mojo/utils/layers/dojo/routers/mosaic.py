import socket

import duckdb
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from mujoco_mojo.utils.log import get_logger

from .. import shared

logger = get_logger(__name__)

router = APIRouter()


def get_network_ip():
    """Detects the primary local network IP of the host machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually have to be reachable; just triggers IP selection
        s.connect(("8.8.8.8", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "localhost"
    finally:
        s.close()
    return ip


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
async def get_trial_viewer(request: Request, trial_id: str):
    """Land here when clicking a trial."""
    job = shared.CURRENT_JOB
    prev_id = None
    next_id = None

    server_ip = get_network_ip()
    port = request.url.port or 8000

    if job:
        # 1. Get the sorted list of all trials that actually have data
        from mujoco_mojo.runtime.results_manager import ResultsManager

        valid_ids = []
        for tn in job.trial_nums:
            path = job.trial_num_to_path(tn)
            if (path / ResultsManager.default_db_name()).exists():
                valid_ids.append(path.name)

        # 2. Find the neighbors of the current trial_id
        try:
            idx = valid_ids.index(trial_id)
            if idx > 0:
                prev_id = valid_ids[idx - 1]
            if idx < len(valid_ids) - 1:
                next_id = valid_ids[idx + 1]
        except ValueError:
            pass

    return shared.templates.TemplateResponse(
        name="trial_viewer.html",
        context={
            "request": request,
            "trial_id": trial_id,
            "prev_id": prev_id,
            "next_id": next_id,
            "external_url": f"http://{server_ip}:{port}",
        },
    )


@router.get("/{trial_id}/data")
async def get_trial_data(trial_id: str):
    """Connects to the specific trial's DuckDB and returns all telemetry."""
    from mujoco_mojo.runtime.results_manager import ResultsManager

    job = shared.CURRENT_JOB
    if not job:
        raise HTTPException(status_code=404, detail="No job active")

    db_path = (
        job.workdir / "trials" / trial_id / ResultsManager.default_db_name()
    ).resolve()

    if not db_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Database not found for {trial_id}"
        )

    try:
        # DuckDB's .pl() execution is zero-copy where possible
        with duckdb.connect(str(db_path), read_only=True) as con:
            query = f"SELECT * FROM {ResultsManager.default_table_name()}"
            df = con.execute(query).pl()

            # Polars conversion to Dict of Lists (Plotly format)
            return df.to_dict(as_series=False)

    except Exception as e:
        logger.error(f"Data retrieval failed for {trial_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read telemetry data")
