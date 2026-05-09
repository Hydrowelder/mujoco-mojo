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


class PhaseExit(IntEnum):
    """Exit types from proximity calculations."""

    BROADPHASE = 0
    """Returned value is from the broadphase checks (bounding sphere to bounding sphere)."""

    VERTEX_TO_VERTEX = 2
    """Returned value is from the vertex to vertex checks."""

    VERTEX_TO_FACE = 2
    """Returned value is from the vertex to vertex checks."""

    FACE_TO_FACE = 3
    """Returned value is from the manifold to manifold checks."""


class ProximityMixin(MojoBaseModel):
    """Provide high-precision triangle-level distance queries."""

    _baked_mesh: trimesh.Trimesh | None = PrivateAttr(default=None)
    """Internal trimesh representation of the geometry."""

    _baked_query: trimesh.proximity.ProximityQuery | None = PrivateAttr(default=None)
    """Pre-computed BVH query object for fast distance lookups."""

    _local_verts: MatN | None = PrivateAttr(default=None)
    _local_faces: MatN | None = PrivateAttr(default=None)
    _rad: float = PrivateAttr(default=np.nan)

    def bake_proximity(self, mj_model: mujoco.MjModel):
        """Builds the BVH tree from the comiled MuJoCo mesh data."""
        geom_self: AnyGeom = self  # pyright: ignore[reportAssignmentType]

        # cache bounding radius
        self._rad = geom_self.geom_rbound(mj_model)

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
    ) -> tuple[float, PhaseExit]: ...

    @overload
    def get_vertex_to_face_proximity(
        self,
        other: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Literal[True],
    ) -> tuple[tuple[float, Vec3, Vec3], PhaseExit]: ...

    def get_vertex_to_face_proximity(
        self,
        other: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: bool = False,
    ) -> tuple[float | tuple[float, Vec3, Vec3], PhaseExit]:
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
            self.bake_proximity(mj_model)
        if other._baked_query is None:
            other.bake_proximity(mj_model)
        assert self._baked_query and other._baked_query
        assert self._local_verts is not None and other._local_verts is not None
        assert self._rad != np.nan and other._rad != np.nan

        geom_self: AnyGeom = self  # pyright: ignore[reportAssignmentType]

        # ========== BROADPHASE: Sphere-Sphere check ==========
        rad_self = self._rad
        rad_other = other._rad

        pos_self = geom_self.rt_xpos(mj_model, mj_data)
        pos_other = other.rt_xpos(mj_model, mj_data)

        # find center to center to center distance and return early if broad phase
        broadphase_dist = float(
            np.linalg.norm(pos_self - pos_other) - (rad_self + rad_other)
        )
        if broadphase_dist > dist_max:
            res = (
                (broadphase_dist, np.zeros(3), np.zeros(3))
                if fromto
                else broadphase_dist
            )
            return res, PhaseExit.BROADPHASE

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
            return res, PhaseExit.VERTEX_TO_FACE
        else:
            min_dist = float(min_b)
            if fromto:
                # pt_on_other was calculated in other's local frame
                p_other = (pts_on_other[idx_b] @ mat_other.T) + pos_other
                p_self = (self_v_in_other[idx_b] @ mat_other.T) + pos_other
                res = (min_dist, p_self, p_other)
            else:
                res = min_dist
            return res, PhaseExit.VERTEX_TO_FACE
