from __future__ import annotations

from typing import Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.types import Mode

__all__ = ["LengthRange"]


class LengthRange(XMLModel):
    """This element controls the computation of actuator length ranges. For an overview of this functionality see Length range section. Note that if this element is omitted the defaults shown below still apply. In order to disable length range computations altogether, include this element and set mode=”none”."""

    attributes = (
        "mode",
        "useexisting",
        "uselimit",
        "accel",
        "maxforce",
        "timeconst",
        "timestep",
        "inttotal",
        "interval",
        "tolrange",
    )

    mode: Optional[Mode] = None
    """Determines the type of actuators to which length range computation is applied. “none” disables this functionality. “all” applies it to all actuators. “muscle” applies it to actuators whose gaintype or biastype is set to “muscle”. “muscleuser” applies it to actuators whose gaintype or biastype is set to either “muscle” or “user”. The default is “muscle” because MuJoCo’s muscle model requires actuator length ranges to be defined."""
    useexisting: Optional[bool] = None
    """If this attribute is “true” and the length range for a given actuator is already defined in the model, the existing value will be used and the automatic computation will be skipped. The range is considered defined if the first number is smaller than the second number. The only reason to set this attribute to “false” is to force re-computation of actuator length ranges - which is needed when the model geometry is modified. Note that the automatic computation relies on simulation and can be slow, so saving the model and using the existing values when possible is recommended."""
    uselimit: Optional[bool] = None
    """If this attribute is “true” and the actuator is attached to a joint or a tendon which has limits defined, these limits will be copied into the actuator length range and the automatic computation will be skipped. This may seem like a good idea but note that in complex models the feasible range of tendon actuators depends on the entire model, and may be smaller than the user-defined limits for that tendon. So the safer approach is to set this to “false”, and let the automatic computation discover the feasible range."""
    accel: Optional[float] = None
    """This attribute scales the forces applied to the simulation in order to push each actuator to its smallest and largest length. The force magnitude is computed so that the resulting joint-space acceleration vector has norm equal to this attribute."""
    maxforce: Optional[float] = None
    """The force computed via the accel attribute above can be very large when the actuator has very small moments. Such a force will still produce reasonable acceleration (by construction) but large numbers could cause numerical issues. Although we have never observed such issues, the present attribute is provided as a safeguard. Setting it to a value larger than 0 limits the norm of the force being applied during simulation. The default setting of 0 disables this safeguard."""
    timeconst: Optional[float] = None
    """The simulation is damped in a non-physical way so as to push the actuators to their limits without the risk of instabilities. This is done by simply scaling down the joint velocity at each time step. In the absence of new accelerations, such scaling will decrease the velocity exponentially. The timeconst attribute specifies the time constant of this exponential decrease, in seconds."""
    timestep: Optional[float] = None
    """The timestep used for the internal simulation. Setting this to 0 will cause the model timestep to be used. The latter is not the default because models that can go unstable usually have small timesteps, while the simulation here is artificially damped and very stable. To speed up the length range computation, users can attempt to increase this value."""
    inttotal: Optional[float] = None
    """The total time interval (in seconds) for running the internal simulation, for each actuator and actuator direction. Each simulation is initialized at qpos0. It is expected to settle after inttotal time has passed."""
    interval: Optional[float] = None
    """The time interval at the end of the simulation over which length data is collected and analyzed. The maximum (or respectively minimum) length achieved during this interval is recorded. The difference between the maximum and minimum is also recorded and is used as a measure of divergence. If the simulation settles, this difference will be small. If it is not small, this could be because the simulation has not yet settled - in which case the above attributes should be adjusted - or because the model does not have sufficient joint and tendon limits and so the actuator range is effectively unlimited. Both of these conditions cause the same compiler error. Recall that contacts are disabled in this simulation, so joint and tendon limits as well as overall geometry are the only things that can prevent actuators from having infinite length."""
    tolrange: Optional[float] = None
    """This determines the threshold for detecting divergence and generating a compiler error. The range of actuator lengths observed during interval is divided by the overall range computed via simulation. If that value is larger than tolrange, a compiler error is generated. So one way to suppress compiler errors is to simply make this attribute larger, but in that case the results could be inaccurate."""
