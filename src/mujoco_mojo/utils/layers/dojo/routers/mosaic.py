import socket
from functools import lru_cache

import polars as pl
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from mujoco_mojo.utils.dataframe import ColumnManifest, MojoDataFrame
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
    """Scans the workdir for folders containing 'telemetry.parquet'"""
    job = shared.CURRENT_JOB
    from mujoco_mojo.runtime.signal_manager import SignalManager

    if job is None:
        logger.warning("Mosaic accessed but CURRENT_JOB is None.")
        return {"trials": []}

    valid_trials = []

    for tn in job.trial_nums:
        trial_dir = job.trial_num_to_path(tn)

        # if there is a db and the trial is actually done
        if (
            trial_dir / SignalManager.default_output_name()
        ).exists() and tn in job._cache:
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
    from mujoco_mojo.runtime.signal_manager import SignalManager

    valid_ids = []
    for tn in job.trial_nums:
        path = job.trial_num_to_path(tn)
        if (path / SignalManager.default_output_name()).exists():
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
def _get_column_manifest(path_str: str, mtime: float) -> ColumnManifest:
    """Retrieves all column names from the table schema."""
    return MojoDataFrame.from_metadata(path_str).mojo.get_manifest()


@lru_cache(maxsize=2048)
def _get_atomic_column(path_str: str, col_name: str, mtime: float):
    """
    Fetches a single column. 'mtime' is the cache-breaker. If the file changes, the mtime changes, triggering a fresh read even if the path and column name are the same.
    """
    return pl.scan_parquet(path_str).select(col_name).collect().to_series().to_list()


@router.get("/{trial_id}/data")
async def get_trial_data(
    trial_id: str, cols: str = Query(None), rotate_by: str = Query(None)
):
    """
    Loops over the columns in the trial_id provided and returns their data. Optionally performs a rotation if requested and there are an associated x, y, and z column.

    Args:
        trial_id (str): Trial to search (e.g. `"trial_001"`).
        cols (str, optional): Comma separated list of column names to return data for (e.g. `"/Bodies/body1/xpos:x,/Bodies/body2/xpos:m"`). Defaults to Query(None).
        rotate_by (str, optional): Quaternion family to rotate vectors by (e.g. `"/Bodies/body1/quat"`). Defaults to Query(None).

    Raises:
        HTTPException: Raised if no shared.CURRENT_JOB was set.
        HTTPException: Raised if the database path for the trial was found.
        HTTPException: Raised if an error occured while extracting data from the database.

    Returns:
        dict: Dictionary containing split columns and their associated data.

    """
    from mujoco_mojo.runtime.signal_manager import SignalManager

    job = shared.CURRENT_JOB
    if not job:
        raise HTTPException(status_code=404, detail="No job active")

    db_path = (
        job.workdir / "trials" / trial_id / SignalManager.default_output_name()
    ).resolve()

    if not db_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Database not found for {trial_id}"
        )

    # use the files last modified time as a cache breaker
    mtime = db_path.stat().st_mtime
    db_path_str = str(db_path)

    # get the manifest of ALL columns in the df
    column_manifest = _get_column_manifest(db_path_str, mtime)

    try:
        requested = cols.split(",") if cols else []
        available_cols = set(column_manifest["all"])

        # determine columns to request
        fetch_targets = [c for c in requested if c in available_cols]

        if rotate_by:
            q_family = [
                f"{rotate_by}:x",
                f"{rotate_by}:y",
                f"{rotate_by}:z",
                f"{rotate_by}:w",
            ]
            for q in q_family:
                if q in available_cols and q not in fetch_targets:
                    fetch_targets.append(q)

        # early exit for no found columns
        if not fetch_targets:
            return {"columns": column_manifest, "data": {}}

        # assemble dataframe
        raw_data = {
            col: _get_atomic_column(db_path_str, col, mtime) for col in fetch_targets
        }
        df = MojoDataFrame.from_dict(raw_data)

        if rotate_by:
            # rotate from world to rotate_by frame
            df = df.mojo.with_rotation(quat_base=rotate_by, invert=True)

        data = {col: df[col].to_list() for col in requested if col in df.columns}

        return {
            "columns": column_manifest,  # Full list of headers for the sidebar
            "data": data,  # Actual arrays for the requested traces
        }

    except Exception as e:
        logger.error(f"Data retrieval failed for {trial_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
