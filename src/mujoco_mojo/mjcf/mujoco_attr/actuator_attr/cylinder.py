from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import field_validator, model_validator

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import BiasType, DynType, GainType, Vec3
from mujoco_mojo.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["ActuatorCylinder"]


class ActuatorCylinder(ActuatorBase):
    """
    This element is suitable for modeling pneumatic or hydraulic cylinders. The underlying general attributes are set as follows:

    !!! note
        These general attributes are accessible via their respective properties for reference.

        | Attribute  | Setting       |
        |:-----------|:--------------|
        | `dyntype`  | filter        |
        | `gaintype` | fixed         |
        | `biastype` | affine        |
        | `dynprm`   | timeconst 0 0 |
        | `gainprm`  | area 0 0      |
        | `biasprm`  | bias(3)       |
    """

    tag = "cylinder"

    attributes = (*ActuatorBase.attributes, "timeconst", "area", "diameter", "bias")

    timeconst: float = 1
    """Time constant of the activation dynamics."""

    area: float = 1
    """Area of the cylinder. This is used internally as actuator gain."""

    diameter: float | None = None
    """Instead of area the user can specify diameter. If both are specified, diameter has precedence."""

    bias: Vec3 = np.array((0, 0, 0))
    """Bias parameters, copied internally into biasprm."""

    @property
    def dyntype(self) -> Literal[DynType.FILTER]:
        """
        Activation dynamics type for the actuator. The available dynamics types were already described in the Actuation model section. Repeating that description in somewhat different notation (corresponding to the mjModel and mjData fields involved).

        !!! note "Included for reference only"
        """
        return DynType.FILTER

    @property
    def gaintype(self) -> Literal[GainType.FIXED]:
        """
        The gain and bias together determine the output of the force generation mechanism, which is currently assumed to be affine. As already explained in Actuation model, the general formula is: scalar_force = gain_term * (act or ctrl) + bias_term. The formula uses the activation state when present, and the control otherwise.

        !!! note "Included for reference only"
        """
        return GainType.FIXED

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
        return np.array((self.timeconst, 0, 0))

    @property
    def gainprm(self) -> Vec3:
        """
        Gain parameters. The built-in gain types (except for muscle) use only the first parameter, but we provide additional parameters in case user callbacks implement a more elaborate model. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return np.array((self.area, 0, 0))

    @property
    def biasprm(self) -> Vec3:
        """
        Bias parameters. The affine bias type uses three parameters. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return self.bias

    @field_validator("timeconst")
    @classmethod
    def validate_timeconst(cls, v: float) -> float:
        if v < 0:
            msg = "timeconst cannot be negative"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @field_validator("area")
    @classmethod
    def validate_area(cls, v: float) -> float:
        if v < 0:
            msg = "area cannot be negative"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @field_validator("diameter")
    @classmethod
    def validate_diameter(cls, v: float) -> float:
        if v < 0:
            msg = "diameter cannot be negative"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_cylinder(self):
        if self.diameter is not None:
            # since diameter take precedence if set
            self.area = np.pi / 4 * self.diameter**2

        return self
