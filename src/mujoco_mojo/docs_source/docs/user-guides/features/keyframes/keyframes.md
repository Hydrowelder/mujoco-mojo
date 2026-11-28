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
def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    mojo_model.us = mojo.UnitSystem.si()
    mojo_model.mjcf.assets = [
        mojo.Asset(
            textures=[
                mojo.TextureBuiltIn(
                    name=mojo.TextureName("sky"),
                    type=mojo.TextureType.SKYBOX,
                    builtin=mojo.TextureBuiltInType.GRADIENT,
                    width=16,
                    height=16,
                    rgb1=Color.SLATE_700.rgb,
                    rgb2=Color.SLATE_950.rgb,
                ),
                grid := mojo.TextureBuiltIn(
                    name=mojo.TextureName("grid"),
                    type=mojo.TextureType.D2,
                    builtin=mojo.TextureBuiltInType.CHECKER,
                    width=512,
                    height=512,
                    rgb1=Color.SLATE_600.rgb,
                    rgb2=Color.SLATE_800.rgb,
                ),
            ],
            materials=[
                floor := mojo.Material(
                    name=mojo.MaterialName("floor"),
                    texture=grid.name,
                    texrepeat=np.array((1, 1)),
                )
            ],
        )
    ]
    mojo_model.mjcf.worldbody = mojo.WorldBody(
        geoms=[
            mojo.GeomPlane(
                name=mojo.GeomName("floor"),
                size=np.array((0, 0, 0.1)),
                material=floor.name,
            )
        ],
        bodies=[
            base := mojo.Body(
                name=mojo.BodyName("base"),
                pose=mojo.PoseQuat(pos=np.array((0, 0, 1.0))),
                freejoints=[mojo.FreeJoint()],
                geoms=[
                    mojo.GeomBox(
                        size=np.array((0.2, 0.2, 0.1)), rgba=Color.INDIGO_500.rgba
                    )
                ],
                bodies=[
                    mojo.Body(
                        name=mojo.BodyName("upper_arm"),
                        pose=mojo.PoseQuat(pos=np.array((0, 0, 0.1))),
                        joints=[
                            shoulder := mojo.Joint(
                                name=mojo.JointName("shoulder"),
                                axis=np.array((0, 1, 0)),
                            )
                        ],
                        geoms=[
                            mojo.GeomCapsule(
                                size=0.04,
                                fromto=np.array((0, 0, 0, 0, 0, 0.4)),
                                rgba=Color.CYAN_400.rgba,
                            )
                        ],
                        bodies=[
                            mojo.Body(
                                name=mojo.BodyName("forearm"),
                                pose=mojo.PoseQuat(pos=np.array((0, 0, 0.4))),
                                joints=[
                                    elbow := mojo.Joint(
                                        name=mojo.JointName("elbow"),
                                        axis=np.array((0, 1, 0)),
                                    )
                                ],
                                geoms=[
                                    mojo.GeomCapsule(
                                        size=0.03,
                                        fromto=np.array((0, 0, 0, 0, 0, 0.3)),
                                        rgba=Color.AMBER_400.rgba,
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
    )
    mojo_model.mjcf.actuators = [
        mojo.Actuator(
            motors=[
                motor := mojo.ActuatorMotor(
                    name=mojo.ActuatorName("shoulder_motor"), joint=shoulder.name
                )
            ]
        )
    ]
```

``` python
assert base.name and shoulder.name and elbow.name and motor.name

mojo_model.mjcf.keyframes = [
    mojo.Keyframe(
        keys=[
            mojo.Key(
                name=mojo.KeyName("tossed"),
                initial=True,
                states=[
                    # the arm rides on the base, so its velocity is set once, at the root of the tree
                    mojo.FreeBodyState(
                        body=base.name,
                        linear_velocity=np.array((1.0, 0, 3.0)),
                        angular_velocity=np.array((0, 0, 2.0)),
                    ),
                    mojo.JointState(joint=shoulder.name, qpos=np.deg2rad(30)),
                    mojo.JointState(
                        joint=elbow.name, qpos=np.deg2rad(-60), qvel=4.0
                    ),
                    mojo.ActuatorState(actuator=motor.name, ctrl=0.5),
                ],
            ),
            mojo.Key(
                name=mojo.KeyName("resting"),
                states=[
                    mojo.FreeBodyState(
                        body=base.name,
                        pose=mojo.PoseQuat(pos=np.array((0, 0, 0.1))),
                    ),
                    mojo.JointState(joint=elbow.name, qpos=np.deg2rad(90)),
                ],
            ),
        ]
    )
]
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
class Handoff(mojo.UserData):
    """Carries the elbow from the generator to the runtime, which kicks it."""

    elbow: mojo.Joint


```

``` python
def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    elbow = mojo_model.get_user_data(Handoff).elbow
    assert elbow.name

    with runtime_manager as rm:
        kicked = False
        while state.data.time < 1.5:
            if state.data.time >= 1.0 and not kicked:
                mojo.JointState(joint=elbow.name, qvel=10.0).write(state)
                kicked = True
            rm.step(state)
    return mojo_model


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
