from typing import TYPE_CHECKING

import mujoco
import numpy as np
import trimesh
from pydantic import PrivateAttr

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.typing import MatN, ProximityType, Vec3
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import GeomMesh

logger = get_logger(__name__)


class ProximityMixin(MojoBaseModel):
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

    _proximity_configured_for: ProximityType | None = PrivateAttr(default=None)

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
