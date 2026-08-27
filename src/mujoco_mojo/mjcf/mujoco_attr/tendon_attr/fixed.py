from __future__ import annotations

import numpy as np
from pydantic import Field

from mujoco_mojo.mjcf.mujoco_attr.tendon_attr.fixed_attr.joint import TendonJoint
from mujoco_mojo.mjcf.mujoco_attr.tendon_attr.tendon_base import TendonBase
from mujoco_mojo.typing import ActuatorForceLimited, Vec2
from mujoco_mojo.utils.utils import is_empty_list

__all__ = ["Fixed"]


class Fixed(TendonBase):
    """This element creates an abstract tendon whose length is defined as a linear combination of joint positions. Recall that the tendon length and its gradient are the only quantities needed for simulation. Thus we could define any scalar function of joint positions, call it "tendon", and plug it in MuJoCo. Presently the only such function is a fixed linear combination. The attributes of fixed tendons are a subset of the attributes of spatial tendons and have the same meaning as above."""

    tag = "fixed"

    attributes = (
        *TendonBase.attributes,
        "actuatorfrclimited",
        "actuatorfrcrange",
        "armature",
    )
    children = ("joints",)

    actuatorfrclimited: ActuatorForceLimited = ActuatorForceLimited.AUTO
    """This attribute specifies whether actuator forces acting on the tendon should be clamped. See Force limits for details. This attribute interacts with the actuatorfrcrange attribute. If this attribute is "false", actuator force clamping is disabled. If it is "true", actuator force clamping is enabled. If this attribute is "auto", and autolimits is set in compiler, actuator force clamping will be enabled if actuatorfrcrange is defined."""

    actuatorfrcrange: Vec2 = np.array((0, 0))
    """Range for clamping total actuator forces acting on this tendon. See Force limits for details. The compiler expects the lower bound to be nonpositive and the upper bound to be nonnegative. Setting this attribute without specifying actuatorfrclimited is an error if compiler-autolimits is "false"."""

    armature: float = 0
    """Inertia associated with changes in tendon length. Setting this attribute to a positive value mm adds a kinetic energy term `1/2mv^2`, where v is the tendon velocity. Tendon inertia is most valuable when modeling the armature inertia in a linear actuator which contains a spinning element or the inertial motion of a fluid in a linear hydraulic actuator. In the illustration, we compare (left) a 3-dof system with a "tendon" implemented with a rotational joint and a slider joint with armature, attached to the world with a connect constraint and (right) an equivalent 1-dof model with an armature-bearing tendon. Like joint armature, this added inertia is only associated with changes in tendon length, and would not affect the dynamics of a moving fixed-length tendon. Because the tendon Jacobian J is position-dependent, tendon armature leads to an additional bias-force term `c = m * J * J_dot ^ T * q_dot`."""

    joints: list[TendonJoint] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Joint elements assigned to Fixed."""
