import numpy as np
import pytest

from mujoco_mojo.mjcf.pose import PoseEuler, PoseQuat
from mujoco_mojo.typing import EulerSeq
from mujoco_mojo.utils.column import Column


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


def test_look_at_pose_roll():
    """Verify Pose.look_at forwards roll to the underlying orientation, leaving position and forward direction unaffected."""
    eye = np.asarray([0.0, 0.0, 0.0])
    target = np.asarray([1.0, 0.0, 0.0])

    pose_no_roll = PoseQuat.look_at(target=target, eye=eye, negative_z=False)
    pose_rolled = PoseQuat.look_at(target=target, eye=eye, roll=90, negative_z=False)

    assert np.allclose(np.asarray(pose_rolled.pos), eye)
    assert np.allclose(
        pose_rolled.apply(np.asarray([0, 0, 1])),
        pose_no_roll.apply(np.asarray([0, 0, 1])),
    )
    assert np.allclose(
        pose_rolled.apply(np.asarray([1, 0, 0])),
        pose_no_roll.apply(np.asarray([0, 1, 0])),
        atol=1e-7,
    )


def test_look_at_pose_up_overrides_roll():
    """Verify Pose.look_at still accepts an explicit up vector, matching the legacy convention."""
    eye = np.asarray([0.0, 0.0, 0.0])
    target = np.asarray([1.0, 0.0, 0.0])

    pose = PoseQuat.look_at(
        target=target, eye=eye, up=np.asarray([0, 0, 1]), negative_z=False
    )

    world_x_axis = pose.apply(np.asarray([1, 0, 0])) - eye
    assert np.allclose(world_x_axis, np.cross([0, 0, 1], [1, 0, 0]), atol=1e-7)


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


_ROW = {
    "Sites/A/xpos:x": 1.0,
    "Sites/A/xpos:y": 2.0,
    "Sites/A/xpos:z": 3.0,
    "Sites/A/quat:w": 0.5,
    "Sites/A/quat:x": 0.5,
    "Sites/A/quat:y": 0.5,
    "Sites/A/quat:z": 0.5,
    "time": 0.25,
}


def test_from_row_builds_the_pose_from_a_telemetry_row():
    pose = PoseQuat.from_row(_ROW, "Sites/A")
    assert np.allclose(pose.pos, [1.0, 2.0, 3.0])
    assert np.allclose(pose.quat, [0.5, 0.5, 0.5, 0.5])


def test_from_row_accepts_a_column_and_other_channels():
    row = {
        k.replace("xpos", "xipos").replace("quat", "xiquat"): v for k, v in _ROW.items()
    }
    pose = PoseQuat.from_row(
        row,
        Column(category="Sites", subgroups=("A",)),
        pos_channel="xipos",
        quat_channel="xiquat",
    )
    assert np.allclose(pose.pos, [1.0, 2.0, 3.0])


def test_from_row_reads_quaternion_components_by_name():
    row = {
        **_ROW,
        "Sites/A/quat:w": 1.0,
        "Sites/A/quat:x": 0.0,
        "Sites/A/quat:y": 0.0,
        "Sites/A/quat:z": 0.0,
    }
    assert np.allclose(PoseQuat.from_row(row, "Sites/A").quat, [1.0, 0.0, 0.0, 0.0])


def test_from_row_raises_naming_every_missing_column():
    row = {k: v for k, v in _ROW.items() if not k.endswith(("quat:y", "xpos:z"))}
    with pytest.raises(ValueError, match="Sites/A/quat:y") as excinfo:
        PoseQuat.from_row(row, "Sites/A")
    assert "Sites/A/xpos:z" in str(excinfo.value)
    assert "request(channels=" in str(excinfo.value)


def test_from_row_rejects_a_single_column_source():
    with pytest.raises(ValueError, match="names a single column"):
        PoseQuat.from_row(_ROW, "Sites/A/xpos:x")
