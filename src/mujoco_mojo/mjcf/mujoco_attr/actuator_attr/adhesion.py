from __future__ import annotations

from typing import Literal

import numpy as np

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import BiasType, BodyName, DynType, GainType, Vec3

__all__ = ["ActuatorAdhesion"]


class ActuatorAdhesion(ActuatorBase):
    """
    This element is used to model a muscle actuator, as described in the Muscles actuators section. The underlying general attributes are set as follows:

    !!! note
        These general attributes are accessible via their respective properties for reference.

        | Attribute     | Setting  |
        |:--------------|:---------|
        | `dyntype`     | none     |
        | `gaintype`    | fixed    |
        | `biastype`    | none     |
        | `trntype`     | body     |
        | `dynprm`      | 1 0 0    |
        | `gainprm`     | gain 0 0 |
        | `biasprm`     | 0 0 0    |
        | `ctrllimited` | true     |

        > `trntype` means transmission type. Meaning the Actuator uses the Body field.
        > It is not accessible as a property. See ActuatorGeneral.
    """

    tag = "adhesion"

    attributes = (
        "name",
        "class_",
        "group",
        "forcelimited",
        "ctrlrange",
        "forcerange",
        "user",  # the above are inherited from ActuatorBase
        "body",
        "gain",
    )

    body: BodyName
    """The actuator acts on all contacts involving this body's geoms."""

    gain: float = 1
    """Gain of the adhesion actuator, in units of force. The total adhesion force applied by the actuator is the control value multiplied by the gain. This force is distributed equally between all the contacts involving geoms belonging to the target body."""

    @property
    def dyntype(self) -> Literal[DynType.NONE]:
        """
        Activation dynamics type for the actuator. The available dynamics types were already described in the Actuation model section. Repeating that description in somewhat different notation (corresponding to the mjModel and mjData fields involved).

        !!! note "Included for reference only"
        """
        return DynType.NONE

    @property
    def gaintype(self) -> Literal[GainType.FIXED]:
        """
        The gain and bias together determine the output of the force generation mechanism, which is currently assumed to be affine. As already explained in Actuation model, the general formula is: scalar_force = gain_term * (act or ctrl) + bias_term. The formula uses the activation state when present, and the control otherwise.

        !!! note "Included for reference only"
        """
        return GainType.FIXED

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
        return np.array((self.gain, 0, 0))

    @property
    def biasprm(self) -> Vec3:
        """
        Bias parameters. The affine bias type uses three parameters. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return np.array((0, 0, 0))
