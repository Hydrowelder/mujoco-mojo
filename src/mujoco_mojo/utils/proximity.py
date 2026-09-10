from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal, Self, cast

import mujoco
import numpy as np
from pydantic import Discriminator, PrivateAttr, Tag, field_validator, model_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import GeomMesh
from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import SiteMesh
from mujoco_mojo.settings import MujocoMojoSettings, VisualizationSettings
from mujoco_mojo.typing import ProximityType, SignalCategory, Vec3
from mujoco_mojo.utils.color import Color
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.signal_metadata import (
    Dimension,
    dim,
    dimensionless_metadata,
    merge_signal_metadata,
)
from mujoco_mojo.visualization import LineConfig

if TYPE_CHECKING:
    from mujoco_mojo.runtime.runtime_manager import RuntimeManager
    from mujoco_mojo.runtime.signal_manager import SignalManager

logger = get_logger(__name__)

__all__ = ["Proximity"]


def _proximityable_discriminator(v: Any) -> str:
    """
    Distinguishes `GeomMesh` from `SiteMesh` for `Proximityable`'s discriminated union.

    Both classes declare `type: Literal[GeomType.MESH]` - it's the only way either spells "I'm the mesh variant" - so they share the exact same discriminator value, and a plain `Field(discriminator="type")` can't tell them apart: pydantic requires each union member to map to a unique tag, and raises at schema-build time otherwise. This checks the actual Python type instead. Only handles already-constructed instances, matching how `Proximity` is actually used throughout the codebase - direct object construction, never raw dict/JSON validation.

    """
    return "site" if isinstance(v, SiteMesh) else "geom"


Proximityable = Annotated[
    Annotated[GeomMesh, Tag("geom")] | Annotated[SiteMesh, Tag("site")],
    Discriminator(_proximityable_discriminator),
]

_REQUEST_CHANNEL_METADATA: dict[str, dict[str, str]] = {
    "dist": dim(Dimension.LENGTH),
    "fromto": dim(Dimension.LENGTH),
    "prox_type": dimensionless_metadata(),
}


class Proximity(MojoBaseModel):
    """Provide high-precision triangle-level distance queries."""

    volume_1: Proximityable
    """First volume to perform proximity calculations for."""

    volume_2: Proximityable
    """Second volume to perform proximity calculations for."""

    dist_max: float
    """The 'cutoff' distance. If objects are further than this (as estimated by a sphere to sphere test), the sphere to sphere estimate will be returned and exit early."""

    algorithm: ProximityType = ProximityType.CONVEX_HULL
    """What algorithm should be used for the narrowphase test."""

    visualize: bool = True
    """Wheter or not to visualize this proximity in the MuJoCo viewer."""

    _last_t: float = PrivateAttr(default=np.nan)
    _last_p1: Vec3 = PrivateAttr(default_factory=lambda: np.full(3, np.nan))
    _last_p2: Vec3 = PrivateAttr(default_factory=lambda: np.full(3, np.nan))
    _last_dist: float = PrivateAttr(default=np.nan)

    _vis: VisualizationSettings = PrivateAttr(default_factory=VisualizationSettings)
    _vis_loaded: bool = PrivateAttr(default=False)

    _requested: bool = PrivateAttr(default=False)
    _warned_unrequested: bool = PrivateAttr(default=False)

    _last_prox_type: ProximityType | None = PrivateAttr(default=None)

    @field_validator("volume_1", "volume_2")
    @classmethod
    def validate_volume_named(cls, v: Proximityable) -> Proximityable:
        if v.name is None:
            msg = "Unable to determine proximity to since volume is unamed"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_names(self) -> Self:
        if self.volume_1.name == self.volume_2.name:
            msg = "Unable to determine proximity to volume (volume_1 and volume_2 have the same name)"
            logger.error(msg)
            raise ValueError(msg)
        return self

    def update_last(self, p1: Vec3, p2: Vec3, state: MjState):
        self._last_t = state.data.time
        self._last_p1 = p1
        self._last_p2 = p2

    def register_to_rm(self, runtime_manager: RuntimeManager | None = None) -> Self:
        from mujoco_mojo.runtime.runtime_manager import RuntimeManager

        (runtime_manager or RuntimeManager.current()).add_proximity(self)
        return self

    def get_sphere_to_sphere_proximity(
        self,
        state: MjState,
    ) -> tuple[float, Vec3, Vec3, bool]:
        """
        Calculates the shortest distance between two volumes using their bounding spheres.

        Args:
            state: The paired MuJoCo model and data instance.

        Returns:
            tuple[float, Vec3, Vec3, bool]: Unsigned (`>= 0`) minimum distance from volume_1 to volume_2, world location of minimum distance on volume_1, world location of minimum distance on volume_2, and if the estimated distance exceeds dist_max.

        """
        # get world orientations and origins
        origin_volume_1 = self.volume_1.rt_pos(state)
        mat_volume_1 = self.volume_1.rt_xmat(state)

        origin_volume_2 = self.volume_2.rt_pos(state)
        mat_volume_2 = self.volume_2.rt_xmat(state)

        if np.isnan(self.volume_1._rad):
            self.volume_1._rad, self.volume_1._local_centroid = (
                self.volume_1.vertex_max_norm(state.model)
            )

        if np.isnan(self.volume_2._rad):
            self.volume_2._rad, self.volume_2._local_centroid = (
                self.volume_2.vertex_max_norm(state.model)
            )

        # shift centers to pre-calculated centroids
        pos_volume_1 = origin_volume_1 + (mat_volume_1 @ self.volume_1._local_centroid)
        pos_volume_2 = origin_volume_2 + (mat_volume_2 @ self.volume_2._local_centroid)

        rad_volume_1 = self.volume_1._rad
        rad_volume_2 = self.volume_2._rad

        vec_volume_1_to_volume_2 = pos_volume_2 - pos_volume_1
        d_centers = float(np.linalg.norm(vec_volume_1_to_volume_2))
        dist = d_centers - (rad_volume_1 + rad_volume_2)

        dist = max(0.0, dist)  # clip to zero
        exceeds_dist_max = dist > self.dist_max

        if d_centers > 1e-9:
            unit_vec = vec_volume_1_to_volume_2 / d_centers
            p1 = pos_volume_1 + (unit_vec * rad_volume_1)
            p2 = pos_volume_2 - (unit_vec * rad_volume_2)
        else:
            p1 = pos_volume_1
            p2 = pos_volume_2

        self.update_last(p1, p2, state)
        return dist, p1, p2, exceeds_dist_max

    def get_convex_hull_proximity(
        self,
        state: MjState,
    ) -> tuple[float, Vec3, Vec3, ProximityType]:
        """
        Calculates the shortest distance between two volumes using their convex hull.

        Args:
            state: The paired MuJoCo model and data instance.

        Returns:
            tuple[float, Vec3, Vec3, ProximityType]: Unsigned (`>= 0`) minimum distance from volume_1 to volume_2, world location of minimum distance on volume_1, world location of minimum distance on volume_2, and which phase the exit occurred in.

        Raises:
            TypeError: If either volume is a `SiteMesh` and the broadphase sphere-to-sphere check doesn't already resolve the query. The narrowphase below is MuJoCo's native `mj_geomDistance`, which only operates on geoms - it indexes `mjModel`'s geom arrays by geom id, a completely separate namespace from a site's id. Use `ProximityType.VERTEX_TO_FACE` or `FACE_TO_FACE` instead, which compute distance via mojo's own trimesh-based BVH query rather than this native call.

        """
        # ========== BROADPHASE ==========
        if self.volume_1._proximity_configured_for != ProximityType.CONVEX_HULL:
            self.volume_1.bake_proximity(state.model, ProximityType.CONVEX_HULL)

        if self.volume_2._proximity_configured_for != ProximityType.CONVEX_HULL:
            self.volume_2.bake_proximity(state.model, ProximityType.CONVEX_HULL)

        d_est, p1, p2, skip = self.get_sphere_to_sphere_proximity(state)

        if skip:
            return d_est, p1, p2, ProximityType.SPHERE_TO_SPHERE

        if isinstance(self.volume_1, SiteMesh) or isinstance(self.volume_2, SiteMesh):
            msg = "CONVEX_HULL proximity's narrowphase uses MuJoCo's native mj_geomDistance, which only supports geoms, not sites. Use ProximityType.VERTEX_TO_FACE or FACE_TO_FACE instead for a SiteMesh."
            logger.error(msg)
            raise TypeError(msg)

        # ========== NARROWPHASE ==========
        # temp buffer for MuJoCo's 6-element output [x1,y1,z1, x2,y2,z2]
        mj_fromto = np.zeros(6)
        min_dist = mujoco.mj_geomDistance(
            m=state.model,
            d=state.data,
            geom1=self.volume_1.get_id(state.model),
            geom2=self.volume_2.get_id(state.model),
            distmax=self.dist_max,
            fromto=mj_fromto,
        )

        min_dist = max(0.0, min_dist)  # clip from below to zero

        p1 = mj_fromto[:3].copy()
        p2 = mj_fromto[3:6].copy()
        self.update_last(p1, p2, state)
        return min_dist, p1, p2, ProximityType.CONVEX_HULL

    def get_vertex_to_face_proximity(
        self,
        state: MjState,
    ) -> tuple[float, Vec3, Vec3, ProximityType]:
        """
        Calculates the vertex to face distance using a multi-phase Bounding Volume Hierarchy (BVH) query.

        Phases:
            1. Broad Phase: Sphere-Sphere check (object level).
            2. Mid Phase: BVH Traversal (eliminating triangle groups). No exit here.
            3. Narrow Phase: Point-to-Face proximity.

        Args:
            state: The paired MuJoCo model and data instance.

        Returns:
            tuple[float, Vec3, Vec3, ProximityType]: Unsigned (`>= 0`) minimum distance from volume_1 to volume_2, world location of minimum distance on volume_1, world location of minimum distance on volume_2, and which phase the exit occurred in.

        """
        if self.volume_1._proximity_configured_for != ProximityType.VERTEX_TO_FACE:
            self.volume_1.bake_proximity(state.model, ProximityType.VERTEX_TO_FACE)

        if self.volume_2._proximity_configured_for != ProximityType.VERTEX_TO_FACE:
            self.volume_2.bake_proximity(state.model, ProximityType.VERTEX_TO_FACE)

        assert self.volume_1._baked_query and self.volume_2._baked_query
        assert (
            self.volume_2._local_verts is not None
            and self.volume_2._local_verts is not None
        )

        # ========== BROADPHASE: Sphere-Sphere check ==========
        # find center to center to center distance and return early if broad phase
        d_est, p1, p2, skip = self.get_sphere_to_sphere_proximity(state)
        if skip:
            return d_est, p1, p2, ProximityType.SPHERE_TO_SPHERE

        # ========== COORDINATE TRANSFORMATION ==========
        pos_volume_1 = self.volume_1.rt_pos(state)
        pos_volume_2 = self.volume_2.rt_pos(state)

        mat_volume_1 = self.volume_1.rt_xmat(state)  # already Mat3 (3x3)
        mat_volume_2 = self.volume_2.rt_xmat(state)
        rel_pos = pos_volume_2 - pos_volume_1

        # ========== NARROWPHASE A: Volume_1-Surface vs. Volume_2-Vertices ==========
        # trimesh uses a BVH internall here (Mid-phase) to find closest triangles
        # combine transforms from volume_1 to volume_2: V_local_volume_1 = R_volume_1.T @ (R_volume_2 @ V_local_volume_2 + p_volume_2 - p_volume_1)
        volume_2_v_in_volume_1 = (
            self.volume_2._local_verts @ mat_volume_2.T + rel_pos
        ) @ mat_volume_1
        pts_on_volume_1, dist_a, _ = self.volume_1._baked_query.on_surface(
            volume_2_v_in_volume_1
        )
        idx_a = np.argmin(dist_a)
        min_a = dist_a[idx_a]

        # ========== NARROWPHASE B: Volume_1-Vertices vs. Volume_2-Surface  ==========
        # transform volume_1 vertices into volume_2's local frame
        volume_1_v_in_volume_2 = (
            self.volume_1._local_verts @ mat_volume_1.T - rel_pos
        ) @ mat_volume_2
        pts_on_volume_2, dist_b, _ = self.volume_2._baked_query.on_surface(
            volume_1_v_in_volume_2
        )
        idx_b = np.argmin(dist_b)
        min_b = dist_b[idx_b]

        # ========== CLEANUP ==========
        # find global min
        if min_a < min_b:
            min_dist = float(min_a)
            p1 = (pts_on_volume_1[idx_a] @ mat_volume_1.T) + pos_volume_1
            p2 = (volume_2_v_in_volume_1[idx_a] @ mat_volume_1.T) + pos_volume_1

            self.update_last(p1, p2, state)
            return min_dist, p1, p2, ProximityType.VERTEX_TO_FACE
        else:
            min_dist = float(min_b)

            # pt_on_volume_2 was calculated in volume_2's local frame
            p2 = (pts_on_volume_2[idx_b] @ mat_volume_2.T) + pos_volume_2
            p1 = (volume_1_v_in_volume_2[idx_b] @ mat_volume_2.T) + pos_volume_2

            self.update_last(p1, p2, state)
            return min_dist, p1, p2, ProximityType.VERTEX_TO_FACE

    def get_face_to_face_proximity(
        self,
        state: MjState,
    ) -> tuple[float, Vec3, Vec3, ProximityType]:
        """
        Calculates the face to face distance using a multi-phase Bounding Volume Hierarchy (BVH) query.

        This is more accurate than the vertex to face method, but comes at higher computational cost.

        Phases:
            1. Broad Phase: Sphere-Sphere check (object level).
            2. Mid Phase: BVH Traversal (eliminating triangle groups). No exit here.
            3. Narrow Phase: Face-to-Face proximity.

        Args:
            state: The paired MuJoCo model and data instance.

        Returns:
            tuple[float, Vec3, Vec3, ProximityType]: Unsigned (`>= 0`) minimum distance from volume_1 to volume_2, world location of minimum distance on volume_1, world location of minimum distance on volume_2, and which phase the exit occurred in.

        """
        if self.volume_1._proximity_configured_for != ProximityType.FACE_TO_FACE:
            self.volume_1.bake_proximity(state.model, ProximityType.FACE_TO_FACE)

        if self.volume_2._proximity_configured_for != ProximityType.FACE_TO_FACE:
            self.volume_2.bake_proximity(state.model, ProximityType.FACE_TO_FACE)

        assert self.volume_1._baked_manager and self.volume_2._baked_manager

        # ========== BROADPHASE: Sphere-Sphere check ==========

        # find center to center to center distance and return early if broad phase
        d_est, p1, p2, skip = self.get_sphere_to_sphere_proximity(state)
        if skip:
            return d_est, p1, p2, ProximityType.SPHERE_TO_SPHERE

        # ========== NARROWPHASE ==========
        # set the other transformation relative to volume_1's local frame
        t_volume_1 = np.eye(4)
        t_volume_1[:3, :3] = self.volume_1.rt_xmat(state)
        t_volume_1[:3, 3] = self.volume_1.rt_pos(state)

        t_volume_2 = np.eye(4)
        t_volume_2[:3, :3] = self.volume_2.rt_xmat(state)
        t_volume_2[:3, 3] = self.volume_2.rt_pos(state)

        self.volume_1._baked_manager.set_transform(self.volume_1.name, t_volume_1)
        self.volume_2._baked_manager.set_transform(self.volume_2.name, t_volume_2)

        # CollisionManager returns distance and the two closest points
        result = self.volume_1._baked_manager.min_distance_other(
            self.volume_2._baked_manager, return_data=True
        )
        min_dist = float(result[0])  # pyright: ignore[reportIndexIssue]
        min_dist = max(0.0, min_dist)  # clip to zero
        data = result[1]  # pyright: ignore[reportIndexIssue]

        assert data
        p1 = data.point(self.volume_1.name)  # pyright: ignore[reportAttributeAccessIssue]
        p2 = data.point(self.volume_2.name)  # pyright: ignore[reportAttributeAccessIssue]

        self.update_last(p1, p2, state)
        return min_dist, p1, p2, ProximityType.FACE_TO_FACE

    def get_proximity(self, state: MjState) -> tuple[float, Vec3, Vec3, ProximityType]:
        """
        Calculates the shortest distance between two volumes using the specified proximity algorithm.

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
            state: The paired MuJoCo model and data instance.

        Returns:
            tuple[float, ProximityType]: If fromto=False, returns the unsigned (`>= 0`) minimum distance and which algorithm produced the result.

            tuple[tuple[float, Vec3, Vec3], ProximityType]: If fromto=True, returns the minimum distance, world location of minimum distance on volume_1, world location of minimum distance on volume_2, and which algorithm produced the result.

        The result is cached per-timestep (keyed on `state.data.time`), so calling this more than once during the same step (e.g. once from `request()`'s telemetry sampler and again from a user-defined runtime input/Load that reads the same `Proximity` instance) only pays for the underlying calculation once.

        """
        is_cached = (
            self._last_prox_type is not None
            and not np.isnan(self._last_dist)
            and state.data.time == self._last_t
        )
        if is_cached:
            assert self._last_prox_type is not None  # narrows for the type checker
            return self._last_dist, self._last_p1, self._last_p2, self._last_prox_type

        match self.algorithm:
            case ProximityType.SPHERE_TO_SPHERE:
                d_est, p1, p2, _skip = self.get_sphere_to_sphere_proximity(state)
                result = (d_est, p1, p2, ProximityType.SPHERE_TO_SPHERE)
            case ProximityType.CONVEX_HULL:
                result = self.get_convex_hull_proximity(state)
            case ProximityType.VERTEX_TO_FACE:
                result = self.get_vertex_to_face_proximity(state)
            case ProximityType.FACE_TO_FACE:
                result = self.get_face_to_face_proximity(state)
            case _:
                msg = f"Method for {self.algorithm.name} not implemented."
                logger.error(msg)
                raise NotImplementedError(msg)

        # the configured algorithm's broadphase sphere-to-sphere check can exit early
        # (objects farther apart than dist_max), so the phase that actually produced
        # this result can flip between SPHERE_TO_SPHERE and the configured narrowphase
        # algorithm from one call to the next; surface that for performance debugging
        prox_type = result[3]
        if self._last_prox_type is not None and prox_type != self._last_prox_type:
            logger.debug(
                f"Proximity {self.pair_name} switched phase: "
                f"{self._last_prox_type.name} -> {prox_type.name} (t={state.data.time:.4f})"
            )
        self._last_prox_type = prox_type
        self._last_dist = result[0]
        # _last_t/_last_p1/_last_p2 were already set by update_last() inside whichever
        # method above produced `result`

        return result

    def get_visuals(
        self, state: MjState, signal_manager: SignalManager | None = None
    ) -> LineConfig | None:
        if not self._vis_loaded:
            self._vis = MujocoMojoSettings().visualization
            self._vis_loaded = True

        if not self.visualize or not self._vis.clearance_line:
            return None

        if (
            signal_manager is not None
            and not self._requested
            and not self._warned_unrequested
        ):
            logger.warning(
                f"Proximity {self.pair_name} is being visualized (clearance line) every "
                "step, which runs the same expensive distance calculation as request(), "
                "but request() was never called so nothing is being logged. Call "
                "request() to log it, or set visualize=False to skip the calculation."
            )
            self._warned_unrequested = True

        # get_proximity() caches per-timestep internally, so this is a no-op if
        # request()'s sampler (or some other caller) already computed it this step
        _dist, p1, p2, _prox_type = self.get_proximity(state)

        return LineConfig(
            pos1=p1,
            pos2=p2,
            color=Color[self._vis.clearance_line].rgba,
            width=0.005,
        )

    @property
    def pair_name(self) -> str:
        return f"{self.volume_1.name}_to_{self.volume_2.name}"

    def request(
        self,
        signal_manager: SignalManager | None = None,
        channels: list[Literal["dist", "fromto", "prox_type"]]
        | dict[Literal["dist", "fromto", "prox_type"], dict[str, Any] | None] = [
            "dist",
            "prox_type",
        ],
    ):
        """
        Registers specific channels for logging.

        | Channel     | Description                                                            | Type   |
        |:------------|:-----------------------------------------------------------------------|:-------|
        | `dist`      | minimum distance between the volume pair, per the proximity algorithm  | scalar |
        | `fromto`    | world coordinates of the nearest point on each volume                  | xyz    |
        | `prox_type` | the `ProximityType` used to compute `dist` and `fromto`, as an integer | scalar |

        Each channel is posted under `subgroups=(pair_name,)`, where `pair_name` is `f"{volume_1.name}_to_{volume_2.name}"`.

        * A `scalar` is posted as a single value with `attr=channel`.
        * An `xyz` is a cartesian vector without a magnitude component, posted as 3 values (`x`, `y`, `z`). `fromto` posts one `xyz` for each volume in the pair, under `subgroups=(pair_name, "fromto", volume_name)`.

        Only the computations required by the requested channels are performed each timestep.

        Each signal is tagged with built-in `dimension`/`unit` metadata for its channel (`dist`/`fromto` as a length, `prox_type` as dimensionless).

        If `signal_manager` is omitted, the `SignalManager` of the active `RuntimeManager` `with` block is used. If that `RuntimeManager` has no `SignalManager` configured, this is a no-op.

        Args:
            signal_manager: The signal manager to register the sampler with.
            channels: The proximity data channels to log. Pass a list to select channels, or a dict mapping channel name to metadata overrides (or `None`) to select channels and attach per-channel metadata in one step.

        """
        from mujoco_mojo.runtime.signal_manager import resolve_signal_manager

        signal_manager = resolve_signal_manager(signal_manager)
        if signal_manager is None:
            return

        if isinstance(channels, dict):
            _meta = cast("dict[str, dict[str, Any] | None]", channels)
            channels = list(channels.keys())
        else:
            _meta = {}

        pair_name = self.pair_name
        _prox_attrs = {"dist", "fromto", "prox_type"}
        needs_proximity = bool(set(channels) & _prox_attrs)

        if needs_proximity:
            self._requested = True

        def sample(state: MjState):
            dist: float = np.nan
            p1: Vec3 = np.zeros(3)
            p2: Vec3 = np.zeros(3)
            prox_type = ProximityType.SPHERE_TO_SPHERE

            if needs_proximity:
                dist, p1, p2, prox_type = self.get_proximity(state)

            for channel in channels:
                meta = merge_signal_metadata(
                    _REQUEST_CHANNEL_METADATA.get(channel),
                    channel,
                    _meta,
                    unit_system=state.us,
                )

                match channel:
                    case "dist":
                        signal_manager.post(
                            value=dist,
                            category=SignalCategory.PROXIMITIES,
                            subgroups=(pair_name,),
                            attr=channel,
                            metadata=meta,
                        )
                    case "fromto":
                        for i, attr in enumerate("xyz"):
                            signal_manager.post(
                                value=float(p1[i]),
                                category=SignalCategory.PROXIMITIES,
                                subgroups=(pair_name, channel, str(self.volume_1.name)),
                                attr=attr,
                                metadata=meta,
                            )
                        for i, attr in enumerate("xyz"):
                            signal_manager.post(
                                value=float(p2[i]),
                                category=SignalCategory.PROXIMITIES,
                                subgroups=(pair_name, channel, str(self.volume_2.name)),
                                attr=attr,
                                metadata=meta,
                            )
                    case "prox_type":
                        signal_manager.post(
                            value=float(prox_type.value),
                            category=SignalCategory.PROXIMITIES,
                            subgroups=(pair_name,),
                            attr=channel,
                            metadata=meta,
                        )
                    case _:
                        continue

        signal_manager.register_sampler(sample)
