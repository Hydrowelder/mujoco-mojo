"""The mission: the times, distances and speeds that steer the berthing."""

from __future__ import annotations

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()  # define a unit system used throughout the model


# --8<-- [start:inputs]
class MissionInput(mojo.UserData):
    """Distances and times that steer the berthing."""

    PRE_STANDOFF: float = 1.5 * US.m
    """How far in front of the grapple fixture the arm parks before the final approach."""

    PARKED_TOLERANCE: float = 0.01 * US.m
    """How close the tip must get to its parking spot to count as parked."""

    COLINEAR_DISTANCE: float = 0.01 * US.m
    """How far off the grapple fixture's axis the tip may be and still count as lined up with it."""

    COLINEAR_ANGLE_DEG: float = 1.0
    """How far, in degrees, the tip's axis may be turned from the grapple fixture's and still count as lined up with it."""

    CLEARANCE_RANGE: float = 3.0 * US.m
    """How far out the clearance between the arm and the hull is measured exactly. Beyond this a part is only known to be at least this far, which is all that matters for clearance."""

    GAP_RANGE: float = 10.0 * US.m
    """How far out the gap between the end effector and the grapple fixture is measured exactly, which covers the whole approach."""

    END_TIME: float = 30.0 * US.s
    """Longest the run may last."""


MISSION = MissionInput()
# --8<-- [end:inputs]
