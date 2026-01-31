from __future__ import annotations

from typing import Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.types import (
    ActuatorFrcLimited,
    JointType,
    Limited,
    Vec2,
    Vec3,
    Vec5,
    VecN,
)

__all__ = ["Joint"]


class Joint(XMLModel):
    """This element creates a joint. As explained in Kinematic tree, a joint creates motion degrees of freedom between the body where it is defined and the body's parent. If multiple joints are defined in the same body, the corresponding spatial transformations (of the body frame relative to the parent frame) are applied in order. If no joints are defined, the body is welded to its parent. Joints cannot be defined in the world body. At runtime the positions and orientations of all joints defined in the model are stored in the vector mjData.qpos, in the order in which the appear in the kinematic tree. The linear and angular velocities are stored in the vector mjData.qvel. These two vectors have different dimensionality when free or ball joints are used, because such joints represent rotations as unit quaternions."""

    tag = "joint"

    attributes = ()

    name: Optional[str] = None
    """Name of the joint."""

    class_: Optional[str] = None
    """Defaults class for setting unspecified attributes."""

    type: Optional[JointType] = None
    """Type of the joint. The keywords have the following meaning: The free type creates a free "joint" with three translational degrees of freedom followed by three rotational degrees of freedom. In other words it makes the body floating. The rotation is represented as a unit quaternion. This joint type is only allowed in bodies that are children of the world body. No other joints can be defined in the body if a free joint is defined. Unlike the remaining joint types, free joints do not have a position within the body frame. Instead the joint position is assumed to coincide with the center of the body frame. Thus at runtime the position and orientation data of the free joint correspond to the global position and orientation of the body frame. Free joints cannot have limits.

    The ball type creates a ball joint with three rotational degrees of freedom. The rotation is represented as a unit quaternion. The quaternion (1,0,0,0) corresponds to the initial configuration in which the model is defined. Any other quaternion is interpreted as a 3D rotation relative to this initial configuration. The rotation is around the point defined by the pos attribute. If a body has a ball joint, it cannot have other rotational joints (ball or hinge). Combining ball joints with slide joints in the same body is allowed.

    The slide type creates a sliding or prismatic joint with one translational degree of freedom. Such joints are defined by a position and a sliding direction. For simulation purposes only the direction is needed; the joint position is used for rendering purposes.

    The hinge type creates a hinge joint with one rotational degree of freedom. The rotation takes place around a specified axis through a specified position. This is the most common type of joint and is therefore the default. Most models contain only hinge and free joints."""

    group: Optional[int] = None
    """Integer group to which the joint belongs. This attribute can be used for custom tags. It is also used by the visualizer to enable and disable the rendering of entire groups of joints."""

    pos: Optional[Pos] = None
    """Position of the joint, specified in the frame of the body where the joint is defined. For free joints this attribute is ignored."""

    axis: Optional[Vec3] = None
    """This attribute specifies the axis of rotation for hinge joints and the direction of translation for slide joints. It is ignored for free and ball joints. The vector specified here is automatically normalized to unit length as long as its length is greater than 10E-14; otherwise a compile error is generated."""

    springdamper: Optional[Vec2] = None
    """When both numbers are positive, the compiler will override any stiffness and damping values specified with the attributes below, and will instead set them automatically so that the resulting mass-spring-damper for this joint has the desired time constant (first value) and damping ratio (second value). This is done by taking into account the joint inertia in the model reference configuration. Note that the format is the same as the solref parameter of the constraint solver."""

    solreflimit: Optional[Vec2] = None
    """Constraint solver parameters for simulating joint limits. See Solver parameters."""

    solimplimit: Optional[Vec5] = None
    """Constraint solver parameters for simulating joint limits. See Solver parameters."""

    solreffriction: Optional[Vec2] = None
    """Constraint solver parameters for simulating dry friction. See Solver parameters."""

    solimpfriction: Optional[Vec5] = None
    """Constraint solver parameters for simulating dry friction. See Solver parameters."""

    stiffness: Optional[float] = None
    """Joint stiffness. If this value is positive, a spring will be created with equilibrium position given by springref below. The spring force is computed along with the other passive forces."""

    range: Optional[Vec2] = None
    """The joint limits. Limits can be imposed on all joint types except for free joints. For hinge and ball joints, the range is specified in degrees or radians depending on the angle attribute of compiler. For ball joints, the limit is imposed on the angle of rotation (relative to the reference configuration) regardless of the axis of rotation. Only the second range parameter is used for ball joints; the first range parameter should be set to 0. See the Limit section in the Computation chapter for more information.
    Setting this attribute without specifying limited is an error if autolimits is "false" in compiler."""

    limited: Optional[Limited] = None
    """This attribute specifies if the joint has limits. It interacts with the range attribute. If this attribute is "false", joint limits are disabled. If this attribute is "true", joint limits are enabled. If this attribute is "auto", and autolimits is set in compiler, joint limits will be enabled if range is defined."""

    actuatorfrcrange: Optional[Vec2] = None
    """Range for clamping total actuator forces acting on this joint. See Force limits for details. It is available only for scalar joints (hinge and slider) and ignored for ball and free joints.

    The compiler expects the first value to be smaller than the second value. Setting this attribute without specifying actuatorfrclimited is an error if compiler-autolimits is "false"."""

    actuatorfrclimited: Optional[ActuatorFrcLimited] = None
    """This attribute specifies whether actuator forces acting on the joint should be clamped. See Force limits for details. It is available only for scalar joints (hinge and slider) and ignored for ball and free joints.

    This attribute interacts with the actuatorfrcrange attribute. If this attribute is "false", actuator force clamping is disabled. If it is "true", actuator force clamping is enabled. If this attribute is "auto", and autolimits is set in compiler, actuator force clamping will be enabled if actuatorfrcrange is defined."""

    actuatorgravcomp: Optional[bool] = None
    """If this flag is enabled, gravity compensation applied to this joint is added to actuator forces (mjData.qfrc_actuator) rather than passive forces (mjData.qfrc_passive). Notionally, this means that gravity compensation is the result of a control system rather than natural buoyancy. In practice, enabling this flag is useful when joint-level actuator force clamping is used. In this case, the total actuation force applied on a joint, including gravity compensation, is guaranteed to not exceed the specified limits. See Force limits and actuatorfrcrange for more details on this type of force limit."""

    margin: Optional[float] = None
    """The distance threshold below which limits become active. Recall that the Constraint solver normally generates forces as soon as a constraint becomes active, even if the margin parameter makes that happen at a distance. This attribute together with solreflimit and solimplimit can be used to model a soft joint limit."""

    ref: Optional[float] = None
    """The reference position or angle of the joint. This attribute is only used for slide and hinge joints. It defines the joint value corresponding to the initial model configuration. Note that the initial configuration itself is unmodified, only the value of the joint at this configuration. The amount of spatial transformation that the joint applies at runtime equals the current joint value stored in mjData.qpos minus this reference value stored in mjModel.qpos0. The meaning of these vectors is discussed in the Kinematic tree section in the Overview chapter."""

    springref: Optional[float] = None
    """The joint position or angle in which the joint spring (if any) achieves equilibrium. Similar to the vector mjModel.qpos0 which stores all joint reference values specified with the ref attribute above, all spring reference values specified with this attribute are stored in the vector mjModel.qpos_spring. The model configuration corresponding to mjModel.qpos_spring is also used to compute the spring reference lengths of all tendons, stored in mjModel.tendon_lengthspring. This is because tendons can also have springs."""

    armature: Optional[float] = None
    """Additional inertia associated with movement of the joint that is not due to body mass. This added inertia is usually due to a rotor (a.k.a armature) spinning faster than the joint itself due to a geared transmission. In the illustration, we compare (left) a 2-dof system with an armature body (purple box), coupled with a gear ratio of 33 to the pendulum using a joint equality constraint, and (right) a simple 1-dof pendulum with an equivalent armature. Because the gear ratio appears twice, multiplying both forces and lengths, the effect is known as "reflected inertia" and the equivalent value is the inertia of the spinning body multiplied by the square of the gear ratio, in this case 9=329=32. The value applies to all degrees of freedom created by this joint.

    Besides increasing the realism of joints with geared transmission, positive armature significantly improves simulation stability, even for small values, and is a recommended possible fix when encountering stability issues."""

    damping: Optional[float] = None
    """Damping applied to all degrees of freedom created by this joint. Unlike friction loss which is computed by the constraint solver, damping is simply a force linear in velocity. It is included in the passive forces. Despite this simplicity, larger damping values can make numerical integrators unstable, which is why our Euler integrator handles damping implicitly. See Integration in the Computation chapter."""

    frictionloss: Optional[float] = None
    """Friction loss due to dry friction. This value is the same for all degrees of freedom created by this joint. Semantically friction loss does not make sense for free joints, but the compiler allows it. To enable friction loss, set this attribute to a positive value."""

    user: Optional[VecN] = None
    """See User parameters."""
