from __future__ import annotations

from typing import Literal

import numpy as np

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import BiasType, BodyName, DynType, GainType, Vec3

__all__ = ["ActuatorAdhesion"]


class ActuatorAdhesion(ActuatorBase):
    """
    This element defines an active adhesion actuator which injects forces at contacts in the normal direction, see illustration video. The model shown in the video can be found here and includes inline annotations. The transmission target is a body, and adhesive forces are injected into all contacts involving geoms which belong to this body. The force is divided equally between multiple contacts. When the gap attribute is not used, this actuator requires active contacts and cannot apply a force at a distance, more like the active adhesion on the feet of geckos and insects rather than an industrial vacuum gripper. In order to enable "suction at a distance", set the gap attribute of the body's geoms to a positive value. This creates a layer around each geom where contacts are detected but no contact forces are generated, and the adhesive force can act across this gap. In the video above, such inactive contacts are blue, while active contacts are orange. An adhesion actuator's length is always 0. ctrlrange is required and must also be nonnegative (no repulsive forces are allowed). The underlying general attributes are set as follows:

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

    This element has a subset of the common attributes and two custom attributes.

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

    # inherited from ActuatorBase but not valid for adhesion's fixed body transmission
    non_xml_fields = (
        "nsample",
        "interp",
        "delay",
        "ctrllimited",
        "lengthrange",
        "gear",
        "damping",
        "armature",
        "cranklength",
        "joint",
        "jointinparent",
        "site",
        "refsite",
        "tendon",
        "cranksite",
        "slidersite",
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
