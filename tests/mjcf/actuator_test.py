from pathlib import Path

import mujoco
import numpy as np
import pytest

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.motor import ActuatorMotor
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.position import ActuatorPosition
from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.typing import ActuatorName, JointName


@pytest.fixture
def motor_setup() -> tuple[MjState, ActuatorMotor]:
    """Single hinge joint driven by a named motor actuator."""
    xml = """
    <mujoco>
        <worldbody>
            <body name="arm">
                <joint name="elbow" type="hinge" axis="0 1 0"/>
                <geom type="capsule" size="0.05" fromto="0 0 0 0.3 0 0"/>
            </body>
        </worldbody>
        <actuator>
            <motor name="elbow_motor" joint="elbow" gear="1"/>
        </actuator>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    actuator = ActuatorMotor(name=ActuatorName("elbow_motor"), joint=JointName("elbow"))
    actuator.get_id(model)
    return MjState(model, data), actuator


def test_rt_ctrl_matches_data(motor_setup: tuple[MjState, ActuatorMotor]) -> None:
    """rt_ctrl() returns the control input set on mjData.ctrl."""
    state, actuator = motor_setup
    state.data.ctrl[0] = 0.5
    mujoco.mj_forward(state.model, state.data)
    assert actuator.rt_ctrl(state) == pytest.approx(0.5)


def test_rt_force_matches_ctrl_for_motor(
    motor_setup: tuple[MjState, ActuatorMotor],
) -> None:
    """rt_force() equals the control input for a direct-drive motor with unit gear."""
    state, actuator = motor_setup
    state.data.ctrl[0] = 0.5
    mujoco.mj_forward(state.model, state.data)
    assert actuator.rt_force(state) == pytest.approx(0.5)


def test_actuator_request_posts_ctrl_signal(
    motor_setup: tuple[MjState, ActuatorMotor], tmp_path: Path
) -> None:
    """ActuatorBase.request() registers a sampler that posts ctrl to signal_manager."""
    state, actuator = motor_setup
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    state.data.ctrl[0] = 0.5
    mujoco.mj_forward(state.model, state.data)

    actuator.request(sm, channels=["ctrl"])
    sm.record(state)

    key = "Actuators/elbow_motor:ctrl"
    assert key in sm._key_to_idx
    idx: int = sm._key_to_idx[key]
    assert sm._data_buffer[0, idx] == pytest.approx(0.5, abs=1e-6)


def test_actuator_request_raises_when_unnamed() -> None:
    """ActuatorBase.request() raises ValueError when the actuator has no name."""
    unnamed = ActuatorMotor(joint=JointName("elbow"))
    sm_mock = object()  # won't be reached
    with pytest.raises(ValueError, match="unnamed"):
        unnamed.request(sm_mock)  # type: ignore[arg-type]


@pytest.fixture
def stateful_position_setup() -> tuple[MjState, ActuatorPosition]:
    """Hinge joint driven by a position actuator with a filtered (stateful) activation."""
    xml = """
    <mujoco>
        <worldbody>
            <body name="arm">
                <joint name="elbow" type="hinge" axis="0 1 0" range="-90 90" limited="true"/>
                <geom type="capsule" size="0.05" fromto="0 0 0 0.3 0 0"/>
            </body>
        </worldbody>
        <actuator>
            <position name="elbow_pos" joint="elbow" timeconst="0.1"/>
        </actuator>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    data.ctrl[0] = 0.5
    for _ in range(50):
        mujoco.mj_step(model, data)
    actuator = ActuatorPosition(
        name=ActuatorName("elbow_pos"), joint=JointName("elbow"), timeconst=0.1
    )
    actuator.get_id(model)
    return MjState(model, data), actuator


def test_rt_act_empty_for_stateless_actuator(
    motor_setup: tuple[MjState, ActuatorMotor],
) -> None:
    """rt_act() is empty for a motor, which has no internal activation dynamics."""
    state, actuator = motor_setup
    assert actuator.rt_act(state).size == 0
    assert actuator.rt_act_dot(state).size == 0


def test_rt_act_matches_data_for_stateful_actuator(
    stateful_position_setup: tuple[MjState, ActuatorPosition],
) -> None:
    """rt_act() returns the actuator's filtered activation state (mjData.act)."""
    state, actuator = stateful_position_setup
    act = actuator.rt_act(state)
    assert act.shape == (1,)
    assert np.allclose(act, state.data.act)


def test_actuator_request_skips_act_for_stateless_actuator(
    motor_setup: tuple[MjState, ActuatorMotor], tmp_path: Path
) -> None:
    """request() does not post act/act_dot for actuators without internal dynamics."""
    state, actuator = motor_setup
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    actuator.request(sm, channels=["act", "act_dot"])
    sm.record(state)

    assert "Actuators/elbow_motor:act" not in sm._key_to_idx
    assert "Actuators/elbow_motor:act_dot" not in sm._key_to_idx


def test_actuator_request_posts_act_for_stateful_actuator(
    stateful_position_setup: tuple[MjState, ActuatorPosition], tmp_path: Path
) -> None:
    """request() posts act as a scalar for a stateful actuator with a single activation variable."""
    state, actuator = stateful_position_setup
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    actuator.request(sm, channels=["act"])
    sm.record(state)

    key = "Actuators/elbow_pos:act"
    assert key in sm._key_to_idx
    idx: int = sm._key_to_idx[key]
    assert sm._data_buffer[0, idx] == pytest.approx(float(state.data.act[0]), abs=1e-6)
