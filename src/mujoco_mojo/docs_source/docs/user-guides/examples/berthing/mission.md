# Mission Runtime

!!! abstract

    This guide writes the runtime: a loop that steps the model through four phases: approach, capture, berth, and release. It calls the arm's methods from the [last guide](7-dof-arm.md#driving-the-servos) and puts the [Proximity](../../features/proximity/proximity.md), [Equality Constraints](../../features/equality-constraints/equality-constraints.md) and [Video Recording](../../features/video-recording/video-recording.md) guides to work.

---

## Mission Inputs

Distances, speeds and times that steer the berthing are in one input class, so they can be tuned in one place.

??? example "Mission Inputs"

    ``` python
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
    ```

---

## Phases

The berthing has four phases:

- **Approach:** move to a spot in front of the grapple fixture and line up with it.
- **Capture:** move in slowly while lined up, then switch the weld on.
- **Berth:** carry the visitor to the berthing point and hold it there.
- **Release:** wait for the visitor to settle once the weld is off.

An enum names them:

``` python
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


```

---

## Setup

The runtime opens the runtime manager, reads the `Berthing` user data back, and hands over the controls and the measurements:

``` python
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
```

- `record_decimation` records telemetry every tenth step, which keeps the files small.
- `arm.register_servos()` gives each servo an `ActuatorControl`, as in the [arm guide](7-dof-arm.md#driving-the-servos).
- `berthing.keep_arm_clear()` tells the arm to keep out of the station and the visitor's hull, which the [arm guide](7-dof-arm.md#inverse-kinematics) covers.
- `berthing.register_proximities()` starts the distance measurements.
- `berthing.register_videos(...)` sets up the two cameras.

Each part that needs a control has a method for it, so the loop only calls them.

---

## Loop

Each step, the loop works out how well the end effector lines up with the fixture, acts on the current phase, and steps the model. The full runtime is here:

??? example "Runtime Code"

    ``` python
    def runtime(
        mojo_model: mojo.MojoModel,
        runtime_manager: rt.RuntimeManager,
        state: mojo.MjState,
        *args,
        **kwargs,
    ) -> mojo.MojoModel:
        """Runs the berthing through its phases: approach, capture, berth and release. Each part that needs a control has a method for it, and this only calls them."""
        with runtime_manager as rm:
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

            while state.data.time < MISSION.END_TIME:
                # the end effector must be on the fixture's axis and pointing along it before it goes in
                off_axis, angle = arm.misalignment(state, site)
                lined_up = berthing.lined_up(state)

                match phase:
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

                rm.step(state)

            logger.info(
                f"finished at t={state.data.time:.1f}s with the weld "
                f"{'on' if capture.is_engaged(state) else 'off'}, the visitor's grapple site "
                f"{1000 * np.linalg.norm(site.rt_pos(state) - berth.rt_pos(state)):.1f} mm from the berthing point"
            )

        return mojo_model


    ```

Approach is the first phase:

``` python
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
```

In the approach, the goal follows the fixture, so the arm keeps up if the visitor drifts. The arm counts as parked when it is close to its parking spot and lined up, which means on the fixture's axis and pointing along it, within the mission's tolerances.

---

## Capture

``` python
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

```

- The end effector moves in only while it is lined up.
- It aims a little past the fixture, so the servos' lag cannot stall it short of the capture gap.
- When the gap is small enough and the arm is lined up, `capture.engage` switches the weld on.
- The visitor is then held, so the gap is zero and its distance to the arm cannot change, and `stop_proximities` stops measuring those.

---

## Berth and Release

``` python
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
```

- The weld ties the end effector to the visitor's grapple site, so putting the end effector on the berthing point puts the visitor there.
- `carry_to` moves the goal to the berthing point in a straight line at a set speed.
- After a hold, `capture.release` switches the weld off.
- The release phase waits for the visitor to settle, and then the loop ends.

---

## Distances

[Proximity](../../features/proximity/proximity.md) measures ten pairs of mesh volumes, nine for the **clearance** and one for the **gap**.

The clearance pairs are everything the arm must keep clear of:

- the first boom, the second boom and the free end effector, each against the visitor's hull
- the same three parts, each against the station's cylinder
- the arm against itself: the free end effector against the first boom and the base end effector, and the second boom against the base end effector. Parts that meet at a joint are left out, since they would always read zero.

The gap pair is the free end effector against the visitor's grapple fixture. `clearance` is the smallest of the nine clearance pairs, and a value of zero means two parts touch.

Once the weld is on, the visitor moves with the arm, so the gap and the hull cannot change any more. `stop_proximities` then sets the `active` flag of those pairs to `False`. The station and arm pairs keep measuring, since the arm still has to clear the station while it carries the visitor.

The housings at the joints are primitive shapes, so these pairs do not see them. [`mink`](7-dof-arm.md#inverse-kinematics) does, since it works from the whole model, which is why the arm also steers clear of the station and the hull on its own.

??? example "Distance Code"

    ``` python
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

    ```

---

## Capture Weld

The capture weld joins the end effector's site to the visitor's grapple site. It is off until the capture, as in the [Equality Constraints](../../features/equality-constraints/equality-constraints.md) guide, and a small class wraps its three actions:

``` python
class Capture(mojo.UserData):
    """A weld between the end effector's tip and the visitor's grapple site, switched off until the capture."""

    weld: mojo.EqualityWeldSite
    """The weld, inactive at the start."""

    def engage(self, state: mojo.MjState) -> None:
        """Switches the weld on, so the visitor goes wherever the arm goes."""
        self.weld.enable(state)

    def release(self, state: mojo.MjState) -> None:
        """Switches the weld off, which lets the visitor go."""
        self.weld.disable(state)

    def is_engaged(self, state: mojo.MjState) -> bool:
        """Whether the weld is on."""
        return self.weld.is_active(state)

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel, arm: Arm, visitor: Visitor) -> Self:
        """Makes the weld and adds it to the model."""
        tip = arm.free_effector.tip.name
        grapple = visitor.fixture.site.name
        assert tip
        assert grapple

        weld = mojo.EqualityWeldSite(
            name=mojo.EqualityName("capture"),
            site1=tip,
            site2=grapple,
            active=False,
        )
        mojo_model.mjcf.equalities.append(mojo.Equality(welds=[weld]))

        return cls(weld=weld)


```

---

## Videos

[Video Recording](../../features/video-recording/video-recording.md) films two cameras, the arm camera and the overview camera, into the trial's folder. Only the nominal trial films. Each frame carries a label with the time, the gap, the clearance and whether the weld is on. After the capture the gap is no longer measured, so the label drops it.

The overview camera records the whole run. The arm camera starts the first time the end effector lines up with the fixture and keeps going from there, since the arm can drift out of tolerance for a moment as it starts to move.

??? example "Video Code"

    ``` python
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

    ```

---

## Running It

Open the example in Reloaded:

``` bash linenums="0"
mujoco-mojo examples run berthing
```

The runtime logs each milestone: parked, captured, at the berthing point, released and finished. The last line says how far the visitor's grapple site ended up from the berthing point.

---

!!! success

    That completes the berthing walkthrough. To change the inputs in `mission.py` and see how the run changes, copy the `berthing` folder out of the package and run your copy from the folder above it with `mujoco-mojo reloaded -g berthing.generate -r berthing.runtime`.
