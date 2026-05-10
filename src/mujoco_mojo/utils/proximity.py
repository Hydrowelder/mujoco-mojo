from __future__ import annotations

from typing import TYPE_CHECKING, Literal, overload

import mujoco
import numpy as np
import trimesh
from pydantic import PrivateAttr

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.typing import MatN, ProximityType, SignalCategory, Vec3
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import GeomMesh
    from mujoco_mojo.runtime.signal_manager import SignalManager

logger = get_logger(__name__)


PROXIMITY_TO_SELF_ERROR_MSG = (
    "Unable to determine proximity to own geometry (self and other have the same name)"
)


class ProximityMixin(MojoBaseModel):
    """Provide high-precision triangle-level distance queries."""

    _baked_mesh: trimesh.Trimesh | None = PrivateAttr(default=None)
    """Internal trimesh representation of the geometry."""

    _baked_query: trimesh.proximity.ProximityQuery | None = PrivateAttr(default=None)
    """Pre-computed BVH query object for fast distance lookups."""

    _baked_manager: trimesh.collision.CollisionManager | None = PrivateAttr(
        default=None
    )
    """Collision manager for face to face path."""

    _local_verts: MatN | None = PrivateAttr(default=None)
    _local_faces: MatN | None = PrivateAttr(default=None)
    _local_centroid: Vec3 = PrivateAttr(default_factory=lambda: np.full(3, np.nan))
    _rad: float = PrivateAttr(default=np.nan)

    def vertex_max_norm(self, mj_model: mujoco.MjModel) -> tuple[float, Vec3]:
        """
        Calculates the tightest sphere that encompasses all vertices, centered at the mesh's bounding box center.

        Returns:
            tuple[float, Vec3]: Tight radius and the local centroid offset.

        """
        geom_self: GeomMesh = self  # pyright: ignore[reportAssignmentType]
        if self._local_verts is None:
            mesh_id = mj_model.geom_dataid[geom_self.get_id(mj_model)]
            if mesh_id == -1:
                raise TypeError(f"Geom '{geom_self.name}' does not have mesh data.")

            adr = mj_model.mesh_vertadr[mesh_id]
            num = mj_model.mesh_vertnum[mesh_id]
            self._local_verts = mj_model.mesh_vert[adr : adr + num].copy()

        # find the centroid of the geom
        v_min = np.asarray(np.min(self._local_verts, axis=0))
        v_max = np.asarray(np.max(self._local_verts, axis=0))
        centroid = (v_min + v_max) / 2

        # find furthest distance reletive to the centroid
        distances = np.linalg.norm(self._local_verts - centroid, axis=1)
        radius = float(np.max(distances))

        return radius, centroid

    def bake_proximity(self, mj_model: mujoco.MjModel, proximity_type: ProximityType):
        """Builds the BVH tree from the comiled MuJoCo mesh data."""
        geom_self: GeomMesh = self  # pyright: ignore[reportAssignmentType]

        # cache bounding radius
        # self._rad = geom_self.rbound(mj_model)
        self._rad, self._local_centroid = geom_self.vertex_max_norm(mj_model)

        match proximity_type:
            case ProximityType.SPHERE_TO_SPHERE | ProximityType.CONVEX_HULL:
                return

        # get mesh id and data from mujoco
        mesh_id = mj_model.geom_dataid[geom_self.get_id(mj_model)]

        if mesh_id == -1:
            msg = "Exact proximity mesh tool is not currently supported for geoms of this type. Please use the `SPHERE_TO_SPHERE`/`CONVEX_HULL` algorithm, or convert the Geom to a GeomMesh."
            logger.error(msg)
            raise TypeError(msg)

        # extract vertices and faces
        if self._local_verts is None:
            adr = mj_model.mesh_vertadr[mesh_id]
            num = mj_model.mesh_vertnum[mesh_id]
            self._local_verts = mj_model.mesh_vert[adr : adr + num].copy()

        f_adr = mj_model.mesh_faceadr[mesh_id]
        f_num = mj_model.mesh_facenum[mesh_id]
        self._local_faces = mj_model.mesh_face[f_adr : f_adr + f_num].copy()

        # create a trimesh and its proximity query
        self._baked_mesh = trimesh.Trimesh(
            vertices=self._local_verts, faces=self._local_faces
        )
        match proximity_type:
            case ProximityType.FACE_TO_FACE:
                if not geom_self.name:
                    msg = "To perform face to face proximity calculations, geom must have a name"
                    logger.error(msg)
                    raise ValueError(msg)
                self._baked_manager = trimesh.collision.CollisionManager()
                self._baked_manager.add_object(geom_self.name, self._baked_mesh)
            case _:
                self._baked_query = trimesh.proximity.ProximityQuery(self._baked_mesh)

        logger.debug(
            f"Baked proximity mesh for {geom_self.name} ({len(self._local_faces)} faces)"
        )

    @overload
    def get_sphere_to_sphere_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[False] = False,
    ) -> tuple[float, bool]: ...

    @overload
    def get_sphere_to_sphere_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[True],
    ) -> tuple[tuple[float, Vec3, Vec3], bool]: ...

    def get_sphere_to_sphere_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: bool = False,
    ) -> tuple[float | tuple[float, Vec3, Vec3], bool]:
        """
        Calculates the shortest distance between two geometries using their bounding spheres.

        Args:
            other (GeomMesh): Second GeomMesh to test against.
            mj_model (mujoco.MjModel): The compiled MuJoCo model instance.
            mj_data (mujoco.MjData): The current simulation state.
            dist_max (float): The 'cutoff' distance. If the objects are further than this, the method will return True in the tuple.
            fromto (bool, optional): Whether or not to return the locations of the minimum distances.

        Returns:
            tuple[float | tuple[float, Vec3, Vec3], bool]: Unsigned (`>= 0`) minimum distance from self to other, world location of minimum distance on self, world location of minimum distance on other, and if the estimated distance exceeds dist_max.

        """
        geom_self: GeomMesh = self  # pyright: ignore[reportAssignmentType]
        if geom_self.name == other.name:
            logger.error(PROXIMITY_TO_SELF_ERROR_MSG)
            raise ValueError(PROXIMITY_TO_SELF_ERROR_MSG)

        # get world orientations and origins
        self_origin = geom_self.rt_xpos(mj_model, mj_data)
        self_mat = geom_self.rt_xmat(mj_model, mj_data)

        other_origin = other.rt_xpos(mj_model, mj_data)
        other_mat = other.rt_xmat(mj_model, mj_data)

        if np.isnan(self._rad):
            self._rad, self._local_centroid = self.vertex_max_norm(mj_model)

        if np.isnan(other._rad):
            other._rad, other._local_centroid = other.vertex_max_norm(mj_model)

        # shift centers to pre-calculated centroids
        pos_self = self_origin + (self_mat @ self._local_centroid)
        pos_other = other_origin + (other_mat @ other._local_centroid)

        rad_self = self._rad
        rad_other = other._rad

        vec_self_other = pos_other - pos_self
        d_centers = float(np.linalg.norm(vec_self_other))
        dist = d_centers - (rad_self + rad_other)

        dist = max(0.0, dist)  # clip to zero
        exceeds_dist_max = dist > dist_max

        if not fromto:
            return dist, exceeds_dist_max

        if d_centers > 1e-9:
            unit_vec = vec_self_other / d_centers
            p1 = pos_self + (unit_vec * rad_self)
            p2 = pos_other - (unit_vec * rad_other)
        else:
            p1 = pos_self
            p2 = pos_other
        return (dist, p1, p2), exceeds_dist_max

    @overload
    def get_convex_hull_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[False] = False,
    ) -> tuple[float, ProximityType]: ...

    @overload
    def get_convex_hull_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[True],
    ) -> tuple[tuple[float, Vec3, Vec3], ProximityType]: ...

    def get_convex_hull_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: bool = False,
    ) -> tuple[float | tuple[float, Vec3, Vec3], ProximityType]:
        """
        Calculates the shortest distance between two geometries using their convex hull.

        Args:
            other (GeomMesh): Second GeomMesh to test against.
            mj_model (mujoco.MjModel): The compiled MuJoCo model instance.
            mj_data (mujoco.MjData): The current simulation state.
            dist_max (float): The 'cutoff' distance. If objects are further than this (as estimated by a sphere to sphere test), the sphere to sphere estimate will be returned and exit early.
            fromto (bool, optional): Whether or not to return the locations of the minimum distances.

        Returns:
            tuple[float | tuple[float, Vec3, Vec3], ProximityType]: Unsigned (`>= 0`) minimum distance from self to other, world location of minimum distance on self, world location of minimum distance on other, and which phase the exit occurred in.

        """
        geom_self: GeomMesh = self  # pyright: ignore[reportAssignmentType]
        if geom_self.name == other.name:
            logger.error(PROXIMITY_TO_SELF_ERROR_MSG)
            raise ValueError(PROXIMITY_TO_SELF_ERROR_MSG)

        # ========== BROADPHASE ==========
        if np.isnan(self._rad):
            self.bake_proximity(mj_model, ProximityType.CONVEX_HULL)
        if np.isnan(other._rad):
            other.bake_proximity(mj_model, ProximityType.CONVEX_HULL)
        assert not np.isnan(self._rad) and not np.isnan(other._rad)

        d_est, skip = self.get_sphere_to_sphere_proximity(
            other=other,
            mj_model=mj_model,
            mj_data=mj_data,
            dist_max=dist_max,
            fromto=fromto,
        )

        if skip:
            return d_est, ProximityType.SPHERE_TO_SPHERE

        # ========== NARROWPHASE ==========
        # temp buffer for MuJoCo's 6-element output [x1,y1,z1, x2,y2,z2]
        mj_fromto = np.zeros(6)
        min_dist = mujoco.mj_geomDistance(
            m=mj_model,
            d=mj_data,
            geom1=geom_self.get_id(mj_model),
            geom2=other.get_id(mj_model),
            distmax=dist_max,
            fromto=mj_fromto,
        )

        min_dist = max(0.0, min_dist)  # clip from below to zero

        if fromto:
            res = (min_dist, mj_fromto[:3].copy(), mj_fromto[3:6].copy())
        else:
            res = min_dist
        return res, ProximityType.CONVEX_HULL

    @overload
    def get_vertex_to_face_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[False] = False,
    ) -> tuple[float, ProximityType]: ...

    @overload
    def get_vertex_to_face_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[True],
    ) -> tuple[tuple[float, Vec3, Vec3], ProximityType]: ...

    def get_vertex_to_face_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: bool = False,
    ) -> tuple[float | tuple[float, Vec3, Vec3], ProximityType]:
        """
        Calculates the vertex to face distance using a multi-phase Bounding Volume Hierarchy (BVH) query.

        Phases:
            1. Broad Phase: Sphere-Sphere check (object level).
            2. Mid Phase: BVH Traversal (eliminating triangle groups). No exit here.
            3. Narrow Phase: Point-to-Face proximity.

        Args:
            other (GeomMesh): The other geom to test against.
            mj_model (mujoco.MjModel): Compiled MuJoCo model.
            mj_data (mujoco.MjData): MuJoCo runtime data.
            dist_max (float): The 'cutoff' distance. If objects are further than this (as estimated by a sphere to sphere test), the sphere to sphere estimate will be returned and exit early.
            fromto (bool): Whether or not to return the locations of the minimum distances.

        Returns:
            tuple[float | tuple[float, Vec3, Vec3], PhaseExit]: Unsigned (`>= 0`) minimum distance between from self to other and which phase the exit occurred in.

            **OR**

            **tuple[float | tuple[float, Vec3, Vec3], PhaseExit]**: Unsigned (`>= 0`) minimum distance from self to other, world location of minimum distance on self, world location of minimum distance on other, and which phase the exit occurred in.

        """
        geom_self: GeomMesh = self  # pyright: ignore[reportAssignmentType]
        if geom_self.name == other.name:
            logger.error(PROXIMITY_TO_SELF_ERROR_MSG)
            raise ValueError(PROXIMITY_TO_SELF_ERROR_MSG)

        if self._baked_query is None:
            self.bake_proximity(mj_model, ProximityType.VERTEX_TO_FACE)
        if other._baked_query is None:
            other.bake_proximity(mj_model, ProximityType.VERTEX_TO_FACE)
        assert self._baked_query and other._baked_query
        assert self._local_verts is not None and other._local_verts is not None
        assert not np.isnan(self._rad) and not np.isnan(other._rad)

        # ========== BROADPHASE: Sphere-Sphere check ==========
        pos_self = geom_self.rt_xpos(mj_model, mj_data)
        pos_other = other.rt_xpos(mj_model, mj_data)

        # find center to center to center distance and return early if broad phase
        d_est, skip = self.get_sphere_to_sphere_proximity(
            other=other,
            mj_model=mj_model,
            mj_data=mj_data,
            dist_max=dist_max,
            fromto=fromto,
        )
        if skip:
            return d_est, ProximityType.SPHERE_TO_SPHERE

        # ========== COORDINATE TRANSFORMATION ==========
        mat_self = geom_self.rt_xmat(mj_model, mj_data)  # already Mat3 (3x3)
        mat_other = other.rt_xmat(mj_model, mj_data)
        rel_pos = pos_other - pos_self

        # combine transforms from self to other: V_local_self = R_self.T @ (R_other @ V_local_other + p_other - p_self)
        other_v_in_self = (other._local_verts @ mat_other.T + rel_pos) @ mat_self

        # ========== NARROWPHASE A: Self-Surface vs. Other-Vertices ==========
        # trimesh uses a BVH internall here (Mid-phase) to find closest triangles
        pts_on_self, dist_a, _ = self._baked_query.on_surface(other_v_in_self)
        idx_a = np.argmin(dist_a)
        min_a = dist_a[idx_a]

        # ========== NARROWPHASE B: Self-Vertices vs. Other-Surface  ==========
        # transform self vertices into others local frame
        self_v_in_other = (self._local_verts @ mat_self.T - rel_pos) @ mat_other
        pts_on_other, dist_b, _ = other._baked_query.on_surface(self_v_in_other)
        idx_b = np.argmin(dist_b)
        min_b = dist_b[idx_b]

        # ========== CLEANUP ==========
        # find global min
        if min_a < min_b:
            min_dist = float(min_a)
            if fromto:
                p_self = (pts_on_self[idx_a] @ mat_self.T) + pos_self
                p_other = (other_v_in_self[idx_a] @ mat_self.T) + pos_self
                res = (min_dist, p_self, p_other)
            else:
                res = min_dist
            return res, ProximityType.VERTEX_TO_FACE
        else:
            min_dist = float(min_b)
            if fromto:
                # pt_on_other was calculated in other's local frame
                p_other = (pts_on_other[idx_b] @ mat_other.T) + pos_other
                p_self = (self_v_in_other[idx_b] @ mat_other.T) + pos_other
                res = (min_dist, p_self, p_other)
            else:
                res = min_dist
            return res, ProximityType.VERTEX_TO_FACE

    @overload
    def get_face_to_face_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[False] = False,
    ) -> tuple[float, ProximityType]: ...

    @overload
    def get_face_to_face_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[True],
    ) -> tuple[tuple[float, Vec3, Vec3], ProximityType]: ...

    def get_face_to_face_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: bool = False,
    ) -> tuple[float | tuple[float, Vec3, Vec3], ProximityType]:
        """
        Calculates the face to face distance using a multi-phase Bounding Volume Hierarchy (BVH) query.

        This is more accurate than the vertex to face method, but comes at higher computational cost.

        Phases:
            1. Broad Phase: Sphere-Sphere check (object level).
            2. Mid Phase: BVH Traversal (eliminating triangle groups). No exit here.
            3. Narrow Phase: Face-to-Face proximity.

        Args:
            other (GeomMesh): The other geom to test against.
            mj_model (mujoco.MjModel): Compiled MuJoCo model.
            mj_data (mujoco.MjData): MuJoCo runtime data.
            dist_max (float): The 'cutoff' distance. If objects are further than this (as estimated by a sphere to sphere test), the sphere to sphere estimate will be returned and exit early.
            fromto (bool): Whether or not to return the locations of the minimum distances.

        Returns:
            tuple[float | tuple[float, Vec3, Vec3], PhaseExit]: Unsigned (`>= 0`) minimum distance between from self to other and which phase the exit occurred in.

            **OR**

            **tuple[float | tuple[float, Vec3, Vec3], PhaseExit]**: Unsigned (`>= 0`) minimum distance from self to other, world location of minimum distance on self, world location of minimum distance on other, and which phase the exit occurred in.

        """
        geom_self: GeomMesh = self  # pyright: ignore[reportAssignmentType]
        if geom_self.name == other.name:
            logger.error(PROXIMITY_TO_SELF_ERROR_MSG)
            raise ValueError(PROXIMITY_TO_SELF_ERROR_MSG)

        if self._baked_manager is None:
            self.bake_proximity(mj_model, ProximityType.FACE_TO_FACE)
        if other._baked_manager is None:
            other.bake_proximity(mj_model, ProximityType.FACE_TO_FACE)
        assert self._baked_manager and other._baked_manager
        assert not np.isnan(self._rad) and not np.isnan(other._rad)

        # ========== BROADPHASE: Sphere-Sphere check ==========

        # find center to center to center distance and return early if broad phase
        d_est, skip = self.get_sphere_to_sphere_proximity(
            other=other,
            mj_model=mj_model,
            mj_data=mj_data,
            dist_max=dist_max,
            fromto=fromto,
        )
        if skip:
            return d_est, ProximityType.SPHERE_TO_SPHERE

        # ========== NARROWPHASE ==========
        # set the other transformation relative to self's local frame
        t_self = np.eye(4)
        t_self[:3, :3] = geom_self.rt_xmat(mj_model, mj_data)
        t_self[:3, 3] = geom_self.rt_xpos(mj_model, mj_data)

        t_other = np.eye(4)
        t_other[:3, :3] = other.rt_xmat(mj_model, mj_data)
        t_other[:3, 3] = other.rt_xpos(mj_model, mj_data)

        self._baked_manager.set_transform(geom_self.name, t_self)
        other._baked_manager.set_transform(other.name, t_other)

        # CollisionManager returns distance and the two closest points
        result = self._baked_manager.min_distance_other(
            other._baked_manager, return_data=True
        )
        min_dist = float(result[0])  # pyright: ignore[reportIndexIssue]
        data = result[1]  # pyright: ignore[reportIndexIssue]

        if fromto and data is not None:
            p_self = data.point(geom_self.name)  # pyright: ignore[reportAttributeAccessIssue]
            p_other = data.point(other.name)  # pyright: ignore[reportAttributeAccessIssue]
            return (min_dist, p_self, p_other), ProximityType.FACE_TO_FACE

        return min_dist, ProximityType.FACE_TO_FACE

    @overload
    def get_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[False] = False,
        algorithm: ProximityType = ProximityType.CONVEX_HULL,
    ) -> tuple[float, ProximityType]: ...

    @overload
    def get_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[True],
        algorithm: ProximityType = ProximityType.CONVEX_HULL,
    ) -> tuple[tuple[float, Vec3, Vec3], ProximityType]: ...

    def get_proximity(
        self,
        other: GeomMesh,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: bool = False,
        algorithm: ProximityType = ProximityType.CONVEX_HULL,
    ) -> tuple[float | tuple[float, Vec3, Vec3], ProximityType]:
        """
        Calculates the shortest distance between two geometries using the specified proximity algorithm.

        This is a general dispatcher method that routes to different proximity calculation algorithms
        based on the `mode` parameter. Each mode offers different tradeoffs between speed and precision:

        **Modes:**
            - `SPHERE_TO_SPHERE`: Fastest. Uses bounding sphere distance only (broadphase).
            - `CONVEX_HULL`: Fast & accurate. Uses MuJoCo's convex hull-based distance (default).
            - `VERTEX_TO_FACE`: Accurate. Multi-phase BVH with vertex-to-surface queries.
            - `FACE_TO_FACE`: Most accurate but slowest. Full mesh-to-mesh distance calculation.

        **Phases (for non-sphere modes):**
            1. Broad Phase: Sphere-Sphere check (object level).
            2. Narrow Phase: Algorithm-specific distance calculation.

        Args:
            other (GeomMesh): The other geometry to test against.
            mj_model (mujoco.MjModel): Compiled MuJoCo model.
            mj_data (mujoco.MjData): MuJoCo runtime data.
            dist_max (float): The 'cutoff' distance. If objects are further than this (as estimated by a sphere to sphere test), the sphere to sphere estimate will be returned and exit early.
            fromto (bool, optional): Whether to return the locations of the minimum distances. Defaults to False.
            algorithm (ProximityType, optional): Which proximity algorithm to use. Defaults to CONVEX_HULL.

        Returns:
            tuple[float, ProximityType]: If fromto=False, returns the unsigned (`>= 0`) minimum distance and which algorithm produced the result.

            tuple[tuple[float, Vec3, Vec3], ProximityType]: If fromto=True, returns the minimum distance, world location of minimum distance on self, world location of minimum distance on other, and which algorithm produced the result.

        """
        geom_self: GeomMesh = self  # pyright: ignore[reportAssignmentType]
        if geom_self.name == other.name:
            logger.error(PROXIMITY_TO_SELF_ERROR_MSG)
            raise ValueError(PROXIMITY_TO_SELF_ERROR_MSG)

        match algorithm:
            case ProximityType.SPHERE_TO_SPHERE:
                d_est, _skip = self.get_sphere_to_sphere_proximity(
                    other=other,
                    mj_model=mj_model,
                    mj_data=mj_data,
                    dist_max=dist_max,
                    fromto=fromto,
                )
                return d_est, ProximityType.SPHERE_TO_SPHERE
            case ProximityType.CONVEX_HULL:
                return self.get_convex_hull_proximity(
                    other=other,
                    mj_model=mj_model,
                    mj_data=mj_data,
                    dist_max=dist_max,
                    fromto=fromto,
                )
            case ProximityType.VERTEX_TO_FACE:
                return self.get_vertex_to_face_proximity(
                    other=other,
                    mj_model=mj_model,
                    mj_data=mj_data,
                    dist_max=dist_max,
                    fromto=fromto,
                )
            case ProximityType.FACE_TO_FACE:
                return self.get_face_to_face_proximity(
                    other=other,
                    mj_model=mj_model,
                    mj_data=mj_data,
                    dist_max=dist_max,
                    fromto=fromto,
                )
            case _:
                if isinstance(algorithm, ProximityType):
                    msg = f"Method for {algorithm.name} not implemented."
                else:
                    msg = f"Method for unknown algorithm ({algorithm}) not implemented."
                logger.error(msg)
                raise NotImplementedError(msg)

    def request_proximity(
        self,
        signal_manager: SignalManager,
        other: GeomMesh,
        dist_max: float,
        algorithm: ProximityType,
        attrs: list[Literal["dist", "fromto", "prox_type"]] = ["dist", "prox_type"],
    ):
        """
        Registers specific geom proximity attributes for logging. Please see the `get_proximity` method for how these outputs are calculated.

        Available Requests:
            `dist`: Minimum distance as calculated by the specified algorithm. Tagged with `Proximities/{pair_name}:dist`.
            `fromto`: World coordinates for where the minimum distance is estimated to occur at. Two sets of coordinates will be returned for self and other. Tagged with `Proximities/{pair_name}/fromto/{(geom_self | other).name}:(x | y | z)`.
            `prox_type`: What type of proximity calculation the previous values are from. Using `dist_max`, `get_proximity` can return a broadphase estimate (bounding sphere to sphere) if the two geometries are distant (greater than `dist_max`). This telemetry will return what type of proximity calculation was performed for this timestep. It is intended to help debug to understand if a jump in telemetry (specifically sharp declines) are real or comes from the broadphase estimate. The values returned will be integer values associated with their specific ProximityType (see the enumeration for the mapping, in general a larger value will mean a more accurate one). Tagged with `Proximities/{pair_name}:prox_type`.

        """
        geom_self: GeomMesh = self  # pyright: ignore[reportAssignmentType]
        if geom_self.name is None or other.name is None:
            msg = f"Cannot request proximity telemetry for unnamed {geom_self.tag}s."
            logger.error(msg)
            raise ValueError(msg)

        fromto = "fromto" in attrs
        pair_name = f"{geom_self.name}_to_{other.name}"

        def sample(mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
            if fromto:
                (dist, p1, p2), prox_type = self.get_proximity(
                    other=other,
                    mj_model=mj_model,
                    mj_data=mj_data,
                    dist_max=dist_max,
                    fromto=True,
                    algorithm=algorithm,
                )
            else:
                dist, prox_type = self.get_proximity(
                    other=other,
                    mj_model=mj_model,
                    mj_data=mj_data,
                    dist_max=dist_max,
                    fromto=False,
                    algorithm=algorithm,
                )
                p1 = p2 = None

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
                        # "Proximities/{pair_name}/fromto/{(geom_self | other).name}:(x | y | z)"
                        if p1 is not None and p2 is not None:
                            for i, k in enumerate("xyz"):
                                signal_manager.post(
                                    value=float(p1[i]),
                                    category=SignalCategory.PROXIMITIES,
                                    subgroups=(pair_name, attr, str(geom_self.name)),
                                    attr=k,
                                )
                            for i, k in enumerate("xyz"):
                                signal_manager.post(
                                    value=float(p2[i]),
                                    category=SignalCategory.PROXIMITIES,
                                    subgroups=(pair_name, attr, str(other.name)),
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
