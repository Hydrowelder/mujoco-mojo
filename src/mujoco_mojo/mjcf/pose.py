from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mujoco_mojo.mjcf.orientation import (
    AxisAngle,
    Euler,
    OrientationBase,
    Quat,
    XYAxes,
    ZAxis,
)
from mujoco_mojo.mjcf.position import Pos

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
