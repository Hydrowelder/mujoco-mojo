from __future__ import annotations

import numpy as np
from pydantic import model_validator

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import (
    ActuatorLimited,
    BiasType,
    BodyName,
    DynType,
    GainType,
    Vec2,
    VecN,
)
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = ["ActuatorGeneral"]


class ActuatorGeneral(ActuatorBase):
    """This element creates a general actuator, providing full access to all actuator components and allowing the user to specify them independently."""

    tag = "general"

    attributes = (
        *ActuatorBase.attributes,
        "actlimited",
        "actrange",
        "body",
        "actdim",
        "dyntype",
        "gaintype",
        "biastype",
        "dynprm",
        "gainprm",
        "biasprm",
        "actearly",
    )

    actlimited: ActuatorLimited = ActuatorLimited.AUTO
    """If true, the internal state (activation) associated with this actuator is automatically clamped to actrange at runtime. If false, activation clamping is disabled. If "auto" and autolimits is set in compiler, activation clamping will automatically be set to true if actrange is defined without explicitly setting this attribute to "true". See the Activation clamping section for more details."""

    actrange: Vec2 = np.array((0, 0))
    """Range for clamping the activation state. The first value must be no greater than the second value. See the Activation clamping section for more details.

    Setting this attribute without specifying actlimited is an error if autolimits is "false" in compiler."""

    body: BodyName | None = None
    """This transmission can apply linear forces at contact points in the direction of the contact normal. The set of contacts is all those belonging to the specified body. This can be used to model natural active adhesion mechanisms like the feet of geckos and insects. The actuator length is again defined as zero. For more information, see the adhesion shortcut below."""

    actdim: float = -1
    """Dimension of the activation state. The default value of -1 instructs the compiler to set the dimension according to the dyntype. Values larger than 1 are only allowed for user-defined activation dynamics, as native types require dimensions of only 0 or 1. For activation dimensions bigger than 1, the last element is used to generate force."""

    dyntype: DynType = DynType.NONE
    """Activation dynamics type for the actuator. The available dynamics types were already described in the Actuation model section. Repeating that description in somewhat different notation (corresponding to the mjModel and mjData fields involved) we have:

    | Keyword       | Description                            |
    |:--------------|:---------------------------------------|
    | `none`        | No internal state                      |
    | `integrator`  | act_dot = ctrl                         |
    | `filter`      | act_dot = (ctrl - act) / dynprm[0]     |
    | `filterexact` | Like filter but with exact integration |
    | `muscle`      | act_dot = mju_muscleDynamics(...)      |
    | `user`        | act_dot = mjcb_act_dyn(...)            |
    """

    gaintype: GainType = GainType.FIXED
    """The gain and bias together determine the output of the force generation mechanism, which is currently assumed to be affine. As already explained in Actuation model, the general formula is: scalar_force = gain_term * (act or ctrl) + bias_term. The formula uses the activation state when present, and the control otherwise. The keywords have the following meaning:

    | Keyword  | Description                                                         |
    |:---------|:--------------------------------------------------------------------|
    | `fixed`  | gain_term = gainprm[0]                                              |
    | `affine` | gain_term = gain_prm[0] + gain_prm[1]*length + gain_prm[2]*velocity |
    | `muscle` | gain_term = mju_muscleGain(...)                                     |
    | `user`   | gain_term = mjcb_act_gain(...)                                      |
    """

    biastype: BiasType = BiasType.NONE
    """The keywords have the following meaning:

    | Keyword  | Description                                                      |
    |:---------|:-----------------------------------------------------------------|
    | `none`   | bias_term = 0                                                    |
    | `affine` | bias_term = biasprm[0] + biasprm[1]*length + biasprm[2]*velocity |
    | `muscle` | bias_term = mju_muscleBias(...)                                  |
    | `user`   | bias_term = mjcb_act_bias(...)                                   |
    """

    dynprm: VecN | None = None
    """Activation dynamics parameters. The built-in activation types (except for muscle) use only the first parameter, but we provide additional parameters in case user callbacks implement a more elaborate model. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle below."""

    gainprm: VecN | None = None
    """Gain parameters. The built-in gain types (except for muscle) use only the first parameter, but we provide additional parameters in case user callbacks implement a more elaborate model. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle below."""

    biasprm: VecN | None = None
    """Bias parameters. The affine bias type uses three parameters. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle below."""

    actearly: bool = False
    """If true, force computation will use the next value of the activation variable rather than the current one. Setting this flag reduces the delay between the control and accelerations by one time-step."""

    @model_validator(mode="after")
    def validate_transmission(self):
        fields = [
            self.joint,
            self.jointinparent,
            self.site,
            self.body,
        ]

        if sum(v is not None for v in fields) != 1:
            msg = "Exactly one of joint, jointinparent, site, or body must be specified"
            logger.error(msg)
            raise ValueError(msg)

        return self
