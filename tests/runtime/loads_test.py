import mujoco
import numpy as np
import pytest

from mujoco_mojo.mjcf.mujoco_attr.body import Body
from mujoco_mojo.mjcf.mujoco_attr.body_attr import SiteSphere
from mujoco_mojo.runtime.load import (
    GeneralForce,
    PointToPointForce,
    ScalarForce,
    VectorForce,
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
    spring.resolve_ids(model, data)
    force, _ = spring.calculate(model, data)

    # Distance is 1.0 along X. Unit vector is [1, 0, 0].
    # Restorative force magnitude is -50 (pulling action_site toward reaction_site).
    assert np.allclose(np.asarray(force), [50.0, 0, 0])


def test_tension_only_spring(basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    model, data = basic_mj_setup
    s1 = SiteSphere(name=SiteName("site1"), size=1)
    s2 = SiteSphere(name=SiteName("site2"), size=1)

    # Rest=1.5. Currently distance is 1.0 (Compressed/Slack).
    cable = PointToPointForce.tension_spring(
        name="cable", action_site=s1, xtion_site=s2, stiffness=100.0, rest_length=1.5
    )
    cable.resolve_ids(model, data)

    force, _ = cable.calculate(model, data)
    assert np.all(force == 0)  # Should be slack


def test_general_force_rotation(basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    model, data = basic_mj_setup
    s1 = SiteSphere(name=SiteName("site1"), size=1)

    # Rotate body/site 90 deg around Y so local Z points at world X
    data.qpos[3:7] = [0.7071, 0, 0.7071, 0]  # xyzw or wxyz depending on setup
    mujoco.mj_forward(model, data)

    # Apply a constant 10N in local Z
    thrust = GeneralForce(
        name="thruster", action_site=s1, fz=lambda t, model, data: 10.0, rel_to_site=s1
    )
    thrust.resolve_ids(model, data)

    f_world, _ = thrust.calculate(model, data)

    # If local Z is rotated to world X, we expect force in X
    assert np.asarray(f_world)[0] > 9.0
    assert np.allclose(np.asarray(f_world)[1:3], [0, 0], atol=1e-5)


def test_runtime_manager_integration(
    basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
):
    """Verifies that the manager correctly injects forces into MuJoCo."""
    model, data = basic_mj_setup

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
    mgr.step(model, data)

    # Check the persistent cache on the spring object
    # Index 0 is the X-component of the calculated world force
    assert _spring._last_f[0] == pytest.approx(50.0)


def test_compression_spring_limit(basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    model, data = basic_mj_setup  # mj_forward already called in fixture
    s1 = SiteSphere(name=SiteName("site1"), size=1)
    s2 = SiteSphere(name=SiteName("site2"), size=1)

    # Rest is 0.5, current dist is 1.0 (Extended).
    bumper = PointToPointForce.compression_spring(
        name="bumper", action_site=s1, xtion_site=s2, stiffness=100.0, rest_length=0.5
    )
    bumper.resolve_ids(model, data)

    force, _ = bumper.calculate(model, data)
    assert np.all(np.asarray(force) == 0)  # Verified: No force when extended

    # --- MOVEMENT PHASE ---
    # Move Body 2 to x=0.2. Now Body 1 is at 0 and Body 2 is at 0.2.
    data.qpos[7] = 0.2

    # CRITICAL: We changed qpos, so we MUST sync Cartesian positions
    mujoco.mj_forward(model, data)

    force_active, _ = bumper.calculate(model, data)

    # Logic: Unit vector (p1-p2) points toward -X.
    # Compression should push Body 1 further -X.
    # F_mag = -100 * (0.2 - 0.5) = +30.
    # Force = +30 * [-1, 0, 0] = [-30, 0, 0]
    assert np.asarray(force_active)[0] < 0


def test_body_reaction_physics(basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    """Verify that VectorForce applies opposite loads to action and reaction bodies."""
    model, data = basic_mj_setup
    s1 = SiteSphere(name=SiteName("site1"))
    b2 = Body(name=BodyName("body2"))

    # Apply 100N in World X to Site 1 (Body 1), reacting on Body 2
    force = VectorForce(
        name="inter_link", action_site=s1, xtion_body=b2, fx=lambda t, m, d: 100.0
    )
    force.resolve_ids(model, data)

    # Clear buffers and apply
    data.qfrc_applied.fill(0)
    force.apply_load(model, data)

    # Body 1 is the first freejoint (indices 0-5), Body 2 is the second (indices 6-11)
    # Check X-force component
    assert data.qfrc_applied[0] == pytest.approx(100.0)  # Action
    assert data.qfrc_applied[6] == pytest.approx(-100.0)  # Reaction


def test_scalar_force_orientation_tracking(
    basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
):
    """Verify ScalarForce follows the site's local X-axis as it rotates."""
    model, data = basic_mj_setup
    s1 = SiteSphere(name=SiteName("site1"))

    # Constant 50N thruster
    thruster = ScalarForce(
        name="thruster", action_site=s1, scalar_func=lambda t, u, m, d: 50.0
    )
    thruster.resolve_ids(model, data)

    # 1. Identity: Local X is World X
    f_world, _ = thruster.calculate(model, data)
    assert np.allclose(f_world, [50.0, 0, 0])

    # 2. Rotate body 90 deg around Z: Local X is now World Y [0, 1, 0]
    # Quat (w,x,y,z) for 90 deg Z: [0.7071, 0, 0, 0.7071]
    data.qpos[3:7] = [0.7071, 0, 0, 0.7071]
    mujoco.mj_forward(model, data)

    f_world_rot, _ = thruster.calculate(model, data)
    assert np.allclose(f_world_rot, [0, 50.0, 0], atol=1e-5)


def test_stroke_compression_spring(
    basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
):
    """Verify the three states of a stroke-limited compression spring."""
    model, data = basic_mj_setup
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
    spring.resolve_ids(model, data)  # sets _r0_mag to 1.0

    # State 1: At rest (d=1.0, delta=0). Force = Preload = 10N.
    f, _ = spring.calculate(model, data)
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
    spring.resolve_ids(model, data)
    data.qpos[7] = 1.25  # Dist = 1.25
    mujoco.mj_forward(model, data)
    f, _ = spring.calculate(model, data)
    # F = 50 - (10 * 0.25) = 47.5
    assert np.linalg.norm(f) == pytest.approx(47.5)

    # State 3: Out of bounds (d=1.6, delta=0.6). Should be 0.
    data.qpos[7] = 0.6
    mujoco.mj_forward(model, data)
    f, _ = spring.calculate(model, data)
    assert np.linalg.norm(f) == 0.0


def test_active_toggle_suppression(
    basic_mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
):
    """Ensure that setting active=False suppresses all forces."""
    model, data = basic_mj_setup
    s1 = SiteSphere(name=SiteName("site1"))

    force = ScalarForce(
        name="dead_force",
        action_site=s1,
        active=False,
        scalar_func=lambda t, u, m, d: 100.0,
    )
    force.resolve_ids(model, data)

    data.qfrc_applied.fill(0)
    force.apply_load(model, data)

    assert np.all(data.qfrc_applied == 0)
    assert len(force.get_visuals(model, data)) == 0
