from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Self

import mujoco
import numpy as np
from pydantic import PrivateAttr, field_validator, model_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import Proximityable
from mujoco_mojo.typing import ProximityType, SignalCategory, Vec3
from mujoco_mojo.utils.color import Color
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.visualization import LineConfig

if TYPE_CHECKING:
    from mujoco_mojo.runtime.runtime_manager import RuntimeManager
    from mujoco_mojo.runtime.signal_manager import SignalManager

logger = get_logger(__name__)

__all__ = ["Proximity"]


class Proximity(MojoBaseModel):
    """Provide high-precision triangle-level distance queries."""

    geom_1: Proximityable
    """First geometry to perform proximity calculations for."""

    geom_2: Proximityable
    """Second geometry to perform proximity calculations for."""

    dist_max: float
    """The 'cutoff' distance. If objects are further than this (as estimated by a sphere to sphere test), the sphere to sphere estimate will be returned and exit early."""

    algorithm: ProximityType = ProximityType.CONVEX_HULL
    """What algorithm should be used for the narrowphase test."""

    visualize: bool = True
    """Wheter or not to visualize this proximity in the MuJoCo viewer."""

    _last_t: float = PrivateAttr(default=np.nan)
    _last_p1: Vec3 = PrivateAttr(default_factory=lambda: np.full(3, np.nan))
    _last_p2: Vec3 = PrivateAttr(default_factory=lambda: np.full(3, np.nan))

    @field_validator("geom_1", "geom_2")
    @classmethod
    def validate_geom_named(cls, v: Proximityable) -> Proximityable:
        if v.name is None:
            msg = "Unable to determine proximity to since geometry is unamed"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_names(self) -> Self:
        if self.geom_1.name == self.geom_2.name:
            msg = "Unable to determine proximity to geometry (geom_1 and geom_2 have the same name)"
            logger.error(msg)
            raise ValueError(msg)
        return self

    def update_last(self, p1: Vec3, p2: Vec3, mj_data: mujoco.MjData):
        self._last_t = mj_data.time
        self._last_p1 = p1
        self._last_p2 = p2

    def register_to_rm(self, runtime_manager: RuntimeManager) -> Self:
        runtime_manager.add_proximity(self)
        return self

    def get_sphere_to_sphere_proximity(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[float, Vec3, Vec3, bool]:
        """
        Calculates the shortest distance between two geometries using their bounding spheres.

        Args:
            mj_model (mujoco.MjModel): The compiled MuJoCo model instance.
            mj_data (mujoco.MjData): The current simulation state.

        Returns:
            tuple[float, Vec3, Vec3, bool]: Unsigned (`>= 0`) minimum distance from geom_1 to geom_2, world location of minimum distance on geom_1, world location of minimum distance on geom_2, and if the estimated distance exceeds dist_max.

        """
        # get world orientations and origins
        origin_geom_1 = self.geom_1.rt_xpos(mj_model, mj_data)
        mat_geom_1 = self.geom_1.rt_xmat(mj_model, mj_data)

        origin_geom_2 = self.geom_2.rt_xpos(mj_model, mj_data)
        mat_geom_2 = self.geom_2.rt_xmat(mj_model, mj_data)

        if np.isnan(self.geom_1._rad):
            self.geom_1._rad, self.geom_1._local_centroid = self.geom_1.vertex_max_norm(
                mj_model
            )

        if np.isnan(self.geom_2._rad):
            self.geom_2._rad, self.geom_2._local_centroid = self.geom_2.vertex_max_norm(
                mj_model
            )

        # shift centers to pre-calculated centroids
        pos_geom_1 = origin_geom_1 + (mat_geom_1 @ self.geom_1._local_centroid)
        pos_geom_2 = origin_geom_2 + (mat_geom_2 @ self.geom_2._local_centroid)

        rad_geom_1 = self.geom_1._rad
        rad_geom_2 = self.geom_2._rad

        vec_geom_1_to_geom_2 = pos_geom_2 - pos_geom_1
        d_centers = float(np.linalg.norm(vec_geom_1_to_geom_2))
        dist = d_centers - (rad_geom_1 + rad_geom_2)

        dist = max(0.0, dist)  # clip to zero
        exceeds_dist_max = dist > self.dist_max

        if d_centers > 1e-9:
            unit_vec = vec_geom_1_to_geom_2 / d_centers
            p1 = pos_geom_1 + (unit_vec * rad_geom_1)
            p2 = pos_geom_2 - (unit_vec * rad_geom_2)
        else:
            p1 = pos_geom_1
            p2 = pos_geom_2

        self.update_last(p1, p2, mj_data)
        return dist, p1, p2, exceeds_dist_max

    def get_convex_hull_proximity(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[float, Vec3, Vec3, ProximityType]:
        """
        Calculates the shortest distance between two geometries using their convex hull.

        Args:
            mj_model (mujoco.MjModel): The compiled MuJoCo model instance.
            mj_data (mujoco.MjData): The current simulation state.

        Returns:
            tuple[float, Vec3, Vec3, ProximityType]: Unsigned (`>= 0`) minimum distance from geom_1 to geom_2, world location of minimum distance on geom_1, world location of minimum distance on geom_2, and which phase the exit occurred in.

        """
        # ========== BROADPHASE ==========
        if self.geom_1._proximity_configured_for != ProximityType.CONVEX_HULL:
            self.geom_1.bake_proximity(mj_model, ProximityType.CONVEX_HULL)

        if self.geom_2._proximity_configured_for != ProximityType.CONVEX_HULL:
            self.geom_2.bake_proximity(mj_model, ProximityType.CONVEX_HULL)

        d_est, p1, p2, skip = self.get_sphere_to_sphere_proximity(
            mj_model=mj_model, mj_data=mj_data
        )

        if skip:
            return d_est, p1, p2, ProximityType.SPHERE_TO_SPHERE

        # ========== NARROWPHASE ==========
        # temp buffer for MuJoCo's 6-element output [x1,y1,z1, x2,y2,z2]
        mj_fromto = np.zeros(6)
        min_dist = mujoco.mj_geomDistance(
            m=mj_model,
            d=mj_data,
            geom1=self.geom_1.get_id(mj_model),
            geom2=self.geom_2.get_id(mj_model),
            distmax=self.dist_max,
            fromto=mj_fromto,
        )

        min_dist = max(0.0, min_dist)  # clip from below to zero

        p1 = mj_fromto[:3].copy()
        p2 = mj_fromto[3:6].copy()
        self.update_last(p1, p2, mj_data)
        return min_dist, p1, p2, ProximityType.CONVEX_HULL

    def get_vertex_to_face_proximity(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[float, Vec3, Vec3, ProximityType]:
        """
        Calculates the vertex to face distance using a multi-phase Bounding Volume Hierarchy (BVH) query.

        Phases:
            1. Broad Phase: Sphere-Sphere check (object level).
            2. Mid Phase: BVH Traversal (eliminating triangle groups). No exit here.
            3. Narrow Phase: Point-to-Face proximity.

        Args:
            mj_model (mujoco.MjModel): Compiled MuJoCo model.
            mj_data (mujoco.MjData): MuJoCo runtime data.

        Returns:
            tuple[float, Vec3, Vec3, ProximityType]: Unsigned (`>= 0`) minimum distance from geom_1 to geom_2, world location of minimum distance on geom_1, world location of minimum distance on geom_2, and which phase the exit occurred in.

        """
        if self.geom_1._proximity_configured_for != ProximityType.VERTEX_TO_FACE:
            self.geom_1.bake_proximity(mj_model, ProximityType.VERTEX_TO_FACE)

        if self.geom_2._proximity_configured_for != ProximityType.VERTEX_TO_FACE:
            self.geom_2.bake_proximity(mj_model, ProximityType.VERTEX_TO_FACE)

        assert self.geom_1._baked_query and self.geom_2._baked_query
        assert (
            self.geom_2._local_verts is not None
            and self.geom_2._local_verts is not None
        )

        # ========== BROADPHASE: Sphere-Sphere check ==========
        # find center to center to center distance and return early if broad phase
        d_est, p1, p2, skip = self.get_sphere_to_sphere_proximity(
            mj_model=mj_model, mj_data=mj_data
        )
        if skip:
            return d_est, p1, p2, ProximityType.SPHERE_TO_SPHERE

        # ========== COORDINATE TRANSFORMATION ==========
        pos_geom_1 = self.geom_1.rt_xpos(mj_model, mj_data)
        pos_geom_2 = self.geom_2.rt_xpos(mj_model, mj_data)

        mat_geom_1 = self.geom_1.rt_xmat(mj_model, mj_data)  # already Mat3 (3x3)
        mat_geom_2 = self.geom_2.rt_xmat(mj_model, mj_data)
        rel_pos = pos_geom_2 - pos_geom_1

        # ========== NARROWPHASE A: Geom_1-Surface vs. Geom_2-Vertices ==========
        # trimesh uses a BVH internall here (Mid-phase) to find closest triangles
        # combine transforms from geom_1 to geom_2: V_local_geom_1 = R_geom_1.T @ (R_geom_2 @ V_local_geom_2 + p_geom_2 - p_geom_1)
        geom_2_v_in_geom_1 = (
            self.geom_2._local_verts @ mat_geom_2.T + rel_pos
        ) @ mat_geom_1
        pts_on_geom_1, dist_a, _ = self.geom_1._baked_query.on_surface(
            geom_2_v_in_geom_1
        )
        idx_a = np.argmin(dist_a)
        min_a = dist_a[idx_a]

        # ========== NARROWPHASE B: Geom_1-Vertices vs. Geom_2-Surface  ==========
        # transform geom_1 vertices into geom_2's local frame
        geom_1_v_in_geom_2 = (
            self.geom_1._local_verts @ mat_geom_1.T - rel_pos
        ) @ mat_geom_2
        pts_on_geom_2, dist_b, _ = self.geom_2._baked_query.on_surface(
            geom_1_v_in_geom_2
        )
        idx_b = np.argmin(dist_b)
        min_b = dist_b[idx_b]

        # ========== CLEANUP ==========
        # find global min
        if min_a < min_b:
            min_dist = float(min_a)
            p1 = (pts_on_geom_1[idx_a] @ mat_geom_1.T) + pos_geom_1
            p2 = (geom_2_v_in_geom_1[idx_a] @ mat_geom_1.T) + pos_geom_1

            self.update_last(p1, p2, mj_data)
            return min_dist, p1, p2, ProximityType.VERTEX_TO_FACE
        else:
            min_dist = float(min_b)

            # pt_on_geom_2 was calculated in geom_2's local frame
            p2 = (pts_on_geom_2[idx_b] @ mat_geom_2.T) + pos_geom_2
            p1 = (geom_1_v_in_geom_2[idx_b] @ mat_geom_2.T) + pos_geom_2

            self.update_last(p1, p2, mj_data)
            return min_dist, p1, p2, ProximityType.VERTEX_TO_FACE

    def get_face_to_face_proximity(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[float, Vec3, Vec3, ProximityType]:
        """
        Calculates the face to face distance using a multi-phase Bounding Volume Hierarchy (BVH) query.

        This is more accurate than the vertex to face method, but comes at higher computational cost.

        Phases:
            1. Broad Phase: Sphere-Sphere check (object level).
            2. Mid Phase: BVH Traversal (eliminating triangle groups). No exit here.
            3. Narrow Phase: Face-to-Face proximity.

        Args:
            mj_model (mujoco.MjModel): Compiled MuJoCo model.
            mj_data (mujoco.MjData): MuJoCo runtime data.

        Returns:
            tuple[float, Vec3, Vec3, ProximityType]: Unsigned (`>= 0`) minimum distance from geom_1 to geom_2, world location of minimum distance on geom_1, world location of minimum distance on geom_2, and which phase the exit occurred in.

        """
        if self.geom_1._proximity_configured_for != ProximityType.FACE_TO_FACE:
            self.geom_1.bake_proximity(mj_model, ProximityType.FACE_TO_FACE)

        if self.geom_2._proximity_configured_for != ProximityType.FACE_TO_FACE:
            self.geom_2.bake_proximity(mj_model, ProximityType.FACE_TO_FACE)

        assert self.geom_1._baked_manager and self.geom_2._baked_manager

        # ========== BROADPHASE: Sphere-Sphere check ==========

        # find center to center to center distance and return early if broad phase
        d_est, p1, p2, skip = self.get_sphere_to_sphere_proximity(
            mj_model=mj_model, mj_data=mj_data
        )
        if skip:
            return d_est, p1, p2, ProximityType.SPHERE_TO_SPHERE

        # ========== NARROWPHASE ==========
        # set the other transformation relative to geom_1's local frame
        t_geom_1 = np.eye(4)
        t_geom_1[:3, :3] = self.geom_1.rt_xmat(mj_model, mj_data)
        t_geom_1[:3, 3] = self.geom_1.rt_xpos(mj_model, mj_data)

        t_geom_2 = np.eye(4)
        t_geom_2[:3, :3] = self.geom_2.rt_xmat(mj_model, mj_data)
        t_geom_2[:3, 3] = self.geom_2.rt_xpos(mj_model, mj_data)

        self.geom_1._baked_manager.set_transform(self.geom_1.name, t_geom_1)
        self.geom_2._baked_manager.set_transform(self.geom_2.name, t_geom_2)

        # CollisionManager returns distance and the two closest points
        result = self.geom_1._baked_manager.min_distance_other(
            self.geom_2._baked_manager, return_data=True
        )
        min_dist = float(result[0])  # pyright: ignore[reportIndexIssue]
        data = result[1]  # pyright: ignore[reportIndexIssue]

        assert data
        p1 = data.point(self.geom_1.name)  # pyright: ignore[reportAttributeAccessIssue]
        p2 = data.point(self.geom_2.name)  # pyright: ignore[reportAttributeAccessIssue]

        self.update_last(p1, p2, mj_data)
        return min_dist, p1, p2, ProximityType.FACE_TO_FACE

    def get_proximity(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> tuple[float, Vec3, Vec3, ProximityType]:
        """
        Calculates the shortest distance between two geometries using the specified proximity algorithm.

        This is a general dispatcher method that routes to different proximity calculation algorithms based on the `algorithm` parameter. Each mode offers different tradeoffs between speed and precision:

        **Modes:**
            - `SPHERE_TO_SPHERE`: Fastest. Uses bounding sphere distance only (broadphase).
            - `CONVEX_HULL`: Fast & accurate. Uses MuJoCo's convex hull-based distance (default).
            - `VERTEX_TO_FACE`: Accurate. Multi-phase BVH with vertex-to-surface queries.
            - `FACE_TO_FACE`: Most accurate but slowest. Full mesh-to-mesh distance calculation.

        **Phases (for non-sphere modes):**
            1. Broad Phase: Sphere-Sphere check (object level).
            2. Narrow Phase: Algorithm-specific distance calculation.

        Args:
            mj_model (mujoco.MjModel): Compiled MuJoCo model.
            mj_data (mujoco.MjData): MuJoCo runtime data.

        Returns:
            tuple[float, ProximityType]: If fromto=False, returns the unsigned (`>= 0`) minimum distance and which algorithm produced the result.

            tuple[tuple[float, Vec3, Vec3], ProximityType]: If fromto=True, returns the minimum distance, world location of minimum distance on geom_1, world location of minimum distance on geom_2, and which algorithm produced the result.

        """
        match self.algorithm:
            case ProximityType.SPHERE_TO_SPHERE:
                d_est, p1, p2, _skip = self.get_sphere_to_sphere_proximity(
                    mj_model=mj_model, mj_data=mj_data
                )
                return d_est, p1, p2, ProximityType.SPHERE_TO_SPHERE
            case ProximityType.CONVEX_HULL:
                return self.get_convex_hull_proximity(
                    mj_model=mj_model, mj_data=mj_data
                )
            case ProximityType.VERTEX_TO_FACE:
                return self.get_vertex_to_face_proximity(
                    mj_model=mj_model, mj_data=mj_data
                )
            case ProximityType.FACE_TO_FACE:
                return self.get_face_to_face_proximity(
                    mj_model=mj_model, mj_data=mj_data
                )
            case _:
                msg = f"Method for {self.algorithm.name} not implemented."
                logger.error(msg)
                raise NotImplementedError(msg)

    def get_visuals(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> LineConfig | None:
        if not self.visualize:
            return

        is_stale = self._last_t != mj_data.time
        is_uninitialized = any(
            [
                np.any(np.isnan(self._last_p1)),
                np.any(np.isnan(self._last_p2)),
                np.isnan(self._last_t),
            ]
        )
        if is_stale or is_uninitialized:
            # run the solver
            self.get_proximity(mj_model, mj_data)

        return LineConfig(
            pos1=self._last_p1, pos2=self._last_p2, color=Color.WHITE.rgba, width=0.005
        )

    def request(
        self,
        signal_manager: SignalManager,
        attrs: list[Literal["dist", "fromto", "prox_type"]] = ["dist", "prox_type"],
    ):
        """
        Registers specific geom proximity attributes for logging. Please see the `get_proximity` method for how these outputs are calculated.

        Available Requests:
            `dist`: Minimum distance as calculated by the specified algorithm. Tagged with `Proximities/{pair_name}:dist`.
            `fromto`: World coordinates for where the minimum distance is estimated to occur at. Two sets of coordinates will be returned for geom_1 and geom_2. Tagged with `Proximities/{pair_name}/fromto/{(geom_1 | geom_2).name}:(x | y | z)`.
            `prox_type`: What type of proximity calculation the previous values are from. Using `dist_max`, `get_proximity` can return a broadphase estimate (bounding sphere to sphere) if the two geometries are distant (greater than `dist_max`). This telemetry will return what type of proximity calculation was performed for this timestep. It is intended to help debug to understand if a jump in telemetry (specifically sharp declines) are real or comes from the broadphase estimate. The values returned will be integer values associated with their specific ProximityType (see the enumeration for the mapping, in general a larger value will mean a more accurate one). Tagged with `Proximities/{pair_name}:prox_type`.

        """
        pair_name = f"{self.geom_1.name}_to_{self.geom_2.name}"

        def sample(mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
            dist, p1, p2, prox_type = self.get_proximity(
                mj_model=mj_model,
                mj_data=mj_data,
            )

            for attr in attrs:
                match attr:
                    case "dist":
                        # "Proximities/{pair_name}:dist"
                        signal_manager.post(
                            value=dist,
                            category=SignalCategory.PROXIMITIES,
                            subgroups=(pair_name,),
                            attr=attr,
                        )
                    case "fromto":
                        # "Proximities/{pair_name}/fromto/{(geom_1 | geom_2).name}:(x | y | z)"
                        for i, k in enumerate("xyz"):
                            signal_manager.post(
                                value=float(p1[i]),
                                category=SignalCategory.PROXIMITIES,
                                subgroups=(pair_name, attr, str(self.geom_1.name)),
                                attr=k,
                            )
                        for i, k in enumerate("xyz"):
                            signal_manager.post(
                                value=float(p2[i]),
                                category=SignalCategory.PROXIMITIES,
                                subgroups=(pair_name, attr, str(self.geom_2.name)),
                                attr=k,
                            )
                    case "prox_type":
                        # "Proximities/{pair_name}:prox_type"
                        signal_manager.post(
                            value=float(prox_type.value),
                            category=SignalCategory.PROXIMITIES,
                            subgroups=(pair_name,),
                            attr=attr,
                        )
                    case _:
                        continue

        signal_manager.register_sampler(sample)
