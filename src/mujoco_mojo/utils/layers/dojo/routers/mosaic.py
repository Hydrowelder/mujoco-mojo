from __future__ import annotations

import asyncio
import hashlib
import json
import re
import socket
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import get_args

import polars as pl
import stochas
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse

from mujoco_mojo.meta import MUJOCO_MOJO_DIR
from mujoco_mojo.typing import SignalCategory
from mujoco_mojo.utils.dataframe import ColumnManifest, MojoDataFrame
from mujoco_mojo.utils.defaults import NAMED_VALUES_FNAME as _NAMED_VALUES_FNAME
from mujoco_mojo.utils.defaults import STOCHAS_DIR_NAME as _STOCHAS_DIR_NAME
from mujoco_mojo.utils.defaults import STOCHAS_DISTS_FNAME as _STOCHAS_DISTS_FNAME
from mujoco_mojo.utils.defaults import TIME_COLUMN_NAME as _TIME_COLUMN_NAME
from mujoco_mojo.utils.filters.filters import UNIT_GROUPS as _UNIT_GROUPS
from mujoco_mojo.utils.filters.filters import AnyFilter as _AnyFilter
from mujoco_mojo.utils.filters.filters import BaseFilter as _BaseFilter
from mujoco_mojo.utils.filters.filters import FilterType as _FilterType
from mujoco_mojo.utils.filters.filters import RotationFilter as _RotationFilter
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
_FILTER_CLASSES: list[type[_BaseFilter]] = (
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
    """Scans the workdir for folders containing telemetry data."""
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
        if prop.get("ui_type") == "quat_col":
            return "quat_col"
        if prop.get("ui_type") == "select":
            return "select"
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
            if name in ("type", "enabled"):
                continue
            # model_json_schema() keys properties by alias when serialize_by_alias=True.
            # alias_generator may be a plain callable (to_camel) or an AliasGenerator
            # object; only call it when it's actually callable.
            ag = cls.model_config.get("alias_generator")
            alias: str = field_info.alias or (ag(name) if callable(ag) else name)
            prop = props.get(alias, props.get(name, {}))
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

            p: dict = {"name": alias, "type": _infer_type(prop), "default": default}
            if p["type"] == "select" and "enum" in prop:
                p["options"] = prop["enum"]
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
            "category": cls.category,
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
    d: Path = MUJOCO_MOJO_DIR / "profiles"
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

_LAB_PREFIX = SignalCategory.LAB  # Virtual column category shown in the Y-axis selector
_LAB_MAX_BYTES = 1024 * 1024  # 1 MB


def _get_lab_dir() -> Path:
    d: Path = MUJOCO_MOJO_DIR / "lab"
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
        ti = exc._template_in_labels
        to = exc._template_out_labels
        return {
            "name": path.relative_to(d).with_suffix("").as_posix(),
            "modified": int(path.stat().st_mtime * 1000),
            "signal_in_columns": exc.signal_in_columns,
            "outputs": exc.output_labels,
            "is_template": bool(ti or to),
            "template_inputs": ti,
            "template_outputs": to,
        }
    except Exception:
        return {
            "name": path.relative_to(d).with_suffix("").as_posix(),
            "modified": int(path.stat().st_mtime * 1000),
            "signal_in_columns": [],
            "outputs": [],
            "is_template": False,
            "template_inputs": [],
            "template_outputs": [],
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


def _lab_dir_mtime() -> float:
    """Max mtime of any file in the lab directory; used as a cache key."""
    d = _get_lab_dir()
    try:
        mtimes = [f.stat().st_mtime for f in d.rglob("*.json")]
        return max(mtimes) if mtimes else 0.0
    except Exception:
        return 0.0


@lru_cache(maxsize=32)
def _valid_lab_columns_cached(parquet_cols: frozenset, lab_mtime: float) -> list:
    """
    BFS to find all valid lab virtual column names for a given parquet column set.

    Mirrors the frontend loadLabSchemas logic. Cached by column frozenset + lab dir mtime.
    Returns a list of 'Lab/{name}/{output}' strings.
    """
    from mujoco_mojo.utils.layers.dojo.lab_executor import LabExecutor

    d = _get_lab_dir()
    labs = []
    for f in sorted(d.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            graph = json.loads(f.read_text(encoding="utf-8"))
            exc = LabExecutor(graph)
            labs.append(
                {
                    "name": f.relative_to(d).with_suffix("").as_posix(),
                    "si_cols": set(exc.signal_in_columns),
                    "outputs": exc.output_labels,
                }
            )
        except Exception:
            pass

    available: set = set(parquet_cols)
    valid_cols: list = []
    processed: set = set()
    changed = True
    while changed:
        changed = False
        for lab in labs:
            name = lab["name"]
            if name in processed:
                continue
            if lab["si_cols"].issubset(available):
                processed.add(name)
                changed = True
                for out in lab["outputs"]:
                    col = f"{_LAB_PREFIX}/{name}/{out}"
                    valid_cols.append(col)
                    available.add(col)
    return valid_cols


@lru_cache(maxsize=128)
def _get_mojo_df(path: Path, mtime: float) -> MojoDataFrame:
    """Zero-row MojoDataFrame for schema queries, cached by path and mtime."""
    return MojoDataFrame.from_metadata(path)


@lru_cache(maxsize=128)
def _get_column_manifest(path: Path, mtime: float) -> ColumnManifest:
    """Retrieves all column names from the table schema."""
    return _get_mojo_df(path, mtime).mojo.get_manifest()


@lru_cache(maxsize=2048)
def _get_atomic_column(path: Path, col_name: str, mtime: float):
    """
    Fetches a single column. 'mtime' is the cache-breaker. If the file changes, the mtime changes, triggering a fresh read even if the path and column name are the same.
    """
    return pl.scan_parquet(path).select(col_name).collect().to_series().to_list()


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

    # Parquet-only manifest (cached), then augment with valid lab virtual columns.
    parquet_manifest = _get_column_manifest(db_path, mtime)
    lab_mtime = _lab_dir_mtime()
    lab_extra = _valid_lab_columns_cached(frozenset(parquet_manifest["all"]), lab_mtime)
    column_manifest = (
        _get_mojo_df(db_path, mtime).mojo.get_manifest(extra_columns=list(lab_extra))
        if lab_extra
        else parquet_manifest
    )

    try:
        requested = cols.split(",") if cols else []
        # available_cols covers only parquet columns for actual fetch logic
        available_cols = set(parquet_manifest["all"])

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

        # ── Collect lab SI columns before building the df ─────────────────────
        # Lab virtual columns are computed from the graph, not read from parquet.
        # We load executors now so we can add their parquet SI deps to fetch_targets.
        lab_cols = [c for c in requested if c.startswith(f"{_LAB_PREFIX}/")]
        from collections import defaultdict as _dd

        by_lab: dict[str, list[tuple[str, str]]] = _dd(list)
        lab_executors: dict = {}

        if lab_cols:
            from mujoco_mojo.utils.layers.dojo.lab_executor import LabExecutor

            for col in lab_cols:
                # Lab names may themselves contain '/' (nested folders), so split
                # from the right - the output label is always the final segment.
                rest = col[len(_LAB_PREFIX) + 1 :]
                if "/" in rest:
                    lab_name, output_label = rest.rsplit("/", 1)
                    by_lab[lab_name].append((col, output_label))

            # Load executors transitively so chained labs have their deps available.
            to_load = list(by_lab.keys())
            while to_load:
                name = to_load.pop()
                if name in lab_executors:
                    continue
                lab_path = _resolve_lab_path(name)
                if not lab_path.exists():
                    continue
                try:
                    g = json.loads(lab_path.read_text(encoding="utf-8"))
                    lab_executors[name] = LabExecutor(g)
                    for si_col in lab_executors[name].signal_in_columns:
                        if si_col.startswith(f"{_LAB_PREFIX}/"):
                            dep_rest = si_col[len(_LAB_PREFIX) + 1 :]
                            if "/" in dep_rest:
                                dep_lab_name = dep_rest.rsplit("/", 1)[0]
                                if dep_lab_name not in lab_executors:
                                    to_load.append(dep_lab_name)
                except Exception:
                    pass

            # Add parquet SI columns and the time column to fetch_targets.
            extra_si: set[str] = set()
            for executor in lab_executors.values():
                for si_col in executor.signal_in_columns:
                    if si_col in available_cols:
                        extra_si.add(si_col)
                # Sibling vector components and quaternion columns needed by any
                # in-graph Rotation node - without these, apply_with_context()
                # can't find the columns it needs and the rotation is a no-op.
                for dep_col in executor.rotation_dependencies:
                    if dep_col in available_cols:
                        extra_si.add(dep_col)
            if _TIME_COLUMN_NAME in available_cols:
                extra_si.add(_TIME_COLUMN_NAME)
            existing_targets = set(fetch_targets)
            fetch_targets.extend(c for c in extra_si if c not in existing_targets)

        # ── Pre-flight: ensure RotationFilter dependencies are fetched ────────
        # Parse filters early (errors are tolerated; full parse happens again below).
        if filters:
            try:
                _preflight = _filter_adapter.validate_python(json.loads(filters))
                _existing = set(fetch_targets)
                for _col, _flist in _preflight.items():
                    for _f in _flist:
                        if not isinstance(_f, _RotationFilter) or not _f.quat_col:
                            continue
                        # Sibling vector components for the column being rotated
                        if (
                            _col.endswith(":x")
                            or _col.endswith(":y")
                            or _col.endswith(":z")
                        ):
                            _base = _col.rsplit(":", 1)[0]
                            for _comp in ("x", "y", "z"):
                                _sib = f"{_base}:{_comp}"
                                if _sib in available_cols and _sib not in _existing:
                                    fetch_targets.append(_sib)
                                    _existing.add(_sib)
                        # Quaternion components
                        for _comp in ("w", "x", "y", "z"):
                            _qc = f"{_f.quat_col}:{_comp}"
                            if _qc in available_cols and _qc not in _existing:
                                fetch_targets.append(_qc)
                                _existing.add(_qc)
            except Exception:
                pass

        # early exit for no found columns
        if not fetch_targets:
            return {"columns": column_manifest, "data": {}}

        # assemble dataframe
        raw_data = {
            col: _get_atomic_column(db_path, col, mtime) for col in fetch_targets
        }
        df = MojoDataFrame.from_dict(raw_data)

        if rotate_by:
            # rotate from world to rotate_by frame
            df = df.mojo.with_rotation(quat_base=rotate_by, invert=True)

        # parse validated filter stacks (col_name -> list[AnyFilter])
        col_filters: dict = {}
        filter_errors: list[str] = []
        if filters:
            try:
                col_filters = _filter_adapter.validate_python(json.loads(filters))
            except Exception as e:
                logger.warning(f"Could not parse filters for {trial_id}: {e}")
                filter_errors.append(_format_filter_error(e))

        data: dict = {}

        # ── Execute lab virtual columns (multi-pass for chained labs) ──────────
        # exec_df accumulates lab outputs alongside the raw fetched columns, so
        # that stacked filters on Lab/... columns (e.g. RotationFilter) can find
        # sibling Lab/... vector components via apply_with_context.
        exec_df = df
        if lab_cols and lab_executors:
            lab_cols_set = set(lab_cols)

            # For transitive deps not directly requested, expose all their outputs
            # so downstream labs can use them as inputs via exec_df.
            all_by_lab: dict[str, list[tuple[str, str]]] = dict(by_lab)
            for lab_name, executor in lab_executors.items():
                if lab_name not in all_by_lab:
                    all_by_lab[lab_name] = [
                        (f"{_LAB_PREFIX}/{lab_name}/{out}", out)
                        for out in executor.output_labels
                    ]

            remaining = dict(all_by_lab)
            for _ in range(len(remaining) + 1):
                if not remaining:
                    break
                progress = False
                for lab_name in list(remaining.keys()):
                    if lab_name not in lab_executors:
                        del remaining[lab_name]
                        progress = True
                        continue
                    executor = lab_executors[lab_name]
                    # Wait until all lab-virtual SI deps are present in exec_df.
                    if any(
                        c not in exec_df.columns
                        for c in executor.signal_in_columns
                        if c.startswith(f"{_LAB_PREFIX}/")
                    ):
                        continue
                    try:
                        outputs = executor.execute(exec_df)
                        new_series: list[pl.Series] = []
                        for full_col, output_label in remaining[lab_name]:
                            if output_label in outputs:
                                s = outputs[output_label].rename(full_col)
                                new_series.append(s)
                                if full_col in lab_cols_set:
                                    data[full_col] = s.to_list()
                        if new_series:
                            exec_df = MojoDataFrame.from_pl(exec_df.hstack(new_series))
                        del remaining[lab_name]
                        progress = True
                    except Exception as exc:
                        logger.warning(f"Lab '{lab_name}' execution failed: {exc}")
                        del remaining[lab_name]
                        progress = True
                if not progress:
                    break

        # ── build response data, applying per-column filters where present ────
        for col in requested:
            if col.startswith(f"{_LAB_PREFIX}/"):
                # Lab output already in data; apply any stacked filters on top.
                filter_list = col_filters.get(col)
                if filter_list and col in data:
                    series = pl.Series(name=col, values=data[col], dtype=pl.Float64)
                    for f in filter_list:
                        ctx = f.apply_with_context(series, exec_df)
                        if ctx is not None:
                            series = ctx
                        else:
                            tmp = pl.DataFrame({col: series})
                            tmp = tmp.with_columns(f.apply(pl.col(col)).alias(col))
                            series = tmp[col]
                    data[col] = series.to_list()
                continue
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


_MEDIA_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".webm", ".gif"})


def _read_file_fps(path: Path) -> float | None:
    """Reads fps from a media file synchronously. Returns None on failure."""
    try:
        if path.suffix.lower() in {".mp4", ".webm"}:
            import mediapy as media

            with media.VideoReader(path) as reader:
                return float(reader.fps)
        if path.suffix.lower() == ".gif":
            from PIL import Image as _Image

            img = _Image.open(path)
            duration_ms = float(img.info.get("duration", 100))
            return 1000.0 / max(duration_ms, 1.0)
    except Exception:
        pass
    return None


def _gif_webm_cache_path(gif_path: Path) -> Path:
    """
    Returns a stable path in the system temp directory for a GIF→WebM conversion.

    The cache key is the resolved path plus mtime so a changed GIF produces a new entry. The OS temp directory is cleaned up on reboot, keeping trial directories free of video blobs.
    """
    key = f"{gif_path.resolve()}:{gif_path.stat().st_mtime}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    cache_dir = Path(tempfile.gettempdir()) / "mujoco_mojo_webm"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / f"{digest}.webm"


def _convert_gif_to_webm_sync(gif_path: Path, webm_path: Path) -> None:
    """Converts a GIF to WebM (VP9) using ffmpeg directly. Blocking — run in executor."""
    import subprocess

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            gif_path,
            # ensure even dimensions (required by most codecs)
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libvpx-vp9",
            "-b:v",
            "0",
            "-crf",
            "33",
            "-an",  # no audio
            "-pix_fmt",
            "yuv420p",
            webm_path,
        ],
        check=True,
        capture_output=True,
    )


def _resolve_trial_dir(trial_id: str) -> Path:
    """Resolves and validates a trial directory path, guarding against path traversal."""
    job = shared.CURRENT_JOB
    if not job:
        raise HTTPException(status_code=503, detail="No job active")
    trials_root = (job.workdir / "trials").resolve()
    trial_dir = (trials_root / trial_id).resolve()
    if not trial_dir.is_relative_to(trials_root) or trial_dir == trials_root:
        raise HTTPException(status_code=400, detail="Invalid trial ID")
    return trial_dir


@router.get("/{trial_id}/media")
async def list_trial_media(trial_id: str) -> dict:
    """Lists media files in the trial directory with their fps metadata."""
    trial_dir = _resolve_trial_dir(trial_id)
    if not trial_dir.is_dir():
        return {"files": []}
    loop = asyncio.get_running_loop()
    paths = sorted(
        p
        for p in trial_dir.iterdir()
        if p.suffix.lower() in _MEDIA_EXTENSIONS and not p.stem.endswith(".mojo_webm")
    )
    files = []
    for p in paths:
        fps = await loop.run_in_executor(None, _read_file_fps, p)
        files.append({"name": p.name, "fps": fps, "mtime": p.stat().st_mtime})
    return {"files": files}


@router.get("/{trial_id}/media/{filename}/as-webm")
async def get_gif_as_webm(trial_id: str, filename: str) -> FileResponse:
    """Converts a GIF to WebM on-demand, cached in the system temp directory."""
    trial_dir = _resolve_trial_dir(trial_id)
    gif_path = (trial_dir / filename).resolve()
    if not gif_path.is_relative_to(trial_dir):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not gif_path.is_file() or gif_path.suffix.lower() != ".gif":
        raise HTTPException(status_code=404, detail="File not found or not a gif")
    webm_path = _gif_webm_cache_path(gif_path)
    if not webm_path.exists():
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _convert_gif_to_webm_sync, gif_path, webm_path)
    return FileResponse(webm_path, media_type="video/webm")


@router.get("/{trial_id}/media/{filename}")
async def get_trial_media_file(trial_id: str, filename: str) -> FileResponse:
    """Serves a single media file from the trial directory."""
    trial_dir = _resolve_trial_dir(trial_id)
    file_path = (trial_dir / filename).resolve()
    if not file_path.is_relative_to(trial_dir):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not file_path.is_file() or file_path.suffix.lower() not in _MEDIA_EXTENSIONS:
        raise HTTPException(status_code=404, detail="File not found")
    _mime: dict[str, str] = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".gif": "image/gif",
    }
    return FileResponse(
        file_path,
        media_type=_mime.get(file_path.suffix.lower(), "application/octet-stream"),
    )


_DEFAULT_LOG_ENTRY = {
    "timestamp": 0,
    "level": "Invalid Level",
    "pathname": "",
    "lineno": None,
    "message": "",
}


def _parse_log_file(log_path: Path) -> list[dict]:
    """
    Parses a `mojo.log` file of newline-delimited JSON log entries.

    Lines that aren't valid JSON (e.g. output from a library that doesn't use
    our JSON formatter) are appended to the message of the preceding entry.
    Entries missing fields are filled in with defaults.
    """
    entries: list[dict] = []
    with log_path.open(encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if not line:
                continue
            try:
                entries.append({**_DEFAULT_LOG_ENTRY, **json.loads(line)})
            except json.JSONDecodeError:
                if entries:
                    entries[-1]["message"] += f"\n{line}"
    return entries


def _chart_data(dist: stochas.AnyDist) -> dict:
    """
    Return chart data for the distribution tooltip.

    Categorical distributions are detected by duck-typing `choices` and rendered
    as a bar chart. Permutations expose `items` but have no meaningful density to
    plot, so only params are shown. All other distributions get a PDF/PMF trace
    plus a CDF trace on a secondary y-axis.
    """
    import numpy as np

    choices = getattr(dist, "choices", None)
    if isinstance(choices, dict):
        labels = [str(k) for k in choices]
        probs = [float(v) for v in choices.values()]
        return {
            "chart_type": "categorical",
            "pdf_x": [],
            "pdf_y": [],
            "cdf_x": [],
            "cdf_y": [],
            "cat_labels": labels,
            "cat_probs": probs,
            "is_discrete": True,
        }

    if getattr(dist, "items", None) is not None:
        return {
            "chart_type": "permutation",
            "pdf_x": [],
            "pdf_y": [],
            "cdf_x": [],
            "cdf_y": [],
            "cat_labels": [],
            "cat_probs": [],
            "is_discrete": True,
        }

    n = 200
    try:
        if dist.is_discrete:
            k_low = int(dist.ppf(0.001))
            k_high = max(int(dist.ppf(0.999)), k_low + 1)
            k = np.arange(k_low, k_high + 1)
            pdf_y = np.asarray(dist.pmf(k), dtype=float)  # pyright: ignore[reportAttributeAccessIssue]
            cdf_y = np.asarray(dist.cdf(k), dtype=float)
            xs = [float(v) for v in k]
            return {
                "chart_type": "discrete",
                "pdf_x": xs,
                "pdf_y": pdf_y.tolist(),
                "cdf_x": xs,
                "cdf_y": cdf_y.tolist(),
                "cat_labels": [],
                "cat_probs": [],
                "is_discrete": True,
            }
        if isinstance(dist, stochas.CauchyDistribution):
            x_low = dist.theta - 5 * dist.sigma
            x_high = dist.theta + 5 * dist.sigma
        else:
            x_low = float(dist.ppf(0.001))
            x_high = float(dist.ppf(0.999))
        x = np.linspace(x_low, x_high, n)
        pdf_y = np.asarray(dist.pdf(x), dtype=float)
        cdf_y = np.asarray(dist.cdf(x), dtype=float)
        return {
            "chart_type": "continuous",
            "pdf_x": x.tolist(),
            "pdf_y": pdf_y.tolist(),
            "cdf_x": x.tolist(),
            "cdf_y": cdf_y.tolist(),
            "cat_labels": [],
            "cat_probs": [],
            "is_discrete": False,
        }
    except Exception:
        return {
            "chart_type": "none",
            "pdf_x": [],
            "pdf_y": [],
            "cdf_x": [],
            "cdf_y": [],
            "cat_labels": [],
            "cat_probs": [],
            "is_discrete": dist.is_discrete,
        }


def _stat(
    dist: stochas.AnyDist, sampled: float | None
) -> tuple[float | None, float | None]:
    """
    Return (z_score, percentile) for a sampled value against a distribution.

    z-score is returned for any distribution that exposes `mu` and `sigma` (normal-family). New normal-like distributions gain z-score support automatically via duck-typing.
    """
    if sampled is None:
        return None, None
    try:
        pct = round(float(dist.cdf(sampled)) * 100, 1)
        mu = getattr(dist, "mu", None)
        sigma = getattr(dist, "sigma", None)
        if mu is not None and sigma is not None and float(sigma) > 0:
            return round((sampled - float(mu)) / float(sigma), 3), pct
        return None, pct
    except Exception:
        return None, None


def _safe_param(v: object) -> object:
    """Convert values that can't be serialized to standard JSON to a display string."""
    import math

    if isinstance(v, float) and math.isinf(v):
        return "-∞" if v < 0 else "∞"
    return v


def _extract_sampled_values(named_raw: dict, name: str) -> list[float] | None:
    """Pull every drawn scalar out of a NamedValue's stored_value, flattening any nesting."""
    import numpy as np

    entry = named_raw.get(name) or named_raw.get("root", {}).get(name)
    if entry is None:
        return None
    sv = entry.get("stored_value")
    if sv is None:
        return None
    try:
        flat = np.array(sv, dtype=float).flatten()
        return [float(v) for v in flat] if len(flat) > 0 else None
    except Exception:
        return None


def _extract_sampled_labels(named_raw: dict, name: str) -> list[str] | None:
    """Pull every drawn label out of a NamedValue's stored_value for non-numeric distributions (e.g. categorical)."""
    entry = named_raw.get(name) or named_raw.get("root", {}).get(name)
    if entry is None:
        return None
    sv = entry.get("stored_value")
    if isinstance(sv, str):
        return [sv]
    if isinstance(sv, list) and sv and all(isinstance(v, str) for v in sv):
        return sv
    return None


def _extract_sampled_permutations(named_raw: dict, name: str) -> list[list] | None:
    """Pull every drawn permutation out of a NamedValue's stored_value, where each draw is itself a list of items."""
    entry = named_raw.get(name) or named_raw.get("root", {}).get(name)
    if entry is None:
        return None
    sv = entry.get("stored_value")
    if isinstance(sv, list) and sv and all(isinstance(row, list) for row in sv):
        return sv
    return None


@router.get("/{trial_id}/dists")
async def get_trial_dists(trial_id: str) -> dict:
    """Returns per-trial distribution configs merged with sampled values and PDF/PMF data."""
    trial_dir = _resolve_trial_dir(trial_id)
    job = shared.CURRENT_JOB
    if not job:
        raise HTTPException(status_code=503, detail="No job active")

    dists_path = job.workdir / _STOCHAS_DIR_NAME / _STOCHAS_DISTS_FNAME
    if not dists_path.exists():
        return {"entries": []}

    try:
        text = dists_path.read_text(encoding="utf-8")
        dist_dict = stochas.DistributionDict.model_validate_json(text)
    except Exception as exc:
        logger.error(f"Failed to parse {dists_path}: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to parse distribution metadata: {exc}"
        ) from exc

    named_path = trial_dir / _NAMED_VALUES_FNAME
    named_raw: dict = {}
    if named_path.exists():
        try:
            named_raw = json.loads(named_path.read_text(encoding="utf-8"))
        except Exception as exc:
            # non-standard JSON (e.g. Infinity from numpydantic) - continue
            # without sampled values rather than returning 500
            logger.warning(f"Failed to parse {named_path}: {exc}")

    loop = asyncio.get_running_loop()

    def _build_entries() -> list[dict]:
        entries = []
        for dist in dist_dict.values():
            chart = _chart_data(dist)
            is_permutation = chart["chart_type"] == "permutation"
            # permutations store each draw as a list of items (a 2D array overall), so
            # the flat-scalar/flat-label extractors below don't apply to them
            sampled_values = (
                None
                if is_permutation
                else _extract_sampled_values(named_raw, dist.name)
            )
            sampled = sampled_values[0] if sampled_values else None
            sampled_labels = (
                None
                if is_permutation
                else _extract_sampled_labels(named_raw, dist.name)
            )
            sampled_permutations = (
                _extract_sampled_permutations(named_raw, dist.name)
                if is_permutation
                else None
            )
            z_score, percentile = _stat(dist, sampled)
            # nominal may be any type T (float, str, list...); expose as a
            # scalar float when possible, or as a string label (e.g. for
            # categorical nominals like "class_A"), mirroring sampled_value /
            # sampled_labels
            nominal_raw = dist.nominal if dist.has_nominal else None
            nominal: float | None = None
            nominal_label: str | None = None
            if nominal_raw is not None:
                try:
                    nominal = float(nominal_raw)  # pyright: ignore[reportArgumentType]
                except (TypeError, ValueError):
                    if isinstance(nominal_raw, str):
                        nominal_label = nominal_raw
                    elif isinstance(nominal_raw, (list, tuple)):
                        nominal_label = ", ".join(str(v) for v in nominal_raw)
            entries.append(
                {
                    "name": dist.name,
                    "dist_type": dist.dist_type,
                    "category": dist.category,
                    "units": dist.units,
                    "nominal": nominal,
                    "nominal_label": nominal_label,
                    "sampled_value": sampled,
                    "sampled_values": sampled_values,
                    "sampled_labels": sampled_labels,
                    "sampled_permutations": sampled_permutations,
                    "z_score": z_score,
                    "percentile": percentile,
                    "is_discrete": chart["is_discrete"],
                    "chart_type": chart["chart_type"],
                    "pdf_x": chart["pdf_x"],
                    "pdf_y": chart["pdf_y"],
                    "cdf_x": chart["cdf_x"],
                    "cdf_y": chart["cdf_y"],
                    "cat_labels": chart["cat_labels"],
                    "cat_probs": chart["cat_probs"],
                    "params": {k: _safe_param(v) for k, v in dist.table_params.items()},
                }
            )
        return entries

    entries = await loop.run_in_executor(None, _build_entries)
    return {"entries": entries}


@router.get("/{trial_id}/logs")
async def get_trial_logs(trial_id: str) -> dict:
    """
    Parses and returns the per-trial log file.

    Looks for `mojo.log` first; if absent, falls back to the first `*.log`
    file (by name) found in the trial directory.
    """
    trial_dir = _resolve_trial_dir(trial_id)
    if not trial_dir.is_dir():
        return {"filename": None, "entries": []}

    log_path = trial_dir / "mojo.log"
    if not log_path.is_file():
        candidates = sorted(trial_dir.glob("*.log"))
        if not candidates:
            return {"filename": None, "entries": []}
        log_path = candidates[0]

    loop = asyncio.get_running_loop()
    entries = await loop.run_in_executor(None, _parse_log_file, log_path)
    return {"filename": log_path.name, "entries": entries}
