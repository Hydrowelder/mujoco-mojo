from __future__ import annotations

from typing import Literal

import numpy as np

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import BiasType, DynType, GainType, Vec3

__all__ = ["ActuatorVelocity"]


class ActuatorVelocity(ActuatorBase):
    """This element creates a velocity servo. Note that in order create a PD controller, one has to define two actuators: a position servo and a velocity servo. This is because MuJoCo actuators are SISO while a PD controller takes two control inputs (reference position and reference velocity). When using this actuator, it is recommended to use the implicitfast or implicit integrators. The underlying general attributes are set as follows:

    !!! note
        These general attributes are accessible via their respective properties for reference.

        | Attribute  | Setting |
        |:-----------|:--------|
        | `dyntype`  | none    |
        | `gaintype` | fixed   |
        | `biastype` | affine  |
        | `dynprm`   | 1 0 0   |
        | `gainprm`  | kv 0 0  |
        | `biasprm`  | 0 0 -kv |
    """

    tag = "velocity"

    attributes = ActuatorBase.attributes + ("kv",)

    kv: float = 0
    """Velocity feedback gain."""

    @property
    def dyntype(self) -> Literal[DynType.NONE]:
        """Activation dynamics type for the actuator. The available dynamics types were already described in the Actuation model section. Repeating that description in somewhat different notation (corresponding to the mjModel and mjData fields involved).

        !!! note "Included for reference only"
        """
        return DynType.NONE

    @property
    def gaintype(self) -> Literal[GainType.FIXED]:
        """The gain and bias together determine the output of the force generation mechanism, which is currently assumed to be affine. As already explained in Actuation model, the general formula is: scalar_force = gain_term * (act or ctrl) + bias_term. The formula uses the activation state when present, and the control otherwise.

        !!! note "Included for reference only"
        """
        return GainType.FIXED

    @property
    def biastype(self) -> Literal[BiasType.AFFINE]:
        """The gain and bias together determine the output of the force generation mechanism, which is currently assumed to be affine. As already explained in Actuation model, the general formula is: scalar_force = gain_term * (act or ctrl) + bias_term. The formula uses the activation state when present, and the control otherwise.

        !!! note "Included for reference only"
        """
        return BiasType.AFFINE

    @property
    def dynprm(self) -> Vec3:
        """Activation dynamics parameters. The built-in activation types (except for muscle) use only the first parameter, but we provide additional parameters in case user callbacks implement a more elaborate model. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return np.array((1, 0, 0))

    @property
    def gainprm(self) -> Vec3:
        """Gain parameters. The built-in gain types (except for muscle) use only the first parameter, but we provide additional parameters in case user callbacks implement a more elaborate model. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return np.array((self.kv, 0, 0))

    @property
    def biasprm(self) -> Vec3:
        """Bias parameters. The affine bias type uses three parameters. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return np.array((0, 0, -self.kv))
