"""
The telemetry column model: a column's name, split into its parts, together with its metadata.

Every column in a telemetry file is named `Category/subgroup/...:attr` (for example `Bodies/box1/xpos:x`). `Column` is the one place that builds and parses that grammar, so the writer (`SignalManager.post`) and any reader agree on it, and a name part that would corrupt it fails loudly at construction instead of silently landing in a different position.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from functools import cached_property, lru_cache
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mujoco_mojo.typing import SignalCategory
from mujoco_mojo.utils.signal_metadata import ColumnMetadata

__all__ = [
    "MATRIX_ATTRS",
    "Column",
    "covering_pattern",
    "fan_out",
    "pose_column_names",
    "pose_missing_error",
]

_PART_PATTERN = r"^[^/:]+$"
"""One name part: non-empty, and free of the `/` and `:` that delimit the grammar."""

_Part = Annotated[str, Field(pattern=_PART_PATTERN)]

_REGEX_META = re.compile(r"([\\.+*?()|\[\]{}^$#&~-])")


def _escape(part: str) -> str:
    """Escapes every regex metacharacter, so a name part matches literally in polars' regex engine."""
    return _REGEX_META.sub(r"\\\1", part)


MATRIX_ATTRS = tuple(str(i) for i in range(9))
"""The attrs of a flattened 3x3 rotation matrix (`xmat`, `ximat`), which posts one column per element."""


class Column(BaseModel):
    """One telemetry column: its name parts and its metadata. `str(column)` is the column name as it appears in the telemetry file."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", use_attribute_docstrings=True
    )

    category: SignalCategory | _Part
    """Top-level category, e.g. `Bodies` (see `SignalCategory` for the built-in ones). Must not be empty or contain `/` or `:`."""

    subgroups: tuple[_Part, ...] = ()
    """Folders under the category, e.g. `("box1", "xpos")`. Empty parts are dropped; none may contain `/` or `:`."""

    attr: _Part | None = Field(default=None)
    """The component or attribute name, e.g. `x`. An empty value is treated as unset; it may not contain `/` or `:`."""

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

    @field_validator("subgroups", mode="before")
    @classmethod
    def _drop_empty_subgroups(cls, v: Any) -> Any:
        if isinstance(v, (tuple, list)):
            return tuple(str(s) for s in v if s)
        return v

    @field_validator("attr", mode="before")
    @classmethod
    def _empty_attr_is_unset(cls, v: Any) -> Any:
        return None if v == "" else v

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
        """
        Splits a column name into its parts; the exact inverse of `str()`. Raises `ValueError` for a malformed name (an empty part).

        Each distinct name is parsed once per process and then served from a cache, so parsing every column of a large frame repeatedly costs a dictionary lookup per name. The returned `Column` is shared, which is safe because it is frozen.
        """
        column = _parse(name)
        if metadata is None:
            return column
        return column.model_copy(
            update={"metadata": ColumnMetadata.validated(metadata)}
        )

    def covers(self, other: Column) -> bool:
        """
        True if `other` is this column or lies beneath it: the same category, `other`'s subgroups start with this column's subgroups, and this column's `attr` is unset or equal to `other`'s. Metadata is ignored.

        A partial column therefore selects a whole subtree: `Column(category="Bodies", subgroups=("box1",))` covers `Bodies/box1/xpos:x` and `Bodies/box1:ke_trans`.
        """
        n = len(self.subgroups)
        return (
            other.category == self.category
            and other.subgroups[:n] == self.subgroups
            and (self.attr is None or self.attr == other.attr)
        )

    def _pattern_body(self) -> str:
        path = "/".join(_escape(p) for p in (self.category, *self.subgroups))
        if self.attr is None:
            return f"{path}(?:[/:].*)?"
        return f"{path}(?:/[^:]*)?:{_escape(self.attr)}"

    def __contains__(self, other: Self | str) -> bool:
        """`child in parent`, the same test as `parent.covers(child)`; a name string is parsed first, and a string outside the telemetry grammar is never contained. Equality is untouched, so `==`, hashing, and `x in [columns]` keep meaning exact match."""
        column = other
        if isinstance(other, str):
            try:
                column = _parse(other)
            except ValueError:
                return False
        return isinstance(column, Column) and self.covers(column)


# `Category(/subgroup)*(:attr)?`, where no part is empty or contains '/' or ':'
_NAME = re.compile(r"([^/:]+)((?:/[^/:]+)*)(?::([^/:]+))?")


@lru_cache(maxsize=65536)
def _parse(name: str) -> Column:
    # cached per name, so the model's own validation runs once per distinct name
    match = _NAME.fullmatch(name)
    if match is None:
        raise ValueError(
            f"Malformed column name {name!r}: expected 'Category/subgroup/...:attr' with no empty part"
        )
    category, subgroups, attr = match.groups()
    return Column(
        category=category,
        subgroups=tuple(subgroups[1:].split("/")) if subgroups else (),
        attr=attr,
    )


def covering_pattern(columns: Iterable[Column]) -> str:
    """
    One anchored regex matching every column name that any of `columns` covers (see `Column.covers`), with every name part escaped so it matches literally.

    It lets a frame select by `Column` inside polars' regex engine instead of parsing each column name in Python, which matters for frames with tens of thousands of columns.
    """
    return "^(?:" + "|".join(c._pattern_body() for c in columns) + ")$"


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


@lru_cache(maxsize=4096)
def pose_column_names(
    source: Column | str, pos_channel: str = "xpos", quat_channel: str = "quat"
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """
    The telemetry column names holding an object's pose: `(x, y, z)` position names and `(w, x, y, z)` quaternion names, in that order.

    `source` names the object, e.g. `Sites/A` or `Column(category="Sites", subgroups=("A",))`, and gives `Sites/A/xpos:x` through `Sites/A/quat:z` for the default channels. Cached per source, so repeated lookups cost a dictionary hit. Raises `ValueError` if `source` names a single column (has an attr) instead of an object.
    """
    column = Column.parse(source) if isinstance(source, str) else source
    if column.attr is not None:
        raise ValueError(
            f"{str(column)!r} names a single column; pass the object it belongs to (for example {'/'.join((column.category, *column.subgroups))!r})"
        )
    pos = fan_out(column.category, (*column.subgroups, pos_channel), "xyz")
    quat = fan_out(column.category, (*column.subgroups, quat_channel), "wxyz")
    return tuple(str(c) for c in pos), tuple(str(c) for c in quat)


def pose_missing_error(
    source: Column | str,
    available: Iterable[str],
    pos_channel: str = "xpos",
    quat_channel: str = "quat",
) -> ValueError | None:
    """A `ValueError` naming every pose column of `source` that is not in `available`, or `None` if the pose is complete."""
    pos_names, quat_names = pose_column_names(source, pos_channel, quat_channel)
    have = (
        available if isinstance(available, (set, frozenset, dict)) else set(available)
    )
    missing = [n for n in (*pos_names, *quat_names) if n not in have]
    if not missing:
        return None
    return ValueError(
        f"No pose for {str(source)!r}: missing columns {', '.join(missing)}. "
        f"Were they requested (for example `request(channels=[{pos_channel!r}, {quat_channel!r}])`)?"
    )
