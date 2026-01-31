from __future__ import annotations

from enum import StrEnum, auto
from typing import Annotated, Literal, Optional

import numpy as np
from pydantic import Field
from scipy.spatial.transform import Rotation as R

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import EulerSeq, Vec3, Vec4, Vec6

__all__ = [
    "Orientation",
    "OrientationType",
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

    def as_quat(self, eulerseq: Optional[EulerSeq | str] = None) -> Quat:
        if isinstance(self, Euler) and self.euler is not None and eulerseq is None:
            raise ValueError(
                "Unable to return for Euler without specifying the euler angle order (xyz, ZXZ, etc.)"
            )
        # returns [w, x, y, z] for MuJoCo
        rot = self._to_rotation(eulerseq)
        q = rot.as_quat()  # scipy returns [x, y, z, w]
        return Quat(quat=np.asarray([q[3], q[0], q[1], q[2]]))

    def as_matrix(self, eulerseq: Optional[EulerSeq | str] = None):
        if isinstance(self, Euler) and self.euler is not None and eulerseq is None:
            raise ValueError(
                "Unable to return for Euler without specifying the euler angle order (xyz, ZXZ, etc.)"
            )
        return self._to_rotation(eulerseq).as_matrix()

    def _to_rotation(self, eulerseq: Optional[EulerSeq | str] = None) -> R:
        # determine the subtype to make a scipy Rotation object
        if isinstance(self, Quat) and self.quat is not None:
            quat = np.asarray(self.quat)
            x, y, z, w = quat[1], quat[2], quat[3], quat[0]
            return R.from_quat([x, y, z, w])
        elif isinstance(self, Euler) and self.euler is not None:
            if eulerseq is None:
                raise ValueError(
                    "Unable to return for Euler without specifying the euler angle order (xyz, ZXZ, etc.)"
                )
            return R.from_euler(eulerseq, np.asarray(self.euler))
        # WARNING: I vibecoded the following
        elif isinstance(self, AxisAngle) and self.axisangle is not None:
            axisangle = np.asarray(self.axisangle)
            axis = axisangle[:3]
            angle = axisangle[3]

            # Normalize the axis vector
            norm = np.linalg.norm(axis)
            if norm == 0:
                raise ValueError(
                    "Axis vector cannot be zero for AxisAngle orientation."
                )
            axis = axis / norm

            # Rotation vector = axis * angle (angle should be in radians)
            # If angle is in degrees, convert: np.radians(angle)
            rotvec = axis * angle
            return R.from_rotvec(rotvec)
        elif isinstance(self, XYAxes) and self.xyaxes is not None:
            vecs = np.asarray(self.xyaxes)
            x = vecs[:3]
            y = vecs[3:]

            # Orthonormalize Y w.r.t X
            x = x / np.linalg.norm(x)
            y = y - np.dot(y, x) * x
            y = y / np.linalg.norm(y)

            z = np.cross(x, y)

            # Build rotation matrix with columns as axes
            rotmat = np.column_stack((x, y, z)).astype(float)
            return R.from_matrix(rotmat)
        elif isinstance(self, ZAxis) and self.zaxis is not None:
            z = np.asarray(self.zaxis)
            z = z / np.linalg.norm(z)

            # Choose arbitrary x-axis that's not colinear with z
            if np.allclose(z, [0, 0, 1]):
                # Already aligned, identity rotation
                return R.identity()
            else:
                # pick temp x along world x-axis
                tmp = np.array([1.0, 0.0, 0.0])
                x = np.cross(tmp, z)
                x /= np.linalg.norm(x)
                y = np.cross(z, x)

                rotmat = np.column_stack((x, y, z))
                return R.from_matrix(rotmat)

        raise NotImplementedError(
            f"Rotation matrix transforms has not yet been developed for type ({type(self)})"
        )


class Quat(OrientationBase):
    """If the quaternion is known, this is the preferred was to specify the frame orientation because it does not involve conversions. Instead it is normalized to unit length and copied into mjModel during compilation. When a model is saved as MJCF, all frame orientations are expressed as quaternions using this attribute."""

    type: Literal[OrientationType.QUAT] = OrientationType.QUAT

    attributes = ("quat",)

    quat: Vec4 = np.array((1, 0, 0, 0))
    """Orientation of the frame. See Frame orientations. Defined as (w, x, y, z) quaternion order (the same as MuJoCo convention)."""


class AxisAngle(OrientationBase):
    """These are the quantities (x,y,z,a) mentioned above. The last number is the angle of rotation, in degrees or radians as specified by the angle attribute of compiler. The first three numbers determine a 3D vector which is the rotation axis. This vector is normalized to unit length during compilation, so the user can specify a vector of any non-zero length. Keep in mind that the rotation is right-handed; if the direction of the vector (x,y,z) is reversed this will result in the opposite rotation. Changing the sign of aa can also be used to specify the opposite rotation."""

    type: Literal[OrientationType.AXISANGLE] = OrientationType.AXISANGLE
    attributes = ("axisangle",)

    axisangle: Vec4 = np.array((1, 0, 0, 0))
    """Orientation of the frame. See Frame orientations."""


class Euler(OrientationBase):
    """Rotation angles around three coordinate axes. The sequence of axes around which these rotations are applied is determined by the eulerseq attribute of compiler and is the same for the entire model."""

    type: Literal[OrientationType.EULER] = OrientationType.EULER
    attributes = ("euler",)

    euler: Vec3 = np.array((0, 0, 0))
    """Orientation of the frame. See Frame orientations. The sequence of axes around which these rotations are applied is determined by the eulerseq attribute of compiler and is the same for the entire model."""


class XYAxes(OrientationBase):
    """The first 3 numbers are the X axis of the frame. The next 3 numbers are the Y axis of the frame, which is automatically made orthogonal to the X axis. The Z axis is then defined as the cross-product of the X and Y axes."""

    type: Literal[OrientationType.XYAXES] = OrientationType.XYAXES
    attributes = ("xyaxes",)

    xyaxes: Vec6 = np.array((1, 0, 0, 0, 1, 0))
    """Orientation of the frame. See Frame orientations."""


class ZAxis(OrientationBase):
    """The Z axis of the frame. The compiler finds the minimal rotation that maps the vector (0,0,1) into the vector specified here. This determines the X and Y axes of the frame implicitly. This is useful for geoms with rotational symmetry around the Z axis, as well as lights - which are oriented along the Z axis of their frame."""

    type: Literal[OrientationType.ZAXIS] = OrientationType.ZAXIS
    attributes = ("zaxis",)

    zaxis: Vec3 = np.array((0, 0, 1))
    """Orientation of the frame. See Frame orientations."""


Orientation = Annotated[
    Quat | AxisAngle | Euler | XYAxes | ZAxis, Field(discriminator="type")
]
"""Discriminated union for type hinting the various types of Orientations."""
