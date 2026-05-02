from __future__ import annotations

import numpy as np
from pydantic import model_validator

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.base import ActuatorBase
from mujoco_mojo.typing import ActuatorInput, Vec2, Vec3, Vec5, Vec6

__all__ = ["ActuatorDCMotor"]


class ActuatorDCMotor(ActuatorBase):
    """
    This element creates a DC motor actuator. See the DC motor technical note for complete mathematical formulations and parameter semantics, but we include a few important notes below. Note that dcmotor does not conform to the affine gain / bias structure of the general actuation model, except for the stateless case.

    - resistance, motorconst and nominal are each optional, but some combination of them is required. See Section 2.1 of the technical note.
    - The control input semantic is either the voltage applied to the motor terminals (the default), or a position or velocity target for a PID controller.
    - Optional features include electrical dynamics (inductance), cogging torque, thermal resistance variation, and LuGre friction.

    The underlying general attributes are set to the dcmotor type, and their associated parameter arrays are computed internally:

    | Attribute  | Setting    |
    |:-----------|:-----------|
    | `dyntype`  | dcmotor    |
    | `gaintype` | dcmotor    |
    | `biastype` | dcmotor    |
    | `dynprm`   | calculated |
    | `gainprm`  | calculated |
    | `biasprm`  | calculated |
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

    input: ActuatorInput = ActuatorInput.VOLTAGE
    """Specifies the input signal semantics. In "voltage" mode, the control directly sets applied motor voltage. In "position" or "velocity" modes, the PID controller uses the control as a reference setpoint relative to the joint trajectory. (see tech note, Section 2.5)"""

    controller: Vec6 = np.array((0, 0, 0, 0, 0, 0))
    """PID controller parameters, defined as `controller` = "`kp`, `ki`, `kd`, `slewmax`, `Imax`, `Vmax`". Depending on the input mode, the controller stabilizes either position or velocity. If the input mode is voltage, `kp`, `ki`, `kd` are ignored. `Vmax` sets the maximum drive voltage `v_max` (Volt); in position/velocity modes it clamps the controller output, in voltage mode it clamps the control signal (if `ctrlrange` is also set, the tighter limit wins). A value of 0 (the default) disables the respective feature. When positive, `slewmax` limits the setpoint rate-of-change, Imax clamps the integrator state (anti-windup), and `Vmax` clamps the drive voltage. (see tech note, Section 2.5)"""

    @model_validator(mode="after")
    def validate_motor_definition(self) -> ActuatorDCMotor:
        """
        Enforce Section 2.1 of the tech note: at least one of resistance, motorconst, or nominal is required to derive the motor properties.
        """
        # Check if all three are their default None state
        if all(v is None for v in (self.resistance, self.motorconst, self.nominal)):
            raise ValueError(
                "DC Motor requires an electromechanical definition. Provide at least one of: 'resistance', 'motorconst', or 'nominal'."
            )
        return self
