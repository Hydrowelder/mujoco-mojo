from __future__ import annotations

from typing import Literal, Self

import numpy as np
from pydantic import model_validator

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import ActuatorInput, BiasType, DynType, GainType, Vec2, Vec3
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = ["ActuatorPid"]

_PID_INPUT_ORDER = [ActuatorInput.POSITION, ActuatorInput.VELOCITY, ActuatorInput.FF]


class ActuatorPid(ActuatorBase):
    """
    This element creates a PID controller with position and velocity setpoint inputs on a single force output, with optional integral action and feedforward. With the default input signature `[pos, vel]` the force is kp * (u_pos - l) + kv * (u_vel - v)` where `l, v` are the actuator length and velocity; with a zero velocity setpoint this is identical to `position`. The input signature is any subset of `[pos, vel, ff]`, selected by input`: an absent setpoint input is fixed at zero, and the `ff` input adds a feedforward force. Integral action is enabled by `ki`: the position error is integrated in `act` and contributes `ki * act` to the force, with anti-windup clamping by `imax`. `slewmax` limits the rate of change of the effective position setpoint. Each of these features, when enabled, adds one activation state, in the order `[slew, integral]`.

    The underlying general attributes are set as follows:

    !!! note
        These general attributes are accessible via their respective properties for reference.

        | Attribute  | Setting     |
        |:-----------|:------------|
        | `dyntype`  | none or pid |
        | `gaintype` | pid         |
        | `biastype` | affine      |
        | `dynprm`   | imax 0 0    |
        | `gainprm`  | ki 0 0      |
        | `biasprm`  | 0 -kp -kv   |

    `ctrlrange` doubles as `posrange`: the range of the position-setpoint input, since `pos` is always the first
    control when present.
    """

    tag = "pid"

    attributes = (
        *ActuatorBase.attributes,
        "kp",
        "kv",
        "dampratio",
        "ki",
        "imax",
        "slewmax",
        "input",
        "velrange",
        "ffrange",
        "inheritrange",
    )

    kp: float = 1
    """Position feedback gain."""

    kv: float = 0
    """Velocity feedback gain: applied to the velocity error when the `vel` input is present, and as pure damping otherwise. This attribute is exclusive with `dampratio`. When using this attribute, it is recommended to use the implicitfast or implicit integrators."""

    dampratio: float = 0
    """Damping applied by the actuator, using damping ratio units, as for `position/dampratio`. This attribute is exclusive with `kv`."""

    ki: float = 0
    """Integral gain. A nonzero value enables integral action: the position error is integrated in `act` (`dyntype` "pid") and contributes `ki * act` to the force. Requires the `pos` input."""

    imax: float = 0
    """Anti-windup limit on the integral state: accumulation stops beyond +/- `imax`. The default value 0 means "unclamped"."""

    slewmax: float = 0
    """Maximum rate of change of the effective position setpoint. When positive, the commanded setpoint is rate-limited through an activation state holding the effective setpoint, as for the dcmotor controller. The default value 0 means "unlimited"."""

    input: tuple[ActuatorInput, ...] = (
        ActuatorInput.POSITION,
        ActuatorInput.VELOCITY,
    )
    """Input signature: a space-separated subset of the tokens "pos", "vel" and "ff", packed in this canonical order. Absent setpoint inputs are fixed at zero, so the control vector contains no inert entries."""

    velrange: Vec2 = np.array((0, 0))
    """Range of the velocity-setpoint input."""

    ffrange: Vec2 = np.array((0, 0))
    """Range of the feedforward input."""

    inheritrange: float = 0
    """Identical to `position/inheritrange`, setting `posrange` (i.e. `ctrlrange`) from the transmission target's range."""

    @property
    def dyntype(self) -> Literal[DynType.NONE, DynType.PID]:
        """
        Activation dynamics type for the actuator. The available dynamics types were already described in the Actuation model section. Repeating that description in somewhat different notation (corresponding to the mjModel and mjData fields involved).

        !!! note "Included for reference only"
        """
        return DynType.PID if (self.ki != 0 or self.slewmax != 0) else DynType.NONE

    @property
    def gaintype(self) -> Literal[GainType.PID]:
        """
        The gain and bias together determine the output of the force generation mechanism, which is currently assumed to be affine. As already explained in Actuation model, the general formula is: scalar_force = gain_term * (act or ctrl) + bias_term. The formula uses the activation state when present, and the control otherwise.

        !!! note "Included for reference only"
        """
        return GainType.PID

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
        if self.dyntype == DynType.PID:
            return np.array((self.imax, 0, 0))
        return np.array((1, 0, 0))

    @property
    def gainprm(self) -> Vec3:
        """
        Gain parameters. The built-in gain types (except for muscle) use only the first parameter, but we provide additional parameters in case user callbacks implement a more elaborate model. The length of this array is not enforced by the parser, so the user can enter as many parameters as needed. These defaults are not compatible with muscle actuators; see muscle.

        !!! note "Included for reference only"
        """
        return np.array((self.ki, 0, 0))

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
    def validate_input(self) -> Self:
        """
        Enforce Section 2.5 of the tech note: `input` is an ordered, deduplicated subset of [pos, vel, ff].
        """
        if not self.input:
            msg = "input must not be empty."
            logger.error(msg)
            raise ValueError(msg)

        invalid = set(self.input) - set(_PID_INPUT_ORDER)
        if invalid:
            msg = f"input may only contain {[t.value for t in _PID_INPUT_ORDER]}, got {[t.value for t in invalid]}."
            logger.error(msg)
            raise ValueError(msg)

        if len(set(self.input)) != len(self.input):
            msg = "Duplicate entries in input."
            logger.error(msg)
            raise ValueError(msg)

        self.input = tuple(sorted(self.input, key=_PID_INPUT_ORDER.index))
        return self

    @model_validator(mode="after")
    def validate_integral_action(self) -> Self:
        if self.ki != 0 and ActuatorInput.POSITION not in self.input:
            msg = (
                "ki requires 'pos' in input: the integrator accumulates position error."
            )
            logger.error(msg)
            raise ValueError(msg)
        return self
