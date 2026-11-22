"""The mission: the times, distances and speeds that steer the berthing."""

from __future__ import annotations

from enum import StrEnum

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

    APPROACH_SPEED: float = 0.15 * US["m/s"]
    """Speed the end effector closes the last stretch at, once it is lined up."""

    CAPTURE_GAP: float = 0.03 * US.m
    """Gap between the end effector and the grapple fixture at which the capture weld is switched on."""

    OVERSHOOT: float = 0.05 * US.m
    """How far past the grapple fixture the end effector is aimed at the end of the final approach. The servos lag behind their commands, so aiming a little past is what keeps the end effector from stalling just short of the capture gap."""

    PULL_DISTANCE: float = 1.0 * US.m
    """How far the arm pulls the visitor back along the fixture's axis, toward the station, once it has it. A stand-in for the berthing point."""

    HOLD_TIME: float = 3.0 * US.s
    """How long the arm holds the visitor after pulling it in, before the run ends."""

    END_TIME: float = 120.0 * US.s
    """Longest the run may last."""


MISSION = MissionInput()
# --8<-- [end:inputs]


# --8<-- [start:phase]
class Phase(StrEnum):
    """The stages of the berthing."""

    APPROACH = "approach"
    """Slew from the home pose to a spot in front of the grapple fixture, lined up with it."""

    CAPTURE = "capture"
    """Close the last stretch slowly, while lined up, and switch the weld on."""

    BERTH = "berth"
    """Carry the visitor to where it goes and hold."""


# --8<-- [end:phase]
