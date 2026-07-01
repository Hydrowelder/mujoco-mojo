from pathlib import Path

import mujoco
import numpy as np
import pytest

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import SiteSphere
from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.typing import SiteName


@pytest.fixture
def two_body_setup():
    """Two free bodies with sites, separated by 1 m in X. Both start at rest."""
    xml = """
    <mujoco>
        <worldbody>
            <body name="body1" pos="0 0 1">
                <freejoint/>
                <geom type="sphere" size="0.1" mass="1"/>
                <site name="site1" pos="0 0 0"/>
            </body>
            <body name="body2" pos="1 0 1">
                <freejoint/>
                <geom type="sphere" size="0.1" mass="1"/>
                <site name="site2" pos="0 0 0"/>
            </body>
        </worldbody>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    s1 = SiteSphere(name=SiteName("site1"), size=0.05)
    s2 = SiteSphere(name=SiteName("site2"), size=0.05)
    state = MjState(model, data)
    s1.get_id(model)
    s2.get_id(model)
    return state, s1, s2


# --- velocity ---


def test_rt_vel_returns_zero_at_rest(two_body_setup):
    """rt_vel() is [0]*6 when the body is stationary."""
    state, s1, _ = two_body_setup
    vel = s1.rt_vel(state)
    assert vel.shape == (6,)
    assert np.allclose(vel, 0.0)


def test_rt_lin_vel_tracks_body_translational_velocity(two_body_setup):
    """rt_lin_vel() matches the linear velocity assigned via qvel."""
    state, s1, _ = two_body_setup
    # freejoint body1: qvel[0:3] = linear, [3:6] = angular
    state.data.qvel[0:3] = [3.0, 0.0, 0.0]
    mujoco.mj_forward(state.model, state.data)

    lin_vel = s1.rt_lin_vel(state)
    assert np.allclose(lin_vel, [3.0, 0.0, 0.0], atol=1e-6)


def test_rt_ang_vel_tracks_body_angular_velocity(two_body_setup):
    """rt_ang_vel() matches the angular velocity assigned via qvel."""
    state, s1, _ = two_body_setup
    state.data.qvel[3:6] = [0.0, 1.0, 0.0]
    mujoco.mj_forward(state.model, state.data)

    ang_vel = s1.rt_ang_vel(state)
    assert np.allclose(ang_vel, [0.0, 1.0, 0.0], atol=1e-6)


def test_rt_velocities_relative_between_two_sites(two_body_setup):
    """rt_velocities(other) gives the 6D velocity of self minus other."""
    state, s1, s2 = two_body_setup
    # body1 moves at 3 m/s X, body2 moves at 1 m/s X
    state.data.qvel[0:3] = [3.0, 0.0, 0.0]  # body1
    state.data.qvel[6:9] = [1.0, 0.0, 0.0]  # body2
    mujoco.mj_forward(state.model, state.data)

    rel = s1.rt_velocities(s2, state)
    assert rel.shape == (6,)
    assert np.allclose(rel[3:6], [2.0, 0.0, 0.0], atol=1e-6)  # linear part


def test_rt_lin_vx_vy_vz_scalars(two_body_setup):
    """rt_lin_vx/vy/vz return the correct scalar components of relative velocity."""
    state, s1, _s2 = two_body_setup
    state.data.qvel[0:3] = [2.0, 3.0, 4.0]
    mujoco.mj_forward(state.model, state.data)

    assert s1.rt_lin_vx(None, state) == pytest.approx(2.0, abs=1e-6)
    assert s1.rt_lin_vy(None, state) == pytest.approx(3.0, abs=1e-6)
    assert s1.rt_lin_vz(None, state) == pytest.approx(4.0, abs=1e-6)


def test_rt_lin_vm_is_magnitude(two_body_setup):
    """rt_lin_vm() returns the magnitude of the linear velocity."""
    state, s1, _ = two_body_setup
    state.data.qvel[0:3] = [3.0, 4.0, 0.0]
    mujoco.mj_forward(state.model, state.data)

    assert s1.rt_lin_vm(None, state) == pytest.approx(5.0, abs=1e-6)


def test_rt_ang_vm_is_magnitude(two_body_setup):
    """rt_ang_vm() returns the magnitude of the angular velocity."""
    state, s1, _ = two_body_setup
    state.data.qvel[3:6] = [0.0, 3.0, 4.0]
    mujoco.mj_forward(state.model, state.data)

    assert s1.rt_ang_vm(None, state) == pytest.approx(5.0, abs=1e-6)


# --- acceleration ---


def test_rt_acc_returns_finite_6d_vector(two_body_setup):
    """rt_acc() returns a finite 6-element vector."""
    state, s1, _ = two_body_setup
    acc = s1.rt_acc(state)
    assert acc.shape == (6,)
    assert np.all(np.isfinite(acc))


def test_rt_lin_acc_and_rt_ang_acc_shapes(two_body_setup):
    """rt_lin_acc / rt_ang_acc slice the 6D vector into (3,) arrays."""
    state, s1, _ = two_body_setup
    lin_acc = s1.rt_lin_acc(state)
    ang_acc = s1.rt_ang_acc(state)
    assert lin_acc.shape == (3,)
    assert ang_acc.shape == (3,)


def test_rt_acc_scalar_derivatives(two_body_setup):
    """rt_lin_ax/ay/az/am and rt_ang_ax/ay/az/am all return finite floats."""
    state, s1, _s2 = two_body_setup
    # exercise all scalar acceleration accessors
    for fn in (s1.rt_lin_ax, s1.rt_lin_ay, s1.rt_lin_az):
        val = fn(None, state)
        assert isinstance(val, float)
        assert np.isfinite(val)
    assert s1.rt_lin_am(None, state) >= 0.0

    for fn in (s1.rt_ang_ax, s1.rt_ang_ay, s1.rt_ang_az):
        val = fn(None, state)
        assert isinstance(val, float)
        assert np.isfinite(val)
    assert s1.rt_ang_am(None, state) >= 0.0


def test_rt_accelerations_relative(
    two_body_setup: tuple[MjState, SiteSphere, SiteSphere],
) -> None:
    """rt_accelerations(other) subtracts the other site's acceleration."""
    state, s1, s2 = two_body_setup
    # both bodies under the same conditions → relative acc ≈ 0
    rel: np.ndarray = s1.rt_accelerations(s2, state)
    assert rel.shape == (6,)
    assert np.allclose(rel, 0.0, atol=1e-6)


def test_rt_quat_is_unit_quaternion(
    two_body_setup: tuple[MjState, SiteSphere, SiteSphere],
) -> None:
    """rt_quat() returns a unit quaternion (norm=1) at the default orientation."""
    state, s1, _s2 = two_body_setup
    q: np.ndarray = s1.rt_quat(state)
    assert q.shape == (4,)
    assert np.linalg.norm(q) == pytest.approx(1.0, abs=1e-6)
    # default orientation → w=1, x=y=z=0
    assert np.allclose(q, [1.0, 0.0, 0.0, 0.0], atol=1e-6)


def test_rt_velocities_with_relative_to(
    two_body_setup: tuple[MjState, SiteSphere, SiteSphere],
) -> None:
    """rt_velocities(other, relative_to=...) rotates the result into the given site's local frame."""
    state, s1, _s2 = two_body_setup
    # give s1 a pure X velocity in the world frame
    state.data.qvel[0:3] = [3.0, 0.0, 0.0]
    mujoco.mj_forward(state.model, state.data)

    # without relative_to: result in world frame
    world_rel: np.ndarray = s1.rt_velocities(None, state)
    # with relative_to=s1 (identity rotation): result should still be [3, 0, 0] in linear
    local_rel: np.ndarray = s1.rt_velocities(None, state, relative_to=s1)

    assert world_rel.shape == (6,)
    assert local_rel.shape == (6,)
    # at identity orientation the frames match
    assert np.allclose(world_rel[3:6], local_rel[3:6], atol=1e-6)


# --- telemetry metadata ---


def test_request_tags_builtin_dimension_metadata(
    two_body_setup: tuple[MjState, SiteSphere, SiteSphere], tmp_path: Path
) -> None:
    """request() tags each channel with its built-in dimension/units metadata."""
    state, s1, _s2 = two_body_setup
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    s1.request(sm, channels=["xpos", "xvelp", "xvelr", "quat"])
    sm.record(state)

    assert sm._column_metadata["Sites/site1/xpos:x"] == {"dimension": "[length]"}
    assert sm._column_metadata["Sites/site1/xvelp:x"] == {
        "dimension": "[length] / [time]"
    }
    assert sm._column_metadata["Sites/site1/xvelr:x"] == {"units": "radian / second"}
    assert sm._column_metadata["Sites/site1/quat:w"] == {"dimension": "[]"}


def test_request_metadata_override(
    two_body_setup: tuple[MjState, SiteSphere, SiteSphere], tmp_path: Path
) -> None:
    """A caller-supplied metadata dict extends the built-in default for a channel."""
    state, s1, _s2 = two_body_setup
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    s1.request(sm, channels={"xpos": {"display_name": "Site Position"}})
    sm.record(state)

    assert sm._column_metadata["Sites/site1/xpos:x"] == {
        "dimension": "[length]",
        "display_name": "Site Position",
    }
