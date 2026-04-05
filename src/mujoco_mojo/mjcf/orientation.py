from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal, Self

import numpy as np
from pydantic import Field
from scipy.spatial.transform import Rotation as R

from mujoco_mojo.mjcf.constants import DEFAULT_ANGLE, DEFAULT_EULERSEQ
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import Angle, EulerSeq, Vec3, Vec4, Vec6
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from .pose import Pose, PoseAxisAngle, PoseEuler, PoseQuat, PoseXYAxes, PoseZAxis
    from .position import Pos

logger = get_logger(__name__)

__all__ = [
    "AxisAngle",
    "Euler",
    "Orientation",
    "OrientationType",
    "Quat",
    "XYAxes",
    "ZAxis",
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


class OrientationBase(XMLModel, ABC):
    """
    Defines the base model for orientations.

    Several model elements have right-handed spatial frames associated with them. These are all the elements defined in the kinematic tree except for joints. A spatial frame is defined by its position and orientation. Specifying 3D positions is straightforward, but specifying 3D orientations can be challenging. This is why MJCF provides several alternative mechanisms. No matter which mechanism the user chooses, the frame orientation is always converted internally to a unit quaternion. Recall that a 3D rotation by angle aa around axis given by the unit vector (x,y,z) corresponds to the quaternion ((cos(a/2),sin(a/2)⋅(x,y,z)). Also recall that every 3D orientation can be uniquely specified by a single 3D rotation by some angle around some axis.

    All MJCF elements that have spatial frames allow the five attributes listed below. The frame orientation is specified using at most one of these attributes. The quat attribute has a default value corresponding to the null rotation, while the others are initialized in the special undefined state. Thus if none of these attributes are specified by the user, the frame is not rotated.
    """

    tag = ""

    # name of the field to convert during XML generation
    _rotation_attr: ClassVar[str] = ""

    def as_quat(self) -> Quat:
        # q = [x, y, z, w] from scipy -> [w, x, y, z] for MuJoCo
        q = self.to_rotation().as_quat()
        return Quat(quat=np.array([q[3], q[0], q[1], q[2]]))

    def as_axisangle(self, angle_type: Angle = DEFAULT_ANGLE) -> AxisAngle:
        """Casts any orientation to an AxisAngle object."""
        return AxisAngle.from_matrix(self.as_matrix()).with_angle(angle_type)

    def as_euler(
        self, seq: EulerSeq = DEFAULT_EULERSEQ, angle_type: Angle = DEFAULT_ANGLE
    ) -> Euler:
        """Casts any orientation to an Euler object."""
        return (
            Euler.from_matrix(self.as_matrix())
            .with_eulerseq(seq)
            .with_angle(angle_type)
        )

    def as_xyaxes(self) -> XYAxes:
        """Casts any orientation to an XYAxes object."""
        return XYAxes.from_matrix(self.as_matrix())

    def as_zaxis(self) -> ZAxis:
        """Casts any orientation to a ZAxis object."""
        return ZAxis.from_matrix(self.as_matrix())

    def as_matrix(self):
        """Returns this orientation as a rotation matrix."""
        return self.to_rotation().as_matrix()

    def apply(self, vec: Vec3) -> np.ndarray:
        """Rotates a vector by this orientation."""
        return self.to_rotation().apply(np.asarray(vec))

    def __mul__(self, other: OrientationBase) -> Quat:
        """Composes two rotations: self * other and returns a Quat."""
        if not isinstance(other, OrientationBase):
            msg = f"Invalid type {type(other)} for multiplication with orientation"
            logger.error(msg)
            raise TypeError(msg)

        res_mat = self.as_matrix() @ other.as_matrix()
        return Quat.from_matrix(res_mat)

    def inv(self) -> Self:
        """Returns the inverse orientation."""
        return type(self).from_matrix(self.as_matrix().T)

    def angle_between(
        self, other: OrientationBase, angle: Angle = Angle.DEGREE
    ) -> float:
        """The absolute shortest angular distance."""
        # Geodesic distance: ||log(R1^T @ R2)||
        diff = self.inv() * other
        as_rad = float(np.linalg.norm(diff.to_rotation().as_rotvec()))
        as_rad = max(0.0, as_rad)
        return as_rad if angle == Angle.RADIAN else np.degrees(as_rad)

    @classmethod
    def look_at(
        cls,
        target: Vec3,
        eye: Vec3 = np.array([0, 0, 0]),
        up: Vec3 = np.array([0, 0, 1]),
        negative_z: bool = True,
    ) -> Self:
        """
        Creates an orientation that points the Z-axis toward/away from a target.

        Args:
            target (Vec3): Where the vector should point to.
            eye (Vec3, optional): From where the vector should point. Defaults to np.array([0, 0, 0]).
            up (Vec3, optional): Up axis for the vector. Defaults to np.array([0, 0, 1]).
            negative_z (bool, optional): Whether the z axis should point its plus or minus axis at the target (Cameras and Lights use minus, Geom uses plus). Defaults to True.

        Returns:
            Self: New instance of Orientation.

        """
        target = np.asarray(target)
        eye = np.asarray(eye)

        forward = target - eye
        forward /= np.linalg.norm(forward)

        if negative_z:
            forward = -forward

        # compute right and up axes to complete orthonormal basis
        right = np.cross(np.asarray(up), forward)
        right /= np.linalg.norm(right)
        actual_up = np.cross(forward, right)

        # matrix is [X, Y, Z] columns
        mat = np.column_stack((right, actual_up, forward))
        return cls.from_matrix(mat)

    @abstractmethod
    def to_rotation(self) -> R:
        """Returns the orientation as a `scipy.spatial.transform` `Rotation` object."""
        pass

    @abstractmethod
    def get_xml_value(
        self, target_degrees: Angle, target_eulerseq: EulerSeq
    ) -> np.ndarray:
        """Must return the value (converted to target units) for XML output."""
        pass

    @abstractmethod
    def as_pose(self, pos: Vec3 | Pos) -> Pose:
        """Returns the orientation with its equal Pose type."""
        pass

    @classmethod
    @abstractmethod
    def from_matrix(cls, matrix: np.ndarray) -> Self:
        """Reconstructs the orientation object from a 3x3 matrix."""
        pass


class Quat(OrientationBase):
    """If the quaternion is known, this is the preferred was to specify the frame orientation because it does not involve conversions. Instead it is normalized to unit length and copied into mjModel during compilation. When a model is saved as MJCF, all frame orientations are expressed as quaternions using this attribute."""

    type: Literal[OrientationType.QUAT] = OrientationType.QUAT

    attributes = ("quat",)
    _rotation_attr = "quat"

    quat: Vec4 = np.array((1, 0, 0, 0))
    """Orientation of the frame. See Frame orientations. Defined as (w, x, y, z) quaternion order (the same as MuJoCo convention)."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Quat):
            return NotImplemented
        return np.array_equal(np.asarray(self.quat), np.asarray(other.quat))

    @classmethod
    def from_matrix(cls, matrix: np.ndarray) -> Self:
        """Reconstructs the Quat object from a 3x3 matrix."""
        rot = R.from_matrix(matrix)
        q = rot.as_quat()

        return cls(quat=np.array([q[3], q[0], q[1], q[2]]))

    def to_rotation(self) -> R:
        # determine the subtype to make a scipy Rotation object
        quat = np.asarray(self.quat)
        x, y, z, w = quat[1], quat[2], quat[3], quat[0]
        return R.from_quat([x, y, z, w])

    def get_xml_value(
        self, target_degrees: Angle, target_eulerseq: EulerSeq
    ) -> np.ndarray:
        # Quaternions don't care about degrees or eulerseq
        return np.asarray(self.quat)

    def as_pose(self, pos: Vec3 | Pos) -> PoseQuat:
        from mujoco_mojo.mjcf.pose import PoseQuat

        return PoseQuat(pos=np.asarray(pos), **self.model_dump())


class AxisAngle(OrientationBase):
    """These are the quantities (x,y,z,a) mentioned above. The last number is the angle of rotation, in degrees or radians as specified by the angle attribute of compiler. The first three numbers determine a 3D vector which is the rotation axis. This vector is normalized to unit length during compilation, so the user can specify a vector of any non-zero length. Keep in mind that the rotation is right-handed; if the direction of the vector (x,y,z) is reversed this will result in the opposite rotation. Changing the sign of aa can also be used to specify the opposite rotation."""

    type: Literal[OrientationType.AXISANGLE] = OrientationType.AXISANGLE
    attributes = ("axisangle",)
    _rotation_attr = "axisangle"

    axisangle: Vec4 = np.array((1, 0, 0, 0))
    """Orientation of the frame. See Frame orientations."""

    angle: Angle = DEFAULT_ANGLE
    """Whether or not the values expressed here are in degrees or not. This should match the setting for your MuJoCo compiler setting."""

    @property
    def is_degrees(self) -> bool:
        return self.angle == Angle.DEGREE

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AxisAngle):
            return NotImplemented
        return np.array_equal(np.asarray(self.axisangle), np.asarray(other.axisangle))

    def to_rotation(self) -> R:
        axisangle = np.asarray(self.axisangle)
        axis = axisangle[:3]
        angle = axisangle[3]

        if self.is_degrees:
            angle = np.radians(angle)

        # Normalize the axis vector
        norm = np.linalg.norm(axis)
        if norm == 0:
            msg = "Axis vector cannot be zero for AxisAngle orientation."
            logger.error(msg)
            raise ValueError(msg)
        axis = axis / norm

        # Rotation vector = axis * angle (angle should be in radians)
        # If angle is in degrees, convert: np.radians(angle)
        rotvec = axis * angle
        return R.from_rotvec(rotvec)

    def get_xml_value(
        self, target_degrees: Angle, target_eulerseq: EulerSeq
    ) -> np.ndarray:
        val = np.array(self.axisangle, dtype=float)
        if self.angle != target_degrees:
            # re-calculate only the 4th element (the angle)
            val[3] = np.degrees(val[3]) if target_degrees else np.radians(val[3])
        return val

    def with_angle(self, angle: Angle) -> Self:
        """Expresses the AxisAngle in either radians or degrees."""
        if angle == self.angle:
            return self

        new_axisangle = np.asarray(self.axisangle)
        new_axisangle[3] = (
            np.degrees(new_axisangle[3])
            if angle == Angle.DEGREE
            else np.radians(new_axisangle[3])
        )

        return self.model_copy(update={"axisangle": new_axisangle, "angle": angle})

    def with_axis(self, axis: Vec3) -> Self:
        """Returns a new AxisAngle with a new axis but the same angle."""
        axis = np.asarray(axis)
        axis = axis / np.linalg.norm(axis)
        new_val = np.array([*axis, np.asarray(self.axisangle)[3]])
        return self.model_copy(update={"axisangle": new_val})

    def with_angle_val(self, angle: float) -> Self:
        """Returns a new AxisAngle with a new angle value but the same axis."""
        new_val = np.array([*np.asarray(self.axisangle)[:3], angle])
        return self.model_copy(update={"axisangle": new_val})

    def as_pose(self, pos: Vec3 | Pos) -> PoseAxisAngle:
        from mujoco_mojo.mjcf.pose import PoseAxisAngle

        return PoseAxisAngle(pos=np.asarray(pos), **self.model_dump())

    @classmethod
    def from_matrix(cls, matrix: np.ndarray) -> Self:
        """Reconstructs the AxisAngle from a 3x3 matrix."""
        rot = R.from_matrix(matrix)
        rotvec = rot.as_rotvec()
        angle_rad = np.linalg.norm(rotvec)

        # handle zero-rotation case
        if angle_rad < 1e-10:
            return cls(axisangle=np.array([1.0, 0.0, 0.0, 0.0]), angle=DEFAULT_ANGLE)

        axis = rotvec / angle_rad
        # convert to degrees if the class default is Angle.DEGREE
        is_deg = DEFAULT_ANGLE == Angle.DEGREE
        angle_val = np.degrees(angle_rad) if is_deg else angle_rad

        return cls(axisangle=np.array([*axis, angle_val]), angle=DEFAULT_ANGLE)


class Euler(OrientationBase):
    """Rotation angles around three coordinate axes. The sequence of axes around which these rotations are applied is determined by the eulerseq attribute of compiler and is the same for the entire model."""

    type: Literal[OrientationType.EULER] = OrientationType.EULER
    attributes = ("euler",)
    _rotation_attr = "euler"

    euler: Vec3 = np.array((0, 0, 0))
    """Orientation of the frame. See Frame orientations. The sequence of axes around which these rotations are applied is determined by the eulerseq attribute of compiler and is the same for the entire model."""

    eulerseq: EulerSeq = DEFAULT_EULERSEQ
    """Euler seqence this orientation object uses."""

    angle: Angle = DEFAULT_ANGLE
    """Whether or not the values expressed here are in degrees or not. This should match the setting for your MuJoCo compiler setting."""

    @property
    def is_degrees(self) -> bool:
        return self.angle == Angle.DEGREE

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Euler):
            return NotImplemented
        return np.array_equal(np.asarray(self.euler), np.asarray(other.euler))

    def to_rotation(self) -> R:
        return R.from_euler(
            self.eulerseq, np.asarray(self.euler), degrees=self.is_degrees
        )

    def get_xml_value(
        self, target_degrees: Angle, target_eulerseq: EulerSeq
    ) -> np.ndarray:
        # if everything is already a match return early
        if self.angle == target_degrees and self.eulerseq == target_eulerseq:
            return np.asarray(self.euler)

        # convert
        return self.to_rotation().as_euler(
            target_eulerseq.value, degrees=target_degrees == Angle.DEGREE
        )

    def as_pose(self, pos: Vec3 | Pos) -> PoseEuler:
        from mujoco_mojo.mjcf.pose import PoseEuler

        return PoseEuler(pos=np.asarray(pos), **self.model_dump())

    def with_eulerseq(self, seq: EulerSeq) -> Self:
        """
        Returns a new instance with a different Euler sequence, maintaining the same physical rotation.
        """
        if seq == self.eulerseq:
            return self

        rot = self.to_rotation()
        new_euler = rot.as_euler(seq.value, degrees=self.is_degrees)
        return self.model_copy(update={"euler": new_euler, "eulerseq": seq})

    def with_angle(self, angle: Angle) -> Self:
        """Expresses the AxisAngle in either radians or degrees."""
        if angle == self.angle:
            return self

        new_euler = (
            np.degrees(np.asarray(self.euler))
            if angle == Angle.DEGREE
            else np.radians(np.asarray(self.euler))
        )

        return self.model_copy(update={"euler": new_euler, "angle": angle})

    @classmethod
    def from_matrix(cls, matrix: np.ndarray) -> Self:
        """Reconstructs Euler angles from a 3x3 matrix."""
        rot = R.from_matrix(matrix)
        is_deg = DEFAULT_ANGLE == Angle.DEGREE

        # as_euler returns a NumPy array of 3 angles
        angles = rot.as_euler(DEFAULT_EULERSEQ.value, degrees=is_deg)

        return cls(euler=angles, eulerseq=DEFAULT_EULERSEQ, angle=DEFAULT_ANGLE)


class XYAxes(OrientationBase):
    """The first 3 numbers are the X axis of the frame. The next 3 numbers are the Y axis of the frame, which is automatically made orthogonal to the X axis. The Z axis is then defined as the cross-product of the X and Y axes."""

    type: Literal[OrientationType.XYAXES] = OrientationType.XYAXES
    attributes = ("xyaxes",)
    _rotation_attr = "xyaxes"

    xyaxes: Vec6 = np.array((1, 0, 0, 0, 1, 0))
    """Orientation of the frame. See Frame orientations."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, XYAxes):
            return NotImplemented
        return np.array_equal(np.asarray(self.xyaxes), np.asarray(other.xyaxes))

    def to_rotation(self) -> R:
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

    def get_xml_value(
        self, target_degrees: Angle, target_eulerseq: EulerSeq | str
    ) -> np.ndarray:
        # XYAxes don't care about degrees or eulerseq
        return np.asarray(self.xyaxes)

    def as_pose(self, pos: Vec3 | Pos) -> PoseXYAxes:
        from mujoco_mojo.mjcf.pose import PoseXYAxes

        return PoseXYAxes(pos=np.asarray(pos), **self.model_dump())

    @classmethod
    def from_matrix(cls, matrix: np.ndarray) -> Self:
        """Extracts X and Y axes directly from the matrix columns."""
        x_axis = matrix[:, 0]
        y_axis = matrix[:, 1]
        return cls(xyaxes=np.concatenate([x_axis, y_axis]))


class ZAxis(OrientationBase):
    """The Z axis of the frame. The compiler finds the minimal rotation that maps the vector (0,0,1) into the vector specified here. This determines the X and Y axes of the frame implicitly. This is useful for geoms with rotational symmetry around the Z axis, as well as lights - which are oriented along the Z axis of their frame."""

    type: Literal[OrientationType.ZAXIS] = OrientationType.ZAXIS
    attributes = ("zaxis",)
    _rotation_attr = "zaxis"

    zaxis: Vec3 = np.array((0, 0, 1))
    """Orientation of the frame. See Frame orientations."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ZAxis):
            return NotImplemented
        return np.array_equal(np.asarray(self.zaxis), np.asarray(other.zaxis))

    def to_rotation(self) -> R:
        z = np.asarray(self.zaxis)
        z = z / np.linalg.norm(z)

        # Choose arbitrary x-axis that's not colinear with z
        if np.allclose(z, [0, 0, 1]):
            # Already aligned, identity rotation
            return R.identity()
        # pick temp x along world x-axis
        tmp = np.array([1.0, 0.0, 0.0])
        x = np.cross(tmp, z)
        x /= np.linalg.norm(x)
        y = np.cross(z, x)

        rotmat = np.column_stack((x, y, z))
        return R.from_matrix(rotmat)

    def get_xml_value(
        self, target_degrees: Angle, target_eulerseq: EulerSeq | str
    ) -> np.ndarray:
        # ZAxis don't care about degrees or eulerseq
        return np.asarray(self.zaxis)

    def as_pose(self, pos: Vec3 | Pos) -> PoseZAxis:
        from mujoco_mojo.mjcf.pose import PoseZAxis

        return PoseZAxis(pos=np.asarray(pos), **self.model_dump())

    @classmethod
    def from_matrix(cls, matrix: np.ndarray) -> Self:
        """Extracts the Z axis from the third column of the matrix."""
        z_axis = matrix[:, 2]
        return cls(zaxis=z_axis)


Orientation = Annotated[
    Quat | AxisAngle | Euler | XYAxes | ZAxis,
    Field(discriminator="type"),
]
"""Discriminated union for type hinting the various types of Orientations."""
