"""The distances, speeds and times that steer the berthing, and its phases."""

from __future__ import annotations

from enum import StrEnum

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()


# --8<-- [start:inputs]
class MissionInput(mojo.UserData):
    """Distances, speeds and times that steer the berthing."""

    PRE_STANDOFF: float = 1.5 * US.m
    """How far in front of the grapple fixture the arm parks."""

    PARKED_TOLERANCE: float = 0.01 * US.m
    """How close the tip must get to its parking spot to count as parked."""

    COLINEAR_DISTANCE: float = 0.01 * US.m
    """How far off the fixture's axis the tip may be and still count as lined up."""

    COLINEAR_ANGLE_DEG: float = 1.0
    """How far, in degrees, the tip's axis may turn from the fixture's and still count as lined up."""

    CLEARANCE_RANGE: float = 3.0 * US.m
    """Range of the clearance measurements: when two parts are further apart than this, the distance is only estimated."""

    GAP_RANGE: float = 10.0 * US.m
    """Range of the gap measurement: when the end effector and the grapple fixture are further apart than this, the distance is only estimated."""

    RECORD_RANGE: float = 2.0 * US.m
    """The arm camera films only while the gap is below this."""

    ARM_CAMERA_FRAME_RATE: float = 20
    """Frame rate of the arm camera's video, in frames per unit of simulation time."""

    OVERVIEW_FRAME_RATE: float = 10
    """Frame rate of the overview camera's video, in frames per unit of simulation time."""

    APPROACH_SPEED: float = 0.15 * US["m/s"]
    """Speed the end effector closes in on the fixture at."""

    CAPTURE_GAP: float = 0.03 * US.m
    """Gap at which the capture weld is switched on."""

    OVERSHOOT: float = 0.05 * US.m
    """How far past the fixture the end effector is aimed, so the servos' lag cannot stall it short of the capture gap."""

    BERTH_SPEED: float = 0.2 * US["m/s"]
    """Speed the arm carries the visitor at."""

    HOLD_TIME: float = 3.0 * US.s
    """How long the arm holds the visitor at the berthing point before letting go."""

    SETTLE_TIME: float = 2.0 * US.s
    """How long the run goes on after the release."""

    END_TIME: float = 120.0 * US.s
    """Longest the run may last."""


MISSION = MissionInput()
# --8<-- [end:inputs]


# --8<-- [start:phase]
class Phase(StrEnum):
    """The phases of the berthing."""

    APPROACH = "approach"
    """Move to a spot in front of the grapple fixture and line up with it."""

    CAPTURE = "capture"
    """Move in slowly while lined up, and switch the weld on."""

    BERTH = "berth"
    """Carry the visitor to the berthing point and hold it there."""

    RELEASE = "release"
    """Wait for the visitor to settle once the weld is off."""


# --8<-- [end:phase]
