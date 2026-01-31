from __future__ import annotations

from typing import Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import (
    CompositeJointKind,
    JointType,
    Limited,
    Vec2,
    Vec3,
    Vec5,
)

__all__ = ["CompositeJoint"]


class CompositeJoint(XMLModel):
    """Depending on the composite type, some joints are created automatically (e.g. the universal joints in rope) while other joints are optional (e.g. the stretch and twist joints in rope). This sub-element is used to specify which optional joints should be created, as well as to adjust the attributes of both automatic and optional joints."""

    tag = "joint"

    attributes = (
        "kind",
        "group",
        "stiffness",
        "damping",
        "armature",
        "solreffix",
        "solimpfix",
        "type",
        "axis",
        "limited",
        "range",
        "margin",
        "solreflimit",
        "solimplimit",
        "frictionloss",
        "solreffriction",
        "solimpfriction",
    )

    kind: CompositeJointKind
    """The joint kind here is orthogonal to the joint type in the rest of MJCF. The joint kind refers to the function of the joint within the mechanism comprising the composite body, while the joint type (hinge or slide) is implied by the joint kind and composite body type.

    The main kind corresponds to the main joints forming each composite type. These joints are automatically included in the model even if the joint sub-element is missing. The main joints are 3D sliders for particle and grid; 1D sliders for box, cylinder and rope; universal joints for cloth, rope and loop. Even though the main joints are included automatically, this sub-element is still useful for adjusting their attributes.
    """

    solreffix: Optional[Vec2] = None
    """These are the solref and solimp attributes used to equality-constrain the joint. Whether or not a given joint is quality-constrained depends on the joint kind and composite object type as explained above. For joints that are not equality-constrained, this attribute has no effect. The defaults are adjusted depending on the composite type. Otherwise these attributes obey the same rules as all other solref and solimp attributes in MJCF. See Solver parameters."""

    solimpfix: Optional[Vec5] = None
    """These are the solref and solimp attributes used to equality-constrain the joint. Whether or not a given joint is quality-constrained depends on the joint kind and composite object type as explained above. For joints that are not equality-constrained, this attribute has no effect. The defaults are adjusted depending on the composite type. Otherwise these attributes obey the same rules as all other solref and solimp attributes in MJCF. See Solver parameters."""

    axis: Optional[Vec3] = None
    """This attribute specifies the axis of rotation for hinge joints and the direction of translation for slide joints. It is ignored for free and ball joints. The vector specified here is automatically normalized to unit length as long as its length is greater than 10E-14; otherwise a compile error is generated."""

    group: Optional[int] = None
    """Integer group to which the joint belongs. This attribute can be used for custom tags. It is also used by the visualizer to enable and disable the rendering of entire groups of joints."""

    stiffness: Optional[float] = None
    """Joint stiffness. The spring force is computed along with the other passive forces."""

    damping: Optional[float] = None
    """Damping applied to all degrees of freedom created by this joint. Unlike friction loss which is computed by the constraint solver, damping is simply a force linear in velocity. It is included in the passive forces. Despite this simplicity, larger damping values can make numerical integrators unstable, which is why our Euler integrator handles damping implicitly. See Integration in the Computation chapter."""

    armature: Optional[float] = None
    """Additional inertia associated with movement of the joint that is not due to body mass. This added inertia is usually due to a rotor (a.k.a armature) spinning faster than the joint itself due to a geared transmission. In the illustration, we compare (left) a 2-dof system with an armature body (purple box), coupled with a gear ratio of 33 to the pendulum using a joint equality constraint, and (right) a simple 1-dof pendulum with an equivalent armature. Because the gear ratio appears twice, multiplying both forces and lengths, the effect is known as "reflected inertia" and the equivalent value is the inertia of the spinning body multiplied by the square of the gear ratio, in this case 9=329=32. The value applies to all degrees of freedom created by this joint.

    Besides increasing the realism of joints with geared transmission, positive armature significantly improves simulation stability, even for small values, and is a recommended possible fix when encountering stability issues."""

    limited: Optional[Limited] = None
    """This attribute specifies if the joint has limits. It interacts with the range attribute. If this attribute is "false", joint limits are disabled. If this attribute is "true", joint limits are enabled. If this attribute is "auto", and autolimits is set in compiler, joint limits will be enabled if range is defined."""

    range: Optional[Vec2] = None
    """The joint limits. Limits can be imposed on all joint types except for free joints. For hinge and ball joints, the range is specified in degrees or radians depending on the angle attribute of compiler. For ball joints, the limit is imposed on the angle of rotation (relative to the reference configuration) regardless of the axis of rotation. Only the second range parameter is used for ball joints; the first range parameter should be set to 0. See the Limit section in the Computation chapter for more information.

    Setting this attribute without specifying limited is an error if autolimits is "false" in compiler."""

    margin: Optional[float] = None
    """The distance threshold below which limits become active. Recall that the Constraint solver normally generates forces as soon as a constraint becomes active, even if the margin parameter makes that happen at a distance. This attribute together with solreflimit and solimplimit can be used to model a soft joint limit."""

    solreflimit: Optional[Vec2] = None
    """Constraint solver parameters for simulating joint limits. See Solver parameters."""

    solimplimit: Optional[Vec5] = None
    """Constraint solver parameters for simulating joint limits. See Solver parameters."""

    frictionloss: Optional[float] = None
    """Friction loss due to dry friction. This value is the same for all degrees of freedom created by this joint. Semantically friction loss does not make sense for free joints, but the compiler allows it. To enable friction loss, set this attribute to a positive value."""

    solreffriction: Optional[Vec2] = None
    """Constraint solver parameters for simulating dry friction. See Solver parameters."""

    solimpfriction: Optional[Vec5] = None
    """Constraint solver parameters for simulating dry friction. See Solver parameters."""

    type: Optional[JointType] = None
    """Type of the joint. The keywords have the following meaning: The free type creates a free "joint" with three translational degrees of freedom followed by three rotational degrees of freedom. In other words it makes the body floating. The rotation is represented as a unit quaternion. This joint type is only allowed in bodies that are children of the world body. No other joints can be defined in the body if a free joint is defined. Unlike the remaining joint types, free joints do not have a position within the body frame. Instead the joint position is assumed to coincide with the center of the body frame. Thus at runtime the position and orientation data of the free joint correspond to the global position and orientation of the body frame. Free joints cannot have limits.

    The ball type creates a ball joint with three rotational degrees of freedom. The rotation is represented as a unit quaternion. The quaternion (1,0,0,0) corresponds to the initial configuration in which the model is defined. Any other quaternion is interpreted as a 3D rotation relative to this initial configuration. The rotation is around the point defined by the pos attribute. If a body has a ball joint, it cannot have other rotational joints (ball or hinge). Combining ball joints with slide joints in the same body is allowed.

    The slide type creates a sliding or prismatic joint with one translational degree of freedom. Such joints are defined by a position and a sliding direction. For simulation purposes only the direction is needed; the joint position is used for rendering purposes.

    The hinge type creates a hinge joint with one rotational degree of freedom. The rotation takes place around a specified axis through a specified position. This is the most common type of joint and is therefore the default. Most models contain only hinge and free joints."""
