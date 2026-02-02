from __future__ import annotations

from typing import Literal

import numpy as np

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import BiasType, DynType, GainType, Vec2, Vec3, Vec9

__all__ = ["ActuatorMuscle"]


class ActuatorMuscle(ActuatorBase):
    """
    This element is used to model a muscle actuator, as described in the Muscles actuators section. The underlying general attributes are set as follows:

    !!! note
        These general attributes are accessible via their respective properties for reference.

        | Attribute  | Setting                                                |
        |:-----------|:-------------------------------------------------------|
        | `dyntype`  | muscle                                                 |
        | `gaintype` | muscle                                                 |
        | `biastype` | muscle                                                 |
        | `dynprm`   | timeconst(2) tausmooth                                 |
        | `gainprm`  | range(2), force, scale, lmin, lmax, vmax, fpmax, fvmax |
        | `biasprm`  | same as `gainprm`                                      |
    """

    tag = "muscle"

    attributes = (
        *ActuatorBase.attributes,
        "timeconst",
        "tausmooth",
        "range",
        "force",
        "scale",
        "lmin",
        "lmax",
        "vmax",
        "fpmax",
        "fvmax",
    )

    timeconst: Vec2 = np.array((0.01, 0.04))
    """Time constants for activation and de-activation dynamics."""

    tausmooth: float = 0
    """Width of smooth transition between activation and deactivation time constants. Units of ctrl, must be nonegative."""

    range: Vec2 = np.array((0.75, 1.05))
    """Operating length range of the muscle, in units of L0."""

    force: float = -1
    """Peak active force at rest. If this value is negative, the peak force is determined automatically using the scale attribute below."""

    scale: float = 200
    """If the force attribute is negative, the peak active force for the muscle is set to this value divided by mjModel.actuator_acc0. The latter is the norm of the joint-space acceleration vector caused by unit force on the actuator's transmission in qpos0. In other words, scaling produces higher peak forces for muscles that pull more weight."""

    lmin: float = 0.5
    """Lower position range of the normalized FLV curve, in units of L0."""

    lmax: float = 1.6
    """Upper position range of the normalized FLV curve, in units of L0."""

    vmax: float = 1.5
    """Shortening velocity at which muscle force drops to zero, in units of L0 per second."""

    fpmax: float = 1.3
    """Passive force generated at lmax, relative to the peak rest force."""

    fvmax: float = 1.2
    """Active force generated at saturating lengthening velocity, relative to the peak rest force."""

    @property
    def dyntype(self) -> Literal[DynType.MUSCLE]:
        """
        Activation dynamics type for the actuator. The available dynamics types were already described in the Actuation model section. Repeating that description in somewhat different notation (corresponding to the mjModel and mjData fields involved).

        !!! note "Included for reference only"
        """
        return DynType.MUSCLE

    @property
    def gaintype(self) -> Literal[GainType.MUSCLE]:
        """
        The gain and bias together determine the output of the force generation mechanism, which is currently assumed to be affine. As already explained in Actuation model, the general formula is: scalar_force = gain_term * (act or ctrl) + bias_term. The formula uses the activation state when present, and the control otherwise.

        !!! note "Included for reference only"
        """
        return GainType.MUSCLE

    @property
    def biastype(self) -> Literal[BiasType.MUSCLE]:
        """
        The gain and bias together determine the output of the force generation mechanism, which is currently assumed to be affine. As already explained in Actuation model, the general formula is: scalar_force = gain_term * (act or ctrl) + bias_term. The formula uses the activation state when present, and the control otherwise.

        !!! note "Included for reference only"
        """
        return BiasType.MUSCLE

    @property
    def dynprm(self) -> Vec3:
        """
        Activation dynamics parameters.

        !!! warning
            These parameters are different than for other actuators!

        !!! note "Included for reference only"
        """
        timeconst1, timeconst2 = tuple(np.asarray(self.timeconst))

        return np.array((timeconst1, timeconst2, self.tausmooth))

    @property
    def gainprm(self) -> Vec9:
        """
        Gain parameters.

        !!! warning
            These parameters are different than for other actuators!

        !!! note "Included for reference only"
        """
        range1, range2 = tuple(np.asarray(self.range))
        return np.array(
            (
                range1,
                range2,
                self.force,
                self.scale,
                self.lmin,
                self.lmax,
                self.vmax,
                self.fpmax,
                self.fvmax,
            ),
        )

    @property
    def biasprm(self) -> Vec9:
        """
        Bias parameters.

        !!! warning
            These parameters are different than for other actuators!

        !!! note "Included for reference only"
        """
        return self.gainprm
