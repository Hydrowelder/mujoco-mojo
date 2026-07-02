from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, cast

if TYPE_CHECKING:
    from typing import Self

    from mujoco_mojo.stochas import UnitSystem

import numpy as np
import polars as pl
import pyarrow.parquet as pq

from mujoco_mojo.typing import (
    ActuatorName,
    BodyName,
    CameraName,
    EqualityName,
    FlexName,
    GeomName,
    InstanceName,
    JointName,
    LightName,
    SensorName,
    SignalCategory,
    SiteName,
    TendonName,
)
from mujoco_mojo.utils.defaults import TIME_COLUMN_NAME
from mujoco_mojo.utils.filters import AnyFilter
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)


def read_column_metadata(path: Path | str) -> dict[str, dict[str, Any]]:
    """Reads the per-column metadata dict from the parquet file footer written by `SignalManager`. Returns an empty dict if the file has no embedded metadata."""
    file_meta = pq.read_metadata(str(path)).metadata
    if not file_meta:
        return {}
    raw = file_meta.get(b"column_metadata")
    if raw is None:
        return {}
    return json.loads(raw.decode())  # type: ignore[no-any-return]


class _MojoFrame(pl.DataFrame):
    """
    Internal implementation of MojoFrame to house static loaders.
    By using an underscored name, we avoid redeclaration errors later.
    """

    @classmethod
    def from_metadata(
        cls, path: Path | str, *args: Any, **kwargs: Any
    ) -> MojoDataFrame:
        """Instantiates a zero-row DataFrame for fast schema discovery."""
        return cls.from_pl(pl.read_parquet(source=path, n_rows=0, *args, **kwargs))

    @classmethod
    def read_parquet(
        cls,
        path: Path | str,
        columns: list[int] | list[str] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> MojoDataFrame:
        """Loads a DataFrame containing only the specific telemetry columns requested."""
        return cls.from_pl(
            pl.read_parquet(source=path, columns=columns, *args, **kwargs)
        )

    @classmethod
    def from_pl(cls, df: pl.DataFrame) -> MojoDataFrame:
        """
        Converts a standard Polars DataFrame into a MojoFrame for the static analyzer.
        """
        return cast(MojoDataFrame, df)

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], *args: Any, **kwargs: Any
    ) -> MojoDataFrame:
        """Creates a MojoFrame from a dictionary."""
        return cls.from_pl(pl.DataFrame(data=data, *args, **kwargs))


if TYPE_CHECKING:
    # MojoFrame is seen by the IDE as the combination of:
    # 1. loaders (_MojoFrame)
    # 2. Polars methods (pl.DataFrame)
    # 3. namespace (MojoFrameProtocol)
    class MojoDataFrame(_MojoFrame):
        @property
        def mojo(self) -> MojoNamespace: ...

        # override polars methods that return DataFrame so the type propagates
        def select(self, *args: Any, **kwargs: Any) -> Self: ...
        def filter(self, *args: Any, **kwargs: Any) -> Self: ...
        def with_columns(self, *args: Any, **kwargs: Any) -> Self: ...
        def sort(self, *args: Any, **kwargs: Any) -> Self: ...
        def head(self, *args: Any, **kwargs: Any) -> Self: ...
        def tail(self, *args: Any, **kwargs: Any) -> Self: ...
        def limit(self, *args: Any, **kwargs: Any) -> Self: ...
        def slice(self, *args: Any, **kwargs: Any) -> Self: ...
        def rename(self, *args: Any, **kwargs: Any) -> Self: ...
        def drop(self, *args: Any, **kwargs: Any) -> Self: ...
        def drop_nulls(self, *args: Any, **kwargs: Any) -> Self: ...
        def unique(self, *args: Any, **kwargs: Any) -> Self: ...
        def sample(self, *args: Any, **kwargs: Any) -> Self: ...
        def join(self, *args: Any, **kwargs: Any) -> Self: ...
        def hstack(self, *args: Any, **kwargs: Any) -> Self: ...
        def vstack(self, *args: Any, **kwargs: Any) -> Self: ...
else:
    # At runtime, it's just our internal class
    MojoDataFrame = _MojoFrame


class ColumnManifest(TypedDict):
    """Manifest of all columns available for plotting."""

    all: list[str]
    """Manifest of all columns available for plotting."""

    rotatable_vectors: list[str]
    """All columns in self.all which are available be rotated using self.available_quats."""

    available_quats: list[str]
    """All quaternion names which have enough information to rotate self.rotateable_vectors."""

    column_metadata: dict[str, dict[str, str]]
    """All per-column signal metadata keyed by column name. Contains all metadata keys (e.g. `unit`, `dimension`, custom keys) for every column that has any metadata. Populated only when `column_metadata` is passed to `get_manifest()`."""


class MojoNamespace:
    """
    Enhanced Polars DataFrame for MuJoCo Mojo telemetry.

    Supports hierarchical signal filtering and common physics transformations.
    """

    def __init__(self, df: pl.DataFrame):
        self._df = df

    @property
    def time(self) -> pl.Series:
        """Access the master simulation time column."""
        return self._df.get_column(TIME_COLUMN_NAME)

    def select_category(self, category: SignalCategory | str) -> MojoDataFrame:
        """Filter columns belonging to a specific SignalCategory (e.g., 'Bodies')."""
        return _MojoFrame.from_pl(self._df.select(pl.col(rf"^{category}/.*$")))

    def select_name(self, name: str) -> MojoDataFrame:
        """General filter for columns associated with a specific object name (e.g., 'racket')."""
        # Matches Category/Name:Attr or Category/Name/Sub:Attr
        return _MojoFrame.from_pl(self._df.select(pl.col(rf"^[^/]+/{name}/.*$")))

    def select_channel(self, channel: str) -> MojoDataFrame:
        """
        Selects all components of a specific channel across any category.

        Matches the logical 'folder' before the attribute separator.
        Example: 'xpos' matches 'Bodies/Hand/xpos:x' and 'Bodies/Hand/xpos:y'.
        """
        # Regex Breakdown:
        # ^.*/        -> Start and match any prefix ending in a slash (the path)
        # {channel}   -> The specific channel name (e.g., xpos)
        # (?::.*)?    -> Optionally match a colon followed by any attribute component
        # $           -> End of string
        return _MojoFrame.from_pl(self._df.select(pl.col(rf"^.*/{channel}(?::.*)?$")))

    def select_attribute(self, attr: str) -> MojoDataFrame:
        """
        Selects a specific attribute across all categories and objects.
        Matches columns ending in ':attr' (e.g. attr='x' matches 'Bodies/racket/xpos:x' and 'Sensors/gyro/data:x').
        """
        return _MojoFrame.from_pl(self._df.select(pl.col(rf"^.*:{attr}$")))

    def select_path_part(self, part: str) -> MojoDataFrame:
        """
        Selects any column whose full path contains `part` as a substring, anywhere.

        Unlike the other `select_*` methods, this does not anchor to a specific position in the path (category, name, channel, or attribute) - it matches `part` wherever it appears.

        Example:
            `select_path_part("racket")` matches `Bodies/racket/xpos:x`, `Custom/MyGroup:racket`, and `Bodies/racket_arm/xpos:x`.

        """
        return _MojoFrame.from_pl(
            self._df.select([c for c in self._df.columns if part in c])
        )

    def select_custom(self, name: str) -> MojoDataFrame:
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.CUSTOM}/{name}/.*$"))
        )

    def select_body(self, name: BodyName) -> MojoDataFrame:
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.BODIES}/{name}/.*$"))
        )

    def select_joint(self, name: JointName) -> MojoDataFrame:
        """Select all signals belonging to a specific Joint (qpos, qvel, etc.)."""
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.JOINTS}/{name}/.*$"))
        )

    def select_site(self, name: SiteName) -> MojoDataFrame:
        """Select all signals recorded at a specific Site."""
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.SITES}/{name}/.*$"))
        )

    def select_geom(self, name: GeomName) -> MojoDataFrame:
        """Select all signals associated with a specific Geom (contacts, etc.)."""
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.GEOMS}/{name}/.*$"))
        )

    def select_sensor(self, name: SensorName) -> MojoDataFrame:
        """Select data from a specific named Sensor."""
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.SENSORS}/{name}/.*$"))
        )

    def select_actuator(self, name: ActuatorName) -> MojoDataFrame:
        """Select data from a specific Actuator."""
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.ACTUATORS}/{name}/.*$"))
        )

    def select_tendon(self, name: TendonName) -> MojoDataFrame:
        """Select data from a specific Tendon."""
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.TENDONS}/{name}/.*$"))
        )

    def select_camera(self, name: CameraName) -> MojoDataFrame:
        """Select pose or FOV data from a specific Camera."""
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.CAMERAS}/{name}/.*$"))
        )

    def select_light(self, name: LightName) -> MojoDataFrame:
        """Select pose or intensity data from a specific Light."""
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.LIGHTS}/{name}/.*$"))
        )

    def select_equality(self, name: EqualityName) -> MojoDataFrame:
        """Select force/error data from an Equality constraint."""
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.CONSTRAINTS}/{name}/.*$"))
        )

    def select_plugin(self, name: InstanceName) -> MojoDataFrame:
        """Select custom state data from a specific Plugin Instance."""
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.PLUGINS}/{name}/.*$"))
        )

    def select_flex(self, name: FlexName) -> MojoDataFrame:
        """Select vertex/stress data from a Deformable Flex object."""
        return _MojoFrame.from_pl(
            self._df.select(pl.col(rf"^{SignalCategory.DEFORMABLES}/{name}/.*$"))
        )

    def _get_base_map(
        self, extra_columns: list[str] | None = None
    ) -> dict[str, set[str]]:
        """
        Internal helper to group suffixes by their common prefixes.

        Example:
            'Bodies/racket/xvelr:x', 'Bodies/racket/xvelr:y' -> {'Bodies/racket/xvelr': {'x', 'y'}}

        extra_columns are included in discovery but are not expected to exist in self._df.

        """
        base_map: dict[str, set[str]] = {}
        for c in list(self._df.columns) + (extra_columns or []):
            if ":" in c:
                prefix, suffix = c.rsplit(":", 1)
                base_map.setdefault(prefix, set()).add(suffix)
        return base_map

    @property
    def rotatable_bases(self) -> set[str]:
        """Returns the unique base names for 3-component vectors (x, y, z)."""
        base_map = self._get_base_map()
        return {
            b
            for b, s in base_map.items()
            if {"x", "y", "z"}.issubset(s) and "w" not in s
        }

    @property
    def quaternion_bases(self) -> set[str]:
        """Returns the unique base names for 4-component quaternions (w, x, y, z)."""
        base_map = self._get_base_map()
        return {b for b, s in base_map.items() if {"w", "x", "y", "z"}.issubset(s)}

    @property
    def rotatable_columns(self) -> list[tuple[str, str, str]]:
        """Returns column names ending in `:x`, `:y`, or `:z` (excluding quaternions which end with `:w`)."""
        expanded = []
        for base in self.rotatable_bases:
            expanded.extend([f"{base}:x", f"{base}:y", f"{base}:z"])
        return expanded

    @property
    def quaternion_columns(self) -> list[str]:
        """
        Returns all columns that form a full quaternion group. Specifically looks for columns ending with `quat:w`, `quat:x`, `quat:y`, `quat:z`.
        """
        expanded = []
        for base in self.quaternion_bases:
            expanded.extend([f"{base}:w", f"{base}:x", f"{base}:y", f"{base}:z"])
        return expanded

    def get_manifest(
        self,
        extra_columns: list[str] | None = None,
        column_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> ColumnManifest:
        """Returns the structured manifest used by the frontend. `extra_columns` are appended to `all` and included in rotatable/quat discovery. Pass `column_metadata` (from `read_column_metadata()`) to populate `column_units`."""
        bm = self._get_base_map(extra_columns)
        all_cols = list(self._df.columns) + (extra_columns or [])
        meta = column_metadata or {}
        col_meta = {col: m for col in all_cols if (m := meta.get(col)) is not None}
        return {
            "all": all_cols,
            "rotatable_vectors": sorted(
                b for b, s in bm.items() if {"x", "y", "z"}.issubset(s) and "w" not in s
            ),
            "available_quats": sorted(
                b for b, s in bm.items() if {"w", "x", "y", "z"}.issubset(s)
            ),
            "column_metadata": col_meta,
        }

    def with_unit_system(
        self,
        target: UnitSystem,
        *,
        path: Path | str | None = None,
        column_metadata: dict[str, dict[str, Any]] | None = None,
        assume_source: UnitSystem | None = None,
    ) -> MojoDataFrame:
        """
        Converts all columns with known units into the target unit system.

        For each column whose metadata carries a concrete `"unit"` key, applies a unit conversion from that stored unit into the equivalent unit in `target`. If `assume_source` is given, columns that only carry a `"dimension"` key (no concrete unit) are treated as if their source unit is the corresponding unit in `assume_source`, so they are converted too.

        All conversions are collected and applied in a single `with_columns()` call (Polars handles the vectorised execution across columns), so this is equivalent in cost to one pass over the data regardless of how many unit groups there are.

        Args:
            target: The target unit system (e.g. `UnitSystem.si()`).
            path: Path to the parquet file to read column metadata from. Used when `column_metadata` is not passed directly.
            column_metadata: Pre-loaded metadata dict (from `read_column_metadata()`). Takes precedence over `path`.
            assume_source: When set, columns with only a `"dimension"` tag (no `"unit"`) are converted as if they were expressed in the corresponding unit from this system.

        """
        from mujoco_mojo.stochas import UnitSystem as _US
        from mujoco_mojo.stochas import ureg
        from mujoco_mojo.utils.filters.filters import UnitFilter

        meta: dict[str, dict[str, Any]]
        if column_metadata is not None:
            meta = column_metadata
        elif path is not None:
            meta = read_column_metadata(path)
        else:
            meta = {}

        def _base_map(us: _US) -> dict[str, str]:
            return {
                k: v
                for k, v in {
                    "[length]": us.length,
                    "[mass]": us.mass,
                    "[time]": us.time,
                    "[temperature]": us.temperature,
                    "[current]": us.current,
                    "[substance]": us.amount,
                    "[luminosity]": us.luminosity,
                }.items()
                if v is not None
            }

        target_map = _base_map(target)
        source_map = _base_map(assume_source) if assume_source is not None else None

        def _unit_str_for(
            dim_dict: dict[str, Any], unit_map: dict[str, str]
        ) -> str | None:
            """Build a unit string from a dimensionality dict + base-unit map. Returns None if any required dimension is unconfigured."""
            u = ureg.dimensionless
            for dim_key, exp in dim_dict.items():
                base = unit_map.get(dim_key)
                if base is None:
                    return None
                u = u * ureg.parse_units(base) ** exp
            return str(u)

        exprs = []
        for col in self._df.columns:
            col_meta = meta.get(col, {})
            src_str: str | None = None

            if "unit" in col_meta:
                try:
                    dim_dict = dict(ureg.get_dimensionality(col_meta["unit"]))
                except Exception:
                    continue
                src_str = col_meta["unit"]
            elif source_map is not None and "dimension" in col_meta:
                dim_str = col_meta["dimension"]
                if dim_str == "[]":
                    continue
                try:
                    dim_dict = dict(ureg.get_dimensionality(dim_str))
                except Exception:
                    continue
                src_str = _unit_str_for(dim_dict, source_map)
                if src_str is None:
                    continue
            else:
                continue

            tgt_str = _unit_str_for(dim_dict, target_map)
            if tgt_str is None:
                continue

            try:
                exprs.append(
                    UnitFilter(from_unit=src_str, to_unit=tgt_str)
                    .apply(pl.col(col))
                    .alias(col)
                )
            except Exception:
                continue

        if not exprs:
            return _MojoFrame.from_pl(self._df)

        return _MojoFrame.from_pl(self._df.with_columns(exprs))

    def with_rotation(self, quat_base: str, invert: bool = True) -> MojoDataFrame:
        """
        Rotates all 3D vectors into a new frame using the specified quaternion.

        Args:
            quat_base (str): Prefix for the [w,x,y,z] quaternion group.
            invert (bool, optional): If True, performs World to Local transformation (use False with the same `quat_base` to revert the rotation). Defaults to True.

        Returns:
            Self: DataFrame with transformed :x, :y, :z columns.

        """
        # validate the quaternion family
        if quat_base not in self.quaternion_bases:
            logger.warning(
                f"Rotation failed: Quaternion base '{quat_base}' not found (please see the quaternion_bases property for valid columns)."
            )
            return _MojoFrame.from_pl(self._df)

        # extract rotation data (N, 4) as [x, y, z, w]
        q_cols = [f"{quat_base}:{k}" for k in "xyzw"]
        qs = self._df.select(q_cols).to_numpy()
        qs = qs / np.linalg.norm(qs, axis=1, keepdims=True)

        # vector part of the quaternion, negated for invert (conjugate == inverse for a unit quat)
        u = -qs[:, :3] if invert else qs[:, :3]
        w = qs[:, 3]

        # rotate all of the rotatables
        new_columns = []
        for base in self.rotatable_bases:
            v_cols = [f"{base}:x", f"{base}:y", f"{base}:z"]
            vs = self._df.select(v_cols).to_numpy()

            # quaternion-vector rotation: v' = v + 2w(u x v) + 2u x (u x v)
            cross_1 = np.cross(u, vs)
            cross_2 = np.cross(u, cross_1)
            v_rot = (
                vs + 2 * w[:, None] * cross_1 + 2 * cross_2
            )  # apply the rotation here!

            # prepare a new series for overwriting
            new_columns.extend(
                [
                    pl.Series(name=f"{base}:x", values=v_rot[:, 0]),
                    pl.Series(name=f"{base}:y", values=v_rot[:, 1]),
                    pl.Series(name=f"{base}:z", values=v_rot[:, 2]),
                ]
            )

        # overwrite with the new rotated data
        return _MojoFrame.from_pl(self._df.with_columns(new_columns))

    def with_filter_map(
        self, filter_map: dict[str, list[AnyFilter]], omit_time: bool = True
    ) -> MojoDataFrame:
        """
        Applies specific filter stacks to mapped columns.

        Args:
            filter_map (dict[str, list[AnyFilter]]): Dictionary mapping column names to a list of filters.
            omit_time (bool, optional): If True, skips the 'time' column even if present in the map. Defaults to True.

        Returns:
            Self: DataFrame with the transformed columns overwritten.

        """
        exprs = []
        for col_name, filters in filter_map.items():
            if col_name not in self._df.columns:
                continue

            if omit_time and col_name == TIME_COLUMN_NAME:
                continue

            expr = pl.col(col_name)
            for f in filters:
                expr = f.apply(expr)

            exprs.append(expr.alias(col_name))

        return _MojoFrame.from_pl(self._df.with_columns(exprs))

    def with_filters(
        self,
        filters: list[AnyFilter],
        columns: list[str] | None = None,
        omit_time: bool = True,
    ) -> MojoDataFrame:
        """
        Applies a sequential stack of filters to the specified or all numeric columns.

        Args:
            filters (list[AnyFilter]): List of Filter objects to apply in order (e.g., LowPass -> Derivative).
            columns (list[str] | None, optional): Specific columns to transform. If None, applies to all available columns. Defaults to None.
            omit_time (bool, optional): If True, prevents filters from being applied to the 'time' column. Defaults to True.

        Returns:
            Self: DataFrame with the transformed columns overwritten.

        """
        target_cols = columns or self._df.columns
        filter_map = {col: filters for col in target_cols}
        return self.with_filter_map(filter_map, omit_time=omit_time)


if not TYPE_CHECKING:
    pl.api.register_dataframe_namespace("mojo")(MojoNamespace)
