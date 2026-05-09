from enum import IntEnum
from typing import TYPE_CHECKING, Literal, overload

import mujoco
import numpy as np
import trimesh
from pydantic import PrivateAttr

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.typing import MatN, Vec3
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import AnyGeom

logger = get_logger(__name__)


class ProximityType(IntEnum):
    """Exit types from proximity calculations."""

    SPHERE_TO_SPHERE = 0
    """Returned value is from a broadphase test (bounding sphere to bounding sphere)."""

    CONVEX_HULL = 1
    """Returned value is from a convex hull to convex hull test."""

    # VERTEX_TO_VERTEX = 2
    # """Returned value is from a vertex to vertex test."""

    VERTEX_TO_FACE = 3
    """Returned value is from a vertex to face test."""

    FACE_TO_FACE = 4
    """Returned value is from a face to face test."""


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
    _rad: float = PrivateAttr(default=np.nan)

    def bake_proximity(self, mj_model: mujoco.MjModel, proximity_type: ProximityType):
        """Builds the BVH tree from the comiled MuJoCo mesh data."""
        geom_self: AnyGeom = self  # pyright: ignore[reportAssignmentType]

        # cache bounding radius
        self._rad = geom_self.rbound(mj_model)

        match proximity_type:
            case ProximityType.SPHERE_TO_SPHERE | ProximityType.CONVEX_HULL:
                return

        # get mesh id and data from mujoco
        mesh_id = mj_model.geom_dataid[geom_self.get_id(mj_model)]

        if mesh_id == -1:
            logger.error(
                "Exact proximity mesh tool is not currently supported for geoms made from primitives."
            )
            return

        # extract vertices and faces
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

        logger.debug(f"Baked BVH for {geom_self.name} ({len(self._local_faces)} faces)")

    @overload
    def get_vertex_to_face_proximity(
        self,
        other: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[False] = False,
    ) -> tuple[float, ProximityType]: ...

    @overload
    def get_vertex_to_face_proximity(
        self,
        other: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[True],
    ) -> tuple[tuple[float, Vec3, Vec3], ProximityType]: ...

    @overload
    def get_face_to_face_proximity(
        self,
        other: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[False] = False,
    ) -> tuple[float, ProximityType]: ...

    @overload
    def get_face_to_face_proximity(
        self,
        other: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[True],
    ) -> tuple[tuple[float, Vec3, Vec3], ProximityType]: ...

    @classmethod
    def _broadphase_test(
        cls,
        rad_a: float,
        pos_a: Vec3,
        rad_b: float,
        pos_b: Vec3,
        dist_max: float,
        fromto: bool = False,
    ) -> tuple[float | tuple[float, Vec3, Vec3], bool]:
        """
        Performs a broadphase proximity test on bounding spheres.

        Args:
            rad_a (float): Bounding radius of A.
            pos_a (Vec3): Position of center of A.
            rad_b (float): Bounding radius of B.
            pos_b (Vec3): Position of center of B.
            dist_max (float): The 'cutoff' distance. If the objects are further than this, dist_max will be returned and exit early (fromto will also return as zeros).
            fromto (bool, optional): Whether or not to return the locations of the minimum distances. Defaults to False.

        Returns:
            tuple[float | tuple[float, Vec3, Vec3], bool]: Unsigned (`>= 0`) minimum distance from self to other, world location of minimum distance on self, world location of minimum distance on other, and if the result is greater than dist_max.

        """
        dist = float(np.linalg.norm(pos_a - pos_b) - (rad_a + rad_b))
        if dist > dist_max:
            res = (dist, np.zeros(3), np.zeros(3)) if fromto else dist
            return res, True
        return dist, False

    def get_vertex_to_face_proximity(
        self,
        other: AnyGeom,
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
            other (AnyGeom): The other geom to test against.
            mj_model (mujoco.MjModel): Compiled MuJoCo model.
            mj_data (mujoco.MjData): MuJoCo runtime data.
            dist_max (float): The 'cutoff' distance. If the objects are further than this, dist_max will be returned and exit early (fromto will also return as zeros).
            fromto (bool): Whether or not to return the locations of the minimum distances.

        Returns:
            tuple[float | tuple[float, Vec3, Vec3], PhaseExit]: Unsigned (`>= 0`) minimum distance between from self to other and which phase the exit occurred in.

            **OR**

            **tuple[float | tuple[float, Vec3, Vec3], PhaseExit]**: Unsigned (`>= 0`) minimum distance from self to other, world location of minimum distance on self, world location of minimum distance on other, and which phase the exit occurred in.

        """
        if self._baked_query is None:
            self.bake_proximity(mj_model, ProximityType.VERTEX_TO_FACE)
        if other._baked_query is None:
            other.bake_proximity(mj_model, ProximityType.VERTEX_TO_FACE)
        assert self._baked_query and other._baked_query
        assert self._local_verts is not None and other._local_verts is not None
        assert not np.isnan(self._rad) and not np.isnan(other._rad)

        geom_self: AnyGeom = self  # pyright: ignore[reportAssignmentType]

        # ========== BROADPHASE: Sphere-Sphere check ==========
        rad_self = self._rad
        rad_other = other._rad

        pos_self = geom_self.rt_xpos(mj_model, mj_data)
        pos_other = other.rt_xpos(mj_model, mj_data)

        # find center to center to center distance and return early if broad phase
        d_est, skip = self._broadphase_test(
            rad_a=rad_self,
            pos_a=pos_self,
            rad_b=rad_other,
            pos_b=pos_other,
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

    def get_face_to_face_proximity(
        self,
        other: AnyGeom,
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
            other (AnyGeom): The other geom to test against.
            mj_model (mujoco.MjModel): Compiled MuJoCo model.
            mj_data (mujoco.MjData): MuJoCo runtime data.
            dist_max (float): The 'cutoff' distance. If the objects are further than this, dist_max will be returned and exit early (fromto will also return as zeros).
            fromto (bool): Whether or not to return the locations of the minimum distances.

        Returns:
            tuple[float | tuple[float, Vec3, Vec3], PhaseExit]: Unsigned (`>= 0`) minimum distance between from self to other and which phase the exit occurred in.

            **OR**

            **tuple[float | tuple[float, Vec3, Vec3], PhaseExit]**: Unsigned (`>= 0`) minimum distance from self to other, world location of minimum distance on self, world location of minimum distance on other, and which phase the exit occurred in.

        """
        if self._baked_manager is None:
            self.bake_proximity(mj_model, ProximityType.FACE_TO_FACE)
        if other._baked_manager is None:
            other.bake_proximity(mj_model, ProximityType.FACE_TO_FACE)
        assert self._baked_manager and other._baked_manager
        assert not np.isnan(self._rad) and not np.isnan(other._rad)

        geom_self: AnyGeom = self  # pyright: ignore[reportAssignmentType]

        # ========== BROADPHASE: Sphere-Sphere check ==========
        rad_self = self._rad
        rad_other = other._rad

        pos_self = geom_self.rt_xpos(mj_model, mj_data)
        pos_other = other.rt_xpos(mj_model, mj_data)

        # find center to center to center distance and return early if broad phase
        d_est, skip = self._broadphase_test(
            rad_a=rad_self,
            pos_a=pos_self,
            rad_b=rad_other,
            pos_b=pos_other,
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
        min_dist = float(result[0])
        data = result[1]

        if fromto and data is not None:
            p_self = data.point(geom_self.name)  # pyright: ignore[reportAttributeAccessIssue]
            p_other = data.point(other.name)  # pyright: ignore[reportAttributeAccessIssue]
            return (min_dist, p_self, p_other), ProximityType.FACE_TO_FACE

        return min_dist, ProximityType.FACE_TO_FACE

    @overload
    def get_convex_hull_proximity(
        self,
        other: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[False] = False,
    ) -> tuple[float, ProximityType]: ...

    @overload
    def get_convex_hull_proximity(
        self,
        other: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[True],
    ) -> tuple[tuple[float, Vec3, Vec3], ProximityType]: ...

    def get_convex_hull_proximity(
        self,
        other: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: bool = False,
    ) -> tuple[float | tuple[float, Vec3, Vec3], ProximityType]:
        """
        Calculates the shortest distance between two geometries using their convex hull.

        Args:
            other (AnyGeom): Second AnyGeom to test against.
            mj_model (mujoco.MjModel): The compiled MuJoCo model instance.
            mj_data (mujoco.MjData): The current simulation state.
            dist_max (float): The 'cutoff' distance. If the objects are further than this, dist_max will be returned and exit early (fromto will also return as zeros).
            fromto (bool, optional): Whether or not to return the locations of the minimum distances.

        Returns:
            tuple[float | tuple[float, Vec3, Vec3], ProximityType]: Signed (`>= 0`) minimum distance from self to other, world location of minimum distance on self, world location of minimum distance on other, and which phase the exit occurred in.

        """
        geom_self: AnyGeom = self  # pyright: ignore[reportAssignmentType]

        # ========== BROADPHASE ==========
        if np.isnan(self._rad):
            self.bake_proximity(mj_model, ProximityType.CONVEX_HULL)
        if np.isnan(other._rad):
            other.bake_proximity(mj_model, ProximityType.CONVEX_HULL)
        assert not np.isnan(self._rad) and not np.isnan(other._rad)

        d_est, skip = self._broadphase_test(
            rad_a=self._rad,
            rad_b=other._rad,
            pos_a=geom_self.rt_xpos(mj_model, mj_data),
            pos_b=other.rt_xpos(mj_model, mj_data),
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
            distmax=d_est[0] if isinstance(d_est, tuple) else d_est,
            fromto=mj_fromto,
        )

        if fromto:
            res = (min_dist, mj_fromto[:3].copy(), mj_fromto[3:6].copy())
        else:
            res = min_dist
        return res, ProximityType.CONVEX_HULL

    @overload
    def get_proximity(
        self,
        other: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[False] = False,
        algorithm: ProximityType = ProximityType.CONVEX_HULL,
    ) -> tuple[float, ProximityType]: ...

    @overload
    def get_proximity(
        self,
        other: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[True],
        algorithm: ProximityType = ProximityType.CONVEX_HULL,
    ) -> tuple[tuple[float, Vec3, Vec3], ProximityType]: ...

    def get_proximity(
        self,
        other: AnyGeom,
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
            other (AnyGeom): The other geometry to test against.
            mj_model (mujoco.MjModel): Compiled MuJoCo model.
            mj_data (mujoco.MjData): MuJoCo runtime data.
            dist_max (float): The 'cutoff' distance. If objects are further than this, dist_max will be returned and exit early (fromto will also return as zeros).
            fromto (bool, optional): Whether to return the locations of the minimum distances. Defaults to False.
            algorithm (ProximityType, optional): Which proximity algorithm to use. Defaults to CONVEX_HULL.

        Returns:
            tuple[float, ProximityType]: If fromto=False, returns the unsigned (`>= 0`) minimum distance and which algorithm produced the result.

            tuple[tuple[float, Vec3, Vec3], ProximityType]: If fromto=True, returns the minimum distance, world location of minimum distance on self, world location of minimum distance on other, and which algorithm produced the result.

        """
        match algorithm:
            case ProximityType.SPHERE_TO_SPHERE:
                geom_self: AnyGeom = self  # pyright: ignore[reportAssignmentType]

                if np.isnan(self._rad):
                    self.bake_proximity(mj_model, ProximityType.SPHERE_TO_SPHERE)
                if np.isnan(other._rad):
                    other.bake_proximity(mj_model, ProximityType.SPHERE_TO_SPHERE)
                assert not np.isnan(self._rad) and not np.isnan(other._rad)
                d_est, _skip = self._broadphase_test(
                    rad_a=self._rad,
                    rad_b=other._rad,
                    pos_a=geom_self.rt_xpos(mj_model, mj_data),
                    pos_b=other.rt_xpos(mj_model, mj_data),
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
                msg = f"Method for {algorithm.name} not implemented."
                logger.error(msg)
                raise NotImplementedError(msg)
