from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Annotated, ClassVar, Literal

import mujoco
import numpy as np
from pydantic import Field

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.pose import AnyPose
from mujoco_mojo.typing import ActuatorName, BodyName, JointName, Vec3, VecN
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = [
    "ActuatorState",
    "AnyKeyState",
    "FreeBodyState",
    "JointState",
    "KeyStateBase",
    "KeyVector",
    "MocapState",
]

KeyVector = Literal["qpos", "qvel", "act", "ctrl", "mpos", "mquat"]
"""The name of one of the state vectors a `Key` holds."""


def _refuse(msg: str) -> ValueError:
    logger.error(msg)
    return ValueError(msg)


def _object_id(model: mujoco.MjModel, obj: mujoco.mjtObj, name: str, what: str) -> int:
    """The ID of the object of type `obj` named `name`, raising when the model has none."""
    obj_id = mujoco.mj_name2id(model, obj, name)
    if obj_id == -1:
        raise _refuse(f"The model has no {what} named '{name}'.")
    return obj_id


def _sized(value: float | np.ndarray, size: int, what: str) -> np.ndarray:
    """`value` as a flat float array, raising when it does not hold exactly `size` numbers."""
    values = np.atleast_1d(np.asarray(value, dtype=float)).ravel()
    if values.size != size:
        raise _refuse(
            f"The {what} takes {size} value(s), but {values.size} were given."
        )
    return values


def _unit_quat(quat: np.ndarray, what: str) -> np.ndarray:
    norm = np.linalg.norm(quat)
    if norm == 0:
        raise _refuse(f"The {what} is a zero quaternion, which is not a rotation.")
    return quat / norm


class KeyStateBase(MojoBaseModel, ABC):
    """
    One object's share of a keyframe: the values a `Key` gives a joint, a free body, an actuator, or a mocap body.

    Each state names the object it sets, and finds where that object's values go in MuJoCo's state vectors from the compiled model, so the order of those vectors never has to be known. A `Key` holds these in `states`, and the vectors are worked out when the model is written or compiled. A state can also be written into a running simulation with `write`.
    """

    writes: ClassVar[tuple[KeyVector, ...]]
    """The key vectors this kind of state fills in."""

    @property
    @abstractmethod
    def target(self) -> str:
        """What this state sets, such as `joint 'elbow'`, used in messages and to refuse two states that set the same thing."""

    @abstractmethod
    def write(self, state: MjState) -> None:
        """Writes this state's values into `state.data`, leaving everything it does not set as it was."""


class JointState(KeyStateBase):
    """
    The position and velocity of a hinge, slide, or ball joint.

    The values are in MuJoCo's own units and conventions, the same as the joint's slice of `qpos` and `qvel`. A free joint is set with `FreeBodyState` instead, which takes a pose and world-frame velocities.
    """

    kind: Literal["joint"] = "joint"

    writes = ("qpos", "qvel")

    joint: JointName
    """Name of the joint, passed as the joint's own `.name`."""

    qpos: float | VecN | None = None
    """Position of the joint: an angle in radians for a hinge, a distance for a slide, or a quaternion (w, x, y, z) relative to the joint's reference orientation for a ball joint. Left unset, the joint keeps its default position (`qpos0`)."""

    qvel: float | VecN | None = None
    """Velocity of the joint: radians per second for a hinge, distance per second for a slide, or for a ball joint the angular velocity of its body relative to the parent body, in radians per second and expressed in the body's own frame. Left unset, the joint is at rest."""

    @property
    def target(self) -> str:
        return f"joint '{self.joint}'"

    def write(self, state: MjState) -> None:
        model = state.model
        jid = _object_id(model, mujoco.mjtObj.mjOBJ_JOINT, self.joint, "joint")

        match model.jnt_type[jid]:
            case mujoco.mjtJoint.mjJNT_FREE:
                raise _refuse(
                    f"Joint '{self.joint}' is a free joint. Set a free body's pose and velocity with FreeBodyState."
                )
            case mujoco.mjtJoint.mjJNT_BALL:
                nq, nv, ball = 4, 3, True
            case _:
                nq, nv, ball = 1, 1, False

        qpos_adr = int(model.jnt_qposadr[jid])
        dof_adr = int(model.jnt_dofadr[jid])

        if self.qpos is not None:
            qpos = _sized(self.qpos, nq, f"qpos of joint '{self.joint}'")
            if ball:
                qpos = _unit_quat(qpos, f"qpos of ball joint '{self.joint}'")
            state.data.qpos[qpos_adr : qpos_adr + nq] = qpos

        if self.qvel is not None:
            state.data.qvel[dof_adr : dof_adr + nv] = _sized(
                self.qvel, nv, f"qvel of joint '{self.joint}'"
            )


class FreeBodyState(KeyStateBase):
    """
    The pose and velocity of a body with a free joint.

    The pose and velocities are given in the world frame, and are converted to MuJoCo's convention, where the angular velocity of a free joint is expressed in the body's own frame. Setting either velocity sets both, with the one left unset at zero.

    A body attached to its parent by hinge or slide joints has no velocity of its own to set: it moves with its parent, plus the motion of its joints, which `JointState` sets.
    """

    kind: Literal["free_body"] = "free_body"

    writes = ("qpos", "qvel")

    body: BodyName
    """Name of the body, passed as the body's own `.name`."""

    pose: AnyPose | None = None
    """World pose of the body's frame. Left unset, the body keeps the pose it was defined with."""

    linear_velocity: Vec3 | None = None
    """Linear velocity of the body's origin in the world frame, or of the point at `reference`'s origin, in `reference`'s axes, when one is given."""

    angular_velocity: Vec3 | None = None
    """Angular velocity of the body in radians per second, in the world frame, or in `reference`'s axes when one is given."""

    reference: AnyPose | None = None
    """
    A world frame the velocities are given in, for a motion that is easier to describe from somewhere other than the body's origin, such as a spin about a point.

    The velocities then describe the rigid motion of the point at the reference's origin, in the reference's axes, and are carried over to the body's origin: `v_body = v + w x (r_body - r_reference)`.
    """

    @property
    def target(self) -> str:
        return f"free body '{self.body}'"

    def write(self, state: MjState) -> None:
        model = state.model
        bid = _object_id(model, mujoco.mjtObj.mjOBJ_BODY, self.body, "body")

        jnt_adr = int(model.body_jntadr[bid])
        if (
            model.body_jntnum[bid] == 0
            or model.jnt_type[jnt_adr] != mujoco.mjtJoint.mjJNT_FREE
        ):
            raise _refuse(
                f"Body '{self.body}' has no free joint, so it moves with its parent. "
                "Set the velocity of the free body at the root of its tree, and the position and velocity of each joint with JointState."
            )

        qpos_adr = int(model.jnt_qposadr[jnt_adr])
        dof_adr = int(model.jnt_dofadr[jnt_adr])
        qpos = state.data.qpos[qpos_adr : qpos_adr + 7]

        if self.pose is not None:
            qpos[:3] = np.asarray(self.pose.pos, dtype=float)
            qpos[3:] = _unit_quat(
                np.asarray(self.pose.as_quat().quat, dtype=float),
                f"pose of body '{self.body}'",
            )

        if self.linear_velocity is None and self.angular_velocity is None:
            return

        v = (
            np.zeros(3)
            if self.linear_velocity is None
            else np.asarray(self.linear_velocity, dtype=float)
        )
        w = (
            np.zeros(3)
            if self.angular_velocity is None
            else np.asarray(self.angular_velocity, dtype=float)
        )

        if self.reference is not None:
            ref_rot = self.reference.as_matrix()
            v, w = ref_rot @ v, ref_rot @ w
            v = v + np.cross(w, qpos[:3] - np.asarray(self.reference.pos, dtype=float))

        # MuJoCo keeps a free joint's angular velocity in the body's frame
        body_rot = np.zeros(9)
        mujoco.mju_quat2Mat(body_rot, qpos[3:])
        state.data.qvel[dof_adr : dof_adr + 3] = v
        state.data.qvel[dof_adr + 3 : dof_adr + 6] = body_rot.reshape(3, 3).T @ w


class ActuatorState(KeyStateBase):
    """The control and activation of an actuator."""

    kind: Literal["actuator"] = "actuator"

    writes = ("ctrl", "act")

    actuator: ActuatorName
    """Name of the actuator, passed as the actuator's own `.name`."""

    ctrl: float | None = None
    """Control input of the actuator. Left unset, it is zero."""

    act: float | VecN | None = None
    """Activation of an actuator with activation dynamics (one value for most, such as a muscle or a `dyntype` of `filter` or `integrator`). Left unset, it is zero."""

    @property
    def target(self) -> str:
        return f"actuator '{self.actuator}'"

    def write(self, state: MjState) -> None:
        model = state.model
        aid = _object_id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, self.actuator, "actuator")

        if self.ctrl is not None:
            state.data.ctrl[aid] = self.ctrl

        if self.act is not None:
            act_adr = int(model.actuator_actadr[aid])
            if act_adr == -1:
                raise _refuse(
                    f"Actuator '{self.actuator}' has no activation state, so it takes no act."
                )
            act_num = int(model.actuator_actnum[aid])
            state.data.act[act_adr : act_adr + act_num] = _sized(
                self.act, act_num, f"act of actuator '{self.actuator}'"
            )


class MocapState(KeyStateBase):
    """The pose of a mocap body (a body with `mocap=True`)."""

    kind: Literal["mocap"] = "mocap"

    writes = ("mpos", "mquat")

    body: BodyName
    """Name of the mocap body, passed as the body's own `.name`."""

    pose: AnyPose
    """World pose of the mocap body."""

    @property
    def target(self) -> str:
        return f"mocap body '{self.body}'"

    def write(self, state: MjState) -> None:
        model = state.model
        bid = _object_id(model, mujoco.mjtObj.mjOBJ_BODY, self.body, "body")

        mocap_id = int(model.body_mocapid[bid])
        if mocap_id == -1:
            raise _refuse(f"Body '{self.body}' is not a mocap body.")

        state.data.mocap_pos[mocap_id] = np.asarray(self.pose.pos, dtype=float)
        state.data.mocap_quat[mocap_id] = _unit_quat(
            np.asarray(self.pose.as_quat().quat, dtype=float),
            f"pose of mocap body '{self.body}'",
        )


AnyKeyState = Annotated[
    JointState | FreeBodyState | ActuatorState | MocapState,
    Field(discriminator="kind"),
]
"""Discriminated union of the states a `Key` can hold."""
