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
