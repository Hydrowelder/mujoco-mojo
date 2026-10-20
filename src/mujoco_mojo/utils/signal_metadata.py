"""
Shared metadata model and helpers for tagging `SignalManager.post()`/`.track()` calls with their physical
quantity, so callers don't need to hand-build Pint dimension/unit strings at every call site.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum, StrEnum
from functools import cache
from typing import TYPE_CHECKING, Any

import pint
from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_serializer,
    model_validator,
)

from mujoco_mojo.typing import Angle
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from mujoco_mojo.stochas import UnitSystem

logger = get_logger(__name__)

__all__ = [
    "ColumnMetadata",
    "Dimension",
    "MetadataLike",
    "MetadataOverrides",
    "TransformType",
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
    user's modeling scale (MuJoCo has no inherent unit system). Use with `dim()`, which
    builds a `metadata={"dimension": ...}` entry for `SignalManager.post()`/`.track()`.
    """

    LENGTH = "[length]"
    VELOCITY = "[length] / [time]"
    ACCELERATION = "[length] / [time] ** 2"
    FORCE = "[mass] * [length] / [time] ** 2"
    ENERGY = "[mass] * [length] ** 2 / [time] ** 2"
    # Same Pint dimensionality as ENERGY (both reduce to mass*length^2/time^2). The term
    # order is deliberately different so Python's enum machinery doesn't collapse this into
    # an alias of ENERGY. Pint normalizes term order, so the two remain dimensionally
    # interchangeable. torque_metadata() adds an extra "quantity" key since Pint alone can't
    # tell torque and energy apart.
    TORQUE = "[length] ** 2 * [mass] / [time] ** 2"
    LINEAR_MOMENTUM = "[mass] * [length] / [time]"
    ANGULAR_MOMENTUM = "[mass] * [length] ** 2 / [time]"
    TIME = "[time]"
    MASS = "[mass]"
    DIMENSIONLESS = "[]"


class TransformType(StrEnum):
    """
    How a signal must be re-expressed under `MojoDataFrame.mojo.change_frame()`.

    `POINT`, `VECTOR`, and `QUATERNION` tag channels grouped into a `:x/:y/:z` (or `:w/:x/:y/:z`) family (see `rotatable_bases`/`quaternion_bases`), which `change_frame` refuses to touch untagged. `SCALAR` says the value does not depend on the frame at all. A lone scalar column needs no tag to be left alone, so tagging it is optional and states the intent; the tag matters for a group whose columns happen to be named `:x/:y/:z` (or `:w/:x/:y/:z`) without being a vector, which it keeps out of any rotation.
    """

    POINT = "point"
    """Translate then rotate (positions)."""

    VECTOR = "vector"
    """Rotate only (velocities, forces, accelerations, momenta, directions)."""

    QUATERNION = "quaternion"
    """Compose: q' = q_b^-1 (x) q."""

    SCALAR = "scalar"
    """Unchanged by a frame change (energies, distances, angles, magnitudes, joint values)."""

    @property
    def metadata(self) -> ColumnMetadata:
        """Builds a `ColumnMetadata` carrying only this `transform_type`, tagging how a signal's grouped vector/quaternion components transform under `MojoDataFrame.mojo.change_frame()`."""
        return _transform_metadata(self)


class ColumnMetadata(BaseModel):
    """
    Metadata describing one telemetry column, stored per column in the parquet footer.

    The declared fields are the ones mujoco-mojo understands and validates. Any other key is kept as-is (`extra="allow"`), so callers can attach their own labels. Unset fields are omitted when dumping, so the serialized form only carries what was actually tagged.
    """

    model_config = ConfigDict(extra="allow", frozen=True, use_attribute_docstrings=True)

    unit: str | None = None
    """Concrete Pint unit string, e.g. `meter / second`. When `dimension` is also set, both must have the same dimensionality."""

    dimension: str | None = None
    """Pint dimension expression for the physical quantity, e.g. `[length] / [time]`. Tags the quantity without committing to a concrete unit, which is the right choice for built-in signals since the modeling unit system isn't knowable."""

    quantity: str | None = None
    """Free-form hint that separates quantities Pint cannot tell apart, e.g. `torque` versus energy."""

    transform_type: TransformType | None = None
    """How this signal's grouped `:x/:y/:z` or `:w/:x/:y/:z` components transform under `change_frame()`. Only set it for channels that are grouped into such a family."""

    enumeration_map: dict[str, int] | None = None
    """Labels for an integer-coded signal, mapping each label to its code, e.g. `{"IDLE": 0, "RUNNING": 1}`. The column still holds the codes (as floats, like all telemetry); `convert_enums()` swaps them for labels and the Dojo shows the labels on the plot. Codes must be unique. Build it from an enum class with `ColumnMetadata.from_enum()`."""

    @field_validator("enumeration_map", mode="before")
    @classmethod
    def _enumeration_map_from_json(cls, v: Any) -> Any:
        # the Signal Lab's Signal Out node edits this as free text
        if not isinstance(v, str):
            return v
        try:
            return json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(
                f'Invalid signal metadata enumeration_map {v!r}: expected a JSON object such as {{"IDLE": 0, "RUNNING": 1}}'
            ) from e

    @field_validator("enumeration_map")
    @classmethod
    def _enumeration_map_is_unambiguous(
        cls, v: dict[str, int] | None
    ) -> dict[str, int] | None:
        if not v:
            return None
        if "" in v:
            raise ValueError("Signal metadata enumeration_map has an empty label")
        seen: dict[int, str] = {}
        for label, code in v.items():
            if code in seen:
                raise ValueError(
                    f"Signal metadata enumeration_map gives code {code} to both {seen[code]!r} and {label!r}; each code needs exactly one label"
                )
            seen[code] = label
        return v

    @field_validator("dimension")
    @classmethod
    def _dimension_parses(cls, v: str | None) -> str | None:
        if v is None:
            return v
        from mujoco_mojo.stochas import ureg

        try:
            ureg.get_dimensionality(v)
        except (pint.UndefinedUnitError, pint.DefinitionSyntaxError) as e:
            raise ValueError(f"Invalid signal metadata dimension {v!r}: {e}") from e
        return v

    @field_validator("unit")
    @classmethod
    def _unit_parses(cls, v: str | None) -> str | None:
        if v is None:
            return v
        from mujoco_mojo.stochas import ureg

        try:
            ureg.parse_units(v)
        except pint.UndefinedUnitError as e:
            raise ValueError(f"Invalid signal metadata unit {v!r}: {e}") from e
        return v

    @field_validator("transform_type", mode="before")
    @classmethod
    def _transform_type_valid(cls, v: Any) -> Any:
        if v is None or isinstance(v, TransformType):
            return v
        try:
            return TransformType(v)
        except ValueError:
            valid = ", ".join(t.value for t in TransformType)
            raise ValueError(
                f"Invalid signal metadata transform_type {v!r}: expected one of {valid}"
            ) from None

    @model_validator(mode="after")
    def _unit_matches_dimension(self) -> ColumnMetadata:
        if self.unit is None or self.dimension is None:
            return self
        from mujoco_mojo.stochas import ureg

        parsed_unit = ureg.parse_units(self.unit)
        dimensionality = ureg.get_dimensionality(self.dimension)
        if parsed_unit.dimensionality != dimensionality:
            raise ValueError(
                f"Signal metadata unit {self.unit!r} ({parsed_unit.dimensionality}) do not "
                f"match dimension {self.dimension!r} ({dimensionality})"
            )
        return self

    @model_serializer(mode="wrap")
    def _omit_unset(self, handler: Any) -> dict[str, Any]:
        return {k: v for k, v in handler(self).items() if v is not None}

    def _set_values(self) -> dict[str, Any]:
        """The fields that are set (declared and extra), without validating or copying deeply."""
        declared = {
            name: value
            for name in type(self).model_fields
            if (value := getattr(self, name)) is not None
        }
        return {**declared, **(self.__pydantic_extra__ or {})}

    def __hash__(self) -> int:
        """Hashes the declared scalar fields only (equal objects still hash equal), so instances can key the per-timestep caches. `enumeration_map` is left out because a dict is not hashable; equality still compares it."""
        return hash((self.unit, self.dimension, self.quantity, self.transform_type))

    def __bool__(self) -> bool:
        """False when nothing is set, so `if metadata:` skips empty metadata."""
        return bool(self._set_values())

    def __or__(self, other: object) -> ColumnMetadata:
        """Merges two metadata objects, with the right side winning where both set a value. Extras are kept. The result is not re-validated (both sides already were, or are validated where they are registered), which keeps per-timestep merges cheap."""
        if not isinstance(other, ColumnMetadata):
            return NotImplemented
        return self.model_copy(update=other._set_values())

    @classmethod
    def from_enum(cls, enum_cls: type[Enum]) -> ColumnMetadata:
        """Builds the metadata for a signal that posts the integer values of `enum_cls`: an `enumeration_map` of every member's name to its value (iterating the class, so aliases are skipped), tagged dimensionless since a code has no unit. Raises `TypeError` if a member's value is not an integer, and `ValueError` if the class has no members."""
        mapping: dict[str, int] = {}
        for member in enum_cls:
            value = member.value
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(
                    f"{enum_cls.__name__}.{member.name} has value {value!r}; an enumeration_map needs integer codes"
                )
            mapping[member.name] = int(value)
        if not mapping:
            raise ValueError(f"{enum_cls.__name__} has no members to map")
        return dimensionless_metadata() | cls(enumeration_map=mapping)

    @classmethod
    def validated(cls, value: MetadataLike) -> ColumnMetadata:
        """Validates a metadata object or a plain dict (always, unlike `model_validate` on an instance), raising a `ValidationError` naming the bad field."""
        return cls.model_validate(
            value.model_dump() if isinstance(value, ColumnMetadata) else dict(value)
        )

    @classmethod
    def unchecked(cls, value: MetadataLike) -> ColumnMetadata:
        """Wraps a plain dict without validating it, for per-timestep merges. The merged result is validated once, where the signal is registered."""
        return (
            value if isinstance(value, ColumnMetadata) else cls.model_construct(**value)
        )

    @classmethod
    def lenient(cls, raw: Mapping[str, Any], *, where: str = "") -> ColumnMetadata:
        """Validates `raw`, but falls back to loading it unvalidated (with a warning) if it is invalid, so files written by other versions still open."""
        try:
            return cls.validated(raw)
        except ValidationError as e:
            logger.warning(f"Loading invalid column metadata{where}: {e}")
            return cls.model_construct(**raw)


MetadataLike = ColumnMetadata | Mapping[str, Any]
"""What callers may pass wherever metadata is accepted: a `ColumnMetadata` or a plain dict."""

MetadataOverrides = Mapping[str, MetadataLike | None]
"""Per-channel metadata overrides, keyed by channel name."""


@cache
def _transform_metadata(kind: TransformType) -> ColumnMetadata:
    return ColumnMetadata(transform_type=kind)


_BASE_TOKENS = (
    "[length]",
    "[mass]",
    "[time]",
    "[temperature]",
    "[current]",
    "[substance]",
    "[luminosity]",
)


def _base_units(unit_system: UnitSystem) -> tuple[str | None, ...]:
    """The unit system's base unit names, in `_BASE_TOKENS` order. Used as a hashable stand-in for the unit system itself."""
    return (
        unit_system.length,
        unit_system.mass,
        unit_system.time,
        unit_system.temperature,
        unit_system.current,
        unit_system.amount,
        unit_system.luminosity,
    )


def _dimension_str_to_unit_string(
    dimension_str: str, base_units: tuple[str | None, ...]
) -> str:
    """Substitutes base unit names into a Pint dimension expression to produce a concrete unit string (e.g. `"[length] / [time]"` + SI -> `"m / second"`)."""
    s = dimension_str
    for token, base in zip(_BASE_TOKENS, base_units, strict=True):
        if base is not None:
            s = s.replace(token, base)
    return s


@cache
def _resolve_dimension(
    meta: ColumnMetadata, base_units: tuple[str | None, ...]
) -> ColumnMetadata:
    assert meta.dimension is not None
    concrete = _dimension_str_to_unit_string(meta.dimension, base_units)
    return meta.model_copy(update={"unit": concrete})


def resolve_dimension_metadata(
    meta: ColumnMetadata, unit_system: UnitSystem
) -> ColumnMetadata:
    """Adds a concrete `unit` string to `meta` derived from its `dimension` and the given `unit_system`. The `dimension` is preserved so callers can still see both the physical quantity type and the concrete unit. Dimensionless signals (`dimension="[]"`) are left unchanged. All other fields (e.g. `quantity`) are preserved. Cached, since `merge_signal_metadata` runs every timestep."""
    if meta.dimension is None or meta.dimension == "[]":
        return meta
    return _resolve_dimension(meta, _base_units(unit_system))


@cache
def dim(dimension: Dimension | str) -> ColumnMetadata:
    """Builds a `dimension`-tagged `ColumnMetadata`. Accepts either a `Dimension` enum member or a Pint unit name string (e.g. `"inch"`), in which case Pint looks up the matching `Dimension` member by dimensionality."""
    if isinstance(dimension, Dimension):
        # check Dimension first: it's a StrEnum and is also an instance of str,
        # so this must come before the str branch to avoid the Pint-lookup path running on
        # a known Dimension value (which would return the wrong enum member for TORQUE vs ENERGY)
        return ColumnMetadata(dimension=str(dimension))
    from mujoco_mojo.stochas import ureg

    target = ureg.get_dimensionality(dimension)
    for member in Dimension:
        if ureg.get_dimensionality(member.value) == target:
            return ColumnMetadata(dimension=str(member))
    raise ValueError(
        f"No Dimension member matches the Pint dimensionality of unit {dimension!r}"
    )


@cache
def unit(unit: str) -> ColumnMetadata:
    """Builds a `unit`-tagged `ColumnMetadata`."""
    return ColumnMetadata(unit=unit)


def dimensionless_metadata() -> ColumnMetadata:
    """Tags a signal as known to have no units (e.g. quaternions, rotation matrices, axis vectors, enum/index values), distinguishing "known to be unitless" from "nobody tagged this column"."""
    return dim(Dimension.DIMENSIONLESS)


def angle_metadata() -> ColumnMetadata:
    """Tags a signal as an angle in radians. MuJoCo's compiled model always stores angles in radians regardless of the XML `angle=` attribute, so this is a concrete unit rather than a scale-ambiguous dimension."""
    return unit(str(Angle.RADIAN))


def angular_rate_metadata(per: str = "second") -> ColumnMetadata:
    """Tags a signal as an angular rate (e.g. angular velocity, angular acceleration) in radians per `per`."""
    return unit(f"{Angle.RADIAN} / {per}")


def torque_metadata() -> ColumnMetadata:
    """Tags a signal as torque. Includes an extra `quantity` hint since torque and energy share the same Pint dimensionality and can't be told apart by dimension alone."""
    return _torque_metadata()


@cache
def _torque_metadata() -> ColumnMetadata:
    return dim(Dimension.TORQUE) | ColumnMetadata(quantity="torque")


@cache
def force_or_torque(jnt_type: int) -> ColumnMetadata:
    """Returns force metadata for a slide joint's generalized force, or torque metadata for any rotational joint (hinge/ball/free)."""
    import mujoco

    if jnt_type == mujoco.mjtJoint.mjJNT_SLIDE:
        return dim(Dimension.FORCE)
    return torque_metadata()


def merge_signal_metadata(
    builtin: ColumnMetadata | None,
    channel: str,
    user_metadata: MetadataOverrides | None,
    *,
    unit_system: UnitSystem | None = None,
) -> ColumnMetadata:
    """Merges a built-in default with the caller-supplied override/extension for `channel`, with user-supplied fields winning on conflict. If `unit_system` is provided and `builtin` has a `dimension`, it is resolved to a concrete unit. Returns an empty `ColumnMetadata` if both are empty. Nothing here is validated: the result is validated when it is used to build a `Column`."""
    if builtin is not None and unit_system is not None:
        builtin = resolve_dimension_metadata(builtin, unit_system)
    override = (user_metadata or {}).get(channel)
    if override is None:
        return builtin if builtin is not None else ColumnMetadata()
    override_meta = ColumnMetadata.unchecked(override)
    return override_meta if builtin is None else builtin | override_meta
