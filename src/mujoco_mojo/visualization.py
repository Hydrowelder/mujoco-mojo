from dataclasses import dataclass

import mujoco
import numpy as np

from mujoco_mojo.typing import Vec3, Vec4
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)


@dataclass
class ArrowConfig:
    pos: Vec3
    vec: Vec3
    color: Vec4
    is_torque: bool

    def draw_in_scene(self, mj_model: mujoco.MjModel, scene: mujoco.MjvScene):
        if scene.ngeom >= scene.maxgeom:
            logger.warning("Unable to draw arrow due to geom. quantity limit")
            return

        # grab current geom slot
        geom = scene.geoms[scene.ngeom]

        # initialize with default
        mujoco.mjv_initGeom(
            geom=geom,
            type=mujoco.mjtGeom.mjGEOM_ARROW,
            size=np.zeros(3),
            pos=np.zeros(3),
            mat=np.zeros(9),
            rgba=np.asarray(self.color, dtype=np.float32),
        )

        # calculate native scaling
        start, end, width = self.resolve_arrow_coords(mj_model)

        # use connector to solve pos and rot. mat.
        mujoco.mjv_connector(
            geom=geom,
            type=mujoco.mjtGeom.mjGEOM_ARROW,
            width=width,
            from_=start,
            to=end,
        )
        geom.rgba = self.color
        scene.ngeom += 1

    def resolve_arrow_coords(
        self, mj_model: mujoco.MjModel
    ) -> tuple[Vec3, Vec3, float]:
        """Calculates the 'from' and 'to' points and width for an arrow."""
        # calculate native scaling
        v_map = mj_model.vis.map
        v_scale = mj_model.vis.scale
        stat = mj_model.stat

        if self.is_torque:
            mag_scale = v_map.torque
            width = v_scale.jointwidth * stat.meansize
        else:
            mag_scale = v_map.force
            width = v_scale.forcewidth * stat.meansize

        # normalize length by mean body mass
        scaled_vec = self.vec * (mag_scale / max(stat.meanmass, 1e-6))
        start = np.asarray(self.pos)
        return start, start + scaled_vec, width


@dataclass
class LineConfig:
    pos1: Vec3
    pos2: Vec3
    color: Vec4
    width: float

    def draw_in_scene(self, scene: mujoco.MjvScene):
        if scene.ngeom >= scene.maxgeom:
            logger.warning("Unable to draw line due to geom. quantity limit")
            return

        # grab current geom slot
        geom = scene.geoms[scene.ngeom]

        # initialize with default
        mujoco.mjv_initGeom(
            geom=geom,
            type=mujoco.mjtGeom.mjGEOM_ARROW,
            size=np.zeros(3),
            pos=np.zeros(3),
            mat=np.zeros(9),
            rgba=np.asarray(self.color, dtype=np.float32),
        )

        # use connector to solve pos and rot. mat.
        mujoco.mjv_connector(
            geom=geom,
            type=mujoco.mjtGeom.mjGEOM_LINE,
            width=self.width,
            from_=self.pos1,
            to=self.pos2,
        )
        geom.rgba = self.color
        scene.ngeom += 1
