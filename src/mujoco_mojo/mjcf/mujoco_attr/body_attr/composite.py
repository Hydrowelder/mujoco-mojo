from __future__ import annotations

import numpy as np
from pydantic import Field

from mujoco_mojo.mjcf.mujoco_attr.body_attr.composite_attr.geom import AnyCompositeGeom
from mujoco_mojo.mjcf.mujoco_attr.body_attr.composite_attr.joint import CompositeJoint
from mujoco_mojo.mjcf.mujoco_attr.body_attr.composite_attr.site import CompositeSite
from mujoco_mojo.mjcf.mujoco_attr.body_attr.composite_attr.skin import CompositeSkin
from mujoco_mojo.mjcf.orientation import Quat
from mujoco_mojo.mjcf.plugin import Plugin
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import CompositeInitial, CompositeType, Vec3, VecN
from mujoco_mojo.utils.utils import is_empty_list

__all__ = ["Composite"]


class Composite(XMLModel):
    """This is not a model element, but rather a macro which expands into multiple model elements representing a composite object. These elements are bodies (with their own joints and geoms) that become children of the parent body containing the macro. The macro expansion is done by the model compiler. If the resulting model is then saved, the macro will be replaced with the actual model elements. The defaults mechanism used in the rest of MJCF does not apply here, even if the parent body has a childclass attribute defined. Instead there are internal defaults adjusted automatically for each composite object type. See Composite objects in the modeling guide for more detailed explanation. Note that several legacy composite types have been replaced by replicate (for repeated objects) and flexcomp (for soft objects). Therefore, the only supported composite type is now cable, which produces an inextensible chain of bodies connected with ball joints."""

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

    prefix: str | None = None
    """All automatically generated model elements have names indicating the element type and index. For example, the body at coordinates (2, 0) in a 2D grid is named "B2_0" by default. If prefix="C" is specified, the same body is named "CB2_0". The prefix is needed when multiple composite objects are used in the same model, to avoid name conflicts."""

    type: CompositeType = CompositeType.CABLE
    """This attribute determines the type of composite object. The only supported type is cable.

    The `cable` type creates a 1D chain of bodies connected with ball joints, each having a geom with user-defined type (cylinder, capsule or box). The geometry can either be defined with an array of 3D vertex coordinates vertex or with prescribed functions with the option curve. Currently, only linear and trigonometric functions are supported. For example, an helix can be obtained with curve="cos(s) sin(s) s". The size is set with the option size, resulting in f(s)={size[1]⋅cos(2π⋅size[2]), size[1]⋅sin(2π⋅size[2]), size[0]⋅s}."""

    count: tuple[int] | tuple[int, int] | tuple[int, int, int]
    """The element count in each dimension of the grid. This can have 1, 2 or 3 numbers, specifying the element count along the X, Y and Z axis of the parent body frame within. Any missing numbers default to 1. If any of these numbers is 1, all subsequent numbers must also be 1, so that the leading dimensions of the grid are used. This means for example that a 1D grid will always extend along the X axis. To achieve a different orientation, rotate the frame of the parent body. Note that some types imply a grid of certain dimensionality, so the requirements for this attribute depend on the specified type."""

    offset: Vec3 = np.array((0, 0, 0))
    """It specifies a 3D offset from the center of the parent body to the center of the first body of the cable. The offset is expressed in the local coordinate frame of the parent body."""

    quat: Quat = Quat(quat=np.array((1, 0, 0, 0)))
    """It specifies a quaternion that rotates the first body frame. The quaternion is expressed in the parent body frame."""

    vertex: VecN | None = None
    """Vertex 3D positions in global coordinates."""

    initial: CompositeInitial = CompositeInitial.NONE
    """Behavior of the first point. Free: free joint. Ball: ball joint. None: no dof."""

    curve: tuple[str, str, str] | None = None
    """Functions specifying the vertex positions. Available functions are s, cos(s), and sin(s), where s is the arc length parameter."""

    size: tuple[int, int, int] | None = None
    """Scaling of the curve functions. size[0] is the scaling of s, size[1] is the radius of cos(s) and sin(s), and size[2] is the speed of the argument (i.e. cos(2*pi*size[2]*s))."""

    joints: list[CompositeJoint] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Joints assigned to composite."""

    geom: AnyCompositeGeom | None = None
    """Geometry assigned to composite."""

    site: CompositeSite | None = None
    """Site assigned to composite."""

    skin: CompositeSkin | None = None
    """Skin assigned to composite."""

    plugins: list[Plugin] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Plugins assigned to composite."""
