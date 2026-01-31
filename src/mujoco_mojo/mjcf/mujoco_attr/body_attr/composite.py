from __future__ import annotations

from typing import Optional, Sequence, Tuple

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.body_attr.composite_attr.geom import CompositeGeom
from mujoco_mojo.mjcf.mujoco_attr.body_attr.composite_attr.joint import CompositeJoint
from mujoco_mojo.mjcf.mujoco_attr.body_attr.composite_attr.site import CompositeSite
from mujoco_mojo.mjcf.mujoco_attr.body_attr.composite_attr.skin import Skin
from mujoco_mojo.mjcf.orientation import Quat
from mujoco_mojo.mjcf.plugin import Plugin
from mujoco_mojo.typing import CompositeInitial, CompositeType, Vec3, VecN

__all__ = ["Composite"]


class Composite(XMLModel):
    """This element is used to construct the kinematic tree via nesting. The element worldbody is used for the top-level body, while the element body is used for all other bodies. The top-level body is a restricted type of body: it cannot have child elements inertial and joint, and also cannot have any attributes. It corresponds to the origin of the world frame, within which the rest of the kinematic tree is defined. Its body name is automatically defined as "world"."""

    tag = "composite"

    attributes = (
        "prefix",
        "type",
        "count",
        "offset",
        "vertex",
        "initial",
        "curve",
        "size",
        "quat",
    )
    children = ("joints", "skin", "geom", "site", "plugins")

    prefix: Optional[str] = None
    """All automatically generated model elements have names indicating the element type and index. For example, the body at coordinates (2, 0) in a 2D grid is named "B2_0" by default. If prefix="C" is specified, the same body is named "CB2_0". The prefix is needed when multiple composite objects are used in the same model, to avoid name conflicts."""

    type: CompositeType
    """This attribute determines the type of composite object. The only supported type is cable.

    The `cable` type creates a 1D chain of bodies connected with ball joints, each having a geom with user-defined type (cylinder, capsule or box). The geometry can either be defined with an array of 3D vertex coordinates vertex or with prescribed functions with the option curve. Currently, only linear and trigonometric functions are supported. For example, an helix can be obtained with curve="cos(s) sin(s) s". The size is set with the option size, resulting in f(s)={size[1]⋅cos(2π⋅size[2]), size[1]⋅sin(2π⋅size[2]),  size[0]⋅s}."""

    count: Tuple[int] | Tuple[int, int] | Tuple[int, int, int]
    """The element count in each dimension of the grid. This can have 1, 2 or 3 numbers, specifying the element count along the X, Y and Z axis of the parent body frame within. Any missing numbers default to 1. If any of these numbers is 1, all subsequent numbers must also be 1, so that the leading dimensions of the grid are used. This means for example that a 1D grid will always extend along the X axis. To achieve a different orientation, rotate the frame of the parent body. Note that some types imply a grid of certain dimensionality, so the requirements for this attribute depend on the specified type."""

    offset: Optional[Vec3] = None
    """It specifies a 3D offset from the center of the parent body to the center of the first body of the cable. The offset is expressed in the local coordinate frame of the parent body."""

    quat: Optional[Quat] = None
    """It specifies a quaternion that rotates the first body frame. The quaternion is expressed in the parent body frame."""

    vertex: Optional[VecN] = None
    """Vertex 3D positions in global coordinates."""

    initial: Optional[CompositeInitial] = None
    """Behavior of the first point. Free: free joint. Ball: ball joint. None: no dof."""

    curve: Optional[Tuple[str, str, str]] = None
    """Functions specifying the vertex positions. Available functions are s, cos(s), and sin(s), where s is the arc length parameter."""

    size: Optional[Tuple[int, int, int]] = None
    """Scaling of the curve functions. size[0] is the scaling of s, size[1] is the radius of cos(s) and sin(s), and size[2] is the speed of the argument (i.e. cos(2*pi*size[2]*s))."""

    joints: Sequence[CompositeJoint] = Field(default_factory=list)
    """Joints assigned to composite."""

    geom: Optional[CompositeGeom] = None
    """Geometry assigned to composite."""

    site: Optional[CompositeSite] = None
    """Site assigned to composite."""

    skin: Optional[Skin] = None
    """Skin assigned to composite."""

    plugins: Sequence[Plugin] = Field(default_factory=list)
    """Plugins assigned to composite."""
