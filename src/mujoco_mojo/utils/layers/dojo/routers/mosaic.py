from __future__ import annotations

import json
import re
import socket
from functools import lru_cache
from pathlib import Path
from typing import get_args

import polars as pl
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from mujoco_mojo.utils.dataframe import ColumnManifest, MojoDataFrame
from mujoco_mojo.utils.filters.filters import UNIT_GROUPS as _UNIT_GROUPS
from mujoco_mojo.utils.filters.filters import AnyFilter as _AnyFilter
from mujoco_mojo.utils.filters.filters import FilterType as _FilterType
from mujoco_mojo.utils.filters.filters import filter_adapter as _filter_adapter
from mujoco_mojo.utils.log import get_logger

from .. import shared
from ..plot_config import PlotConfig as _PlotConfig

logger = get_logger(__name__)

router = APIRouter()

# Derived from FilterType enum ; automatically includes any new filter type added to filters.py.
# Used to identify the filter name in Pydantic error location tuples when formatting messages.
_FILTER_TYPE_NAMES: set[str] = {str(ft) for ft in _FilterType}

# Derived from AnyFilter's union members ; automatically includes any new filter class.
# AnyFilter = Annotated[ScaleFilter | AbsoluteValueFilter | ..., Field(discriminator="type")]
# get_args(AnyFilter)[0] is the bare union; get_args of that gives the individual classes.
_annotated_args = get_args(_AnyFilter)
_FILTER_CLASSES: list[type] = (
    list(get_args(_annotated_args[0])) if _annotated_args else []
)

_CONSTRAINT_OPS = {
    "less_than_equal": "≤",
    "less_than": "<",
    "greater_than_equal": "≥",
    "greater_than": ">",
}


def _format_filter_error(exc: Exception) -> str:
    """Format a Pydantic ValidationError into a short, human-readable message."""
    from pydantic import ValidationError

    if not isinstance(exc, ValidationError):
        return str(exc).split("\n")[0] or "Filter error"

    try:
        errors = exc.errors(include_url=False)
    except TypeError:
        errors = exc.errors()  # older pydantic build without include_url kwarg

    if not errors:
        return "Filter validation failed - check filter settings"

    first = errors[0]
    loc: tuple = first.get("loc", ())
    msg: str = first.get("msg", "")
    err_type: str = first.get("type", "")
    ctx: dict = first.get("ctx", {}) or {}

    # Resolve filter type and field from location tuple
    # e.g. ('/Bodies/xpos:x', 0, 'low_pass', 'alpha') → filter='Low Pass', field='alpha'
    filter_label: str | None = None
    field_name: str | None = None
    for i, part in enumerate(loc):
        if isinstance(part, str) and part in _FILTER_TYPE_NAMES:
            filter_label = part.replace("_", " ").title()
            if i + 1 < len(loc) and isinstance(loc[i + 1], str):
                field_name = loc[i + 1]

    prefix = f"{filter_label}: " if filter_label else ""

    # ── Unit-specific model validator errors ──────────────────────────────
    m = re.match(r"Value error, Unknown unit definition: '(.+?)' is not defined", msg)
    if m:
        return f"Unknown unit '{m.group(1)}'"
    m = re.match(r"Value error, Incompatible units: (.+?) and (.+?) \(", msg)
    if m:
        return f"Incompatible units: {m.group(1)} → {m.group(2)}"

    # ── Generic model validator (custom @model_validator) ─────────────────
    if msg.startswith("Value error, "):
        clean = msg.removeprefix("Value error, ")
        return f"{prefix}{clean}"

    # ── Field-level numeric constraint (gt, ge, lt, le) ───────────────────
    if err_type in _CONSTRAINT_OPS:
        op = _CONSTRAINT_OPS[err_type]
        # Use next/in to avoid treating 0 as falsy (ctx.get("gt") or ... breaks on gt=0)
        limit = next((ctx[k] for k in ("gt", "ge", "lt", "le") if k in ctx), None)
        field_str = f"{field_name} " if field_name else ""
        return f"{prefix}{field_str}must be {op} {limit}"

    # ── Tagged-union discriminator mismatch (bad filter type string) ───────
    if "union" in err_type or "tagged" in err_type:
        return "Unknown filter type - check filter configuration"

    # ── Fallback: clean up the raw Pydantic message ───────────────────────
    clean = re.sub(r"\s*\[type=\w+.*?\]\s*$", "", msg).strip()
    clean = clean.removeprefix("Value error,").strip()
    return (
        f"{prefix}{clean}"
        if clean
        else "Filter validation failed - check filter settings"
    )


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


@router.get("/api/filter-schema")
async def get_filter_schema():
    """
    Returns metadata for all available filter types, derived from Pydantic models.

    Filter classes are auto-discovered from AnyFilter's union; no changes needed here
    when a new filter is added to filters.py.
    """
    from pydantic_core import PydanticUndefined

    def _infer_type(prop: dict) -> str:
        if prop.get("ui_type") == "col":
            return "col"
        if "anyOf" in prop:
            non_null = [s for s in prop["anyOf"] if s.get("type") != "null"]
            prop = non_null[0] if non_null else {}
        t = prop.get("type", "")
        if t == "integer":
            return "int"
        if t == "number":
            return "float"
        if t == "boolean":
            return "bool"
        return "string"

    result = []
    for cls in _FILTER_CLASSES:
        schema = cls.model_json_schema()
        props = schema.get("properties", {})
        type_val = str(cls.model_fields["type"].default)

        params = []
        for name, field_info in cls.model_fields.items():
            if name == "type":
                continue
            prop = props.get(name, {})
            if "anyOf" in prop:
                non_null = [s for s in prop["anyOf"] if s.get("type") != "null"]
                prop_clean = {**prop, **(non_null[0] if non_null else {})}
            else:
                prop_clean = prop

            default = field_info.default
            if default is PydanticUndefined:
                default = None
            elif isinstance(default, float):
                default = round(float(default), 8)

            p: dict = {"name": name, "type": _infer_type(prop), "default": default}
            if "minimum" in prop_clean:
                p["min"] = prop_clean["minimum"]
            if "maximum" in prop_clean:
                p["max"] = prop_clean["maximum"]
            if "exclusiveMinimum" in prop_clean:
                p["exclusive_min"] = prop_clean["exclusiveMinimum"]
            if "exclusiveMaximum" in prop_clean:
                p["exclusive_max"] = prop_clean["exclusiveMaximum"]
            params.append(p)

        description = (cls.__doc__ or "").strip()
        description = description.split("\n")[0].strip()

        entry: dict = {
            "type": type_val,
            "label": type_val.replace("_", " ").title(),
            "description": description,
            "params": params,
        }
        if type_val == "unit":
            entry["unit_groups"] = [
                {"label": label, "units": units} for label, units in _UNIT_GROUPS
            ]
        result.append(entry)

    return result


# ---------------------------------------------------------------------------
# Profiles  ·  named saved views stored under ~/.mujoco-mojo/profiles/
# ---------------------------------------------------------------------------


def _get_profiles_dir() -> Path:
    d: Path = Path.home() / ".mujoco-mojo" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sanitize_profile_name(name: str) -> str:
    """
    Return a filesystem-safe relative path from the user-supplied profile name.

    Supports folder separators, e.g. 'robotics/arm_reach/baseline'.
    Each segment is sanitized independently; empty segments are dropped.
    """
    name = name.strip()[:256]
    segments = [s.strip() for s in name.split("/") if s.strip()]
    safe: list[str] = []
    for seg in segments:
        seg = re.sub(r"[^\w\s\-]", "", seg)
        seg = re.sub(r"\s+", "_", seg)
        seg = re.sub(r"_+", "_", seg).strip("_")
        if seg:
            safe.append(seg[:64])
    return "/".join(safe) or "profile"


def _resolve_profile_path(name: str) -> Path:
    """Return the resolved path for a profile, raising 400 if it escapes the profiles dir."""
    d = _get_profiles_dir()
    path = (d / f"{_sanitize_profile_name(name)}.json").resolve()
    if not path.is_relative_to(d.resolve()):
        raise HTTPException(status_code=400, detail="Invalid profile name")
    return path


@router.get("/api/profiles")
async def list_profiles():
    """List all saved profiles, including those in sub-folders."""
    d = _get_profiles_dir()
    profiles = [
        {
            "name": f.relative_to(d).with_suffix("").as_posix(),
            "modified": int(f.stat().st_mtime * 1000),
        }
        for f in sorted(
            d.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )
    ]
    return profiles


@router.get("/api/profiles/{name:path}")
async def get_profile(name: str):
    """Return the PlotConfig JSON for a saved profile, validated against the schema."""
    from pydantic import ValidationError

    path = _resolve_profile_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Profile not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        config = _PlotConfig.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Profile '{name}' failed validation and cannot be loaded: {exc}",
        ) from exc
    return config.model_dump()


_PROFILE_MAX_BYTES = 512 * 1024  # 512 KB (more than enough for any real PlotConfig)


@router.post("/api/profiles/{name:path}")
async def save_profile(name: str, request: Request, body: _PlotConfig):
    """
    Save the current PlotConfig as a named profile.

    FastAPI/Pydantic validates the request body structure automatically.
    The Content-Length header is checked first as a lightweight size guard.
    Sub-folder paths (e.g. 'project/baseline') are supported; directories
    are created automatically.
    """
    cl = request.headers.get("content-length")
    if cl and int(cl) > _PROFILE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Profile payload too large")
    path = _resolve_profile_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.model_dump_json(), encoding="utf-8")
    d = _get_profiles_dir()
    return {"name": path.relative_to(d).with_suffix("").as_posix()}


@router.delete("/api/profiles/{name:path}")
async def delete_profile(name: str):
    """Delete a saved profile."""
    path = _resolve_profile_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Profile not found")
    path.unlink()
    d = _get_profiles_dir()
    # Remove empty parent directories up to (but not including) the profiles root.
    parent = path.parent
    while parent != d and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent
    return {"deleted": path.relative_to(d).with_suffix("").as_posix()}


# ---------------------------------------------------------------------------
# Lab  ·  filter graph configs stored under ~/.mujoco-mojo/lab/
# ---------------------------------------------------------------------------

_LAB_PREFIX = "Lab"  # Virtual column category shown in the Y-axis selector
_LAB_MAX_BYTES = 1024 * 1024  # 1 MB


def _get_lab_dir() -> Path:
    d: Path = Path.home() / ".mujoco-mojo" / "lab"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sanitize_lab_name(name: str) -> str:
    """
    Return a filesystem-safe relative path from the user-supplied lab name.

    Supports folder separators, e.g. 'robotics/arm_reach/baseline'.
    Each segment is sanitized independently; empty segments are dropped.
    """
    name = name.strip()[:256]
    segments = [s.strip() for s in name.split("/") if s.strip()]
    safe: list[str] = []
    for seg in segments:
        seg = re.sub(r"[^\w\s\-]", "", seg)
        seg = re.sub(r"\s+", "_", seg)
        seg = re.sub(r"_+", "_", seg).strip("_")
        if seg:
            safe.append(seg[:64])
    return "/".join(safe) or "lab"


def _resolve_lab_path(name: str) -> Path:
    d = _get_lab_dir()
    path = (d / f"{_sanitize_lab_name(name)}.json").resolve()
    if not path.is_relative_to(d.resolve()):
        raise HTTPException(status_code=400, detail="Invalid lab name")
    return path


def _lab_meta(path: Path, d: Path) -> dict:
    """Parse a saved lab file and return metadata for the API."""
    from mujoco_mojo.utils.layers.dojo.lab_executor import LabExecutor

    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
        exc = LabExecutor(graph)
        return {
            "name": path.relative_to(d).with_suffix("").as_posix(),
            "modified": int(path.stat().st_mtime * 1000),
            "signal_in_columns": exc.signal_in_columns,
            "outputs": exc.output_labels,
        }
    except Exception:
        return {
            "name": path.relative_to(d).with_suffix("").as_posix(),
            "modified": int(path.stat().st_mtime * 1000),
            "signal_in_columns": [],
            "outputs": [],
        }


@router.get("/api/lab")
async def list_labs():
    """List all saved lab graphs with their input column requirements and output labels."""
    d = _get_lab_dir()
    return [
        _lab_meta(f, d)
        for f in sorted(
            d.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )
    ]


@router.get("/api/lab/{name:path}")
async def get_lab(name: str):
    """Return the raw LiteGraph JSON for a saved lab."""
    path = _resolve_lab_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Lab not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/api/lab/{name:path}")
async def save_lab(name: str, request: Request):
    """Save a LiteGraph graph JSON as a named lab."""
    cl = request.headers.get("content-length")
    if cl and int(cl) > _LAB_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Lab payload too large")
    body = await request.json()
    path = _resolve_lab_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding="utf-8")
    d = _get_lab_dir()
    return {"name": path.relative_to(d).with_suffix("").as_posix()}


@router.delete("/api/lab/{name:path}")
async def delete_lab(name: str):
    """Delete a saved lab."""
    path = _resolve_lab_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Lab not found")
    path.unlink()
    d = _get_lab_dir()
    # Remove empty parent directories up to (but not including) the lab root.
    parent = path.parent
    while parent != d and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent
    return {"deleted": path.relative_to(d).with_suffix("").as_posix()}


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
    trial_id: str,
    cols: str = Query(None),
    rotate_by: str = Query(None),
    filters: str = Query(None),
):
    """
    Loops over the columns in the trial_id provided and returns their data. Optionally performs a rotation if requested and there are an associated x, y, and z column.

    Args:
        trial_id (str): Trial to search (e.g. `"trial_001"`).
        cols (str, optional): Comma separated list of column names to return data for (e.g. `"/Bodies/body1/xpos:x,/Bodies/body2/xpos:m"`). Defaults to Query(None).
        rotate_by (str, optional): Quaternion family to rotate vectors by (e.g. `"/Bodies/body1/quat"`). Defaults to Query(None).
        filters (str, optional): String representation of filters to be applied sequentially. Defaults to Query(None).

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

        # parse validated filter stacks (col_name → list[AnyFilter])
        col_filters: dict = {}
        filter_errors: list[str] = []
        if filters:
            try:
                col_filters = _filter_adapter.validate_python(json.loads(filters))
            except Exception as e:
                logger.warning(f"Could not parse filters for {trial_id}: {e}")
                filter_errors.append(_format_filter_error(e))

        data: dict = {}

        # ── Lab virtual columns ────────────────────────────────────────────────
        # Columns named "Lab/{lab_name}/{output_label}" are computed by running
        # the saved lab graph rather than reading from the parquet file.
        lab_cols = [c for c in requested if c.startswith(f"{_LAB_PREFIX}/")]
        if lab_cols:
            from mujoco_mojo.utils.layers.dojo.lab_executor import LabExecutor

            # Group by lab name to execute each graph once
            from collections import defaultdict as _dd

            by_lab: dict[str, list[tuple[str, str]]] = _dd(list)
            for col in lab_cols:
                parts = col.split("/", 2)
                if len(parts) == 3:
                    _, lab_name, output_label = parts
                    by_lab[lab_name].append((col, output_label))

            for lab_name, col_outputs in by_lab.items():
                lab_path = _resolve_lab_path(lab_name)
                if not lab_path.exists():
                    continue
                try:
                    graph = json.loads(lab_path.read_text(encoding="utf-8"))
                    outputs = LabExecutor(graph).execute(df)
                    for full_col, output_label in col_outputs:
                        if output_label in outputs:
                            data[full_col] = outputs[output_label].to_list()
                except Exception as exc:
                    logger.warning(f"Lab '{lab_name}' execution failed: {exc}")

        # ── build response data, applying per-column filters where present ────
        for col in requested:
            if col not in df.columns:
                continue
            series = df[col]
            filter_list = col_filters.get(col)
            if filter_list:
                if series.dtype != pl.Float64:
                    series = series.cast(pl.Float64)
                for f in filter_list:
                    # context-aware filters (e.g. derivative/integral wrt another col)
                    ctx = f.apply_with_context(series, df)
                    if ctx is not None:
                        series = ctx
                    else:
                        tmp = pl.DataFrame({col: series})
                        tmp = tmp.with_columns(f.apply(pl.col(col)).alias(col))
                        series = tmp[col]
            data[col] = series.to_list()

        return {
            "columns": column_manifest,
            "data": data,
            "filter_errors": filter_errors,
        }

    except Exception as e:
        logger.error(f"Data retrieval failed for {trial_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
