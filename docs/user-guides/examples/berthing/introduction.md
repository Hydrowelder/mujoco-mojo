# Berthing

!!! abstract

    This guide walks through a model of a robotic arm, in the style of Canadarm2, that grabs a visiting vehicle, carries it to a berthing point on a space station and lets it go. The arm has seven joints, each driven by a position servo, and [`mink`](https://kevinzakka.github.io/mink/), an inverse-kinematics library built on MuJoCo, calculates the joint angles that move the arm's end effector to a goal position and orientation.

    <figure markdown="span">
        <video controls muted loop playsinline width="80%">
            <source src="overview.mp4" type="video/mp4">
        </video>
        <figcaption>The berthing run, filmed by its overview camera. The label shows the gap to the grapple fixture, the arm's clearance and whether the weld is on. Once the vehicle is grabbed, the gap is no longer measured and the label drops it.</figcaption>
    </figure>

This example puts the feature guides to work:

- [Proximity](../../features/proximity.md) measures the gap between the arm and the grapple fixture it is closing on, and the clearance of the arm from the vehicle, the station and itself.
- [Equality Constraints](../../features/equality-constraints.md) provide the capture weld, which is off until the arm is in place and then holds the vehicle to the arm.
- [Video Recording](../../features/video-recording.md) films the run from a camera on the arm and from a fixed camera that follows the vehicle.

It also follows the `Handoff` pattern of the [runtime script](../../workflow/runtime-script.md): the generator keeps what the runtime will need in `user_data`, and the runtime reads it back. And it shows how Mojo works with an established MuJoCo library: `mink` moves the arm, and it reads the same compiled model that Mojo builds. Install it with `pip install mink` before running the example.

---

## Project Layout

Code for the example lives in [the berthing folder](https://github.com/Hydrowelder/mujoco-mojo/tree/master/docs/user-guides/examples/berthing){target="_blank"}, with one file for each part of the model:

| File              | Holds                                                                                                        |
| :---------------- | :----------------------------------------------------------------------------------------------------------- |
| `simulation.py`   | The parts put together, with the `generate` and `runtime` entry points.                                      |
| `mission.py`      | The distances, speeds and times that steer the berthing, and its phases.                                     |
| `station.py`      | The station: a cylinder with a grapple fixture on top for the arm's base, and a berthing point.              |
| `visitor.py`      | The visiting vehicle: a cylindrical hull with a grapple fixture, free to move.                               |
| `fixture.py`      | A short post with a site on its end, which the arm grabs. The visitor carries one, and so does the station.  |
| `arm.py`          | The arm, with its servos, the inverse-kinematics solver and the camera on its free end.                      |
| `end_effector.py` | A cylinder with a site on its end that latches onto a grapple fixture. The arm has the same one at each end. |
| `capture.py`      | The weld that joins the arm's free end effector to the visitor's grapple fixture.                            |
| `overview.py`     | A fixed camera that follows the arm's free end.                                                              |
| `environment.py`  | A dark gradient sky and the sun.                                                                             |
| `shapes.py`       | Helpers shared by the parts.                                                                                 |

---

## How the Parts Fit Together

Each part is a class that holds what the runtime will need later, as `UserData`, and has a `new` method that builds the part into the model and returns it. `Berthing` is the root. It holds the five parts, and `Berthing.new` builds each one in turn:

``` python
--8<-- "docs/user-guides/examples/berthing/simulation.py:new"
```

`generate` calls `Berthing.new` and stores the result on `mojo_model.user_data`, so the runtime can read it back with `get_user_data(Berthing)`. It also sets the options for the whole model. Contacts are switched off, because nothing here is meant to touch, and the weld is a constraint, not a contact, so it still works.

``` python
--8<-- "docs/user-guides/examples/berthing/simulation.py:generate"
```

---

## Running It

A run has four phases: the arm approaches and lines up with the fixture, moves in slowly and switches the weld on, carries the vehicle to the berthing point, and lets go. The runtime is a loop that steps through them, and each part has methods for the controls it needs, which the loop only calls.

To watch it, run the Reloaded script from the example's folder:

``` bash linenums="0"
./reloaded.sh
```

It runs `mujoco-mojo reloaded -g simulation.generate -r simulation.runtime`, which opens the model in [Reloaded](../../features/reloaded.md) and runs it.

<!-- docs/assets/models/berthing/model.xml is written by scripts/gen_docs_models.py, and a pre-push hook keeps it current. Do not edit it by hand. -->

You can also look around the model in your browser with MuJoCo Live. It is the model as `generate` leaves it, before any runtime behavior, so nothing drives the arm, the weld is off, and no distance is measured.

[Open the model in MuJoCo Live :material-open-in-new:](https://live.mujoco.org/?model=github:Hydrowelder/mujoco-mojo/master/docs/assets/models/berthing/model.xml){ .md-button .md-button--primary target=_blank }

---

!!! success

    That is the lay of the land. In the next guide we build the station and the visitor.
