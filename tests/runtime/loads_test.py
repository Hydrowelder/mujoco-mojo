import mujoco
import numpy as np
import pytest

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.body import Body
from mujoco_mojo.mjcf.mujoco_attr.body_attr import SiteSphere
from mujoco_mojo.runtime.load import (
    GeneralLoad,
    PointToPointForce,
    ScalarForce,
    ScalarTorque,
    VectorForce,
    VectorTorque,
)
from mujoco_mojo.runtime.runtime_manager import RuntimeManager
from mujoco_mojo.typing import BodyName, SiteName


@pytest.fixture
def basic_mj_setup() -> tuple[mujoco.MjModel, mujoco.MjData]:
    """Creates a minimal model with two sites for testing."""
    xml = """
    <mujoco>
        <worldbody>
            <body name="body1" pos="0 0 0">
                <freejoint/>
                <geom type="sphere" size="0.1"/>
                <site name="site1" pos="0 0 0"/>
            </body>
            <body name="body2" pos="1 0 0">
                <freejoint/>
                <geom type="sphere" size="0.1"/>
                <site name="site2" pos="0 0 0"/>
            </body>
        </worldbody>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


def test_ideal_spring_magnitude(basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    model, data = basic_mj_setup
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"), size=1)
    s2 = SiteSphere(name=SiteName("site2"), size=1)

    # K=100, Rest=0.5. At distance 1.0, Force should be 100 * (1.0 - 0.5) = 50.
    spring = PointToPointForce.ideal_spring(
        name="test_spring",
        action_site=s1,
        xtion_site=s2,
        stiffness=100.0,
        rest_length=0.5,
    )
    spring.resolve_ids(state)
    force, _ = spring.calculate(state)

    # Distance is 1.0 along X. Unit vector is [1, 0, 0].
    # Restorative force magnitude is -50 (pulling action_site toward reaction_site).
    assert np.allclose(np.asarray(force), [50.0, 0, 0])


def test_tension_only_spring(basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    model, data = basic_mj_setup
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"), size=1)
    s2 = SiteSphere(name=SiteName("site2"), size=1)

    # Rest=1.5. Currently distance is 1.0 (Compressed/Slack).
    cable = PointToPointForce.tension_spring(
        name="cable", action_site=s1, xtion_site=s2, stiffness=100.0, rest_length=1.5
    )
    cable.resolve_ids(state)

    force, _ = cable.calculate(state)
    assert np.all(force == 0)  # Should be slack


def test_general_force_rotation(basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    model, data = basic_mj_setup
    s1 = SiteSphere(name=SiteName("site1"), size=1)

    # Rotate body/site 90 deg around Y so local Z points at world X
    data.qpos[3:7] = [0.7071, 0, 0.7071, 0]  # xyzw or wxyz depending on setup
    mujoco.mj_forward(model, data)
    state = MjState(model, data)

    # Apply a constant 10N in local Z
    thrust = GeneralLoad(
        name="thruster", action_site=s1, fz=lambda ud, s: 10.0, rel_to_site=s1
    )
    thrust.resolve_ids(state)

    f_world, _ = thrust.calculate(state)

    # If local Z is rotated to world X, we expect force in X
    assert np.asarray(f_world)[0] > 9.0
    assert np.allclose(np.asarray(f_world)[1:3], [0, 0], atol=1e-5)


def test_runtime_manager_integration(
    basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
):
    """Verifies that the manager correctly injects forces into MuJoCo."""
    model, data = basic_mj_setup
    state = MjState(model, data)

    # We need a MojoModel to initialize the manager
    mgr = RuntimeManager()

    s1 = SiteSphere(name=SiteName("site1"), size=1)
    s2 = SiteSphere(name=SiteName("site2"), size=1)

    # Setup a spring: k=100, rest=0.5. Dist is 1.0.
    # Force should be 50N pulling bodies together.
    _spring = PointToPointForce.ideal_spring(
        name="test_spring",
        action_site=s1,
        xtion_site=s2,
        stiffness=100.0,
        rest_length=0.5,
    ).register_to_rm(mgr)

    # Apply the step
    mgr.step(state)

    # Check the persistent cache on the spring object
    # Index 0 is the X-component of the calculated world force
    assert _spring._last_f[0] == pytest.approx(50.0)


def test_compression_spring_limit(basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    model, data = basic_mj_setup  # mj_forward already called in fixture
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"), size=1)
    s2 = SiteSphere(name=SiteName("site2"), size=1)

    # Rest is 0.5, current dist is 1.0 (Extended).
    bumper = PointToPointForce.compression_spring(
        name="bumper", action_site=s1, xtion_site=s2, stiffness=100.0, rest_length=0.5
    )
    bumper.resolve_ids(state)

    force, _ = bumper.calculate(state)
    assert np.all(np.asarray(force) == 0)  # Verified: No force when extended

    # --- MOVEMENT PHASE ---
    # Move Body 2 to x=0.2. Now Body 1 is at 0 and Body 2 is at 0.2.
    data.qpos[7] = 0.2

    # CRITICAL: We changed qpos, so we MUST sync Cartesian positions
    mujoco.mj_forward(model, data)

    force_active, _ = bumper.calculate(state)

    # Logic: Unit vector (p1-p2) points toward -X.
    # Compression should push Body 1 further -X.
    # F_mag = -100 * (0.2 - 0.5) = +30.
    # Force = +30 * [-1, 0, 0] = [-30, 0, 0]
    assert np.asarray(force_active)[0] < 0


def test_body_reaction_physics(basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    """Verify that VectorForce applies opposite loads to action and reaction bodies."""
    model, data = basic_mj_setup
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"))
    b2 = Body(name=BodyName("body2"))

    # Apply 100N in World X to Site 1 (Body 1), reacting on Body 2
    force = VectorForce(
        name="inter_link", action_site=s1, xtion_body=b2, fx=lambda ud, s: 100.0
    )
    force.resolve_ids(state)

    # Clear buffers and apply
    data.qfrc_applied.fill(0)
    force.apply_load(state)

    # Body 1 is the first freejoint (indices 0-5), Body 2 is the second (indices 6-11)
    # Check X-force component
    assert data.qfrc_applied[0] == pytest.approx(100.0)  # Action
    assert data.qfrc_applied[6] == pytest.approx(-100.0)  # Reaction


def test_scalar_force_orientation_tracking(
    basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
):
    """Verify ScalarForce follows the site's local X-axis as it rotates."""
    model, data = basic_mj_setup
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"))

    # Constant 50N thruster
    thruster = ScalarForce(
        name="thruster", action_site=s1, scalar_func=lambda ud, s: 50.0
    )
    thruster.resolve_ids(state)

    # 1. Identity: Local X is World X
    f_world, _ = thruster.calculate(state)
    assert np.allclose(f_world, [50.0, 0, 0])

    # 2. Rotate body 90 deg around Z: Local X is now World Y [0, 1, 0]
    # Quat (w,x,y,z) for 90 deg Z: [0.7071, 0, 0, 0.7071]
    data.qpos[3:7] = [0.7071, 0, 0, 0.7071]
    mujoco.mj_forward(model, data)

    f_world_rot, _ = thruster.calculate(state)
    assert np.allclose(f_world_rot, [0, 50.0, 0], atol=1e-5)


def test_stroke_compression_spring(
    basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
):
    """Verify the three states of a stroke-limited compression spring."""
    model, data = basic_mj_setup
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"))
    s2 = SiteSphere(name=SiteName("site2"))

    # Initial dist = 1.0. Set r0 = 1.0, max_stroke = 0.5.
    # Active range is 1.0 to 1.5.
    spring = PointToPointForce.stroke_compression_spring(
        name="limited_spring",
        action_site=s1,
        xtion_site=s2,
        stiffness=100.0,
        preload=10.0,
        max_stroke=0.5,
    )
    spring.resolve_ids(state)  # sets _r0_mag to 1.0

    # State 1: At rest (d=1.0, delta=0). Force = Preload = 10N.
    f, _ = spring.calculate(state)
    assert np.linalg.norm(f) == pytest.approx(10.0)

    # State 2: Mid-stroke (d=1.25, delta=0.25).
    # Force = 10 - (100 * 0.25) = -15. Since return is max(0, f_mag), should be 0.
    # Let's adjust preload to be higher for a better test.
    spring = PointToPointForce.stroke_compression_spring(
        name="stiff_spring",
        action_site=s1,
        xtion_site=s2,
        stiffness=10.0,
        preload=50.0,
        max_stroke=0.5,
    )
    spring.resolve_ids(state)
    data.qpos[7] = 1.25  # Dist = 1.25
    mujoco.mj_forward(model, data)
    f, _ = spring.calculate(state)
    # F = 50 - (10 * 0.25) = 47.5
    assert np.linalg.norm(f) == pytest.approx(47.5)

    # State 3: Out of bounds (d=1.6, delta=0.6). Should be 0.
    data.qpos[7] = 0.6
    mujoco.mj_forward(model, data)
    f, _ = spring.calculate(state)
    assert np.linalg.norm(f) == 0.0


def test_active_toggle_suppression(
    basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
):
    """Ensure that setting active=False suppresses all forces."""
    model, data = basic_mj_setup
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"))

    force = ScalarForce(
        name="dead_force",
        action_site=s1,
        active=False,
        scalar_func=lambda ud, s: 100.0,
    )
    force.resolve_ids(state)

    data.qfrc_applied.fill(0)
    force.apply_load(state)

    assert np.all(data.qfrc_applied == 0)
    assert len(force.get_visuals(state)) == 0


def test_scalar_torque_orientation_tracking(
    basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
):
    """Verify ScalarTorque follows the site's local X-axis as it rotates."""
    model, data = basic_mj_setup
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"))

    # Constant 10Nm torque along local X
    twister = ScalarTorque(
        name="twister", action_site=s1, scalar_func=lambda ud, s: 10.0
    )
    twister.resolve_ids(state)

    # 1. Identity: Local X is World X
    _, t_world = twister.calculate(state)
    assert np.allclose(t_world, [10.0, 0, 0])

    # 2. Rotate body 90 deg around Y: Local X is now World -Z [0, 0, -1]
    # Quat (w,x,y,z) for 90 deg Y: [0.7071, 0, 0.7071, 0]
    data.qpos[3:7] = [0.7071, 0, 0.7071, 0]
    mujoco.mj_forward(model, data)

    _, t_world_rot = twister.calculate(state)
    assert np.allclose(t_world_rot, [0, 0, -10.0], atol=1e-5)


def test_spring_damping_logic(basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    """Verify that damping correctly opposes relative velocity."""
    model, data = basic_mj_setup
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"))
    s2 = SiteSphere(name=SiteName("site2"))

    # Spring with NO stiffness, ONLY damping (c=10.0)
    # Dist is 1.0, rest_length is 1.0 (no displacement force)
    damper = PointToPointForce.ideal_spring(
        name="damper", action_site=s1, xtion_site=s2, damping=10.0, rest_length=1.0
    )
    damper.resolve_ids(state)

    # Set Body 1 moving away from Body 2 at 2.0 m/s in X
    # Body 1 is the first freejoint (qvel indices 0-5)
    data.qvel[0] = 2.0
    mujoco.mj_forward(model, data)

    # Logic: vel = 2.0, c = 10.0. F_mag = -1.0 * (0 + 10 * 2) = -20N.
    # Unit vector (p1 - p2) is [1, 0, 0].
    # Result should be [-20, 0, 0] (pulling back against motion).
    f, _ = damper.calculate(state)
    assert np.allclose(f, [-20.0, 0, 0])


def test_torque_reaction_physics(basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    """Verify that VectorTorque applies opposite torques to action and reaction bodies."""
    model, data = basic_mj_setup
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"))
    b2 = Body(name=BodyName("body2"))

    # Apply 50Nm in World Y to Body 1, reacting on Body 2
    torque = VectorTorque(
        name="torsion_bar", action_site=s1, xtion_body=b2, ty=lambda ud, s: 50.0
    )
    torque.resolve_ids(state)

    data.qfrc_applied.fill(0)
    torque.apply_load(state)

    # Freejoint qfrc mapping: [fx, fy, fz, tx, ty, tz]
    # Body 1 (indices 0-5): Torque is index 4
    assert data.qfrc_applied[4] == pytest.approx(50.0)
    # Body 2 (indices 6-11): Torque is index 10
    assert data.qfrc_applied[10] == pytest.approx(-50.0)


def test_general_force_6dof_application(
    basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
):
    """Verify that GeneralForce applies both F and T correctly in world frame."""
    model, data = basic_mj_setup
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"))

    # Apply [10, 20, 30] Force and [1, 2, 3] Torque
    load = GeneralLoad(
        name="complex_load",
        action_site=s1,
        fx=lambda ud, s: 10.0,
        fy=lambda ud, s: 20.0,
        fz=lambda ud, s: 30.0,
        tx=lambda ud, s: 1.0,
        ty=lambda ud, s: 2.0,
        tz=lambda ud, s: 3.0,
    )
    load.resolve_ids(state)

    f_world, t_world = load.calculate(state)

    assert np.allclose(f_world, [10, 20, 30])
    assert np.allclose(t_world, [1, 2, 3])


def test_point_to_point_validation_error():
    """Verify that PointToPointForce rejects 'rel_to_site' via Pydantic validator."""
    s1 = SiteSphere(name=SiteName("s1"))
    s2 = SiteSphere(name=SiteName("s2"))

    # We use the constructor directly to bypass the factory and hit the validator
    with pytest.raises(ValueError, match="cannot use 'rel_to_site'"):
        PointToPointForce(
            name="err",
            action_site=s1,
            xtion_site=s2,
            rel_to_site=s1,  # This triggers your _validate_frame method
            magnitude_func=lambda ud, s: 0.0,
        )


def test_stochastic_named_value_unwrap(
    basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
):
    """Verify that stiffness/damping work when passed as NamedValues."""
    model, data = basic_mj_setup
    state = MjState(model, data)
    from mujoco_mojo.stochas import NamedValue, ValueName

    # Use a NamedValue for stiffness
    k_stochastic = NamedValue(name=ValueName("random_k"), stored_value=250.0)

    spring = PointToPointForce.ideal_spring(
        name="stoch_spring",
        action_site=SiteSphere(name=SiteName("site1")),
        xtion_site=SiteSphere(name=SiteName("site2")),
        stiffness=k_stochastic,
        rest_length=0.0,
    )
    spring.resolve_ids(state)

    # Dist=1.0, k=250. Force should be 250N.
    f, _ = spring.calculate(state)
    assert np.linalg.norm(f) == pytest.approx(250.0)


def test_scalar_torque_math(basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    """Verify ScalarTorque applies torque along the site's local X-axis."""
    model, data = basic_mj_setup
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"))

    # Apply 15Nm torque
    torque = ScalarTorque(name="motor", action_site=s1, scalar_func=lambda ud, s: 15.0)
    torque.resolve_ids(state)

    # At identity, local X is world X
    _, t_world = torque.calculate(state)
    assert np.allclose(t_world, [15.0, 0, 0])


def test_body_reaction_force_to_world(
    basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
):
    """Verify that if xtion_body is None, only the action force is applied."""
    model, data = basic_mj_setup
    state = MjState(model, data)
    s1 = SiteSphere(name=SiteName("site1"))

    # xtion_body is None by default in BodyReactionForce
    force = VectorForce(name="gravity_sim", action_site=s1, fz=lambda ud, s: -10.0)
    force.resolve_ids(state)

    data.qfrc_applied.fill(0)
    force.apply_load(state)

    # Body 1 (indices 0-5) should feel the force
    assert data.qfrc_applied[2] == -10.0
    # Body 2 (indices 6-11) should feel NOTHING (no reaction body)
    assert np.all(data.qfrc_applied[6:] == 0)
