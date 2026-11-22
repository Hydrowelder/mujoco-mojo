# 7-DOF Arm

!!! abstract

    This guide builds the arm: a shoulder with three degrees of freedom (DOF), two booms, an elbow with one DOF, and a wrist with three DOF, with an end effector at each end. The base end is latched onto the station's fixture, and the free end reaches for the visitor. Each of the seven joints has a position servo, and an inverse-kinematics solver works out the joint angles that move the free end effector to a goal position and orientation.

---

## End Effector

An end effector is a cylinder with a site on its end. To grab a grapple fixture, the arm lines this site up with the fixture's site. The arm has the same end effector at each end.

??? example "End Effector Inputs"

    ``` python
    --8<-- "docs/user-guides/examples/berthing/end_effector.py:inputs"
    ```

``` python
--8<-- "docs/user-guides/examples/berthing/end_effector.py:end_effector"
```

A frame at the end effector's root holds the cylinder and the site. Its X axis points along the end effector, from the root toward the site, and the site has the same orientation. When the arm grabs a fixture, the two sites line up and their X axes point the same way. As with the fixture, `mount` places the root and sets which way it points, and `name` prefixes everything the end effector makes.

---

## Inputs and Home Pose

Inputs for the arm hold the dimensions and masses of its parts, the servos, the camera, and the home pose.

??? example "Arm Inputs"

    ``` python
    --8<-- "docs/user-guides/examples/berthing/arm.py:inputs"
    ```

Built bent into a V that points toward the visitor, the arm starts in its home pose, and every joint angle is measured from it. The home angles are part of the joint bodies' poses, so a servo commanded to zero holds the arm in the home pose.

---

## Joints

A few small helpers build the joints, and each is used many times:

- **Housings**, one each for roll, yaw and pitch, are the shapes at a joint. They are colored by the axis they turn about, red for roll (X), green for pitch (Y) and blue for yaw (Z), which makes each joint's axis visible in the viewer. The shoulder and the wrist have the same three, and building each housing once means the two ends cannot differ.
- `hinge` makes every joint. It gives each one the arm's armature, an added inertia that keeps the light joints stable under the servos' high gains, so the servos can be stiff.
- `turned` places a joint's body at its home angle. The arm is built bent, so each body is turned from straight by its home angle about its own axis. This is how the home pose gets into the model.
- `out_of_station` places the whole arm. The station's fixture points into the station, but the arm should point out of it, so the first body is given a half turn about Y, and everything after it follows.

??? example "Helper Code"

    ``` python
    --8<-- "docs/user-guides/examples/berthing/arm.py:helpers"
    ```

---

## Nesting the Bodies

This arm is a chain of bodies, one for each joint, starting at the station. Each body is a child of the one before it, so each joint turns everything after it. The shoulder has three DOF, so it has three bodies: roll, yaw and pitch. Their axes meet at one point:

``` python
--8<-- "docs/user-guides/examples/berthing/arm.py:shoulder"
```

The rest of the chain follows the same pattern:

- **First boom:** a shape on the pitch body.
- **Elbow:** one body, which carries the elbow housing and the second boom.
- **Wrist:** three bodies, the same as the shoulder, hanging from the elbow body.
- **Free end effector:** attached to the last wrist body.
- **Base end effector:** latched onto the station's fixture, with its end at the fixture's site. The whole chain sits in the fixture's frame.
- **Reach envelope:** a translucent hemisphere as large as the arm is long, which shows how far the arm can reach. For visualization only.

---

## Servos

Each joint gets a position servo. A servo pulls its joint toward a commanded angle using some gain, damping, and range:

``` python
--8<-- "docs/user-guides/examples/berthing/arm.py:servos"
```

---

## Driving the Servos

Commanded angles live in a list on the arm, one for each joint. Each servo gets an `ActuatorControl`, which copies its joint's commanded angle into the control array every step. `ActuatorControl` is one of Mojo's [loads](../../workflow/runtime-script.md#defining-loads).

``` python
--8<-- "docs/user-guides/examples/berthing/arm.py:register"
```

`slew` moves the commanded angles toward goal angles, one step at a time, at a limited rate. The joint with the furthest to go moves at the full rate, and the others move slower, so all of them arrive together. `move_to` asks the solver for the angles that put the end effector at a goal, then calls `slew` with them:

``` python
--8<-- "docs/user-guides/examples/berthing/arm.py:slew"
```

`approach` does the same for a goal in front of a site, with the end effector facing it. The goal follows the site, so the arm keeps up if the visitor drifts:

``` python
--8<-- "docs/user-guides/examples/berthing/arm.py:approach"
```

`carry_to` is like `move_to`, but the goal travels to the target in a straight line at a set speed. That is how the arm carries the visitor. `misalignment` measures how far the end effector is from lining up with a site, and the runtime uses it to decide when the arm can move in.

---

## Solving for the Angles

Damped least squares solves for the angles. Each iteration moves the joints a small step that the Jacobian says brings the end effector closer to the goal, and it repeats until the end effector is close enough.

- It works on a private copy of the state, so it does not disturb the running simulation.
- It starts from its own last answer, so a goal that holds still costs almost nothing.
- A goal does not fix all seven joints, because the elbow can swivel about the line from the shoulder to the wrist. A gentle pull toward home picks one answer from the many.

??? example "Solver Code"

    ``` python
    --8<-- "docs/user-guides/examples/berthing/arm.py:solve"
    ```

---

## Camera

Only the free end has a camera. It is placed in the end effector's frame, so it turns with the wrist roll, and it is off the axis, so the end effector stays out of the picture. The [Video Recording](../../features/video-recording.md) guide covers filming a camera.

``` python
--8<-- "docs/user-guides/examples/berthing/arm.py:camera"
```

---

!!! success

    That completes the arm, which can now be driven to a goal. In the last guide we write the runtime that runs the berthing.
