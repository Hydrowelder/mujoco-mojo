"""
MuJoCo model-introspection helpers for resolving the physical quantity a joint's or actuator's generalized data represents, for use as `SignalManager` metadata defaults.

Joint- and tendon-transmission actuators, and joint-referencing sensors, are restricted by MuJoCo's compiler to single-DOF (hinge/slide) joint targets -- ball/free joints are invalid targets for these (e.g. a `<motor joint=.../>` or `<jointpos joint=.../>` on a ball/free joint fails to compile), so `joint_type_metadata()` only needs to distinguish slide from "everything else", without separately handling ball/free.
"""

from __future__ import annotations

import mujoco

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.utils.signal_metadata import (
    Dimension,
    angle_metadata,
    angular_rate_metadata,
    dim,
    force_or_torque,
)

__all__ = [
    "actuator_transmission_metadata",
    "joint_type_metadata",
    "sensor_referenced_joint_type",
]


def joint_type_metadata(jnt_type: int) -> dict[str, dict[str, str]]:
    """
    Returns `{"pos": ..., "vel": ..., "frc": ...}` metadata for a single-DOF joint's generalized position/velocity/force, based on its type: angle-based (units) for hinge, or length-based (dimension) for slide.
    """
    if jnt_type == mujoco.mjtJoint.mjJNT_SLIDE:
        return {
            "pos": dim(Dimension.LENGTH),
            "vel": dim(Dimension.VELOCITY),
            "frc": dim(Dimension.FORCE),
        }
    return {
        "pos": angle_metadata(),
        "vel": angular_rate_metadata(),
        "frc": force_or_torque(jnt_type),
    }


def actuator_transmission_metadata(
    state: MjState, actuator_id: int
) -> dict[str, dict[str, str]] | None:
    """
    Resolves `{"length": ..., "velocity": ..., "force": ...}` metadata for a JOINT/JOINTINPARENT- or TENDON-transmission actuator. Returns None for SITE/BODY/SLIDERCRANK transmission, since the `gear` attribute lets those mean anything -- those channels stay user-injectable-only.
    """
    trntype = int(state.model.actuator_trntype[actuator_id])

    if trntype in (mujoco.mjtTrn.mjTRN_JOINT, mujoco.mjtTrn.mjTRN_JOINTINPARENT):
        jnt_id = int(state.model.actuator_trnid[actuator_id, 0])
        jnt_type = int(state.model.jnt_type[jnt_id])
        joint_meta = joint_type_metadata(jnt_type)
        return {
            "length": joint_meta["pos"],
            "velocity": joint_meta["vel"],
            "force": joint_meta["frc"],
        }

    if trntype == mujoco.mjtTrn.mjTRN_TENDON:
        return {
            "length": dim(Dimension.LENGTH),
            "velocity": dim(Dimension.VELOCITY),
            "force": dim(Dimension.FORCE),
        }

    return None


def sensor_referenced_joint_type(state: MjState, sensor_id: int) -> int | None:
    """
    Returns the `mjtJoint` type of the joint a sensor references, or None if the sensor's `sensor_objtype` isn't a joint (e.g. actuator-referencing sensors, which instead resolve via `actuator_transmission_metadata` on the referenced actuator id).
    """
    if int(state.model.sensor_objtype[sensor_id]) != mujoco.mjtObj.mjOBJ_JOINT:
        return None
    jnt_id = int(state.model.sensor_objid[sensor_id])
    return int(state.model.jnt_type[jnt_id])
