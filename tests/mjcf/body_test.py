import mujoco
import numpy as np
import pytest

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.body import Body
from mujoco_mojo.typing import BodyName


@pytest.fixture
def body_setup() -> tuple[MjState, Body]:
    """Single free body at the world origin with mass=2."""
    xml = """
    <mujoco>
        <worldbody>
            <body name="box" pos="0 0 1">
                <freejoint/>
                <geom type="box" size="0.1 0.1 0.1" mass="2"/>
            </body>
        </worldbody>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    body = Body(name=BodyName("box"))
    body.get_id(model)
    return MjState(model, data), body


def test_rt_mass(body_setup: tuple[MjState, Body]) -> None:
    """rt_mass() returns the mass defined in the model."""
    state, body = body_setup
    assert body.rt_mass(state) == pytest.approx(2.0)


def test_rt_pos_at_initial_position(body_setup: tuple[MjState, Body]) -> None:
    """rt_pos() returns the initial world position of the body."""
    state, body = body_setup
    pos: np.ndarray = body.rt_pos(state)
    assert pos.shape == (3,)
    assert np.allclose(pos, [0.0, 0.0, 1.0], atol=1e-6)


def test_rt_xmat_is_identity_at_rest(body_setup: tuple[MjState, Body]) -> None:
    """rt_xmat() is the 3x3 identity rotation at the default orientation."""
    state, body = body_setup
    mat: np.ndarray = body.rt_xmat(state)
    assert mat.shape == (3, 3)
    assert np.allclose(mat, np.eye(3), atol=1e-6)


def test_rt_xmat_flatten(body_setup: tuple[MjState, Body]) -> None:
    """rt_xmat(flatten=True) returns a 9-element flat array."""
    state, body = body_setup
    flat: np.ndarray = body.rt_xmat(state, flatten=True)
    assert flat.shape == (9,)


def test_rt_quat_at_identity_orientation(body_setup: tuple[MjState, Body]) -> None:
    """rt_quat() returns the unit quaternion (w=1, x=y=z=0) at default orientation."""
    state, body = body_setup
    q: np.ndarray = body.rt_quat(state)
    assert q.shape == (4,)
    assert np.allclose(q, [1.0, 0.0, 0.0, 0.0], atol=1e-6)


def test_rt_lin_vel_is_zero_at_rest(body_setup: tuple[MjState, Body]) -> None:
    """rt_lin_vel() returns [0, 0, 0] when the body is stationary."""
    state, body = body_setup
    vel: np.ndarray = body.rt_lin_vel(state)
    assert vel.shape == (3,)
    assert np.allclose(vel, 0.0)


def test_rt_ang_vel_is_zero_at_rest(body_setup: tuple[MjState, Body]) -> None:
    """rt_ang_vel() returns [0, 0, 0] when the body is stationary."""
    state, body = body_setup
    assert np.allclose(body.rt_ang_vel(state), 0.0)


def test_rt_lin_vel_tracks_qvel(body_setup: tuple[MjState, Body]) -> None:
    """rt_lin_vel() matches the translational velocity set via qvel."""
    state, body = body_setup
    state.data.qvel[0:3] = [4.0, 0.0, 0.0]
    mujoco.mj_forward(state.model, state.data)
    assert np.allclose(body.rt_lin_vel(state), [4.0, 0.0, 0.0], atol=1e-6)


def test_rt_lin_mom_equals_mass_times_velocity(
    body_setup: tuple[MjState, Body],
) -> None:
    """rt_lin_mom() = mass * rt_lin_vel()."""
    state, body = body_setup
    state.data.qvel[0:3] = [3.0, 0.0, 0.0]
    mujoco.mj_forward(state.model, state.data)
    mom: np.ndarray = body.rt_lin_mom(state)
    assert np.allclose(mom, [6.0, 0.0, 0.0], atol=1e-6)  # mass=2, vel=3


def test_rt_inertia_diag_is_positive(body_setup: tuple[MjState, Body]) -> None:
    """rt_inertia_diag() returns three positive inertia values."""
    state, body = body_setup
    diag: np.ndarray = body.rt_inertia_diag(state)
    assert diag.shape == (3,)
    assert np.all(diag > 0)


def test_rt_parent_body_id_is_world(body_setup: tuple[MjState, Body]) -> None:
    """rt_parent_body_id() for a top-level body is 0 (world)."""
    state, body = body_setup
    parent_id: int = body.rt_parent_body_id(state)
    assert parent_id == 0


def test_rt_trans_ke_is_zero_at_rest(body_setup: tuple[MjState, Body]) -> None:
    """rt_trans_ke() is 0 when the body is stationary."""
    state, body = body_setup
    assert body.rt_trans_ke(state) == pytest.approx(0.0)


def test_rt_trans_ke_positive_with_velocity(body_setup: tuple[MjState, Body]) -> None:
    """rt_trans_ke() is positive when the body is moving."""
    state, body = body_setup
    state.data.qvel[0:3] = [2.0, 0.0, 0.0]
    mujoco.mj_forward(state.model, state.data)
    # KE = 0.5 * 2 * 4 = 4
    assert body.rt_trans_ke(state) == pytest.approx(4.0, abs=1e-6)
