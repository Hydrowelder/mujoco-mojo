from dataclasses import dataclass
from typing import ClassVar, Protocol, runtime_checkable

import mujoco
import numpy as np

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.typing import Vec3, Vec4
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)


@runtime_checkable
class Traceable(Protocol):
    """Anything with a world position that can be followed by a `Tracer`, e.g. a `Body`, `Site`, or `Geom`."""

    def rt_pos(self, state: MjState) -> Vec3: ...


@dataclass
class ArrowConfig:
    pos: Vec3
    vec: Vec3
    color: Vec4
    is_torque: bool
    length_scale: float = 1.0
    """Extra multiplier applied on top of MuJoCo's native length scaling, for stretching or shrinking this arrow's length independently of the others."""
    width_scale: float = 1.0
    """Extra multiplier applied on top of MuJoCo's native width scaling, for thickening or thinning this arrow's shaft independently of the others."""

    # the arrow head consumes a fixed fraction of the shaft width regardless of length, so a fixed
    # width (e.g. jointwidth) on a short vector renders as a flattened disk rather than an arrow.
    # capping the width relative to the resolved length keeps the head/shaft proportions sane at
    # any magnitude.
    _MAX_WIDTH_TO_LENGTH_RATIO: ClassVar[float] = 0.25

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

        # normalize length by mean body mass, then apply the caller's custom length scale
        scaled_vec = (
            self.vec * (mag_scale / max(stat.meanmass, 1e-6)) * self.length_scale
        )
        start = np.asarray(self.pos)
        end = start + scaled_vec

        # apply the caller's custom width scale, then cap it so a short vector doesn't render as
        # a disk (see _MAX_WIDTH_TO_LENGTH_RATIO)
        length = float(np.linalg.norm(scaled_vec))
        width = min(width * self.width_scale, length * self._MAX_WIDTH_TO_LENGTH_RATIO)

        return start, end, width


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
