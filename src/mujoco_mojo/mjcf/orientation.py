from __future__ import annotations

from enum import StrEnum, auto
from typing import Annotated, Literal, Optional, TypeAlias

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.types import Vec3, Vec4, Vec6

__all__ = [
    "Orientation",
    "Quat",
    "AxisAngle",
    "XYAxes",
    "ZAxis",
    "Euler",
]


class OrientationType(StrEnum):
    """Defines the type field for orientation types (used for discriminated union)."""

    QUAT = auto()
    """Quaternion type."""
    AXISANGLE = auto()
    """Axis angle type."""
    XYAXES = auto()
    """XY axes type."""
    ZAXIS = auto()
    """Z axis type."""
    EULER = auto()
    """Euler angle type."""


class OrientationBase(XMLModel):
    """Defines the base model for orientations.

    Several model elements have right-handed spatial frames associated with them. These are all the elements defined in the kinematic tree except for joints. A spatial frame is defined by its position and orientation. Specifying 3D positions is straightforward, but specifying 3D orientations can be challenging. This is why MJCF provides several alternative mechanisms. No matter which mechanism the user chooses, the frame orientation is always converted internally to a unit quaternion. Recall that a 3D rotation by angle aa around axis given by the unit vector (x,y,z) corresponds to the quaternion ((cos(a/2),sin(a/2)⋅(x,y,z)). Also recall that every 3D orientation can be uniquely specified by a single 3D rotation by some angle around some axis.

    All MJCF elements that have spatial frames allow the five attributes listed below. The frame orientation is specified using at most one of these attributes. The quat attribute has a default value corresponding to the null rotation, while the others are initialized in the special undefined state. Thus if none of these attributes are specified by the user, the frame is not rotated."""

    tag = ""


class Quat(OrientationBase):
    """If the quaternion is known, this is the preferred was to specify the frame orientation because it does not involve conversions. Instead it is normalized to unit length and copied into mjModel during compilation. When a model is saved as MJCF, all frame orientations are expressed as quaternions using this attribute."""

    type: Literal[OrientationType.QUAT] = OrientationType.QUAT

    attributes = ("quat",)

    quat: Optional[Vec4] = None
    """Orientation of the frame. See Frame orientations. Defined as (w, x, y, z) quaternion order (the same as MuJoCo convention)."""


class AxisAngle(OrientationBase):
    """These are the quantities (x,y,z,a) mentioned above. The last number is the angle of rotation, in degrees or radians as specified by the angle attribute of compiler. The first three numbers determine a 3D vector which is the rotation axis. This vector is normalized to unit length during compilation, so the user can specify a vector of any non-zero length. Keep in mind that the rotation is right-handed; if the direction of the vector (x,y,z) is reversed this will result in the opposite rotation. Changing the sign of aa can also be used to specify the opposite rotation."""

    type: Literal[OrientationType.AXISANGLE] = OrientationType.AXISANGLE
    attributes = ("axisangle",)

    axisangle: Optional[Vec4] = None
    """Orientation of the frame. See Frame orientations."""


class Euler(OrientationBase):
    """Rotation angles around three coordinate axes. The sequence of axes around which these rotations are applied is determined by the eulerseq attribute of compiler and is the same for the entire model."""

    type: Literal[OrientationType.EULER] = OrientationType.EULER
    attributes = ("euler",)

    euler: Optional[Vec3] = None
    """Orientation of the frame. See Frame orientations. The sequence of axes around which these rotations are applied is determined by the eulerseq attribute of compiler and is the same for the entire model."""


class XYAxes(OrientationBase):
    """The first 3 numbers are the X axis of the frame. The next 3 numbers are the Y axis of the frame, which is automatically made orthogonal to the X axis. The Z axis is then defined as the cross-product of the X and Y axes."""

    type: Literal[OrientationType.XYAXES] = OrientationType.XYAXES
    attributes = ("xyaxes",)

    xyaxes: Optional[Vec6] = None
    """Orientation of the frame. See Frame orientations."""


class ZAxis(OrientationBase):
    """The Z axis of the frame. The compiler finds the minimal rotation that maps the vector (0,0,1) into the vector specified here. This determines the X and Y axes of the frame implicitly. This is useful for geoms with rotational symmetry around the Z axis, as well as lights - which are oriented along the Z axis of their frame."""

    type: Literal[OrientationType.ZAXIS] = OrientationType.ZAXIS
    attributes = ("zaxis",)

    zaxis: Optional[Vec3] = None
    """Orientation of the frame. See Frame orientations."""


Orientation: TypeAlias = Annotated[
    Quat | AxisAngle | Euler | XYAxes | ZAxis,
    Field(discriminator="type"),
]
