import numpy as np

from mujoco_mojo.mjcf.pose import PoseEuler, PoseQuat
from mujoco_mojo.typing import EulerSeq


def test_pose_initialization():
    """Verify that Pose captures both position and orientation correctly."""
    p = np.asarray([1.0, 2.0, 3.0])
    q = np.asarray([1.0, 0.0, 0.0, 0.0])
    pose = PoseQuat(pos=p, quat=q)

    assert np.array_equal(np.asarray(pose.pos), p)
    assert np.array_equal(np.asarray(pose.quat), q)


def test_pose_apply():
    """Test point transformation (local to world)."""
    # Pose: Translate [1, 1, 1], Rotate 90deg around Z
    pose = PoseEuler(
        pos=np.asarray([1.0, 1.0, 1.0]),
        euler=np.asarray([0, 0, 90]),
        eulerseq=EulerSeq.XYZ,
    )

    # Local point: [1, 0, 0]
    # 1. Rotate [1, 0, 0] by 90z -> [0, 1, 0]
    # 2. Translate by [1, 1, 1] -> [1, 2, 1]
    local_pt = np.asarray([1.0, 0.0, 0.0])
    world_pt = pose.apply(local_pt)

    assert np.allclose(world_pt, [1.0, 2.0, 1.0])


def test_pose_multiplication_composition():
    """Test composition of two Poses."""
    # P1: Move 1m North (+Y)
    p1 = PoseQuat(pos=np.asarray([0, 1, 0]))
    # P2: Move 1m East (+X)
    p2 = PoseQuat(pos=np.asarray([1, 0, 0]))

    # Combined should be [1, 1, 0]
    p_combined = p1 * p2
    assert isinstance(p_combined, PoseQuat)
    assert np.allclose(np.asarray(p_combined.pos), [1.0, 1.0, 0.0])


def test_pose_inversion():
    """Verify P * P.inv() results in the identity pose."""
    pose = PoseEuler(pos=np.asarray([5.0, -2.0, 3.0]), euler=np.asarray([45, 30, 10]))

    pose_inv = pose.inv()
    identity = pose * pose_inv

    assert np.allclose(np.asarray(identity.pos), [0, 0, 0], atol=1e-7)
    assert np.allclose(identity.as_matrix(), np.eye(3), atol=1e-7)


def test_expressed_in():
    """Test relative coordinate frame transformation."""
    # World frame: Ball at [10, 0, 0], Camera at [2, 0, 0]
    ball_world = PoseQuat(pos=np.asarray([10.0, 0.0, 0.0]))
    cam_world = PoseQuat(pos=np.asarray([2.0, 0.0, 0.0]))

    # Ball from camera's perspective should be at [8, 0, 0]
    ball_rel = ball_world.expressed_in(cam_world)

    assert np.allclose(np.asarray(ball_rel.pos), [8.0, 0.0, 0.0])


def test_look_at_pose():
    """Verify Pose.look_at sets both position and pointing direction."""
    eye = np.asarray([0.0, 0.0, 1.0])
    target = np.asarray([0.0, 0.0, 0.0])  # Looking straight down

    # For a camera (-Z points at target), at [0,0,1] looking at [0,0,0],
    # the camera orientation should be identity (pointing down -Z).
    pose = PoseQuat.look_at(target=target, eye=eye, negative_z=True)

    assert np.allclose(np.asarray(pose.pos), eye)
    # Check that the -Z axis in world space points toward the target
    # Point [0, 0, -1] in local should be [0, 0, 0] in world
    assert np.allclose(pose.apply(np.asarray([0, 0, -1])), [0, 0, 0])


def test_pose_converters():
    """Verify pivoting between Pose types preserves translation."""
    p_orig = np.asarray([7.0, 8.0, 9.0])
    pose_quat = PoseQuat(pos=p_orig, quat=np.asarray([1, 0, 0, 0]))

    # Convert to Euler
    pose_euler = pose_quat.as_pose_euler(seq=EulerSeq.XYZ)
    assert isinstance(pose_euler, PoseEuler)
    assert np.array_equal(np.asarray(pose_euler.pos), p_orig)

    # Convert to ZAxis
    pose_z = pose_euler.as_pose_zaxis()
    assert np.array_equal(np.asarray(pose_z.pos), p_orig)
    assert np.allclose(np.asarray(pose_z.zaxis), [0, 0, 1])
