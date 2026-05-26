from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, cast

if TYPE_CHECKING:
    from typing import Self

import polars as pl
from scipy.spatial.transform import Rotation as R

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
        Matches exact scalars (':nutation_deg') or vector groups (':x').
        """
        # Matches ':attr' at the end of a string OR ':attr' followed by anything
        return _MojoFrame.from_pl(self._df.select(pl.col(rf"^.*/{attr}(:.*)?$")))

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

    def get_manifest(self, extra_columns: list[str] | None = None) -> ColumnManifest:
        """Returns the structured manifest used by the frontend. extra_columns are appended to 'all' and included in rotatable/quat discovery."""
        bm = self._get_base_map(extra_columns)
        return {
            "all": list(self._df.columns) + (extra_columns or []),
            "rotatable_vectors": sorted(
                b for b, s in bm.items() if {"x", "y", "z"}.issubset(s) and "w" not in s
            ),
            "available_quats": sorted(
                b for b, s in bm.items() if {"w", "x", "y", "z"}.issubset(s)
            ),
        }

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

        # extract roation data (N, 4)
        q_cols = [f"{quat_base}:{k}" for k in "xyzw"]  # w last for scipy!
        qs = self._df.select(q_cols).to_numpy()
        transformer = R.from_quat(qs)
        if invert:
            transformer = transformer.inv()

        # rotate all of the rotatables
        new_columns = []
        for base in self.rotatable_bases:
            v_cols = [f"{base}:x", f"{base}:y", f"{base}:z"]
            vs = self._df.select(v_cols).to_numpy()

            v_rot = transformer.apply(vs)  # apply the rotation here!

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
