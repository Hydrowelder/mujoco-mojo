import numpy as np

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

Color = mojo.utils.Color


# --8<-- [start:handoff]
class Handoff(mojo.UserData):
    """Carries the elbow from the generator to the runtime, which kicks it."""

    elbow: mojo.Joint


# --8<-- [end:handoff]


# --8<-- [start:model]
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
    # --8<-- [end:model]

    # --8<-- [start:key]
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
    # --8<-- [end:key]

    mojo_model.user_data = Handoff(elbow=elbow)
    return mojo_model


# --8<-- [start:runtime]
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


# --8<-- [end:runtime]
