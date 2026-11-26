"""
A trial's sampled inputs set against the distributions they were drawn from.

The Dojo's distributions panel (`routers/mosaic.py`) and SensAI's job agent (`utils/sensai/tools/dist_report.py`) both read a job's saved distributions and a trial's saved draws. What a draw is in the unit its distribution was declared in, its z-score, and the nominal are worked out here, once, so the two cannot disagree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, SupportsFloat

import stochas
from pint.errors import PintError

from mujoco_mojo.utils.defaults import (
    NAMED_VALUES_FNAME,
    STOCHAS_DIR_NAME,
    STOCHAS_DISTS_FNAME,
)
from mujoco_mojo.utils.filters.filters import ureg
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = [
    "WITH_MU_AND_SIGMA",
    "extract_sampled_labels",
    "extract_sampled_values",
    "in_unit",
    "read_distributions",
    "read_named_values",
    "safe_param",
    "sampled_values_in_dist_unit",
    "split_nominal",
    "stored_unit",
    "z_and_percentile",
]


def read_distributions(workdir: Path) -> stochas.DistributionDict | None:
    """The distributions a job's trials were drawn from, or None when it saved none. Raises `ValueError` when the file is there but cannot be read as distributions."""
    path = workdir / STOCHAS_DIR_NAME / STOCHAS_DISTS_FNAME
    if not path.exists():
        return None
    try:
        return stochas.DistributionDict.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise ValueError(f"{path}: {exc}") from exc


def read_named_values(trial_dir: Path) -> dict[str, Any]:
    """What a trial drew, as the JSON it was saved as. Empty when it saved none or the file cannot be read (it can hold non-standard JSON, such as Infinity from numpydantic), so a trial's draws are left out rather than failing the whole request."""
    path = trial_dir / NAMED_VALUES_FNAME
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Failed to parse {path}: {exc}")
        return {}


def split_nominal(nominal_raw: object) -> tuple[float | None, str | None]:
    """
    Return (nominal, nominal_label) for a distribution's nominal value.

    A nominal may be any type (float, str, list...). Numbers and numeric strings are exposed as a float, other strings and sequences as a label (e.g. for categorical nominals like "class_A").
    """
    if isinstance(nominal_raw, str):
        try:
            return float(nominal_raw), None
        except ValueError:
            return None, nominal_raw
    if isinstance(nominal_raw, (list, tuple)):
        return None, ", ".join(str(v) for v in nominal_raw)
    if isinstance(nominal_raw, SupportsFloat):
        try:
            return float(nominal_raw), None
        except (TypeError, ValueError):
            pass
    return None, None


# the distributions that have both a `mu` and a `sigma`, which a z-score is measured with. a test fails when a distribution gains both, so this list cannot fall behind
WITH_MU_AND_SIGMA = (
    stochas.NormalDistribution,
    stochas.TruncatedNormalDistribution,
    stochas.LaplaceDistribution,
)


def has_z_score(dist: stochas.AnyDist) -> bool:
    """Whether `dist` is one a z-score is given for, which is one with a `mu` and a `sigma`."""
    return isinstance(dist, WITH_MU_AND_SIGMA)


def z_and_percentile(
    dist: stochas.AnyDist, sampled: float | None
) -> tuple[float | None, float | None]:
    """
    Return (z_score, percentile) for a sampled value against a distribution.

    The z-score is given only for a distribution with a `mu` and a `sigma` (`WITH_MU_AND_SIGMA`); every other one has a percentile alone.
    """
    if sampled is None:
        return None, None
    try:
        pct = round(float(dist.cdf(sampled)) * 100, 1)
        if isinstance(dist, WITH_MU_AND_SIGMA) and float(dist.sigma) > 0:
            return round((sampled - float(dist.mu)) / float(dist.sigma), 3), pct
        return None, pct
    except Exception:
        return None, None


def safe_param(v: object) -> object:
    """Convert values that can't be serialized to standard JSON to a display string."""
    import math

    if isinstance(v, float) and math.isinf(v):
        return "-∞" if v < 0 else "∞"
    return v


def extract_sampled_values(named_raw: dict[str, Any], name: str) -> list[float] | None:
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


def stored_unit(named_raw: dict[str, Any], name: str) -> str | None:
    """The unit a NamedValue's `stored_value` is expressed in, or `None` if none was recorded. Sampling converts a drawn value into the model's base unit and records that unit on the NamedValue, while the distribution keeps the unit it was declared in."""
    entry = named_raw.get(name) or named_raw.get("root", {}).get(name)
    unit = entry.get("unit") if entry else None
    if isinstance(unit, dict):
        unit = unit.get("name")
    return unit if isinstance(unit, str) and unit else None


def in_unit(
    values: list[float], from_unit: str | None, to_unit: str | None
) -> list[float]:
    """Re-expresses `values` from `from_unit` in `to_unit`. They come back as they were when either unit is unknown, when the units are the same, or when pint cannot convert between them, so an unrecognized unit leaves the number visible instead of hiding the row."""
    if not from_unit or not to_unit or from_unit == to_unit:
        return values
    import numpy as np

    try:
        converted = ureg.Quantity(np.asarray(values, dtype=float), from_unit).to(
            to_unit
        )
    except (PintError, ValueError, TypeError):
        return values
    return [float(v) for v in np.ravel(converted.magnitude)]


def sampled_values_in_dist_unit(
    named_raw: dict[str, Any], dist: stochas.AnyDist
) -> list[float] | None:
    """The drawn scalars for `dist`, in the unit `dist` was declared in. A distribution's parameters, nominal, and chart are all in its declared unit, so the drawn value has to be too, or the z-score and percentile compare a base-unit number against declared-unit parameters."""
    values = extract_sampled_values(named_raw, dist.name)
    if values is None or dist.unit is None:
        return values
    return in_unit(values, stored_unit(named_raw, dist.name), str(dist.unit))


def extract_sampled_labels(named_raw: dict[str, Any], name: str) -> list[str] | None:
    """Pull every drawn label out of a NamedValue's stored_value for non-numeric distributions (e.g. categorical)."""
    entry = named_raw.get(name) or named_raw.get("root", {}).get(name)
    if entry is None:
        return None
    sv = entry.get("stored_value")
    if isinstance(sv, str):
        return [sv]
    if isinstance(sv, list) and sv and all(isinstance(v, str) for v in sv):
        return [v for v in sv if isinstance(v, str)]
    return None
