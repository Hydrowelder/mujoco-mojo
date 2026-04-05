from __future__ import annotations

from typing import Annotated, Any, Self

import numpy as np
from pydantic import Field

from mujoco_mojo.mjcf.constants import DEFAULT_ANGLE, DEFAULT_EULERSEQ
from mujoco_mojo.mjcf.orientation import (
    AxisAngle,
    Euler,
    OrientationBase,
    Quat,
    XYAxes,
    ZAxis,
)
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.typing import Angle, EulerSeq, Vec3

__all__ = [
    "Pose",
    "PoseAxisAngle",
    "PoseEuler",
    "PoseQuat",
    "PoseXYAxes",
    "PoseZAxis",
]


class PoseBase(Pos, OrientationBase):
    """
    Base class for objects representing a full 3D coordinate frame.
    Inherits math logic from Pos and rotation logic from OrientationBase.
    """

    tag = ""
    attributes = (*Pos.attributes, *OrientationBase.attributes)

    def inv(self) -> PoseQuat:
        """Returns the inverse Pose."""
        r_inv = self.as_matrix().T
        p_inv = -(r_inv @ np.asarray(self.pos))
        return Quat.from_matrix(r_inv).as_pose(pos=p_inv)

    def apply(self, vec: Vec3) -> np.ndarray:
        """Transforms a point from local coordinates to parent coordinates."""
        # v' = R*v + p
        return self.as_matrix() @ np.asarray(vec) + np.asarray(self.pos)

    def __mul__(self, other: Any) -> Any:
        # point transform
        if isinstance(other, (np.ndarray, list, tuple)) and len(other) == 3:
            return self.apply(np.asarray(other))

        # pose composition
        if isinstance(other, PoseBase):
            new_r = self.as_matrix() @ other.as_matrix()
            new_p = self.as_matrix() @ np.asarray(other.pos) + np.asarray(self.pos)
            return Quat.from_matrix(new_r).as_pose(pos=new_p)

        return NotImplemented

    def expressed_in(self, target: PoseBase) -> PoseQuat:
        """Returns this pose expressed relative to a target frame."""
        return target.inv() * self

    @classmethod
    def look_at(
        cls,
        target: Vec3,
        eye: Vec3 = np.array([0, 0, 0]),
        up: Vec3 = np.array([0, 0, 1]),
        negative_z: bool = True,
    ) -> Self:
        """
        Creates a full Pose that points the Z-axis toward/away from a target.

        Args:
            target (Vec3): Where the vector should point to.
            eye (Vec3, optional): From where the vector should point. Defaults to np.array([0, 0, 0]).
            up (Vec3, optional): Up axis for the vector. Defaults to np.array([0, 0, 1]).
            negative_z (bool, optional): Whether the z axis should point its plus or minus axis at the target (Cameras and Lights use minus, Geom uses plus). Defaults to True.

        Returns:
            Self: New instance of Pose.

        """
        ori = Quat.look_at(target=target, eye=eye, up=up, negative_z=negative_z)
        return cls.from_matrix(ori.as_matrix()).model_copy(update={"pos": eye})

    def as_pose_quat(self) -> PoseQuat:
        """Converts this pose to a PoseQuat representation."""
        # as_quat() returns a Quat; as_pose(pos) turns it back into a Pose
        return self.as_quat().as_pose(pos=self.pos)

    def as_pose_euler(
        self, seq: EulerSeq = DEFAULT_EULERSEQ, angle: Angle = DEFAULT_ANGLE
    ) -> PoseEuler:
        """Converts this pose to a PoseEuler representation."""
        return self.as_euler(seq=seq, angle_type=angle).as_pose(pos=self.pos)

    def as_pose_axisangle(self, angle: Angle = DEFAULT_ANGLE) -> PoseAxisAngle:
        """Converts this pose to a PoseAxisAngle representation."""
        return self.as_axisangle(angle_type=angle).as_pose(pos=self.pos)

    def as_pose_xyaxes(self) -> PoseXYAxes:
        """Converts this pose to a PoseXYAxes representation."""
        return self.as_xyaxes().as_pose(pos=self.pos)

    def as_pose_zaxis(self) -> PoseZAxis:
        """Converts this pose to a PoseZAxis representation."""
        return self.as_zaxis().as_pose(pos=self.pos)


class PoseQuat(PoseBase, Quat):
    """A full pose defined by a position and a quaternion."""

    attributes = (*PoseBase.attributes, *Quat.attributes)


class PoseEuler(PoseBase, Euler):
    """A full pose defined by a position and Euler angles."""

    attributes = (*PoseBase.attributes, *Euler.attributes)


class PoseAxisAngle(PoseBase, AxisAngle):
    """A full pose defined by a position and an axis-angle."""

    attributes = (*PoseBase.attributes, *AxisAngle.attributes)


class PoseXYAxes(PoseBase, XYAxes):
    """A full pose defined by a position and XY axes."""

    attributes = (*PoseBase.attributes, *XYAxes.attributes)


class PoseZAxis(PoseBase, ZAxis):
    """A full pose defined by a position and a Z axis."""

    attributes = (*PoseBase.attributes, *ZAxis.attributes)


# Unified type for MJCF elements that support any orientation type
Pose = Annotated[
    PoseQuat | PoseAxisAngle | PoseEuler | PoseXYAxes | PoseZAxis,
    Field(discriminator="type"),
]
"""Discriminated union for type hinting the various types of Orientations."""
