import mujoco
import numpy as np

from mujoco_mojo.typing import Vec3


def resolve_arrow_coords(
    mj_model: mujoco.MjModel, pos: Vec3, vec: Vec3, is_torque: bool
) -> tuple[Vec3, Vec3, float]:
    """Calculates the 'from' and 'to' points and width for an arrow."""
    # calculate native scaling
    v_map = mj_model.vis.map
    v_scale = mj_model.vis.scale
    stat = mj_model.stat

    if is_torque:
        mag_scale = v_map.torque
        width = v_scale.jointwidth * stat.meansize
    else:
        mag_scale = v_map.force
        width = v_scale.forcewidth * stat.meansize

    # normalize length by mean body mass
    scaled_vec = vec * (mag_scale / max(stat.meanmass, 1e-6))
    start = np.asarray(pos)
    return start, start + scaled_vec, width
