from typing import NamedTuple

import numpy as np
import pytest

from mujoco_mojo.mjcf import (
    Body,
    Mujoco,
    PoseQuat,
    PoseRef,
    SiteSphere,
    WorldBody,
)
from mujoco_mojo.mjcf.meta.frame import Frame
from mujoco_mojo.mjcf.pose import PoseEuler
from mujoco_mojo.typing import EulerSeq

# ── fixture ───────────────────────────────────────────────────────────────────


class _TwoBranch(NamedTuple):
    model: Mujoco
    worldbody: WorldBody
    arm: Body
    torso: Body
    sensor: SiteSphere


def _two_branch_model() -> _TwoBranch:
    """
    Two bodies off worldbody: arm at [1,0,0], torso at [-1,0,0].

    sensor site sits at [0,0,0.5] local to arm, so [1,0,0.5] in world.
    """
    sensor = SiteSphere(size=0.05, pose=PoseQuat(pos=np.array([0.0, 0.0, 0.5])))
    arm = Body(pose=PoseQuat(pos=np.array([1.0, 0.0, 0.0])))
    arm.sites.append(sensor)
    torso = Body(pose=PoseQuat(pos=np.array([-1.0, 0.0, 0.0])))
    worldbody = WorldBody()
    worldbody.bodies.extend([arm, torso])
    model = Mujoco(worldbody=worldbody)
    return _TwoBranch(model, worldbody, arm, torso, sensor)


# ── registration ──────────────────────────────────────────────────────────────


def test_worldbody_is_registered():
    m = _two_branch_model()
    graph = m.model.pose_context
    assert id(m.worldbody) in graph._registered


def test_bodies_and_sites_are_registered():
    m = _two_branch_model()
    graph = m.model.pose_context
    assert id(m.arm) in graph._registered
    assert id(m.torso) in graph._registered
    assert id(m.sensor) in graph._registered


def test_frame_is_registered():
    frame = Frame(pose=PoseQuat(pos=np.array([0.0, 0.0, 1.0])))
    arm = Body(pose=PoseQuat(pos=np.array([1.0, 0.0, 0.0])))
    arm.frames.append(frame)
    worldbody = WorldBody()
    worldbody.bodies.append(arm)
    model = Mujoco(worldbody=worldbody)

    graph = model.pose_context
    assert id(frame) in graph._registered


# ── local_pose math ───────────────────────────────────────────────────────────


def test_local_pose_same_frame_is_identity():
    """Expressing a body in its own frame should give the identity pose."""
    m = _two_branch_model()
    graph = m.model.pose_context

    result = graph.local_pose(m.arm, m.arm)
    assert np.allclose(result.pos, [0, 0, 0], atol=1e-7)
    assert np.allclose(result.as_matrix(), np.eye(3), atol=1e-7)


def test_local_pose_body_in_worldbody():
    """Arm at [1,0,0] expressed in worldbody frame should give [1,0,0]."""
    m = _two_branch_model()
    result = m.model.pose_context.local_pose(m.arm, m.worldbody)
    assert np.allclose(result.pos, [1, 0, 0], atol=1e-7)


def test_local_pose_site_in_worldbody():
    """Sensor at [0,0,0.5] on arm at [1,0,0] -> world pos [1,0,0.5]."""
    m = _two_branch_model()
    result = m.model.pose_context.local_pose(m.sensor, m.worldbody)
    assert np.allclose(result.pos, [1, 0, 0.5], atol=1e-7)


def test_cross_branch_translation():
    """Sensor world pos [1,0,0.5], torso at [-1,0,0] -> [2,0,0.5] in torso frame."""
    m = _two_branch_model()
    result = m.model.pose_context.local_pose(m.sensor, m.torso)
    assert np.allclose(result.pos, [2, 0, 0.5], atol=1e-7)


def test_cross_branch_rotation():
    """
    Arm rotated 90deg around Z at origin; site at [1,0,0] local -> [0,1,0] world.
    Expressed in torso at [0,-1,0], result should be [0,2,0].
    """
    site = SiteSphere(size=0.05, pose=PoseQuat(pos=np.array([1.0, 0.0, 0.0])))
    arm = Body(
        pose=PoseEuler(
            pos=np.array([0.0, 0.0, 0.0]),
            euler=np.array([0.0, 0.0, 90.0]),
            eulerseq=EulerSeq.XYZ,
        )
    )
    arm.sites.append(site)
    torso = Body(pose=PoseQuat(pos=np.array([0.0, -1.0, 0.0])))
    worldbody = WorldBody()
    worldbody.bodies.extend([arm, torso])
    model = Mujoco(worldbody=worldbody)

    result = model.pose_context.local_pose(site, torso)
    assert np.allclose(result.pos, [0, 2, 0], atol=1e-6)


def test_deep_tree_pose():
    """
    Three levels deep: world -> a (1,0,0) -> b (0,1,0) -> c (0,0,1).
    World pos of c should be [1,1,1].
    """
    body_c = Body(pose=PoseQuat(pos=np.array([0.0, 0.0, 1.0])))
    body_b = Body(pose=PoseQuat(pos=np.array([0.0, 1.0, 0.0])))
    body_b.bodies.append(body_c)
    body_a = Body(pose=PoseQuat(pos=np.array([1.0, 0.0, 0.0])))
    body_a.bodies.append(body_b)
    worldbody = WorldBody()
    worldbody.bodies.append(body_a)
    model = Mujoco(worldbody=worldbody)

    result = model.pose_context.local_pose(body_c, worldbody)
    assert np.allclose(result.pos, [1, 1, 1], atol=1e-7)


def test_frame_pose_in_worldbody():
    """Frame at [0,0,1] on arm at [1,0,0] -> world pos [1,0,1]."""
    frame = Frame(pose=PoseQuat(pos=np.array([0.0, 0.0, 1.0])))
    arm = Body(pose=PoseQuat(pos=np.array([1.0, 0.0, 0.0])))
    arm.frames.append(frame)
    worldbody = WorldBody()
    worldbody.bodies.append(arm)
    model = Mujoco(worldbody=worldbody)

    result = model.pose_context.local_pose(frame, worldbody)
    assert np.allclose(result.pos, [1, 0, 1], atol=1e-7)


def test_nested_frame_pose():
    """
    Nested frames: body at [1,0,0], frame_a at [0,1,0], frame_b at [0,0,1].
    frame_b world pos = [1,1,1].
    """
    frame_b = Frame(pose=PoseQuat(pos=np.array([0.0, 0.0, 1.0])))
    frame_a = Frame(pose=PoseQuat(pos=np.array([0.0, 1.0, 0.0])))
    frame_a.frames.append(frame_b)
    arm = Body(pose=PoseQuat(pos=np.array([1.0, 0.0, 0.0])))
    arm.frames.append(frame_a)
    worldbody = WorldBody()
    worldbody.bodies.append(arm)
    model = Mujoco(worldbody=worldbody)

    result = model.pose_context.local_pose(frame_b, worldbody)
    assert np.allclose(result.pos, [1, 1, 1], atol=1e-7)


# ── PoseRef ───────────────────────────────────────────────────────────────────


def test_pose_ref_to_quat():
    """PoseRef.to_quat resolves via the Mujoco instance."""
    m = _two_branch_model()
    result = PoseRef(frame=m.sensor, relative_to=m.torso).to_quat(m.model)
    assert np.allclose(result.pos, [2, 0, 0.5], atol=1e-7)


def test_pose_ref_multiple():
    """Multiple PoseRefs resolved via the same Mujoco instance give consistent results."""
    m = _two_branch_model()

    r1 = PoseRef(frame=m.sensor, relative_to=m.torso).to_quat(m.model)
    r2 = PoseRef(frame=m.arm, relative_to=m.worldbody).to_quat(m.model)

    assert np.allclose(r1.pos, [2, 0, 0.5], atol=1e-7)
    assert np.allclose(r2.pos, [1, 0, 0], atol=1e-7)


# ── Mujoco.local_pose convenience ────────────────────────────────────────────


def test_mujoco_local_pose_matches_graph():
    """Mujoco.local_pose should give the same result as building the graph manually."""
    m = _two_branch_model()

    via_method = m.model.local_pose(frame=m.sensor, relative_to=m.torso)
    via_graph = m.model.pose_context.local_pose(m.sensor, m.torso)

    assert np.allclose(via_method.pos, via_graph.pos, atol=1e-7)
    assert np.allclose(via_method.as_matrix(), via_graph.as_matrix(), atol=1e-7)


def test_mujoco_pose_graph_raises_without_worldbody():
    model = Mujoco()
    with pytest.raises(ValueError, match="worldbody"):
        model.pose_context


# ── error cases ───────────────────────────────────────────────────────────────


def test_frame_not_in_tree_raises():
    m = _two_branch_model()
    orphan = Body(pose=PoseQuat(pos=np.array([5.0, 0.0, 0.0])))
    graph = m.model.pose_context

    with pytest.raises(ValueError, match="frame is not registered"):
        graph.local_pose(orphan, m.torso)


def test_relative_to_not_in_tree_raises():
    m = _two_branch_model()
    orphan = Body(pose=PoseQuat(pos=np.array([5.0, 0.0, 0.0])))
    graph = m.model.pose_context

    with pytest.raises(ValueError, match="relative_to is not registered"):
        graph.local_pose(m.sensor, orphan)
