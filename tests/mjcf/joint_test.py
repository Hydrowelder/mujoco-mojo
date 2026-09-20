from pathlib import Path

import mujoco
import pytest

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.body_attr.joint import Joint
from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.typing import JointName


@pytest.fixture
def hinge_setup() -> tuple[MjState, Joint]:
    """Single body with a named hinge joint."""
    xml = """
    <mujoco>
        <worldbody>
            <body name="arm">
                <joint name="elbow" type="hinge" axis="0 1 0"/>
                <geom type="capsule" size="0.05" fromto="0 0 0 0.3 0 0"/>
            </body>
        </worldbody>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    joint = Joint(name=JointName("elbow"))
    joint.get_id(model)
    return MjState(model, data), joint


def test_joint_request_posts_qpos_signal(
    hinge_setup: tuple[MjState, Joint], tmp_path: Path
) -> None:
    """Joint.request() registers a sampler that posts qpos to signal_manager."""
    state, joint = hinge_setup
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    # set a known joint position
    state.data.qpos[0] = 1.23
    mujoco.mj_forward(state.model, state.data)

    joint.request(sm, channels=["qpos"])
    sm.record(state)

    key = "Joints/elbow:qpos"
    assert key in sm._key_to_idx
    idx: int = sm._key_to_idx[key]
    assert sm._data_buffer[0, idx] == pytest.approx(1.23, abs=1e-6)


def test_joint_request_posts_qvel_signal(
    hinge_setup: tuple[MjState, Joint], tmp_path: Path
) -> None:
    """Joint.request() posts qvel for a hinge joint."""
    state, joint = hinge_setup
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    state.data.qvel[0] = 2.5
    mujoco.mj_forward(state.model, state.data)

    joint.request(sm, channels=["qvel"])
    sm.record(state)

    key = "Joints/elbow:qvel"
    assert key in sm._key_to_idx
    idx: int = sm._key_to_idx[key]
    assert sm._data_buffer[0, idx] == pytest.approx(2.5, abs=1e-6)


def test_joint_request_raises_when_unnamed() -> None:
    """Joint.request() raises ValueError when the joint has no name."""
    unnamed = Joint()
    sm_mock = object()  # won't be reached
    with pytest.raises(ValueError, match="unnamed"):
        unnamed.request(sm_mock)  # type: ignore[arg-type]


def test_rt_qpos_matches_data(hinge_setup: tuple[MjState, Joint]) -> None:
    """rt_qpos() returns the joint's qpos slice."""
    state, joint = hinge_setup
    state.data.qpos[0] = 1.23
    mujoco.mj_forward(state.model, state.data)
    assert joint.rt_qpos(state) == pytest.approx([1.23], abs=1e-6)


def test_rt_qvel_matches_data(hinge_setup: tuple[MjState, Joint]) -> None:
    """rt_qvel() returns the joint's qvel slice."""
    state, joint = hinge_setup
    state.data.qvel[0] = 2.5
    mujoco.mj_forward(state.model, state.data)
    assert joint.rt_qvel(state) == pytest.approx([2.5], abs=1e-6)


def test_rt_qfrc_passive_reflects_damping() -> None:
    """rt_qfrc_passive() is nonzero for a damped joint with nonzero velocity."""
    xml = """
    <mujoco>
        <worldbody>
            <body name="arm">
                <joint name="elbow" type="hinge" axis="0 1 0" damping="1.0"/>
                <geom type="capsule" size="0.05" fromto="0 0 0 0.3 0 0"/>
            </body>
        </worldbody>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    data.qvel[0] = 2.0
    mujoco.mj_forward(model, data)
    joint = Joint(name=JointName("elbow"))
    joint.get_id(model)
    state = MjState(model, data)
    assert joint.rt_qfrc_passive(state) == pytest.approx([-2.0], abs=1e-6)


def test_joint_request_tags_hinge_qpos_qvel_with_angle_metadata(
    hinge_setup: tuple[MjState, Joint], tmp_path: Path
) -> None:
    """A hinge joint's qpos/qvel are tagged with concrete radian-based unit."""
    state, joint = hinge_setup
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    joint.request(sm, channels=["qpos", "qvel"])
    sm.record(state)

    assert sm._column_metadata["Joints/elbow:qpos"] == {"unit": "radian"}
    assert sm._column_metadata["Joints/elbow:qvel"] == {"unit": "radian / second"}


def test_joint_request_tags_slide_qpos_qvel_with_length_dimension(
    tmp_path: Path,
) -> None:
    """A slide joint's qpos/qvel are tagged with scale-ambiguous length/velocity dimensions, not concrete unit."""
    xml = """
    <mujoco>
        <worldbody>
            <body name="cart">
                <joint name="rail" type="slide" axis="1 0 0"/>
                <geom type="box" size="0.1 0.1 0.1"/>
            </body>
        </worldbody>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    joint = Joint(name=JointName("rail"))
    joint.get_id(model)
    state = MjState(model, data)

    sm = SignalManager(export_path=tmp_path / "tel.parquet")
    joint.request(sm, channels=["qpos", "qvel"])
    sm.record(state)

    assert sm._column_metadata["Joints/rail:qpos"] == {"dimension": "[length]"}
    assert sm._column_metadata["Joints/rail:qvel"] == {"dimension": "[length] / [time]"}


def test_joint_request_metadata_override(
    hinge_setup: tuple[MjState, Joint], tmp_path: Path
) -> None:
    """A caller-supplied metadata dict extends the built-in default for a channel."""
    state, joint = hinge_setup
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    joint.request(sm, channels={"qpos": {"display_name": "Elbow Angle"}})
    sm.record(state)

    assert sm._column_metadata["Joints/elbow:qpos"] == {
        "unit": "radian",
        "display_name": "Elbow Angle",
    }


def test_rt_dims_for_free_joint() -> None:
    """rt_qpos()/rt_qvel() return 7/6 element vectors for a free joint."""
    xml = """
    <mujoco>
        <worldbody>
            <body name="box">
                <freejoint name="root"/>
                <geom type="box" size="0.1 0.1 0.1"/>
            </body>
        </worldbody>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    joint = Joint(name=JointName("root"))
    joint.get_id(model)
    state = MjState(model, data)
    assert joint.rt_qpos(state).shape == (7,)
    assert joint.rt_qvel(state).shape == (6,)


def _joint_state(xml: str, joint_name: str) -> tuple[MjState, Joint]:
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    joint = Joint(name=JointName(joint_name))
    joint.get_id(model)
    return MjState(model, data), joint


_FREE_XML = """
<mujoco>
    <worldbody>
        <body name="box">
            <freejoint name="root"/>
            <geom type="box" size="0.1 0.1 0.1"/>
        </body>
    </worldbody>
</mujoco>
"""

_BALL_XML = """
<mujoco>
    <worldbody>
        <body name="arm">
            <joint name="shoulder" type="ball"/>
            <geom type="capsule" size="0.05" fromto="0 0 0 0.3 0 0"/>
        </body>
    </worldbody>
</mujoco>
"""


def test_free_joint_request_tags_transform_types(tmp_path: Path) -> None:
    """A free joint's split channels are tagged by shape: position as a point, orientation as a quaternion, and every linear/angular rate or force as a free vector."""
    state, joint = _joint_state(_FREE_XML, "root")
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    joint.request(sm, channels=["qpos", "qvel", "qfrc_actuator"])
    sm.record(state)

    meta = sm._column_metadata
    assert meta["Joints/root/pos_qpos:x"]["transform_type"] == "point"
    assert meta["Joints/root/quat_qpos:w"]["transform_type"] == "quaternion"
    assert meta["Joints/root/lin_qvel:x"]["transform_type"] == "vector"
    assert meta["Joints/root/ang_qvel:x"]["transform_type"] == "vector"
    assert meta["Joints/root/lin_qfrc_actuator:x"]["transform_type"] == "vector"
    assert meta["Joints/root/ang_qfrc_actuator:x"]["transform_type"] == "vector"


def test_ball_joint_request_tags_transform_types(tmp_path: Path) -> None:
    """A ball joint's qpos is a quaternion, while its qvel/qfrc_* are free (angular) vectors."""
    state, joint = _joint_state(_BALL_XML, "shoulder")
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    joint.request(sm, channels=["qpos", "qvel", "qfrc_passive"])
    sm.record(state)

    meta = sm._column_metadata
    assert meta["Joints/shoulder/qpos:w"]["transform_type"] == "quaternion"
    assert meta["Joints/shoulder/qvel:x"]["transform_type"] == "vector"
    assert meta["Joints/shoulder/qfrc_passive:x"]["transform_type"] == "vector"


def test_single_dof_joint_scalars_carry_no_transform_type(
    hinge_setup: tuple[MjState, Joint], tmp_path: Path
) -> None:
    """Hinge/slide scalars are never grouped into :x/:y/:z families, so they must not be tagged."""
    state, joint = hinge_setup
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    joint.request(sm, channels=["qpos", "qvel"])
    sm.record(state)

    assert "transform_type" not in sm._column_metadata["Joints/elbow:qpos"]
    assert "transform_type" not in sm._column_metadata["Joints/elbow:qvel"]
