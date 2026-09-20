"""
The telemetry column model: a column's name, split into its parts, together with its metadata.

Every column in a telemetry file is named `Category/subgroup/...:attr` (for example `Bodies/box1/xpos:x`). `Column` is the one place that builds and parses that grammar, so the writer (`SignalManager.post`) and any reader agree on it, and a name part that would corrupt it fails loudly at construction instead of silently landing in a different position.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from functools import cached_property
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mujoco_mojo.typing import SignalCategory
from mujoco_mojo.utils.signal_metadata import ColumnMetadata

__all__ = ["MATRIX_ATTRS", "Column", "fan_out"]

_RESERVED = ("/", ":")

MATRIX_ATTRS = tuple(str(i) for i in range(9))
"""The attrs of a flattened 3x3 rotation matrix (`xmat`, `ximat`), which posts one column per element."""


def _check_part(label: str, value: str) -> str:
    if any(ch in value for ch in _RESERVED):
        raise ValueError(
            f"{label} {value!r} would corrupt the column name grammar ('/' and ':' are reserved)"
        )
    return value


class Column(BaseModel):
    """One telemetry column: its name parts and its metadata. `str(column)` is the column name as it appears in the telemetry file."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", use_attribute_docstrings=True
    )

    category: SignalCategory | str
    """Top-level category, e.g. `Bodies` (see `SignalCategory` for the built-in ones)."""

    subgroups: tuple[str, ...] = ()
    """Folders under the category, e.g. `("box1", "xpos")`. Empty parts are dropped."""

    attr: str | None = None
    """The component or attribute name, e.g. `x`. An empty value is treated as unset."""

    metadata: ColumnMetadata = Field(default_factory=ColumnMetadata)
    """Metadata persisted for this column in the telemetry file's footer. Validated when the column is built (a plain dict is accepted), so the per-timestep merges that produce it can skip validation."""

    @field_validator("metadata", mode="before")
    @classmethod
    def _metadata_is_validated(cls, v: Any) -> Any:
        if v is None:
            return ColumnMetadata()
        if isinstance(v, (ColumnMetadata, dict)):
            return ColumnMetadata.validated(v)
        return v

    @field_validator("category", mode="before")
    @classmethod
    def _category_is_a_plain_string(cls, v: Any) -> Any:
        # a SignalCategory member is a str subclass; store its plain value
        return str(v) if isinstance(v, str) else v

    @field_validator("category")
    @classmethod
    def _category_is_valid(cls, v: str) -> str:
        if not v:
            raise ValueError("category must not be empty")
        return _check_part("category", v)

    @field_validator("subgroups", mode="before")
    @classmethod
    def _drop_empty_subgroups(cls, v: Any) -> Any:
        if isinstance(v, (tuple, list)):
            return tuple(str(s) for s in v if s)
        return v

    @field_validator("subgroups")
    @classmethod
    def _subgroups_are_valid(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for part in v:
            _check_part("subgroup", part)
        return v

    @field_validator("attr")
    @classmethod
    def _attr_is_valid(cls, v: str | None) -> str | None:
        if not v:
            return None
        return _check_part("attr", v)

    @cached_property
    def _hash(self) -> int:
        # a cached_property lives in the instance `__dict__`, so reading it skips pydantic's slow private-attribute lookup: `SignalManager.post` hashes a column every timestep
        return hash((self.category, self.subgroups, self.attr, self.metadata))

    def __hash__(self) -> int:
        return self._hash

    def model_copy(
        self, *, update: Mapping[str, Any] | None = None, deep: bool = False
    ) -> Self:
        copied = super().model_copy(update=update, deep=deep)
        # the copy carries this column's cached hash, which is stale once a field is updated
        vars(copied).pop("_hash", None)
        return copied

    def __str__(self) -> str:
        name = "/".join((self.category, *self.subgroups))
        return f"{name}:{self.attr}" if self.attr else name

    @classmethod
    def parse(cls, name: str, metadata: ColumnMetadata | None = None) -> Column:
        """Splits a column name into its parts; the exact inverse of `str()`. Raises `ValueError` for a malformed name (an empty part)."""
        path, sep, attr = name.rpartition(":")
        if not sep:
            path, attr = name, ""
        elif not attr:
            raise ValueError(f"Malformed column name {name!r}: empty attribute")
        parts = path.split("/")
        if not all(parts):
            raise ValueError(f"Malformed column name {name!r}: empty part")
        return cls(
            category=parts[0],
            subgroups=tuple(parts[1:]),
            attr=attr or None,
            metadata=metadata if metadata is not None else ColumnMetadata(),
        )


def fan_out(
    category: str,
    subgroups: tuple[str, ...],
    attrs: Iterable[str],
    metadata: ColumnMetadata | None = None,
) -> tuple[Column, ...]:
    """One `Column` per attr, all sharing the same category, subgroups, and metadata (e.g. the `x`/`y`/`z`/`m` columns of a vector). Build these once and reuse them: `SignalManager.post` is called every timestep."""
    meta = metadata if metadata is not None else ColumnMetadata()
    return tuple(
        Column(category=category, subgroups=subgroups, attr=attr, metadata=meta)
        for attr in attrs
    )
