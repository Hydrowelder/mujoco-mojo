"""The whole model: the components put together, and the `generate` entry point that builds it."""

from __future__ import annotations

from typing import Self

import numpy as np
from arm import Arm
from capture import Capture
from environment import Environment
from mission import MISSION, Phase
from overview import Overview
from pydantic import PrivateAttr
from station import Station
from visitor import Visitor

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

logger = mojo.utils.get_logger(__name__)
US = mojo.UnitSystem.si()  # define a unit system used throughout the model


# --8<-- [start:model]
class Berthing(mojo.UserData):
    """Root user data for the whole model, which collects the parts the runtime will need. `generate` stores it on `mojo_model.user_data`, and the runtime reads it back with `mojo_model.get_user_data(Berthing)`."""

    station: Station
    """The station, with the grapple fixture the arm is latched onto."""

    arm: Arm
    """The arm, with its joints and servos, its two end effectors and its camera."""

    visitor: Visitor
    """The visiting vehicle, with the grapple fixture the arm grabs."""

    overview: Overview
    """The fixed camera that follows the visitor."""

    capture: Capture
    """The weld that joins the arm to the visitor, which starts switched off."""

    _clearances: list[mojo.utils.Proximity] = PrivateAttr(default_factory=list)
    """The distance from each part of the arm that could hit the hull to the hull, made by `register_proximities`."""

    _gap: mojo.utils.Proximity | None = PrivateAttr(default=None)
    """The distance from the free end effector to the visitor's grapple fixture, made by `register_proximities`."""

    def register_proximities(self) -> None:
        """
        Starts measuring the two distances the mission watches, and logs them. Call it inside the runtime manager's `with` block.

        The clearance is how close each boom and the end effector are to the visitor's hull, which has to stay above zero. The gap is how far the end effector is from the visitor's grapple fixture, which the arm is closing. `Proximity` measures between mesh volumes, which is why all of these parts are builtin meshes: it uses the convex hull of each, which is exact for the cylinders here.
        """
        arm, visitor = self.arm, self.visitor
        self._clearances = [
            mojo.utils.Proximity(
                volume_1=part, volume_2=visitor.hull, dist_max=MISSION.CLEARANCE_RANGE
            ).register_to_rm()
            for part in (arm.boom_1, arm.boom_2, arm.free_effector.geom)
        ]
        self._gap = mojo.utils.Proximity(
            volume_1=arm.free_effector.geom,
            volume_2=visitor.fixture.geom,
            dist_max=MISSION.GAP_RANGE,
        ).register_to_rm()

        for proximity in (*self._clearances, self._gap):
            proximity.request(channels=["dist", "fromto", "prox_type"])

    def gap(self, state: mojo.MjState) -> float:
        """The distance from the free end effector to the visitor's grapple fixture, in meters."""
        assert self._gap  # made by register_proximities
        return self._gap.get_proximity(state)[0]

    def clearance(self, state: mojo.MjState) -> float:
        """The distance from the closest of the booms and the free end effector to the visitor's hull, in meters, which is capped at `MISSION.CLEARANCE_RANGE`."""
        return min(part.get_proximity(state)[0] for part in self._clearances)

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        """Builds every component and puts it in the model."""
        mojo_model.mjcf.model = mojo.ModelName("Berthing")
        mojo_model.mjcf.worldbody = mojo.WorldBody()

        station = Station.new(mojo_model)
        arm = Arm.new(mojo_model, station.fixture)
        Environment.new(mojo_model)
        visitor = Visitor.new(mojo_model)
        overview = Overview.new(mojo_model, visitor.body)
        capture = Capture.new(mojo_model, arm, visitor)

        return cls(
            station=station,
            arm=arm,
            visitor=visitor,
            overview=overview,
            capture=capture,
        )


# --8<-- [end:model]


# --8<-- [start:generate]
def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Generates the MJCF model."""
    mojo_model.us = US
    mojo_model.user_data = Berthing.new(mojo_model)

    mojo_model.mjcf.options.append(
        mojo.Option(
            timestep=0.002 * US.s,
            gravity=np.array((0, 0, 0)) * US["m/s**2"],
            # the arm's servos are stiff and heavily damped, so the integrator treats that damping implicitly
            integrator=mojo.Integrator.IMPLICITFAST,
            # nothing in this model is meant to touch, so contacts are off (the parts overlap in places, which would push them apart) and the distances that matter are measured by Proximity; the capture weld is a constraint, not a contact, so it still works
            flag=mojo.Flag(contact=mojo.typing.EnableDisable.DISABLE),
        )
    )

    # a viewer sizes its frames, joint axes and other markers in units of the model's mean body size, which MuJoCo works out on its own (and the big station makes it large), so it is fixed at one meter and the scales below are lengths in meters
    mojo_model.mjcf.statistics.append(mojo.Statistic(meansize=1.0 * US.m))
    mojo_model.mjcf.visuals.append(
        mojo.Visual(scale=mojo.VisualScale(framelength=0.5, framewidth=0.03))
    )
    return mojo_model


# --8<-- [end:generate]


# --8<-- [start:runtime]
def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    """Runs the berthing. Each part of the model that needs a control applied has a method of its own for it, and this only calls them."""
    with runtime_manager as rm:
        berthing = mojo_model.get_user_data(Berthing)
        arm, visitor, capture = berthing.arm, berthing.visitor, berthing.capture
        site = visitor.fixture.site
        arm.register_servos()
        berthing.register_proximities()

        dt = state.model.opt.timestep
        phase = Phase.APPROACH
        standoff = (
            MISSION.PRE_STANDOFF
        )  # how far in front of the fixture the tip is aimed
        goal_tip, goal_frame = (
            np.zeros(3),
            np.eye(3),
        )  # where the visitor is carried to, set at capture
        arrived_at: float | None = None

        while state.data.time < MISSION.END_TIME:
            # the end effector has to be on the fixture's axis and pointing along it before it goes in, not just near a spot on it
            off_axis, angle = arm.misalignment(state, site)
            lined_up = off_axis < MISSION.COLINEAR_DISTANCE and angle < np.deg2rad(
                MISSION.COLINEAR_ANGLE_DEG
            )

            match phase:
                case Phase.APPROACH:
                    # the goal is worked out from where the grapple fixture is now, so the arm keeps following it if the visitor drifts
                    remaining = arm.approach(state, site, standoff)
                    if remaining < MISSION.PARKED_TOLERANCE and lined_up:
                        logger.info(
                            f"t={state.data.time:.1f}s: parked, gap {berthing.gap(state):.3f} m, "
                            f"{1000 * off_axis:.1f} mm off the fixture's axis and {np.degrees(angle):.2f} degrees "
                            f"out of line, {berthing.clearance(state):.2f} m clear of the hull"
                        )
                        phase = Phase.CAPTURE

                case Phase.CAPTURE:
                    # creep in, but only while lined up, and aim a little past the fixture so the servos' lag never stalls the end effector short of the capture gap
                    if lined_up:
                        standoff = max(
                            standoff - MISSION.APPROACH_SPEED * dt, -MISSION.OVERSHOOT
                        )
                    arm.approach(state, site, standoff)

                    gap = berthing.gap(state)
                    if gap < MISSION.CAPTURE_GAP and lined_up:
                        capture.engage(state)
                        logger.info(
                            f"t={state.data.time:.1f}s: captured, gap {gap * 1000:.1f} mm, "
                            f"{1000 * off_axis:.1f} mm off the fixture's axis and {np.degrees(angle):.2f} degrees out of line"
                        )

                        # from here the fixture goes wherever the tip goes, so the goal is fixed in the world: back along the fixture's axis, with the same orientation. The frame is copied because `rt_xmat` is a view of the live data, which would follow the visitor round instead of holding it
                        goal_frame = site.rt_xmat(state).copy()
                        goal_tip = (
                            site.rt_pos(state)
                            - MISSION.PULL_DISTANCE * goal_frame[:, 0]
                        )
                        phase = Phase.BERTH

                case Phase.BERTH:
                    remaining = arm.move_to(state, goal_tip, goal_frame)
                    if remaining < MISSION.PARKED_TOLERANCE:
                        if arrived_at is None:
                            arrived_at = state.data.time
                            logger.info(f"t={arrived_at:.1f}s: pulled in, holding")
                        if state.data.time - arrived_at > MISSION.HOLD_TIME:
                            break

            rm.step(state)

        logger.info(
            f"finished at t={state.data.time:.1f}s with the weld "
            f"{'on' if capture.is_engaged(state) else 'off'}"
        )

    return mojo_model


# --8<-- [end:runtime]
