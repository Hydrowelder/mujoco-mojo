from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import model_validator

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import BiasType, DynType, GainType, Vec3

__all__ = ["ActuatorPosition"]


class ActuatorPosition(ActuatorBase):
    """This element creates a position servo with an optional first-order filter. The underlying general attributes are set as follows:

    !!! note
        These general attributes are accessible via their respective properties for reference.

        | Attribute  | Setting             |
        |:-----------|:--------------------|
        | `dyntype`  | none or filterexact |
        | `gaintype` | fixed               |
        | `biastype` | affine              |
        | `dynprm`   | timeconst 0 0       |
        | `gainprm`  | kp 0 0              |
        | `biasprm`  | 0 -kp -kv           |
    """

    tag = "position"

    attributes = ActuatorBase.attributes + (
        "kp",
        "kv",
        "dampratio",
        "timeconst",
        "inheritrange",
    )

    kp: float = 1
    """Position feedback gain."""

    kv: float = 0
    """Damping applied by the actuator. When using this attribute, it is recommended to use the implicitfast or implicit integrators."""

    dampratio: float = 0
    """Damping applied by the actuator, using damping ratio units. This attribute is exclusive with kv and has similar meaning, but instead of units of force/velocity, the units are `2 * sqrt(kp * m)`, corresponding to a harmonic oscillator's damping ratio. A value of 1 corresponds to a critically damped oscillator, which often produces desirable behavior. Values smaller or larger than 1 correspond to underdamped and overdamped oscillations, respectively. The mass mm is computed at the reference configuration mjModel.qpos0, taking into account joint armature. However, passive damping or frictionloss in the affected joints are not taken into account; if they are non-negligible, dampratio values smaller than 1 might be required to achieve desirable motion. When using this attribute, it is recommended to use the implicitfast or implicit integrators."""

    timeconst: float = 0
    """Time-constant of optional first-order filter. If larger than zero, the actuator uses the filterexact dynamics type, if zero (the default) no filter is used."""

    inheritrange: float = 0
    """Automatically set the actuator's ctrlrange to match the transmission target's range. The default value means "disabled". A positive value X sets the ctrlrange around the midpoint of the target range, scaled by X. For example if the target joint has range of `[0, 1]`, then a value of 1.0 will set ctrlrange to `[0, 1]`; values of 0.8 and 1.2 will set the ctrlrange to `[0.1, 0.9]` and `[-0.1, 1.1]`, respectively. Values smaller than 1 are useful for not hitting the limits; values larger than 1 are useful for maintaining control authority at the limits (being able to push on them). This attribute is exclusive with ctrlrange and available only for joint and tendon transmissions which have range defined. Note that while inheritrange is available both as a position attribute and in the default class, saved XMLs always convert it to explicit ctrlrange at the actuator."""

    @property
    def dyntype(self) -> Literal[DynType.FILTEREXACT, DynType.NONE]:
        """Activation dynamics type for the actuator. The available dynamics types were already described in the Actuation model section. Repeating that description in somewhat different notation (corresponding to the mjModel and mjData fields involved).

        !!! note "Included for reference only"
        """
        return DynType.FILTEREXACT if self.timeconst > 0 else DynType.NONE

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
        if self.timeconst > 0:
            return np.array((self.timeconst, 0, 0))
        return np.array((1, 0, 0))

    @property
    def gainprm(self) -> Vec3:
        """Gain parameters. The built-in gain types (except for muscle) use only the first parameter, but we provide additional parameters in case user callbacks implement a more elaborate model. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return np.array((self.kp, 0, 0))

    @property
    def biasprm(self) -> Vec3:
        """Bias parameters. The affine bias type uses three parameters. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return np.array((0, -self.kp, -self.kv))

    @model_validator(mode="after")
    def validate_position(self):
        if self.kv != 0 and self.dampratio != 0:
            raise ValueError("kv and dampratio are mutually exclusive")

        if self.timeconst < 0:
            raise ValueError("timeconst must be >= 0")

        return self
