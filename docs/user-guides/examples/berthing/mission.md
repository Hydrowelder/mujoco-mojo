# Mission Runtime

!!! abstract

    This guide writes the runtime: a loop that steps the model through four phases: approach, capture, berth, and release. It calls the arm's methods from the [last guide](7-dof-arm.md#driving-the-servos) and puts the [Proximity](../../features/proximity.md), [Equality Constraints](../../features/equality-constraints.md) and [Video Recording](../../features/video-recording.md) guides to work.

---

## Mission Inputs

Distances, speeds and times that steer the berthing are in one input class, so they can be tuned in one place.

??? example "Mission Inputs"

    ``` python
    --8<-- "docs/user-guides/examples/berthing/mission.py:inputs"
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
--8<-- "docs/user-guides/examples/berthing/mission.py:phase"
```

---

## Setup

The runtime opens the runtime manager, reads the `Berthing` user data back, and hands over the controls and the measurements:

``` python
--8<-- "docs/user-guides/examples/berthing/simulation.py:setup"
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
    --8<-- "docs/user-guides/examples/berthing/simulation.py:runtime"
    ```

Approach is the first phase:

``` python
--8<-- "docs/user-guides/examples/berthing/simulation.py:approach-phase"
```

In the approach, the goal follows the fixture, so the arm keeps up if the visitor drifts. The arm counts as parked when it is close to its parking spot and lined up, which means on the fixture's axis and pointing along it, within the mission's tolerances.

---

## Capture

``` python
--8<-- "docs/user-guides/examples/berthing/simulation.py:capture-phase"
```

- The end effector moves in only while it is lined up.
- It aims a little past the fixture, so the servos' lag cannot stall it short of the capture gap.
- When the gap is small enough and the arm is lined up, `capture.engage` switches the weld on.
- The visitor is then held, so the gap is zero and its distance to the arm cannot change, and `stop_proximities` stops measuring those.

---

## Berth and Release

``` python
--8<-- "docs/user-guides/examples/berthing/simulation.py:berth-phase"
```

- The weld ties the end effector to the visitor's grapple site, so putting the end effector on the berthing point puts the visitor there.
- `carry_to` moves the goal to the berthing point in a straight line at a set speed.
- After a hold, `capture.release` switches the weld off.
- The release phase waits for the visitor to settle, and then the loop ends.

---

## Distances

[Proximity](../../features/proximity.md) measures ten pairs of mesh volumes, nine for the **clearance** and one for the **gap**.

The clearance pairs are everything the arm must keep clear of:

- the first boom, the second boom and the free end effector, each against the visitor's hull
- the same three parts, each against the station's cylinder
- the arm against itself: the free end effector against the first boom and the base end effector, and the second boom against the base end effector. Parts that meet at a joint are left out, since they would always read zero.

The gap pair is the free end effector against the visitor's grapple fixture. `clearance` is the smallest of the nine clearance pairs, and a value of zero means two parts touch.

Once the weld is on, the visitor moves with the arm, so the gap and the hull cannot change any more. `stop_proximities` then sets the `active` flag of those pairs to `False`. The station and arm pairs keep measuring, since the arm still has to clear the station while it carries the visitor.

The housings at the joints are primitive shapes, so these pairs do not see them. [`mink`](7-dof-arm.md#inverse-kinematics) does, since it works from the whole model, which is why the arm also steers clear of the station and the hull on its own.

??? example "Distance Code"

    ``` python
    --8<-- "docs/user-guides/examples/berthing/simulation.py:proximities"
    ```

---

## Capture Weld

The capture weld joins the end effector's site to the visitor's grapple site. It is off until the capture, as in the [Equality Constraints](../../features/equality-constraints.md) guide, and a small class wraps its three actions:

``` python
--8<-- "docs/user-guides/examples/berthing/capture.py:capture"
```

---

## Videos

[Video Recording](../../features/video-recording.md) films two cameras, the arm camera and the overview camera, into the trial's folder. Only the nominal trial films. Each frame carries a label with the time, the gap, the clearance and whether the weld is on. After the capture the gap is no longer measured, so the label drops it.

The overview camera records the whole run. The arm camera starts the first time the end effector lines up with the fixture and keeps going from there, since the arm can drift out of tolerance for a moment as it starts to move.

??? example "Video Code"

    ``` python
    --8<-- "docs/user-guides/examples/berthing/simulation.py:videos"
    ```

---

## Running It

Run the Reloaded script from the example's folder:

``` bash linenums="0"
./reloaded.sh
```

The runtime logs each milestone: parked, captured, at the berthing point, released and finished. The last line says how far the visitor's grapple site ended up from the berthing point.

---

!!! success

    That completes the berthing walkthrough. Change the inputs in `mission.py` and see how the run changes.
