import numpy as np
import pytest

from mujoco_mojo.mjcf.orientation import AxisAngle, Euler, OrientationType, Quat, XYAxes
from mujoco_mojo.typing import Angle, EulerSeq


def test_quat_identity():
    """Verify Quat identity behavior and matrix conversion."""
    q = Quat(quat=np.asarray([1.0, 0.0, 0.0, 0.0]))
    assert np.allclose(q.as_matrix(), np.eye(3))
    assert q.type == OrientationType.QUAT


def test_euler_conversions():
    """Test Euler to matrix and back, including sequence changes."""
    # 90 degrees around Z
    e = Euler(euler=np.asarray([0, 0, 90]), eulerseq=EulerSeq.xyz, angle=Angle.DEGREE)

    mat = e.as_matrix()
    # Expected: x->y, y->-x, z->z
    expected = np.asarray([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    assert np.allclose(mat, expected, atol=1e-7)

    # Test with_eulerseq (convert xyz 90z to zyx)
    e_zyx = e.with_eulerseq(EulerSeq.zyx)
    assert e_zyx.eulerseq == EulerSeq.zyx
    assert np.allclose(e_zyx.as_matrix(), expected)


def test_axis_angle_with_helpers():
    """Test AxisAngle and its 'with_' modification methods."""
    aa = AxisAngle(axisangle=np.asarray([0, 0, 1, 90]), angle=Angle.DEGREE)

    # Change axis to X
    aa_x = aa.with_axis(np.asarray([1, 0, 0]))
    assert np.array_equal(np.asarray(aa_x.axisangle)[:3], [1, 0, 0])

    # Change angle value
    aa_180 = aa_x.with_angle_val(180.0)
    assert np.asarray(aa_180.axisangle)[3] == 180.0


def test_composition_and_inversion():
    """Test self * other and inv()."""
    # R1: 90 deg around X, R2: 90 deg around Y
    r1 = Euler(euler=np.asarray([90, 0, 0]))
    r2 = Euler(euler=np.asarray([0, 90, 0]))

    # Compose
    combined = r1 * r2
    assert isinstance(combined, Quat)  # Base class returns Quat for math

    # Invert
    inv_r1 = r1.inv()
    identity_check = r1 * inv_r1
    assert np.allclose(identity_check.as_matrix(), np.eye(3), atol=1e-7)


def test_angle_between():
    """Test the geodesic distance between orientations."""
    r1 = Euler(euler=np.asarray([0, 0, 0]))
    r2 = Euler(euler=np.asarray([0, 0, 90]))

    dist = r1.angle_between(r2, angle=Angle.DEGREE)
    assert pytest.approx(dist) == 90.0

    dist_rad = r1.angle_between(r2, angle=Angle.RADIAN)
    assert pytest.approx(dist_rad) == np.pi / 2


def test_look_at_factory():
    """Verify look_at produces the correct pointing vector."""
    # Look from origin toward +X
    target = [1, 0, 0]
    eye = [0, 0, 0]

    # Camera/Light convention: -Z points at target
    q = Quat.look_at(target=np.asarray(target), eye=np.asarray(eye), negative_z=True)

    # Forward vector in local space is [0, 0, -1]
    # Rotate it to world space; should match the pointing direction [1, 0, 0]
    world_forward = q.apply(np.asarray([0, 0, -1]))
    assert np.allclose(world_forward, [1, 0, 0], atol=1e-7)


def test_look_at_roll_zero_points_x_toward_world_z():
    """Verify roll=0 places the local X axis as close to world +Z as possible."""
    # Forward (world) = +X, since negative_z=False with target along +X
    q = Quat.look_at(
        target=np.asarray([1, 0, 0]), eye=np.asarray([0, 0, 0]), negative_z=False
    )

    # X axis in world space should be the projection of world +Z onto the
    # plane perpendicular to forward (+X), which is world +Z itself here.
    world_x_axis = q.apply(np.asarray([1, 0, 0]))
    assert np.allclose(world_x_axis, [0, 0, 1], atol=1e-7)


def test_look_at_roll_rotates_about_forward_axis():
    """Verify a 90 degree roll rotates the secondary axes but not the forward direction."""
    q_no_roll = Quat.look_at(
        target=np.asarray([1, 0, 0]), eye=np.asarray([0, 0, 0]), negative_z=False
    )
    q_rolled = Quat.look_at(
        target=np.asarray([1, 0, 0]),
        eye=np.asarray([0, 0, 0]),
        roll=90,
        negative_z=False,
    )

    # Forward direction is unaffected by roll.
    assert np.allclose(
        q_no_roll.apply(np.asarray([0, 0, 1])), q_rolled.apply(np.asarray([0, 0, 1]))
    )
    # A 90 degree roll moves the old X axis onto the old Y axis.
    assert np.allclose(
        q_rolled.apply(np.asarray([1, 0, 0])),
        q_no_roll.apply(np.asarray([0, 1, 0])),
        atol=1e-7,
    )


def test_look_at_roll_radians():
    """Verify roll accepts radians when angle=Angle.RADIAN."""
    q_deg = Quat.look_at(
        target=np.asarray([1, 0, 0]),
        eye=np.asarray([0, 0, 0]),
        roll=90,
        angle=Angle.DEGREE,
        negative_z=False,
    )
    q_rad = Quat.look_at(
        target=np.asarray([1, 0, 0]),
        eye=np.asarray([0, 0, 0]),
        roll=np.pi / 2,
        angle=Angle.RADIAN,
        negative_z=False,
    )

    assert np.allclose(q_deg.as_matrix(), q_rad.as_matrix(), atol=1e-7)


def test_look_at_up_overrides_roll():
    """Verify an explicit up vector takes precedence over roll and matches the legacy convention."""
    q = Quat.look_at(
        target=np.asarray([1, 0, 0]),
        eye=np.asarray([0, 0, 0]),
        up=np.asarray([0, 0, 1]),
        negative_z=False,
    )

    # Legacy convention: X = up x forward, Y = forward x X.
    world_x_axis = q.apply(np.asarray([1, 0, 0]))
    assert np.allclose(world_x_axis, np.cross([0, 0, 1], [1, 0, 0]), atol=1e-7)


def test_look_at_roll_handles_forward_colinear_with_world_z():
    """Verify look_at falls back gracefully when forward is colinear with world +Z."""
    q = Quat.look_at(
        target=np.asarray([0, 0, 0]), eye=np.asarray([0, 0, 1]), negative_z=True
    )

    assert np.allclose(q.as_matrix(), np.eye(3), atol=1e-7)


def test_universal_casts():
    """Verify we can pivot between any representation."""
    # Start with XYAxes
    xy = XYAxes(xyaxes=np.asarray([0, 1, 0, -1, 0, 0]))  # Rotated 90 deg around Z

    # Cast to Euler
    e = xy.as_euler(seq=EulerSeq.xyz)
    assert isinstance(e, Euler)
    assert np.allclose(e.as_matrix(), xy.as_matrix())

    # Cast to Quat
    q = e.as_quat()
    assert isinstance(q, Quat)
    assert np.allclose(q.as_matrix(), xy.as_matrix())


def test_vector_rotation():
    """Test the apply() method."""
    q = Euler(euler=np.asarray([0, 0, 90])).as_quat()
    v = [1, 0, 0]

    v_rot = q.apply(np.asarray(v))
    # 90 deg around Z takes X to Y
    assert np.allclose(v_rot, [0, 1, 0], atol=1e-7)
