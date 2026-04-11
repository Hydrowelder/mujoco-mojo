import socket
from functools import lru_cache
from typing import TypedDict

import duckdb
import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from scipy.spatial.transform import Rotation as R

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


class ColumnManifest(TypedDict):
    all: list[str]
    rotateable_vectors: list[str]
    available_quats: list[str]


@lru_cache(maxsize=128)
def _get_column_manifest(db_path_str: str, mtime: float) -> ColumnManifest:
    """Retrieves all column names from the DuckDB table schema."""
    from mujoco_mojo.runtime.results_manager import ResultsManager

    with duckdb.connect(db_path_str, read_only=True) as con:
        # 'DESCRIBE' is a very fast metadata-only query in DuckDB
        table = ResultsManager.default_table_name()
        res = con.execute(f"DESCRIBE {table}").fetchall()
        # res returns rows like: (column_name, type, null, key, default, extra)
    real_cols: list[str] = [row[0] for row in res]

    # Map prefixes to the total set of suffixes they possess
    prefix_map: dict[str, set[str]] = {}
    for c in real_cols:
        if ":" in c:
            prefix, suffix = c.rsplit(":", 1)
            prefix_map.setdefault(prefix, set()).add(suffix)

    # Strict set comparison ensures quaternions and vectors are disjoint
    # A quaternion (w,x,y,z) will not match {"x", "y", "z"}
    rotateable_vectors = [
        p for p, s in prefix_map.items() if {"x", "y", "z"}.issubset(s) and "w" not in s
    ]

    available_quats = [
        p for p, s in prefix_map.items() if {"w", "x", "y", "z"}.issubset(s)
    ]

    return {
        "all": real_cols,
        "rotateable_vectors": sorted(rotateable_vectors),
        "available_quats": sorted(available_quats),
    }


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
    db_path_str = str(db_path)

    # get the manifest of ALL columns in the df
    column_manifest = _get_column_manifest(db_path_str, mtime)

    try:
        data = {}
        requested = cols.split(",") if cols else []

        col_set = set(column_manifest["all"])

        # primary data fetch
        for col in requested:
            if col in col_set:
                data[col] = _get_atomic_column(db_path_str, col, mtime)

        # rotate vector is possible
        if rotate_by:
            q_family = [
                f"{rotate_by}:x",
                f"{rotate_by}:y",
                f"{rotate_by}:z",
                f"{rotate_by}:w",
            ]

            if not all(q in col_set for q in q_family):
                logger.warning(
                    f"Incomplete quaternion family for: {trial_id} {rotate_by}"
                )
            else:
                # load quat data (N, 4)
                qs = np.column_stack(
                    [_get_atomic_column(db_path_str, q, mtime) for q in q_family]
                )
                rot_transformer = R.from_quat(qs).inv()

                # identify vector families in the requested cols
                vec_prefixes = set(
                    c.rsplit(":", 1)[0]
                    for c in requested
                    if any(c.endswith(s) for s in [":x", ":y", ":z"])
                )

                for prefix in vec_prefixes:
                    f_family = [f"{prefix}:x", f"{prefix}:y", f"{prefix}:z"]

                    if all(v in col_set for v in f_family):
                        # Load the 3D vectors (N, 3)
                        vs = np.column_stack(
                            [
                                _get_atomic_column(db_path_str, v, mtime)
                                for v in f_family
                            ]
                        )

                        # 5. Apply the rotation to the entire array at once
                        raw_sample = vs[-1]
                        v_rot = rot_transformer.apply(vs)
                        rot_sample = v_rot[-1]

                        logger.debug(f"ROTATION CHECK [{prefix}]:")
                        logger.debug(f"  BEFORE: {raw_sample}")
                        logger.debug(f"  AFTER:  {rot_sample}")
                        logger.debug(
                            f"  DIFF:   {np.linalg.norm(raw_sample - rot_sample)}"
                        )
                        logger.debug(f"  QUAT AT SAMPLE: {qs[-1]}")

                        # 6. Overwrite the original keys for the frontend
                        data[f"{prefix}:x"] = v_rot[:, 0].tolist()
                        data[f"{prefix}:y"] = v_rot[:, 1].tolist()
                        data[f"{prefix}:z"] = v_rot[:, 2].tolist()

                        logger.debug(
                            f"Vectorized rotation complete for {prefix} in {rotate_by} frame."
                        )

        return {
            "columns": column_manifest,  # Full list of headers for the sidebar
            "data": data,  # Actual arrays for the requested traces
        }

    except Exception as e:
        logger.error(f"Data retrieval failed for {trial_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
