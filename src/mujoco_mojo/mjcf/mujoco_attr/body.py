from __future__ import annotations

from typing import Optional, Sequence

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.body_attr.free_joint import FreeJoint
from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import Geom
from mujoco_mojo.mjcf.mujoco_attr.body_attr.inertial import Inertial
from mujoco_mojo.mjcf.mujoco_attr.body_attr.joint import Joint
from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import Site
from mujoco_mojo.mjcf.orientation import Orientation
from mujoco_mojo.mjcf.plugin import Plugin
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.types import Sleep, VecN

__all__ = ["Body", "WorldBody"]

_body_attr = (
    "name",
    "childclass",
    "pos",
    "orientation",
    "mocap",
    "gravcomp",
    "sleep",
    "user",
)
_body_children = (
    "inertial",
    "joints",
    "freejoints",
    "geoms",
    "sites",
    "cameras",
    "lights",
    "composites",
    "flexcomps",
    "plugins",
    "attaches",
    "frames",
    "bodies",
)


class Body(XMLModel):
    """This element is used to construct the kinematic tree via nesting. The element worldbody is used for the top-level body, while the element body is used for all other bodies. The top-level body is a restricted type of body: it cannot have child elements inertial and joint, and also cannot have any attributes. It corresponds to the origin of the world frame, within which the rest of the kinematic tree is defined. Its body name is automatically defined as "world"."""

    tag = "body"

    attributes = _body_attr
    children = _body_children

    name: Optional[str] = None
    """Name of the body."""

    childclass: Optional[str] = None
    """If this attribute is present, all descendant elements that admit a defaults class will use the class specified here, unless they specify their own class or another body or frame with a childclass attribute is encountered along the chain of nested bodies and frames. Recall Default settings."""

    mocap: Optional[bool] = None
    """If this attribute is "true", the body is labeled as a mocap body. This is allowed only for bodies that are children of the world body and have no joints. Such bodies are fixed from the viewpoint of the dynamics, but nevertheless the forward kinematics set their position and orientation from the fields mjData.mocap_{pos,quat} at each time step. The size of these arrays is adjusted by the compiler so as to match the number of mocap bodies in the model. This mechanism can be used to stream motion capture data into the simulation. Mocap bodies can also be moved via mouse perturbations in the interactive visualizer, even in dynamic simulation mode. This can be useful for creating props with adjustable position and orientation."""

    pos: Optional[Pos] = None
    """The 3D position of the body frame, in the parent coordinate frame. If undefined it defaults to (0,0,0)."""

    orientation: Optional[Orientation] = None
    """See Frame orientations."""

    gravcomp: Optional[float] = None
    """Gravity compensation force, specified as fraction of body weight. This attribute creates an upwards force applied to the body's center of mass, countering the force of gravity. As an example, a value of 1 creates an upward force equal to the body's weight and compensates for gravity exactly. Values greater than 1 will create a net upwards force or buoyancy effect."""

    sleep: Optional[Sleep] = None
    """Sleep policy for the tree under this body. This attribute is only supported by moving bodies which are the root of a kinematic tree. For the default auto, the compiler will set the sleep policy as follows:

    * A tree which is affected by actuators is not allowed to sleep (overridable).
    * Trees which are connected by tendons which have non-zero stiffness and damping are not allowed to sleep (overridable).
    * Trees which are connected by tendons which connect more than two trees are not allowed to sleep (not overridable).
    * flexes are not allowed to sleep (not overridable).
    * All other trees are allowed to sleep (overridable).

    The policies never and allowed constitute user overrides of the automatic compiler policy.

    The init sleep policy can only be specified by the user and means "initialize this tree as asleep". This policy is implemented in mj_resetData and mj_makeData and only applies to the default configuration. If a keyframe changes the configuration of (or assigns nonzero velocity to) a sleeping tree, it will be woken up. This policy is useful for very large models where waiting for the automatic sleeping mechanism to kick in can be expensive. Trees initialized as sleeping can be placed in unstable configurations like deep penetration or in mid-air, but will only move when woken up. Also note that this policy can fail. For example if a tree marked as sleep="init" is in contact with a tree not marked as such (i.e., they are in the same island) then it is impossible to put the tree to sleep; such models will lead to a compilation error.

    See implementation notes for more details."""

    user: Optional[VecN] = None
    """See User parameters. Has length of `nbody_user`"""

    inertial: Optional[Inertial] = None
    joints: Sequence[Joint] = Field(default_factory=list)
    freejoints: Optional[Sequence[FreeJoint]] = Field(default_factory=list)
    geoms: Sequence[Geom] = Field(default_factory=list)
    sites: Optional[Sequence[Site]] = Field(default_factory=list)
    cameras: Optional[Sequence[float]] = Field(default_factory=list)  # TODO
    lights: Optional[Sequence[float]] = Field(default_factory=list)  # TODO
    composites: Optional[Sequence[float]] = Field(default_factory=list)  # TODO
    flexcomps: Optional[Sequence[float]] = Field(default_factory=list)  # TODO
    plugins: Optional[Sequence[Plugin]] = Field(default_factory=list)  # TODO
    attaches: Optional[Sequence[float]] = Field(default_factory=list)  # TODO
    frames: Optional[Sequence[float]] = Field(default_factory=list)  # TODO

    bodies: Sequence[Body] = Field(default_factory=list)


_temp_list = list(_body_children)
for not_in in ("inertial", "joints"):
    _temp_list.remove(not_in)
_world_body_children = tuple(_temp_list)


class WorldBody(Body):
    """This element is used to construct the kinematic tree via nesting. The element worldbody is used for the top-level body, while the element body is used for all other bodies. The top-level body is a restricted type of body: it cannot have child elements inertial and joint, and also cannot have any attributes. It corresponds to the origin of the world frame, within which the rest of the kinematic tree is defined. Its body name is automatically defined as "world"."""

    tag = "worldbody"

    attributes = ()
    children = _world_body_children
