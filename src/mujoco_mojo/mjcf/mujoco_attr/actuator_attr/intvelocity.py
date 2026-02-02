from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import model_validator

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import BiasType, DynType, GainType, Vec3

__all__ = ["ActuatorIntegratedVelocity"]


class ActuatorIntegratedVelocity(ActuatorBase):
    """
    This element creates an integrated-velocity servo. For more information, see the Activation clamping section of the Modeling chapter. The underlying general attributes are set as follows:

    !!! note
        These general attributes are accessible via their respective properties for reference.

        | Attribute    | Setting    |
        |:-------------|:-----------|
        | `dyntype`    | integrator |
        | `gaintype`   | fixed      |
        | `biastype`   | affine     |
        | `actlimited` | true       |
        | `dynprm`     | 1 0 0      |
        | `gainprm`    | kp 0 0     |
        | `biasprm`    | 0 -kp -kv  |
    """

    tag = "intvelocity"

    attributes = (*ActuatorBase.attributes, "kp", "kv", "dampratio", "inheritrange")

    kp: float = 1
    """Position feedback gain."""

    kv: float = 0
    """Damping applied by the actuator. When using this attribute, it is recommended to use the implicitfast or implicit integrators."""

    dampratio: float = 0
    """See position/dampratio."""

    inheritrange: float = 0
    """Identical to position/inheritrange, but sets actrange (which has the same length semantics as the transmission target) rather than ctrlrange (which has velocity semantics)."""

    @property
    def dyntype(self) -> Literal[DynType.INTEGRATOR]:
        """
        Activation dynamics type for the actuator. The available dynamics types were already described in the Actuation model section. Repeating that description in somewhat different notation (corresponding to the mjModel and mjData fields involved).

        !!! note "Included for reference only"
        """
        return DynType.INTEGRATOR

    @property
    def gaintype(self) -> Literal[GainType.FIXED]:
        """
        The gain and bias together determine the output of the force generation mechanism, which is currently assumed to be affine. As already explained in Actuation model, the general formula is: scalar_force = gain_term * (act or ctrl) + bias_term. The formula uses the activation state when present, and the control otherwise.

        !!! note "Included for reference only"
        """
        return GainType.FIXED

    @property
    def actlimited(self) -> Literal[True]:
        """
        If true, the internal state (activation) associated with this actuator is automatically clamped to actrange at runtime. If false, activation clamping is disabled. If "auto" and autolimits is set in compiler, activation clamping will automatically be set to true if actrange is defined without explicitly setting this attribute to "true". See the Activation clamping section for more details.

        !!! note "Included for reference only"
        """
        return True

    @property
    def biastype(self) -> Literal[BiasType.AFFINE]:
        """
        The gain and bias together determine the output of the force generation mechanism, which is currently assumed to be affine. As already explained in Actuation model, the general formula is: scalar_force = gain_term * (act or ctrl) + bias_term. The formula uses the activation state when present, and the control otherwise.

        !!! note "Included for reference only"
        """
        return BiasType.AFFINE

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
    def validate_position(self):
        if self.kv != 0 and self.dampratio != 0:
            raise ValueError("kv and dampratio are mutually exclusive")

        return self
