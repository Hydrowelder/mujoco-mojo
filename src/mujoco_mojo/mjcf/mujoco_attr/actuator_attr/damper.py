from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field, model_validator

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import ActuatorControlLimited, BiasType, DynType, GainType, Vec3
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = ["ActuatorDamper"]


class ActuatorDamper(ActuatorBase):
    """
    This element is an active damper which produces a force proportional to both velocity and control: `F = - kv * velocity * control`, where `kv` must be nonnegative. `ctrlrange` is required and must also be nonnegative. When using this actuator, it is recommended to use the implicitfast or implicit integrators. The underlying general attributes are set as follows:

    !!! note
        These general attributes are accessible via their respective properties for reference.

        | Attribute     | Setting |
        |:--------------|:--------|
        | `dyntype`     | none    |
        | `gaintype`    | affine  |
        | `biastype`    | none    |
        | `ctrllimited` | true    |
        | `dynprm`      | 1 0 0   |
        | `gainprm`     | 0 0 -kv |
        | `biasprm`     | 0 0 0   |
    """

    tag = "damper"

    attributes = (
        *ActuatorBase.attributes,
        "kv",
    )

    kv: float = 1
    """Velocity feedback gain."""

    ctrllimited: Literal[ActuatorControlLimited.TRUE] = Field(  # HACK # type: ignore
        default=ActuatorControlLimited.TRUE,
        description="Always ActuatorControlLimited.TRUE for ActuatorDamper",
        frozen=True,
    )
    """If true, the control input to this actuator is automatically clamped to ctrlrange at runtime. If false, control input clamping is disabled. If "auto" and autolimits is set in compiler, control clamping will automatically be set to true if ctrlrange is defined without explicitly setting this attribute to "true". Note that control input clamping can also be globally disabled with the clampctrl attribute of option/flag.

    !!! note "Included for reference only"

    !!! danger "Hack"
        This field is always set to true and has been frozen. The static analyzer has been told to ignore due to overriding the type of the parameter from an enum to a branch of the enum. Its the best I got
    """

    @property
    def dyntype(self) -> Literal[DynType.NONE]:
        """
        Activation dynamics type for the actuator. The available dynamics types were already described in the Actuation model section. Repeating that description in somewhat different notation (corresponding to the mjModel and mjData fields involved).

        !!! note "Included for reference only"
        """
        return DynType.NONE

    @property
    def gaintype(self) -> Literal[GainType.AFFINE]:
        """
        The gain and bias together determine the output of the force generation mechanism, which is currently assumed to be affine. As already explained in Actuation model, the general formula is: scalar_force = gain_term * (act or ctrl) + bias_term. The formula uses the activation state when present, and the control otherwise.

        !!! note "Included for reference only"
        """
        return GainType.AFFINE

    @property
    def biastype(self) -> Literal[BiasType.NONE]:
        """
        The gain and bias together determine the output of the force generation mechanism, which is currently assumed to be affine. As already explained in Actuation model, the general formula is: scalar_force = gain_term * (act or ctrl) + bias_term. The formula uses the activation state when present, and the control otherwise.

        !!! note "Included for reference only"
        """
        return BiasType.NONE

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
        return np.array((0, 0, -self.kv))

    @property
    def biasprm(self) -> Vec3:
        """
        Bias parameters. The affine bias type uses three parameters. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return np.array((0, 0, 0))

    @model_validator(mode="after")
    def validate_position(self):
        if self.kv < 0:
            msg = "kv cannot be negative"
            logger.error(msg)
            raise ValueError(msg)

        if any(np.asarray(self.ctrlrange) < 0):
            msg = "ctrlrange cannot be negative"
            logger.error(msg)
            raise ValueError(msg)
        return self
