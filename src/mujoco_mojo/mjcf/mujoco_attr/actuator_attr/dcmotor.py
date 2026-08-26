from __future__ import annotations

from typing import Self

import numpy as np
from pydantic import model_validator

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import ActuatorInput, Vec2, Vec3, Vec5, Vec6
from mujoco_mojo.utils.log import get_logger

__all__ = ["ActuatorDCMotor"]

logger = get_logger(__name__)


class ActuatorDCMotor(ActuatorBase):
    """
    This element creates a DC motor actuator. See the DC motor technical note for complete mathematical formulations and parameter semantics, but we include a few important notes below. Note that dcmotor does not conform to the affine gain / bias structure of the general actuation model, except for the stateless case.

    - resistance, motorconst and nominal are each optional, but some combination of them is required. See Section 2.1 of the technical note.
    - The control block is selected by input: any subset of `[pos, vel, ff]`, where `pos` and `vel` are setpoint inputs to the on-board PID controller and `ff` is a torque feedforward added to its output; the `voltage` input is the raw terminal voltage. The default is the plain voltage-commanded motor. With `input="none"` the actuator has no control inputs at all and acts as a purely passive device.
    - Optional features include electrical dynamics (inductance), cogging torque, thermal resistance variation, and LuGre friction.

    The underlying general attributes are set to the dcmotor type, and their associated parameter arrays are computed internally:

    | Attribute  | Setting  |
    |:-----------|:---------|
    | `dyntype`  | dcmotor  |
    | `gaintype` | dcmotor  |
    | `biastype` | dcmotor  |
    | `dynprm`   | computed |
    | `gainprm`  | computed |
    | `biasprm`  | computed |
    """

    tag = "dcmotor"

    attributes = (
        *ActuatorBase.attributes,
        "resistance",
        "motorconst",
        "nominal",
        "inductance",
        "thermal",
        "saturation",
        "cogging",
        "lugre",
        "input",
        "controller",
    )

    resistance: float | None = None
    """Terminal resistance R in Ohm. (see tech note, Sections 1.1 and 2.1)"""

    motorconst: Vec2 | None = None
    """Motor constants, defined as `motorconst` = "`Kt Ke`" (N·m/A, equivalently V·s/rad). `Kt` is the torque constant and `Ke` the back-EMF constant; they can differ when magnetic saturation is present. If both are positive, the effective constant is `K=sqrt(Kt Ke)` (geometric mean). If only one is positive, `K` equals that value. If a datasheet specifies the speed constant `Kv` in rad/(V·s), use `Ke=1/Kv`. (see tech note, Sections 1.1 and 2.1)"""

    nominal: Vec3 | None = None
    """Nominal operating point, defined as `nominal` = "`voltage`, `stall_torque`, `no_load_speed`". The compiler derives `K=voltage/no_load_speed` and `R=K·voltage/stall_torque`. (see tech note, Sections 1.1 and 2.1)"""

    inductance: Vec2 = np.array((0, 0))
    """Electrical dynamics, defined as `inductance` = "`L`, `timeconst`" (Henry, seconds). These are alternative specifications: `L` is the winding inductance and `timeconst=L/R` is the electrical time constant. Specify one; if both are given, `L` takes precedence. If both are 0 (the default), no electrical dynamics are modeled and the current is computed algebraically. Adds one activation variable for armature current. (see tech note, Sections 1.1.1 and 2.2)"""

    thermal: Vec6 = np.array((0, 0, 0, 0, 0, 0))
    """Thermal model, defined as `thermal` = "`resistance`, `capacitance`, `timeconst`, `tempcoef`, `reftemp`, `ambient`" (K/W, J/K, s, 1/K, °C, °C). The first three sub-values specify the thermal time constant: timeconst = resistance x capacitance. Specify either timeconst directly, or resistance and capacitance; if all three are given, timeconst takes precedence. If all are 0 (the default), thermal modeling is disabled. Adds one activation variable for winding temperature. (see tech note, Sections 1.3 and 2.3)"""

    saturation: Vec3 = np.array((0, 0, 0))
    """Limits on the actuator, defined as `saturation` = "`torque`, `current`, `current_rate`". torque and current are alternative specifications of the maximum continuous torque: if current is given, `torque = K⋅current`; if both are given, torque takes precedence. Sets forcerange to [`-τ_max`, `τ_max`]. current_rate sets the maximum rate of change of current `(di/dt)_max` (requires inductance). A value of 0 (the default) for any sub-value disables the respective limit. (see tech note, Section 2)"""

    cogging: Vec3 = np.array((0, 0, 0))
    """Cogging torque, defined as `cogging` = "`amplitude`, `poles`, `phase`" (N·m, integer, rad). Adds a position-dependent `torque = amplitude⋅sin(poles⋅θ+phase)`. Disabled when `amplitude = 0` (the default). (see tech note, Sections 1.2 and 2.1)"""

    lugre: Vec5 = np.array((0, 0, 0, 0, 0))
    """LuGre friction, defined as `lugre` = "`stiffness`, `damping`, `coulomb` static stribeck" (N·m/rad, N·m·s/rad, N·m, N·m, rad/s). Disabled when `stiffness = 0` (the default). Adds one activation variable for bristle deflection. Note that the viscous damping coefficient `sigma_2` is not part of the lugre attribute and should be added to the standard actuator damping attribute. (see tech note, Sections 1.4 and 2.4)"""

    input: tuple[ActuatorInput, ...] = (ActuatorInput.VOLTAGE,)
    """Input signature: a space-separated subset of the tokens "pos", "vel", "ff" and "voltage", required in this canonical order. The `pos` and `vel` inputs are setpoints for the on-board controller, and `ff` is a torque feedforward added to its output, as for pid/input. The `voltage` input is different in kind: it is the raw terminal voltage of the physical device, applied downstream of the controller and its Vmax clamp. `input="voltage"` (the default) is the plain voltage-commanded motor. Absent setpoint inputs are fixed at zero. The keyword "none" selects the empty signature: the actuator has no control inputs and is purely passive, useful for modeling friction and cogging as passive joint forces. The terminal voltage is zero, so back-EMF drives current through the (shorted) motor and brakes the joint; setting motorconst to zero disables the electrical branch. (see tech note, Section 2.5)"""

    controller: Vec6 = np.array((0, 0, 0, 0, 0, 0))
    """PID controller parameters, defined as `controller` = "`kp`, `ki`, `kd`, `slewmax`, `Imax`, `Vmax`". The gains are in torque space, as for pid: the controller commands the torque `τ=kp(upos-l)+kd(uvel-l_dot)+k_i*x_I+u_ff` over the inputs present in the input signature, absent setpoints being fixed at zero, and drives the voltage `v=(R/K)*τ+K*l_dot`, the second term compensating back-EMF as in a current-controlled driver: commanded torque is delivered exactly until a limit is reached. Torque-space gains from datasheet voltage-space values are obtained by multiplying by `K/R`. The integrator state `x_I` accumulates position error and requires the `pos` input; controller gains require a controller input and a positive motorconst. A value of 0 (the default) disables the respective feature. When positive, slewmax limits the rate-of-change of the first input (position setpoint in rad/s, or with signatures lacking pos, velocity setpoint or torque feedforward), Imax clamps the integrator state (anti-windup), and Vmax clamps the drive voltage v_max (Volt), upstream of the raw `voltage` input. (see tech note, Section 2.5)"""

    @model_validator(mode="after")
    def validate_motor_definition(self) -> Self:
        """
        Enforce Section 2.1 of the tech note: at least one of resistance, motorconst, or nominal is required to derive the motor properties.
        """
        # Check if all three are their default None state
        if all(v is None for v in (self.resistance, self.motorconst, self.nominal)):
            msg = "DC Motor requires an electromechanical definition. Provide at least one of: 'resistance', 'motorconst', or 'nominal'."
            logger.error(msg)
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_input(self) -> Self:
        """
        Enforce Section 2.5 of the tech note: `input` is an ordered, deduplicated subset of [pos, vel, ff, voltage], or the standalone sentinel `none`.
        """
        if not self.input:
            msg = "input must not be empty. Use ActuatorInput.NONE for a purely passive motor."
            logger.error(msg)
            raise ValueError(msg)

        if ActuatorInput.NONE in self.input:
            if len(self.input) > 1:
                msg = "'none' cannot be combined with other input tokens."
                logger.error(msg)
                raise ValueError(msg)
            return self

        _input = tuple(set(self.input))
        if len(_input) != len(self.input):
            logger.warning(
                f"Duplicate entries in input for DCMotor {self.name}. Proceeding anyway."
            )

        order = [
            ActuatorInput.POSITION,
            ActuatorInput.VELOCITY,
            ActuatorInput.FF,
            ActuatorInput.VOLTAGE,
        ]
        self.input = tuple(sorted(_input, key=order.index))
        return self

    @model_validator(mode="after")
    def validate_controller_gains(self) -> Self:
        """
        Enforce Section 2.5 of the tech note: the integrator requires the pos input, and any nonzero controller gain requires a controller-type input plus a resolvable motor constant.
        """
        kp, ki, kd = self.controller[0], self.controller[1], self.controller[2]

        if ki != 0 and ActuatorInput.POSITION not in self.input:
            msg = "controller ki requires 'pos' in input: the integrator accumulates position error."
            logger.error(msg)
            raise ValueError(msg)

        if kp != 0 or ki != 0 or kd != 0:
            if not {ActuatorInput.POSITION, ActuatorInput.VELOCITY} & set(self.input):
                msg = "Nonzero controller gains (kp, ki, kd) require 'pos' or 'vel' in input."
                logger.error(msg)
                raise ValueError(msg)
            if self.motorconst is None and self.nominal is None:
                msg = (
                    "Nonzero controller gains require a positive motor constant, derived "
                    "from 'motorconst' or 'nominal' ('resistance' alone is not sufficient)."
                )
                logger.error(msg)
                raise ValueError(msg)

        return self
