from __future__ import annotations

from pathlib import Path
from typing import Self, TypedDict, cast

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
from mujoco_mojo.utils.filters import AnyFilter
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = ["DataFrame"]


class ColumnManifest(TypedDict):
    all: list[str]
    rotatable_vectors: list[str]
    available_quats: list[str]


class DataFrame(pl.DataFrame):
    """
    Enhanced Polars DataFrame for MuJoCo Mojo telemetry.

    Supports hierarchical signal filtering and common physics transformations.
    """

    @classmethod
    def from_metadata(cls, path: Path | str, *args, **kwargs) -> Self:
        """
        Instantiates a zero-row DataFrame containing only the schema.
        Perfect for fast column discovery and UI population.
        """
        schema_df = pl.read_parquet(source=path, n_rows=0, *args, **kwargs)
        return cast(Self, cls(schema_df))

    @classmethod
    def from_columns(
        cls, path: Path | str, columns: list[str], *args, **kwargs
    ) -> Self:
        """
        Instantiates a DataFrame containing only the specific columns requested.
        """
        df = pl.read_parquet(source=path, columns=columns, *args, **kwargs)
        return cast(Self, cls(df))

    def _from_pl(self, df: pl.DataFrame) -> Self:
        return cast(Self, self.__class__(df))

    def select_category(self, category: SignalCategory | str) -> Self:
        """Filter columns belonging to a specific SignalCategory (e.g., 'Bodies')."""
        return self._from_pl(self.select(pl.col(f"^{category}/.*")))

    def select_attribute(self, attr: str) -> Self:
        """
        Selects a specific attribute across all categories and objects.
        Matches exact scalars (':nutation_deg') or vector groups (':xvelr:x').
        """
        # Matches ':attr' at the end of a string OR ':attr:' followed by anything
        return self._from_pl(self.select(pl.col(f"^.*:{attr}(:.*)?$")))

    def select_body(self, name: BodyName) -> Self:
        return self._from_pl(self.select(pl.col(f"^{SignalCategory.BODIES}/{name}.*")))

    def select_joint(self, name: JointName) -> Self:
        """Select all signals belonging to a specific Joint (qpos, qvel, etc.)."""
        return self._from_pl(
            self.select(pl.col(f"^{SignalCategory.JOINTS}/{name}[:/].*"))
        )

    def select_site(self, name: SiteName) -> Self:
        """Select all signals recorded at a specific Site."""
        return self._from_pl(
            self.select(pl.col(f"^{SignalCategory.SITES}/{name}[:/].*"))
        )

    def select_geom(self, name: GeomName) -> Self:
        """Select all signals associated with a specific Geom (contacts, etc.)."""
        return self._from_pl(
            self.select(pl.col(f"^{SignalCategory.GEOMS}/{name}[:/].*"))
        )

    def select_sensor(self, name: SensorName) -> Self:
        """Select data from a specific named Sensor."""
        return self._from_pl(
            self.select(pl.col(f"^{SignalCategory.SENSORS}/{name}[:/].*"))
        )

    def select_actuator(self, name: ActuatorName) -> Self:
        """Select data from a specific Actuator."""
        return self._from_pl(
            self.select(pl.col(f"^{SignalCategory.ACTUATORS}/{name}[:/].*"))
        )

    def select_tendon(self, name: TendonName) -> Self:
        """Select data from a specific Tendon."""
        return self._from_pl(
            self.select(pl.col(f"^{SignalCategory.TENDONS}/{name}[:/].*"))
        )

    def select_camera(self, name: CameraName) -> Self:
        """Select pose or FOV data from a specific Camera."""
        return self._from_pl(
            self.select(pl.col(f"^{SignalCategory.CAMERAS}/{name}[:/].*"))
        )

    def select_light(self, name: LightName) -> Self:
        """Select pose or intensity data from a specific Light."""
        return self._from_pl(
            self.select(pl.col(f"^{SignalCategory.LIGHTS}/{name}[:/].*"))
        )

    def select_equality(self, name: EqualityName) -> Self:
        """Select force/error data from an Equality constraint."""
        return self._from_pl(
            self.select(pl.col(f"^{SignalCategory.CONSTRAINTS}/{name}[:/].*"))
        )

    def select_plugin(self, name: InstanceName) -> Self:
        """Select custom state data from a specific Plugin Instance."""
        return self._from_pl(
            self.select(pl.col(f"^{SignalCategory.PLUGINS}/{name}[:/].*"))
        )

    def select_flex(self, name: FlexName) -> Self:
        """Select vertex/stress data from a Deformable Flex object."""
        return self._from_pl(
            self.select(pl.col(f"^{SignalCategory.DEFORMABLES}/{name}[:/].*"))
        )

    def select_name(self, name: str) -> Self:
        """General filter for columns associated with a specific object name (e.g., 'racket')."""
        # Matches Category/Name:Attr or Category/Name/Sub:Attr
        return self._from_pl(self.select(pl.col(f"^[^/]+/{name}[:/].*")))

    def _get_base_map(self) -> dict[str, set[str]]:
        """
        Internal helper to group suffixes by their common prefixes.

        Example:
            'Bodies/racket:xvelr:x', 'Bodies/racket:xvelr:y' -> {'Bodies/racket:xvelr': {'x', 'y'}}

        """
        base_map: dict[str, set[str]] = {}
        for c in self.columns:
            if ":" in c:
                prefix, suffix = c.rsplit(":")  # we may have :ke_trans, or ke_rot, etc.
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

    def get_manifest(self) -> ColumnManifest:
        """Returns the structured manifest used by the frontend."""
        return {
            "all": self.columns,
            "rotatable_vectors": sorted(list(self.rotatable_bases)),
            "available_quats": sorted(list(self.quaternion_bases)),
        }

    def with_rotation(self, quat_base: str, invert: bool = True) -> Self:
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
            return self

        # extract roation data (N, 4)
        q_cols = [f"{quat_base}:{k}" for k in "xyzw"]  # w last for scipy!
        qs = self.select(q_cols).to_numpy()
        transformer = R.from_quat(qs)
        if invert:
            transformer = transformer.inv()

        # rotate all of the rotatables
        new_columns = []
        for base in self.rotatable_bases:
            v_cols = [f"{base}:x", f"{base}:y", f"{base}:z"]
            vs = self.select(v_cols).to_numpy()

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
        return self._from_pl(self.with_columns(new_columns))

    def with_filters(
        self,
        filters: list[AnyFilter],
        columns: list[str] | None = None,
        omit_time: bool = True,
    ) -> Self:
        """
        Applies a sequential stack of filters to the specified or all numeric columns.

        Args:
            filters (list[AnyFilter]): List of Filter objects to apply in order (e.g., LowPass -> Derivative).
            columns (list[str] | None, optional): Specific columns to transform. If None, applies to all available columns. Defaults to None.
            omit_time (bool, optional): If True, prevents filters from being applied to the 'time' column. Defaults to True.

        Returns:
            Self: DataFrame with the transformed columns overwritten.

        """
        target_cols = columns or self.columns
        if omit_time:
            target_cols = [c for c in target_cols if c != "time"]
        exprs = []

        for col_name in target_cols:
            if col_name not in self.columns:
                continue

            # start the chain with the raw column
            expr = pl.col(col_name)

            # pipe the expression through every filter in the stack
            for f in filters:
                expr = f.apply(expr)

            exprs.append(expr.alias(col_name))

        return self._from_pl(self.with_columns(exprs))
