from __future__ import annotations

from typing import Literal, Self

import numpy as np
from pydantic import model_validator

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import (
    BiasType,
    DynType,
    GainType,
    OrientationInput,
    Vec2,
    Vec3,
)
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = ["ActuatorOrientation"]


class ActuatorOrientation(ActuatorBase):
    """
    This element creates an orientation servo: a geodesic PD controller on a relative orientation, targeting a ball joint or a site with a refsite. Unlike per-axis `position` servos, the servo acts jointly on the full orientation: the force is `kp * log(q^-1 q_target) - kv * omega`, exact for arbitrary axis combinations, with a unique equilibrium at every commanded orientation. The transmission has 3 force outputs; force, error and angular velocity are expressed in the child (joint or site) frame. The commanded orientation is given in the input` chart: an exponential-map vector (3 controls, the default) or a quaternion (4 controls). `forcerange` clamps the norm of the output torque, preserving its direction; the lower bound must be 0. Actuator sensors report one value per force output. The integrator variant, which stores the orientation setpoint in `act`, is available via `general` with `dyntype` "integrator" and is expmap-only.

    The underlying general attributes are set as follows:

    !!! note
        These general attributes are accessible via their respective properties for reference.

        | Attribute  | Setting   |
        |:-----------|:----------|
        | `dyntype`  | none      |
        | `gaintype` | so3       |
        | `biastype` | so3       |
        | `gainprm`  | kp 0 0    |
        | `biasprm`  | 0 -kp -kv |

    """

    tag = "orientation"

    attributes = (
        "name",
        "class_",
        "group",
        "nsample",
        "interp",
        "delay",
        "ctrlrange",
        "forcerange",
        "forcelimited",
        "user",
        "joint",
        "site",
        "refsite",
        "kp",
        "kv",
        "dampratio",
        "input",
    )

    # inherited from ActuatorBase but not valid for orientation's ball-joint/refsite-site transmission
    non_xml_fields = (
        "ctrllimited",
        "lengthrange",
        "gear",
        "cranklength",
        "damping",
        "armature",
        "jointinparent",
        "tendon",
        "cranksite",
        "slidersite",
    )

    ctrlrange: Vec2 = np.array((0, 0))
    """Range for clamping the control input, as described in `ctrlrange`. For this multi-input actuator, the same range limits are replicated and applied independently to each of the 3 (expmap) or 4 (quaternion) control inputs in the control block."""

    forcerange: Vec2 = np.array((0, 0))
    """Range for clamping the torque output, as described in `forcerange`. The torque is clamped on its norm, preserving its direction: the second value bounds the torque magnitude and the first value must be 0."""

    kp: float = 1
    """Position feedback gain, in units of torque per radian of geodesic error."""

    kv: float = 0
    """Damping applied by the actuator, per force output. This attribute is exclusive with `dampratio`. When using this attribute, it is recommended to use the implicitfast or implicit integrators."""

    dampratio: float = 0
    """Damping applied by the actuator, using damping ratio units, as for `position/dampratio`. This attribute is exclusive with `kv`."""

    input: OrientationInput = OrientationInput.EXPMAP
    """Chart of the commanded orientation. With "expmap" the control block is an exponential-map vector (3 controls, in radians). With "quat" the control block is a quaternion (4 controls, w-first); the commanded quaternion is normalized by the servo, making the force scale- and antipodally-invariant, and the control block resets to the identity quaternion. The quat chart requires `dyntype="none"` (always true for this element)."""

    @property
    def dyntype(self) -> Literal[DynType.NONE]:
        """
        Activation dynamics type for the actuator. The available dynamics types were already described in the Actuation model section. Repeating that description in somewhat different notation (corresponding to the mjModel and mjData fields involved).

        !!! note "Included for reference only"
        """
        return DynType.NONE

    @property
    def gaintype(self) -> Literal[GainType.SO3]:
        """
        The gain and bias together determine the output of the force generation mechanism. For SO(3) transmissions the geodesic orientation error takes the place of length/velocity in the usual affine formula.

        !!! note "Included for reference only"
        """
        return GainType.SO3

    @property
    def biastype(self) -> Literal[BiasType.SO3]:
        """
        The gain and bias together determine the output of the force generation mechanism. For SO(3) transmissions the geodesic orientation error and angular velocity take the place of length/velocity in the usual affine formula.

        !!! note "Included for reference only"
        """
        return BiasType.SO3

    @property
    def dynprm(self) -> Vec3:
        """
        Activation dynamics parameters. The built-in activation types (except for muscle) use only the first parameter, but we provide additional parameters in case user callbacks implement a more elaborate model. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return np.array((1, 0, 0))

    @property
    def gainprm(self) -> Vec3:
        """
        Gain parameters. The built-in gain types (except for muscle) use only the first parameter, but we provide additional parameters in case user callbacks implement a more elaborate model. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return np.array((self.kp, 0, 0))

    @property
    def biasprm(self) -> Vec3:
        """
        Bias parameters. The affine bias type uses three parameters. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return np.array((0, -self.kp, -self.kv))

    @model_validator(mode="after")
    def validate_gains(self) -> Self:
        if self.kv != 0 and self.dampratio != 0:
            msg = "kv and dampratio are mutually exclusive"
            logger.error(msg)
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_forcerange(self) -> Self:
        if self.forcerange[0] != 0:
            msg = "forcerange lower bound must be 0: forcerange clamps the torque norm, not a signed component."
            logger.error(msg)
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_transmission(self) -> Self:
        if sum(v is not None for v in (self.joint, self.site)) != 1:
            msg = "Exactly one of joint or site must be specified."
            logger.error(msg)
            raise ValueError(msg)

        if self.site is not None and self.refsite is None:
            msg = "A site transmission requires refsite: orientation targets a ball joint, or a site with a refsite."
            logger.error(msg)
            raise ValueError(msg)

        return self
