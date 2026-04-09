import socket
from functools import lru_cache

import duckdb
from fastapi import APIRouter, HTTPException, Query, Request
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
        request=request, name="mosaic.html", context={"request": request}
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

    if not job:
        raise HTTPException(status_code=404, detail="No active job found.")

    server_ip = get_network_ip()
    port = request.url.port or 8000

    # 1. Get the sorted list of all trials that actually have data
    from mujoco_mojo.runtime.results_manager import ResultsManager

    valid_ids = []
    for tn in job.trial_nums:
        path = job.trial_num_to_path(tn)
        if (path / ResultsManager.default_db_name()).exists():
            valid_ids.append(path.name)

    if trial_id not in valid_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Trial '{trial_id}' does not exist or has no telemetry data.",
        )

    # 2. Find the neighbors of the current trial_id
    idx = valid_ids.index(trial_id)
    prev_id = valid_ids[idx - 1] if idx > 0 else None
    next_id = valid_ids[idx + 1] if idx < len(valid_ids) - 1 else None

    return shared.templates.TemplateResponse(
        request=request,
        name="trial_viewer.html",
        context={
            "request": request,
            "trial_id": trial_id,
            "prev_id": prev_id,
            "next_id": next_id,
            "external_url": f"http://{server_ip}:{port}",
        },
    )


@lru_cache(maxsize=128)
def _get_column_manifest(db_path_str: str, mtime: float) -> list[str]:
    """Retrieves all column names from the DuckDB table schema."""
    from mujoco_mojo.runtime.results_manager import ResultsManager

    with duckdb.connect(db_path_str, read_only=True) as con:
        # 'DESCRIBE' is a very fast metadata-only query in DuckDB
        table = ResultsManager.default_table_name()
        res = con.execute(f"DESCRIBE {table}").fetchall()
        # res returns rows like: (column_name, type, null, key, default, extra)
        return [row[0] for row in res]


@lru_cache(maxsize=2048)  # Increased size because we are caching individual columns
def _get_atomic_column(db_path_str: str, col_name: str, mtime: float):
    """
    Fetches a single column. 'mtime' is the cache-breaker. If the file changes, the mtime changes, triggering a fresh read even if the path and column name are the same.
    """
    from mujoco_mojo.runtime.results_manager import ResultsManager

    with duckdb.connect(db_path_str, read_only=True) as con:
        table = ResultsManager.default_table_name()
        # Fetching a single column is DuckDB's superpower
        return (
            con.execute(f'SELECT "{col_name}" FROM {table}').pl().to_series().to_list()
        )


@router.get("/{trial_id}/data")
async def get_trial_data(trial_id: str, cols: str = Query(None)):
    """
    Connects to the specific trial's DuckDB.
    'cols' is an optional comma-separated string of column names.
    """
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

    # THE CACHE BREAKER: Get the file's last modified time
    # If you restart a job, the new file will have a new mtime.
    mtime = db_path.stat().st_mtime

    try:
        db_path_str = str(db_path)

        # get the manifest of ALL columns in the df
        all_columns = _get_column_manifest(db_path_str, mtime)

        data = {}
        if cols:
            requested = cols.split(",")
            for col in requested:
                if col in all_columns:
                    data[col] = _get_atomic_column(db_path_str, col, mtime)

        return {
            "columns": all_columns,  # Full list of headers for the sidebar
            "data": data,  # Actual arrays for the requested traces
        }

    except Exception as e:
        logger.error(f"Data retrieval failed for {trial_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
