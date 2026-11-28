from pathlib import Path

import mujoco
import numpy as np
import pytest

import mujoco_mojo as mojo


def _arm(
    extra_joint_first: bool = False,
) -> tuple[mojo.Mujoco, mojo.JointName, mojo.JointName]:
    """A two-link arm hinged at the shoulder and elbow, optionally with a slide joint defined before both. Returns the model and the names of the shoulder and elbow joints."""
    shoulder = mojo.Joint(name=mojo.JointName("shoulder"), axis=np.array((0, 1, 0)))
    elbow = mojo.Joint(name=mojo.JointName("elbow"), axis=np.array((0, 1, 0)))
    capsule = mojo.GeomCapsule(size=0.05, fromto=np.array((0, 0, 0, 0, 0, -0.5)))
    bodies = [
        mojo.Body(
            name=mojo.BodyName("upper"),
            joints=[shoulder],
            geoms=[capsule],
            bodies=[
                mojo.Body(
                    name=mojo.BodyName("lower"),
                    pose=mojo.PoseQuat(pos=np.array((0, 0, -0.5))),
                    joints=[elbow],
                    geoms=[capsule],
                )
            ],
        )
    ]
    if extra_joint_first:
        bodies.insert(
            0,
            mojo.Body(
                name=mojo.BodyName("slider"),
                joints=[
                    mojo.Joint(name=mojo.JointName("slide"), type=mojo.JointType.SLIDE)
                ],
                geoms=[mojo.GeomSphere(size=0.05)],
            ),
        )
    assert shoulder.name and elbow.name
    return (
        mojo.Mujoco(worldbody=mojo.WorldBody(bodies=bodies)),
        shoulder.name,
        elbow.name,
    )


def _free_box(quat: np.ndarray = np.array((1.0, 0, 0, 0))) -> mojo.Mujoco:
    """A free box at (1, 0, 0) with orientation `quat`, a hinged child, and a mocap body."""
    return mojo.Mujoco(
        worldbody=mojo.WorldBody(
            bodies=[
                mojo.Body(
                    name=mojo.BodyName("box"),
                    pose=mojo.PoseQuat(pos=np.array((1.0, 0, 0)), quat=quat),
                    freejoints=[mojo.FreeJoint()],
                    geoms=[mojo.GeomBox(size=np.array((0.1, 0.2, 0.3)))],
                    bodies=[
                        mojo.Body(
                            name=mojo.BodyName("flap"),
                            joints=[mojo.Joint(name=mojo.JointName("hinge"))],
                            geoms=[mojo.GeomSphere(size=0.05)],
                        )
                    ],
                ),
                mojo.Body(
                    name=mojo.BodyName("target"),
                    mocap=True,
                    geoms=[mojo.GeomSphere(size=0.05, contype=0, conaffinity=0)],
                ),
            ]
        )
    )


def _with_keys(mjcf: mojo.Mujoco, *keys: mojo.Key) -> mojo.Mujoco:
    mjcf.keyframes = [mojo.Keyframe(keys=list(keys))]
    return mjcf


def _world_angular_velocity(state: mojo.MjState, body: str) -> np.ndarray:
    mujoco.mj_forward(state.model, state.data)
    vel = np.zeros(6)
    mujoco.mj_objectVelocity(
        state.model,
        state.data,
        mujoco.mjtObj.mjOBJ_BODY,
        state.model.body(body).id,
        vel,
        0,
    )
    return vel[:3]


def test_joint_states_fill_only_their_own_slots() -> None:
    """A joint state sets its joint's entries, and every other joint keeps qpos0 and zero velocity."""
    mjcf, _, elbow = _arm()
    key = mojo.Key(
        name=mojo.KeyName("kicked"),
        states=[mojo.JointState(joint=elbow, qpos=-0.6, qvel=5.0)],
    )
    model = _with_keys(mjcf, key).to_mj_model()
    np.testing.assert_allclose(model.key("kicked").qpos, (0, -0.6))
    np.testing.assert_allclose(model.key("kicked").qvel, (0, 5.0))


def test_states_follow_their_joint_when_the_layout_changes() -> None:
    """Adding a joint ahead of the arm moves the elbow's slot, and its key value moves with it."""
    mjcf, _, elbow = _arm(extra_joint_first=True)
    key = mojo.Key(
        name=mojo.KeyName("kicked"),
        states=[mojo.JointState(joint=elbow, qpos=-0.6)],
    )
    model = _with_keys(mjcf, key).to_mj_model()
    np.testing.assert_allclose(model.key("kicked").qpos, (0, 0, -0.6))


def test_written_xml_holds_the_resolved_vectors(tmp_path: Path) -> None:
    """write_xml writes plain MJCF vectors, which MuJoCo reads back without Mojo."""
    mjcf, shoulder, elbow = _arm()
    key = mojo.Key(
        name=mojo.KeyName("kicked"),
        states=[
            mojo.JointState(joint=shoulder, qpos=0.3),
            mojo.JointState(joint=elbow, qvel=5.0),
        ],
    )
    path = tmp_path / "arm.xml"
    xml = _with_keys(mjcf, key).write_xml(path)
    assert 'qpos="0.3 0.0"' in xml
    assert 'qvel="0.0 5.0"' in xml
    assert "ctrl" not in xml

    model = mujoco.MjModel.from_xml_path(str(path))
    np.testing.assert_allclose(model.key("kicked").qpos, (0.3, 0))
    np.testing.assert_allclose(model.key("kicked").qvel, (0, 5.0))


def test_mj_spec_holds_the_resolved_vectors() -> None:
    mjcf, _, elbow = _arm()
    key = mojo.Key(
        name=mojo.KeyName("kicked"),
        states=[mojo.JointState(joint=elbow, qpos=-0.6)],
    )
    model = _with_keys(mjcf, key).to_mj_spec().compile()
    np.testing.assert_allclose(model.key("kicked").qpos, (0, -0.6))


def test_prep_for_sim_starts_from_the_initial_key(tmp_path: Path) -> None:
    mjcf, _, elbow = _arm()
    _with_keys(
        mjcf,
        mojo.Key(
            name=mojo.KeyName("rest"),
            states=[mojo.JointState(joint=elbow, qpos=0.1)],
        ),
        mojo.Key(
            name=mojo.KeyName("kicked"),
            initial=True,
            states=[mojo.JointState(joint=elbow, qpos=-0.6, qvel=5.0)],
        ),
    )
    for save_path in (None, tmp_path / "arm.xml"):
        state = mjcf.prep_for_sim(save_path)
        np.testing.assert_allclose(state.data.qpos, (0, -0.6))
        np.testing.assert_allclose(state.data.qvel, (0, 5.0))


def test_prep_for_sim_key_overrides_the_initial_one() -> None:
    mjcf, _, elbow = _arm()
    _with_keys(
        mjcf,
        mojo.Key(
            name=mojo.KeyName("rest"),
            states=[mojo.JointState(joint=elbow, qpos=0.1)],
        ),
        mojo.Key(
            name=mojo.KeyName("kicked"),
            initial=True,
            states=[mojo.JointState(joint=elbow, qpos=-0.6)],
        ),
    )
    np.testing.assert_allclose(
        mjcf.prep_for_sim(key=mojo.KeyName("rest")).data.qpos, (0, 0.1)
    )
    np.testing.assert_allclose(mjcf.prep_for_sim(key=0).data.qpos, (0, 0.1))
    with pytest.raises(ValueError, match="no key named 'missing'"):
        mjcf.prep_for_sim(key=mojo.KeyName("missing"))
    with pytest.raises(ValueError, match="has 2 keys"):
        mjcf.prep_for_sim(key=5)


def test_prep_for_sim_without_an_initial_key_starts_at_the_default() -> None:
    mjcf, _, elbow = _arm()
    _with_keys(
        mjcf,
        mojo.Key(
            name=mojo.KeyName("kicked"),
            states=[mojo.JointState(joint=elbow, qpos=-0.6)],
        ),
    )
    np.testing.assert_allclose(mjcf.prep_for_sim().data.qpos, (0, 0))


def test_only_one_key_can_be_initial() -> None:
    mjcf, _, _ = _arm()
    _with_keys(
        mjcf,
        mojo.Key(name=mojo.KeyName("a"), initial=True),
        mojo.Key(name=mojo.KeyName("b"), initial=True),
    )
    with pytest.raises(ValueError, match="Only one key can be initial"):
        mjcf.prep_for_sim()


def test_key_refuses_states_mixed_with_vectors() -> None:
    with pytest.raises(ValueError, match="sets qpos directly"):
        mojo.Key(
            name=mojo.KeyName("k"),
            qpos=np.array((0.0, 0.0)),
            states=[mojo.JointState(joint=mojo.JointName("elbow"), qvel=1.0)],
        )


def test_key_with_states_or_initial_needs_a_name() -> None:
    with pytest.raises(ValueError, match="needs a name"):
        mojo.Key(states=[mojo.JointState(joint=mojo.JointName("elbow"), qvel=1.0)])
    with pytest.raises(ValueError, match="needs a name"):
        mojo.Key(initial=True)


def test_key_refuses_two_states_for_one_object() -> None:
    mjcf, _, elbow = _arm()
    key = mojo.Key(
        name=mojo.KeyName("k"),
        states=[
            mojo.JointState(joint=elbow, qpos=0.1),
            mojo.JointState(joint=elbow, qvel=1.0),
        ],
    )
    with pytest.raises(ValueError, match="joint 'elbow' more than once"):
        _with_keys(mjcf, key).to_mj_model()


@pytest.mark.parametrize(
    ("state", "message"),
    [
        (
            mojo.JointState(joint=mojo.JointName("nope"), qpos=0.1),
            "no joint named 'nope'",
        ),
        (
            mojo.JointState(joint=mojo.JointName("hinge"), qpos=np.array((1.0, 2.0))),
            "takes 1 value",
        ),
        (
            mojo.FreeBodyState(body=mojo.BodyName("flap"), angular_velocity=np.ones(3)),
            "has no free joint",
        ),
        (
            mojo.MocapState(body=mojo.BodyName("box"), pose=mojo.PoseQuat()),
            "not a mocap body",
        ),
    ],
)
def test_states_refuse_what_the_model_cannot_take(
    state: mojo.AnyKeyState, message: str
) -> None:
    key = mojo.Key(name=mojo.KeyName("k"), states=[state])
    with pytest.raises(ValueError, match=message):
        _with_keys(_free_box(), key).to_mj_model()


def test_joint_state_refuses_a_free_joint() -> None:
    mjcf = _free_box()
    assert mjcf.worldbody is not None
    mjcf.worldbody.bodies[0].freejoints = [mojo.FreeJoint(name=mojo.JointName("free"))]
    key = mojo.Key(
        name=mojo.KeyName("k"),
        states=[mojo.JointState(joint=mojo.JointName("free"), qvel=0.0)],
    )
    with pytest.raises(ValueError, match="FreeBodyState"):
        _with_keys(mjcf, key).to_mj_model()


def test_free_body_angular_velocity_is_given_in_the_world_frame() -> None:
    """A world-z spin stays a world-z spin on a body rotated 90 degrees about x, whose own z is world -y."""
    quat = np.array((np.cos(np.pi / 4), np.sin(np.pi / 4), 0, 0))
    key = mojo.Key(
        name=mojo.KeyName("spin"),
        initial=True,
        states=[
            mojo.FreeBodyState(
                body=mojo.BodyName("box"), angular_velocity=np.array((0, 0, 1.0))
            )
        ],
    )
    state = _with_keys(_free_box(quat), key).prep_for_sim()
    np.testing.assert_allclose(
        _world_angular_velocity(state, "box"), (0, 0, 1), atol=1e-9
    )


def test_free_body_pose_and_velocity_about_a_reference() -> None:
    """A spin about a point carries over to the body's origin as w x (r_body - r_point)."""
    key = mojo.Key(
        name=mojo.KeyName("orbit"),
        initial=True,
        states=[
            mojo.FreeBodyState(
                body=mojo.BodyName("box"),
                pose=mojo.PoseEuler(
                    pos=np.array((0, 2.0, 0)), euler=np.array((0, 0, 90))
                ),
                angular_velocity=np.array((0, 0, 1.0)),
                reference=mojo.PoseQuat(pos=np.array((0, 1.0, 0))),
            )
        ],
    )
    state = _with_keys(_free_box(), key).prep_for_sim()
    np.testing.assert_allclose(state.data.qpos[:3], (0, 2, 0))
    np.testing.assert_allclose(
        state.data.qvel[:3], np.cross((0, 0, 1), (0, 1, 0)), atol=1e-9
    )
    np.testing.assert_allclose(
        _world_angular_velocity(state, "box"), (0, 0, 1), atol=1e-9
    )


def test_hinge_and_mocap_states_share_a_key_with_a_free_body() -> None:
    key = mojo.Key(
        name=mojo.KeyName("all"),
        initial=True,
        states=[
            mojo.FreeBodyState(
                body=mojo.BodyName("box"), linear_velocity=np.array((1.0, 0, 0))
            ),
            mojo.JointState(joint=mojo.JointName("hinge"), qpos=0.5, qvel=2.0),
            mojo.MocapState(
                body=mojo.BodyName("target"),
                pose=mojo.PoseQuat(
                    pos=np.array((0, 0, 3.0)), quat=np.array((2.0, 0, 0, 0))
                ),
            ),
        ],
    )
    state = _with_keys(_free_box(), key).prep_for_sim()
    np.testing.assert_allclose(state.data.qpos[:3], (1, 0, 0))
    np.testing.assert_allclose(state.data.qpos[7], 0.5)
    np.testing.assert_allclose(state.data.qvel, (1, 0, 0, 0, 0, 0, 2))
    np.testing.assert_allclose(state.data.mocap_pos[0], (0, 0, 3))
    np.testing.assert_allclose(state.data.mocap_quat[0], (1, 0, 0, 0))


def test_ball_joint_state_takes_a_quaternion_and_an_angular_velocity() -> None:
    mjcf = mojo.Mujoco(
        worldbody=mojo.WorldBody(
            bodies=[
                mojo.Body(
                    name=mojo.BodyName("pendulum"),
                    joints=[
                        mojo.Joint(
                            name=mojo.JointName("ball"), type=mojo.JointType.BALL
                        )
                    ],
                    geoms=[mojo.GeomSphere(size=0.05)],
                )
            ]
        )
    )
    key = mojo.Key(
        name=mojo.KeyName("k"),
        states=[
            mojo.JointState(
                joint=mojo.JointName("ball"),
                qpos=np.array((0, 0, 0, 2.0)),
                qvel=np.array((0, 0, 1.0)),
            )
        ],
    )
    model = _with_keys(mjcf, key).to_mj_model()
    np.testing.assert_allclose(model.key("k").qpos, (0, 0, 0, 1))
    np.testing.assert_allclose(model.key("k").qvel, (0, 0, 1))


def test_actuator_state_sets_ctrl_and_act() -> None:
    mjcf, shoulder, elbow = _arm()
    mjcf.actuators = [
        mojo.Actuator(
            motors=[
                mojo.ActuatorMotor(name=mojo.ActuatorName("motor"), joint=shoulder)
            ],
            intvelocities=[
                mojo.ActuatorIntegratedVelocity(
                    name=mojo.ActuatorName("servo"), joint=elbow, kp=10
                )
            ],
        )
    ]
    key = mojo.Key(
        name=mojo.KeyName("k"),
        states=[
            mojo.ActuatorState(actuator=mojo.ActuatorName("motor"), ctrl=1.5),
            mojo.ActuatorState(actuator=mojo.ActuatorName("servo"), act=0.25),
        ],
    )
    model = _with_keys(mjcf, key).to_mj_model()
    np.testing.assert_allclose(model.key("k").ctrl, (1.5, 0))
    np.testing.assert_allclose(model.key("k").act, (0.25,))

    no_act = mojo.Key(
        name=mojo.KeyName("k"),
        states=[mojo.ActuatorState(actuator=mojo.ActuatorName("motor"), act=1.0)],
    )
    with pytest.raises(ValueError, match="no activation state"):
        _with_keys(mjcf, no_act).to_mj_model()


def test_key_states_survive_a_json_round_trip() -> None:
    """The runner saves each trial's model as JSON, so the states have to come back as the classes they were."""
    mjcf, _, elbow = _arm()
    key = mojo.Key(
        name=mojo.KeyName("k"),
        initial=True,
        states=[
            mojo.JointState(joint=elbow, qpos=np.array((0.5,))),
            mojo.FreeBodyState(
                body=mojo.BodyName("b"), pose=mojo.PoseEuler(euler=np.array((0, 0, 30)))
            ),
            mojo.ActuatorState(actuator=mojo.ActuatorName("a"), ctrl=1.0),
            mojo.MocapState(body=mojo.BodyName("m"), pose=mojo.PoseQuat()),
        ],
    )
    loaded = mojo.Mujoco.model_validate_json(_with_keys(mjcf, key).model_dump_json())
    states = loaded.keyframes[0].keys[0].states
    assert [type(s) for s in states] == [
        mojo.JointState,
        mojo.FreeBodyState,
        mojo.ActuatorState,
        mojo.MocapState,
    ]
    assert loaded.keyframes[0].keys[0].initial
    assert isinstance(states[1], mojo.FreeBodyState)
    assert isinstance(states[1].pose, mojo.PoseEuler)


def test_set_initial_velocity_spins_a_rotated_body_about_the_world_axis() -> None:
    """The angular velocity is converted into the body's frame, where MuJoCo keeps it."""
    quat = np.array((np.cos(np.pi / 4), np.sin(np.pi / 4), 0, 0))
    mjcf = _free_box(quat)
    assert mjcf.worldbody is not None
    box = mjcf.worldbody.bodies[0]
    state = mjcf.prep_for_sim()
    box.set_initial_velocity(state, angular_velocity=np.array((0, 0, 1.0)))
    np.testing.assert_allclose(
        _world_angular_velocity(state, "box"), (0, 0, 1), atol=1e-9
    )


def test_set_initial_velocity_refuses_a_hinged_body() -> None:
    """A body on a hinge moves with its parent, and used to crash with a numpy broadcast error."""
    mjcf = _free_box()
    assert mjcf.worldbody is not None
    flap = mjcf.worldbody.bodies[0].bodies[0]
    state = mjcf.prep_for_sim()
    with pytest.raises(ValueError, match="has no free joint"):
        flap.set_initial_velocity(state, linear_velocity=np.array((1.0, 0, 0)))
