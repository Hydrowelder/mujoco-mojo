import numpy as np
import pytest

from mujoco_mojo.mjcf.mujoco_attr.body_attr import Inertial
from mujoco_mojo.mjcf.pose import PoseQuat
from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.stochas import (
    DistName,
    NormalDistribution,
    UniformDistribution,
)


@pytest.fixture
def mojo_model() -> MojoModel:
    """Provides a basic MojoModel for sampling tests."""
    return MojoModel().with_seed(42).with_trial_num(1)


@pytest.fixture
def simple_box_inertial() -> Inertial:
    """A standard 1kg, 1x1x1 box at origin."""
    return Inertial(
        mass=1.0,
        pose=PoseQuat(pos=np.asarray([0, 0, 0])),
        diaginertia=np.asarray([1 / 6, 1 / 6, 1 / 6]),
    )


def test_inertia_matrix_calculation(simple_box_inertial: Inertial):
    """Verify diagonal and full inertia matrix reconstruction."""
    expected = np.diag([1 / 6, 1 / 6, 1 / 6])
    assert np.allclose(simple_box_inertial.inertia_matrix, expected)


def test_parallel_axis_addition(simple_box_inertial: Inertial):
    """Test adding two identical cubes offset from each other."""
    # Move a second identical cube to [1, 0, 0]
    other = Inertial(
        mass=1.0,
        pose=PoseQuat(pos=np.asarray([1, 0, 0])),
        diaginertia=np.asarray([1 / 6, 1 / 6, 1 / 6]),
    )

    combined = simple_box_inertial + other

    # Combined mass should be 2.0
    assert combined.mass == 2.0
    # Combined CoM should be at [0.5, 0, 0]
    assert np.allclose(combined.pose.pos, [0.5, 0, 0])
    # Verify the I_xx remains the same (axis of rotation passes through both CoMs)
    # Note: Principal axes might rotate, so we check the resulting matrix diagonals
    assert combined.i_xx == pytest.approx(1 / 3)  # (1/6 + 1/6)


def test_inertial_subtraction(simple_box_inertial: Inertial):
    """Test 'carving out' matter."""
    small_mass = Inertial(
        mass=0.5,
        pose=PoseQuat(pos=np.asarray([0, 0, 0])),
        diaginertia=np.asarray([1 / 12, 1 / 12, 1 / 12]),
    )

    result = simple_box_inertial - small_mass

    assert result.mass == 0.5
    assert result.i_xx == pytest.approx(1 / 6 - 1 / 12)


def test_subtraction_physics_failure(simple_box_inertial: Inertial):
    """Ensure subtracting a 'larger' inertia than exists raises ValueError."""
    # Impossible: Subtracting more inertia than the base has
    massive_tool = Inertial(
        mass=0.1,
        pose=PoseQuat(pos=np.asarray([0, 0, 0])),
        diaginertia=np.asarray([10, 10, 10]),
    )

    with pytest.raises(ValueError, match="Resulting inertia matrix is non-physical"):
        _ = simple_box_inertial - massive_tool


def test_from_random_vector_draw(mojo_model: MojoModel):
    """Test sampling mass and position as single distributions."""
    m_dist = NormalDistribution(name=DistName("rand_mass"), mu=1.0, sigma=0.1)
    p1_dist = UniformDistribution(name=DistName("rand_pos_x"), low=-1, high=1)
    p2_dist = UniformDistribution(name=DistName("rand_pos_y"), low=-1, high=1)
    p3_dist = UniformDistribution(name=DistName("rand_pos_z"), low=-1, high=1)

    # We provide a valid diaginertia so physics check passes
    item = Inertial.from_random(
        mojo_model=mojo_model,
        mass=m_dist,
        pos=(p1_dist, p2_dist, p3_dist),
        diaginertia=np.asarray([0.1, 0.1, 0.1]),
    )

    assert item.mass > 0
    assert "rand_mass" in mojo_model.named
    assert "rand_pos_x" in mojo_model.named
    assert "rand_pos_y" in mojo_model.named
    assert "rand_pos_z" in mojo_model.named


def test_from_random_component_draw(mojo_model: MojoModel):
    """Test sampling individual X, Y, Z components of the position."""
    x_dist = UniformDistribution(name=DistName("pos_x"), low=5, high=6)

    # Mix distribution with static floats
    item = Inertial.from_random(
        mojo_model=mojo_model,
        mass=1.0,
        pos=(x_dist, 0.0, 0.0),
        diaginertia=np.asarray([0.1, 0.1, 0.1]),
    )

    assert isinstance(item.pose, PoseQuat)
    pos_array = np.asarray(item.pose.pos)
    assert 5 <= pos_array[0] <= 6
    assert pos_array[1] == 0.0
    assert "pos_x" in mojo_model.named


def test_from_random_max_retries(mojo_model: MojoModel):
    """Verify the retry logic when a distribution is physically impossible."""
    # Force a failure: Mass is positive, but diaginertia is zero/negative
    # (Uniform low=0 effectively creates invalid non-positive-definite matrices)
    bad_dist = UniformDistribution(name=DistName("bad_inertia"), low=-1.0, high=0.0)

    with pytest.raises(RuntimeError, match="Failed to generate valid Inertial"):
        Inertial.from_random(
            mojo_model=mojo_model,
            mass=1.0,
            pos=np.asarray([0, 0, 0]),
            diaginertia=(bad_dist, bad_dist, bad_dist),
            max_retries=3,
        )
