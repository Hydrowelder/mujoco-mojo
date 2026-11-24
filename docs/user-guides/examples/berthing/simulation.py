"""The whole model: the parts put together, with the `generate` and `runtime` entry points."""

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
US = mojo.UnitSystem.si()


# --8<-- [start:model]
# --8<-- [start:new]
class Berthing(mojo.UserData):
    """Root user data: the parts the runtime needs. `generate` stores it on `mojo_model.user_data`, and the runtime reads it back with `get_user_data`."""

    station: Station
    """The station, with the fixture the arm's base is attached to."""

    arm: Arm
    """The arm, with its joints, servos, end effectors and camera."""

    visitor: Visitor
    """The visiting vehicle, with the fixture the arm grabs."""

    overview: Overview
    """The fixed camera that follows the visitor."""

    capture: Capture
    """The weld that joins the arm to the visitor."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        """Builds every part and puts it in the model."""
        mojo_model.mjcf.model = mojo.ModelName("Berthing")
        mojo_model.mjcf.worldbody = mojo.WorldBody()

        station = Station.new(mojo_model)
        arm = Arm.new(mojo_model, station.fixture)
        Environment.new(mojo_model)
        visitor = Visitor.new(mojo_model)
        overview = Overview.new(mojo_model, arm.free_end)
        capture = Capture.new(mojo_model, arm, visitor)

        return cls(
            station=station,
            arm=arm,
            visitor=visitor,
            overview=overview,
            capture=capture,
        )

    # --8<-- [end:new]

    # --8<-- [start:proximities]
    _hull_clearances: list[mojo.utils.Proximity] = PrivateAttr(default_factory=list)
    """Distances from each boom and the free end effector to the hull, which stop mattering once the visitor is held."""

    _other_clearances: list[mojo.utils.Proximity] = PrivateAttr(default_factory=list)
    """Distances from the arm to the station and to itself, which matter until the end."""

    _gap: mojo.utils.Proximity | None = PrivateAttr(default=None)
    """Distance from the free end effector to the visitor's grapple fixture."""

    def register_proximities(self) -> None:
        """Starts measuring and logging the clearance of the arm from the hull, the station and itself, and the gap to the grapple fixture. Call it inside the runtime manager's `with` block."""
        arm, visitor, station = self.arm, self.visitor, self.station

        # `Proximity` works on mesh volumes, which is why these parts are meshes
        def measure(
            one: mojo.GeomMesh, other: mojo.GeomMesh, visualize: bool = False
        ) -> mojo.utils.Proximity:
            return mojo.utils.Proximity(
                volume_1=one,
                volume_2=other,
                dist_max=MISSION.CLEARANCE_RANGE,
                visualize=visualize,
            ).register_to_rm()

        moving = (arm.boom_1, arm.boom_2, arm.free_effector.geom)
        self._hull_clearances = [
            measure(part, visitor.hull, visualize=True) for part in moving
        ]
        self._other_clearances = [
            *(measure(part, station.cylinder) for part in moving),
            # parts that meet at a joint are left out, since they would always read zero
            measure(arm.free_effector.geom, arm.boom_1),
            measure(arm.free_effector.geom, arm.base_effector.geom),
            measure(arm.boom_2, arm.base_effector.geom),
        ]
        self._gap = mojo.utils.Proximity(
            volume_1=arm.free_effector.geom,
            volume_2=visitor.fixture.geom,
            dist_max=MISSION.GAP_RANGE,
        ).register_to_rm()

        for proximity in (*self._hull_clearances, *self._other_clearances, self._gap):
            proximity.request(channels=["dist", "fromto", "prox_type"])

    def gap(self, state: mojo.MjState) -> float:
        """Distance from the free end effector to the visitor's grapple fixture."""
        assert self._gap  # made by register_proximities
        return self._gap.get_proximity(state)[0]

    def clearance(self, state: mojo.MjState) -> float:
        """Distance from the arm to the closest thing it must keep clear of, which is zero if two of them touch."""
        return min(
            proximity.get_proximity(state)[0]
            for proximity in (*self._hull_clearances, *self._other_clearances)
            if proximity.active
        )

    @property
    def tracking(self) -> bool:
        """Whether the gap and the hull distances are still being measured."""
        return self._gap is not None and self._gap.active

    def stop_proximities(self) -> None:
        """Stops measuring, drawing and logging the gap and the hull distances. Call it once the weld is on: the visitor is held, so there is nothing left to watch there."""
        assert self._gap  # made by register_proximities
        for proximity in (*self._hull_clearances, self._gap):
            proximity.active = False

    # --8<-- [end:proximities]

    def keep_arm_clear(self) -> None:
        """Tells the arm to keep clear of the station and the visitor, except where its free end effector meets the visitor's grapple fixture."""
        self.arm.keep_clear_of(
            self.station.cylinder,
            self.station.fixture.geom,
            self.visitor.hull,
            grapple=self.visitor.fixture.geom,
        )

    def lined_up(self, state: mojo.MjState) -> bool:
        """Whether the free end effector is on the fixture's axis and pointing along it, within the mission's tolerances."""
        off_axis, angle = self.arm.misalignment(state, self.visitor.fixture.site)
        return bool(
            off_axis < MISSION.COLINEAR_DISTANCE
            and angle < np.deg2rad(MISSION.COLINEAR_ANGLE_DEG)
        )

    # --8<-- [start:videos]
    def register_videos(self, mojo_model: mojo.MojoModel, state: mojo.MjState) -> None:
        """Films both cameras into the trial's folder, with a label on every frame. Only the nominal trial films. Call it inside the runtime manager's `with` block, after `register_proximities`."""
        if not mojo_model.is_nominal:
            return

        arm_camera, overview_camera = self.arm.camera.name, self.overview.camera.name
        assert arm_camera
        assert overview_camera

        def label(state: mojo.MjState) -> rt.LabelConfig:
            weld = "on" if self.capture.is_engaged(state) else "off"
            gap = f"gap = {self.gap(state):5.2f} m    " if self.tracking else ""
            return {
                "text": f"t = {state.data.time:6.1f} s    {gap}clearance = {self.clearance(state):4.2f} m    weld {weld}",
                "background_color": mojo.utils.Color.SLATE_900.with_alpha(0.7),
            }

        # the clip starts when first lined up and then carries on, since the arm can drift out of tolerance for a moment as it starts to move
        started = False

        def arm_camera_trigger(state: mojo.MjState) -> bool:
            nonlocal started
            started = started or self.lined_up(state)
            return started and (
                not self.tracking or self.gap(state) < MISSION.RECORD_RANGE
            )

        rt.VideoRecorder(
            path=mojo_model.trial_dir / "arm_camera.mp4",
            camera_name=arm_camera,
            frame_rate=MISSION.ARM_CAMERA_FRAME_RATE,
            show_proximities=True,
            recording_trigger=arm_camera_trigger,
            frame_label=label,
        ).setup(state).register_to_rm()

        rt.VideoRecorder(
            path=mojo_model.trial_dir / "overview.mp4",
            camera_name=overview_camera,
            frame_rate=MISSION.OVERVIEW_FRAME_RATE,
            show_proximities=True,
            frame_label=label,
        ).setup(state).register_to_rm()

    # --8<-- [end:videos]


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
            # the servos are stiff and heavily damped, which only an implicit integrator keeps stable at this timestep
            integrator=mojo.Integrator.IMPLICITFAST,
        )
    )

    # fixed at one meter because the viewer sizes frames and joint axes by the mean body size, which the large station inflates
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
    """Runs the berthing through its phases: approach, capture, berth and release. Each part that needs a control has a method for it, and this only calls them."""
    with runtime_manager as rm:
        # --8<-- [start:setup]
        if rm.signal_manager:
            rm.signal_manager.record_decimation = 10
        berthing = mojo_model.get_user_data(Berthing)
        arm, visitor, capture = berthing.arm, berthing.visitor, berthing.capture
        site = visitor.fixture.site
        arm.register_servos()
        berthing.keep_arm_clear()
        berthing.register_proximities()
        berthing.register_videos(mojo_model, state)

        dt = state.model.opt.timestep
        berth = berthing.station.berth
        phase = Phase.APPROACH
        standoff = MISSION.PRE_STANDOFF
        arrived_at: float | None = None
        released_at: float | None = None
        # --8<-- [end:setup]

        while state.data.time < MISSION.END_TIME:
            # the end effector must be on the fixture's axis and pointing along it before it goes in
            off_axis, angle = arm.misalignment(state, site)
            lined_up = berthing.lined_up(state)

            match phase:
                # --8<-- [start:approach-phase]
                case Phase.APPROACH:
                    # the goal follows the fixture, so the arm keeps up if the visitor drifts
                    remaining = arm.approach(state, site, standoff)
                    if remaining < MISSION.PARKED_TOLERANCE and lined_up:
                        logger.info(
                            f"t={state.data.time:.1f}s: parked, gap {berthing.gap(state):.3f} m, "
                            f"{1000 * off_axis:.1f} mm off the fixture's axis and {np.degrees(angle):.2f} degrees "
                            f"out of line, {berthing.clearance(state):.2f} m of clearance"
                        )
                        phase = Phase.CAPTURE
                # --8<-- [end:approach-phase]

                # --8<-- [start:capture-phase]
                case Phase.CAPTURE:
                    # move in only while lined up, aiming a little past the fixture so the servos' lag cannot stall the end effector short of the capture gap
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

                        # the visitor is held, so its gap and distance to the arm cannot change
                        berthing.stop_proximities()
                        phase = Phase.BERTH

                # --8<-- [end:capture-phase]

                # --8<-- [start:berth-phase]
                case Phase.BERTH:
                    # the weld ties the tip to the visitor's grapple site, so putting the tip on the berthing point puts the visitor there
                    remaining = arm.carry_to(
                        state,
                        berth.rt_pos(state),
                        berth.rt_xmat(state),
                        MISSION.BERTH_SPEED,
                    )
                    if remaining < MISSION.PARKED_TOLERANCE:
                        if arrived_at is None:
                            arrived_at = state.data.time
                            logger.info(
                                f"t={arrived_at:.1f}s: at the berthing point, holding"
                            )
                        if state.data.time - arrived_at > MISSION.HOLD_TIME:
                            capture.release(state)
                            released_at = state.data.time
                            logger.info(f"t={released_at:.1f}s: released")
                            phase = Phase.RELEASE

                case Phase.RELEASE:
                    # nothing holds the visitor now, so it should stay where it was put
                    assert released_at is not None
                    if state.data.time - released_at > MISSION.SETTLE_TIME:
                        break
                # --8<-- [end:berth-phase]

            rm.step(state)

        logger.info(
            f"finished at t={state.data.time:.1f}s with the weld "
            f"{'on' if capture.is_engaged(state) else 'off'}, the visitor's grapple site "
            f"{1000 * np.linalg.norm(site.rt_pos(state) - berth.rt_pos(state)):.1f} mm from the berthing point"
        )

    return mojo_model


# --8<-- [end:runtime]
