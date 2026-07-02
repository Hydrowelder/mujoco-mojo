"""
Shared metadata helpers for tagging `SignalManager.post()`/`.track()` calls with their physical
quantity, so callers don't need to hand-build Pint dimension/unit strings at every call site.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from mujoco_mojo.typing import Angle

if TYPE_CHECKING:
    from mujoco_mojo.stochas import UnitSystem

__all__ = [
    "Dimension",
    "angle_metadata",
    "angular_rate_metadata",
    "dim",
    "dimensionless_metadata",
    "force_or_torque",
    "merge_signal_metadata",
    "resolve_dimension_metadata",
    "torque_metadata",
    "unit",
]


class Dimension(StrEnum):
    """
    Pint dimension expressions for physical quantities whose concrete unit depends on the
    user's modeling scale (MuJoCo has no inherent unit system) -- use with `dim()`, which
    builds a `metadata={"dimension": ...}` entry for `SignalManager.post()`/`.track()`.
    """

    LENGTH = "[length]"
    VELOCITY = "[length] / [time]"
    ACCELERATION = "[length] / [time] ** 2"
    FORCE = "[mass] * [length] / [time] ** 2"
    ENERGY = "[mass] * [length] ** 2 / [time] ** 2"
    # Same Pint dimensionality as ENERGY (both reduce to mass*length^2/time^2). The term
    # order is deliberately different so Python's enum machinery doesn't collapse this into
    # an alias of ENERGY -- Pint normalizes term order, so the two remain dimensionally
    # interchangeable. torque_metadata() adds an extra "quantity" key since Pint alone can't
    # tell torque and energy apart.
    TORQUE = "[length] ** 2 * [mass] / [time] ** 2"
    LINEAR_MOMENTUM = "[mass] * [length] / [time]"
    ANGULAR_MOMENTUM = "[mass] * [length] ** 2 / [time]"
    TIME = "[time]"
    MASS = "[mass]"
    DIMENSIONLESS = "[]"


def _dimension_str_to_unit_string(dimension_str: str, unit_system: UnitSystem) -> str:
    """Substitutes base unit names into a Pint dimension expression to produce a concrete unit string (e.g. `"[length] / [time]"` + SI -> `"m / second"`)."""
    replacements = {
        "[length]": unit_system.length,
        "[mass]": unit_system.mass,
        "[time]": unit_system.time,
        "[temperature]": unit_system.temperature,
        "[current]": unit_system.current,
        "[substance]": unit_system.amount,
        "[luminosity]": unit_system.luminosity,
    }
    s = dimension_str
    for token, base in replacements.items():
        if base is not None:
            s = s.replace(token, base)
    return s


def resolve_dimension_metadata(
    meta: dict[str, str], unit_system: UnitSystem
) -> dict[str, str]:
    """Adds a concrete `"unit"` string to `meta` derived from its `"dimension"` key and the given `unit_system`. The `"dimension"` key is preserved so callers can still see both the physical quantity type and the concrete unit. Dimensionless signals (`dimension="[]"`) are left unchanged. All other keys in `meta` (e.g. `"quantity"`) are preserved."""
    if "dimension" not in meta or meta["dimension"] == "[]":
        return meta
    concrete = _dimension_str_to_unit_string(meta["dimension"], unit_system)
    return {**meta, "unit": concrete}


def dim(dimension: Dimension | str) -> dict[str, str]:
    """Builds a `dimension=`-keyed metadata entry. Accepts either a `Dimension` enum member or a Pint unit name string (e.g. `"inch"`), in which case Pint looks up the matching `Dimension` member by dimensionality."""
    if isinstance(dimension, Dimension):
        # check Dimension first -- Dimension is a StrEnum and is also an instance of str,
        # so this must come before the str branch to avoid the Pint-lookup path running on
        # a known Dimension value (which would return the wrong enum member for TORQUE vs ENERGY)
        return {"dimension": str(dimension)}
    from mujoco_mojo.stochas import ureg

    target = ureg.get_dimensionality(dimension)
    for member in Dimension:
        if ureg.get_dimensionality(member.value) == target:
            return {"dimension": str(member)}
    raise ValueError(
        f"No Dimension member matches the Pint dimensionality of unit {dimension!r}"
    )


def unit(unit: str) -> dict[str, str]:
    """Builds a `unit=`-keyed metadata entry."""
    return {"unit": unit}


def dimensionless_metadata() -> dict[str, str]:
    """Tags a signal as known to have no units (e.g. quaternions, rotation matrices, axis vectors, enum/index values), distinguishing "known to be unitless" from "nobody tagged this column"."""
    return dim(Dimension.DIMENSIONLESS)


def angle_metadata() -> dict[str, str]:
    """Tags a signal as an angle in radians. MuJoCo's compiled model always stores angles in radians regardless of the XML `angle=` attribute, so this is a concrete unit rather than a scale-ambiguous dimension."""
    return unit(str(Angle.RADIAN))


def angular_rate_metadata(per: str = "second") -> dict[str, str]:
    """Tags a signal as an angular rate (e.g. angular velocity, angular acceleration) in radians per `per`."""
    return unit(f"{Angle.RADIAN} / {per}")


def torque_metadata() -> dict[str, str]:
    """Tags a signal as torque. Includes an extra `quantity` hint since torque and energy share the same Pint dimensionality and can't be told apart by dimension alone."""
    return {**dim(Dimension.TORQUE), "quantity": "torque"}


def force_or_torque(jnt_type: int) -> dict[str, str]:
    """Returns force metadata for a slide joint's generalized force, or torque metadata for any rotational joint (hinge/ball/free)."""
    import mujoco

    if jnt_type == mujoco.mjtJoint.mjJNT_SLIDE:
        return dim(Dimension.FORCE)
    return torque_metadata()


def merge_signal_metadata(
    builtin: dict[str, str] | None,
    channel: str,
    user_metadata: Mapping[str, dict[str, Any] | None] | None,
    *,
    unit_system: UnitSystem | None = None,
) -> dict[str, Any] | None:
    """Merges a built-in default metadata dict with the caller-supplied override/extension for `channel`, with user-supplied keys winning on conflict. If `unit_system` is provided and `builtin` contains a `"dimension"` key, the dimension is resolved to a concrete unit string. Returns `None` if both are empty."""
    if builtin is not None and unit_system is not None:
        builtin = resolve_dimension_metadata(builtin, unit_system)
    user_override = (user_metadata or {}).get(channel)
    merged = {**(builtin or {}), **(user_override or {})}
    return merged or None
