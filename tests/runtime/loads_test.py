import mujoco
import numpy as np
import pytest

from mujoco_mojo.mjcf.mujoco_attr.body_attr import SiteSphere
from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.runtime.forcing_function import GeneralForce, PointToPointForce
from mujoco_mojo.runtime.runtime_manager import RuntimeManager
from mujoco_mojo.typing import SiteName


@pytest.fixture
def basic_mj_setup():
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


def test_ideal_spring_magnitude(basic_mj_setup):
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
    spring.resolve_ids(model)
    force, _ = spring.calculate(model, data)

    # Distance is 1.0 along X. Unit vector is [1, 0, 0].
    # Restorative force magnitude is -50 (pulling action_site toward reaction_site).
    assert np.allclose(np.asarray(force), [50.0, 0, 0])


def test_tension_only_spring(basic_mj_setup):
    model, data = basic_mj_setup
    s1 = SiteSphere(name=SiteName("site1"), size=1)
    s2 = SiteSphere(name=SiteName("site2"), size=1)

    # Rest=1.5. Currently distance is 1.0 (Compressed/Slack).
    cable = PointToPointForce.tension_spring(
        name="cable", action_site=s1, xtion_site=s2, stiffness=100.0, rest_length=1.5
    )
    cable.resolve_ids(model)

    force, _ = cable.calculate(model, data)
    assert np.all(force == 0)  # Should be slack


def test_general_force_rotation(basic_mj_setup):
    model, data = basic_mj_setup
    s1 = SiteSphere(name=SiteName("site1"), size=1)

    # Rotate body/site 90 deg around Y so local Z points at world X
    data.qpos[3:7] = [0.7071, 0, 0.7071, 0]  # xyzw or wxyz depending on setup
    mujoco.mj_forward(model, data)

    # Apply a constant 10N in local Z
    thrust = GeneralForce(
        name="thruster", action_site=s1, fz=lambda t: 10.0, rel_to_site=s1
    )
    thrust.resolve_ids(model)

    f_world, _ = thrust.calculate(model, data)

    # If local Z is rotated to world X, we expect force in X
    assert np.asarray(f_world)[0] > 9.0
    assert np.allclose(np.asarray(f_world)[1:3], [0, 0], atol=1e-5)


def test_runtime_manager_integration(basic_mj_setup):
    """Verifies that the manager correctly injects forces into MuJoCo."""
    model, data = basic_mj_setup

    # We need a MojoModel to initialize the manager
    mojo = MojoModel()
    mgr = RuntimeManager(mojo_model=mojo)

    s1 = SiteSphere(name=SiteName("site1"), size=1)
    s2 = SiteSphere(name=SiteName("site2"), size=1)

    # Setup a spring: k=100, rest=0.5. Dist is 1.0.
    # Force should be 50N pulling bodies together.
    spring = PointToPointForce.ideal_spring(
        name="test_spring",
        action_site=s1,
        xtion_site=s2,
        stiffness=100.0,
        rest_length=0.5,
    )

    mgr.add_load(spring)
    mgr.resolve(model)

    # Ensure buffer is clean
    data.qfrc_applied[:] = 0.0

    # Apply the step
    mgr.apply_step(model, data)

    # For freejoints, indices [0:3] are the global translation forces for body1
    # Body 1 (action) is at x=0, Body 2 (xtion) is at x=1.
    # Spring is extended, so it pulls Body 1 toward +X.
    assert data.qfrc_applied[0] == pytest.approx(50.0)

    # Body 2 (xtion) is at index 6 in qfrc_applied (3 for freejoint pos, 3 for ori)
    # It should be pulled toward -X.
    assert data.qfrc_applied[6] == pytest.approx(-50.0)


def test_compression_spring_limit(basic_mj_setup):
    model, data = basic_mj_setup  # mj_forward already called in fixture
    s1 = SiteSphere(name=SiteName("site1"), size=1)
    s2 = SiteSphere(name=SiteName("site2"), size=1)

    # Rest is 0.5, current dist is 1.0 (Extended).
    bumper = PointToPointForce.compression_spring(
        name="bumper", action_site=s1, xtion_site=s2, stiffness=100.0, rest_length=0.5
    )
    bumper.resolve_ids(model)

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
