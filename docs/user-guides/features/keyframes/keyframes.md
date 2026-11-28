# Keyframes

!!! abstract

    A **keyframe** is a named snapshot of a simulation's state: joint positions and velocities, controls, and the poses of mocap bodies. Mojo lets you write one by naming the joints, bodies, and actuators it sets, and starts every run from the key you mark as initial.

---

## The Problem

MuJoCo stores a key as flat vectors laid out in the order of `qpos` and `qvel`. A hinge or slide joint takes one entry of each, a ball joint four and three, and a free joint seven and six. Writing a key by hand means knowing where every joint sits in those vectors, and adding a joint anywhere earlier in the tree moves everything after it. MuJoCo fills a vector that is too short with defaults without saying so, so a key that has drifted out of step still loads, just onto the wrong joints.

Free joints add a second trap: MuJoCo keeps a free joint's angular velocity in the body's own frame, not the world frame, so a spin written as a world axis turns the body about a different axis whenever it starts rotated.

---

## Setting a Key by Reference

A `Key` takes a list of `states`, each naming the object it sets. When the model is compiled, Mojo looks each one up and writes the vectors for you. Everything a key does not mention keeps the model's default: joints stay where they were defined, at rest.

``` python
--8<-- "docs/user-guides/features/keyframes/keyframes_example.py:model"
```

``` python
--8<-- "docs/user-guides/features/keyframes/keyframes_example.py:key"
```

| State           | Sets                           | Values                                                                                                                              |
| --------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `JointState`    | a hinge, slide, or ball joint  | `qpos` and `qvel` in MuJoCo's units: radians for a hinge, a quaternion and an angular velocity in the body's frame for a ball joint |
| `FreeBodyState` | a body with a free joint       | a world `pose`, and a `linear_velocity` and `angular_velocity` in the world frame, optionally described about a `reference` frame   |
| `ActuatorState` | an actuator                    | `ctrl`, and `act` for an actuator with activation dynamics                                                                          |
| `MocapState`    | a mocap body                   | a world `pose`                                                                                                                      |

???+ tip "Tip: Set velocity at the root of the tree"

    A body attached to its parent by hinge or slide joints has no velocity of its own: it moves with its parent, plus the motion of its joints. Give the free body at the root of the tree a `FreeBodyState`, and each joint below it a `JointState`. `FreeBodyState` refuses a body without a free joint and says so.

???+ warning "Warning: A key with states needs a name"

    Mojo finds the key in the compiled model by its name. A key also cannot set `qpos`, `qvel`, `act`, `ctrl`, `mpos`, or `mquat` directly and through `states` at once.

---

## Starting From a Key

`initial=True` marks the key every run starts from. The runner and Reloaded both load it after compiling the model, so the runtime receives a state that is already there. At most one key in a model can be initial, and with none the simulation starts from the model's default state.

The same state classes work during a run: `write` puts a state's values into the running simulation, here kicking the elbow at one second. The generator hands the elbow to the runtime through its user data, so the runtime takes the joint's name from the joint itself.

``` python
--8<-- "docs/user-guides/features/keyframes/keyframes_example.py:handoff"
```

``` python
--8<-- "docs/user-guides/features/keyframes/keyframes_example.py:runtime"
```

---

## Picking a Key in Reloaded

Reloaded can start every run from another key without touching the generator. Type `key resting` (or `key 1`, by number) and every run starts from that key until you type `key none`, which goes back to the one marked initial. The key dropdown in the status bar does the same, and lists the keys of the last model built, as does the Key setting in Reloaded's window in Studio.

Studio's Options panel has a key picker of its own. Pressing Reset with a key picked there sets `key` to it and runs the model again. Studio's button to save the current state into a key only changes the viewer's copy of the model, which the next run replaces, so keys belong in the generator.

---

## What Ends Up in the XML

The written `model.xml` holds ordinary `qpos`, `qvel`, and `ctrl` vectors, so MuJoCo, Studio, and MuJoCo Live read the keys without Mojo. The states themselves are kept in the trial's saved model config, which is what playback reads. Reading the XML back with `Mujoco.from_xml` gives keys with vectors and no states.

---

!!! success

    You can now write keyframes by naming what they set, without counting entries in `qpos`, and start every run from the one you mark as initial.
