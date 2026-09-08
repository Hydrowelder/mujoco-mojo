import mujoco
import numpy as np

from mujoco_mojo.mjcf import (
    Body,
    Camera,
    GeomSphere,
    Joint,
    Light,
    Mujoco,
    PoseQuat,
    SiteSphere,
    WorldBody,
)
from mujoco_mojo.mjcf.meta.frame import Frame
from mujoco_mojo.typing import Angle, BodyName, EulerSeq, JointName, JointType, SiteName


def _leg_body(name: str = "leg") -> Body:
    body = Body(name=BodyName(name), pose=PoseQuat(pos=np.array((0.0, 0.0, 1.0))))
    body.joints.append(
        Joint(
            name=JointName(f"{name}_hinge"),
            type=JointType.HINGE,
            axis=np.array((0, 1, 0)),
        )
    )
    body.geoms.append(GeomSphere(size=0.1))
    return body


def test_frame_accepts_bodies_geoms_sites_cameras_lights() -> None:
    """Frame's new fields hold real elements without raising."""
    frame = Frame(pose=PoseQuat(pos=np.array((1.0, 0.0, 0.0))))
    frame.bodies.append(_leg_body())
    frame.geoms.append(GeomSphere(size=0.05))
    frame.sites.append(SiteSphere(name=SiteName("anchor"), size=0.05))
    frame.cameras.append(Camera())
    frame.lights.append(Light())

    assert len(frame.bodies) == 1
    assert len(frame.geoms) == 1
    assert len(frame.sites) == 1
    assert len(frame.cameras) == 1
    assert len(frame.lights) == 1


def test_frame_to_xml_nests_children() -> None:
    """to_xml() writes bodies/sites as real nested elements under <frame>."""
    frame = Frame(pose=PoseQuat(pos=np.array((1.0, 0.0, 0.0))))
    frame.bodies.append(_leg_body())
    frame.sites.append(SiteSphere(name=SiteName("anchor"), size=0.05))

    el = frame.to_xml(compiler_degrees=Angle.DEGREE, compiler_eulerseq=EulerSeq.XYZ)

    assert el.tag == "frame"
    assert {child.tag for child in el} == {"body", "site"}


def test_frame_folds_pose_into_wrapped_body_and_site() -> None:
    """Compiling through MuJoCo: a frame's pose is folded into its wrapped body/site, matching real MJCF frame semantics."""
    frame = Frame(pose=PoseQuat(pos=np.array((1.0, 0.0, 0.0))))
    frame.bodies.append(_leg_body())
    frame.sites.append(
        SiteSphere(
            name=SiteName("anchor"),
            pose=PoseQuat(pos=np.array((0.0, 0.0, 0.5))),
            size=0.05,
        )
    )

    worldbody = WorldBody()
    worldbody.frames.append(frame)
    model = Mujoco(worldbody=worldbody)

    mj_model = model.to_mj_model()

    leg_id = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_BODY, "leg")
    assert np.allclose(mj_model.body_pos[leg_id], (1.0, 0.0, 1.0))

    site_id = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_SITE, "anchor")
    assert np.allclose(mj_model.site_pos[site_id], (1.0, 0.0, 0.5))


def test_walk_bodies_finds_bodies_nested_in_a_frame() -> None:
    """Body.walk_bodies() must see bodies wrapped in a Frame, not just direct .bodies children."""
    frame = Frame(pose=PoseQuat(pos=np.array((1.0, 0.0, 0.0))))
    frame.bodies.append(_leg_body())

    worldbody = WorldBody()
    worldbody.frames.append(frame)

    names = [b.name for b in worldbody.walk_bodies()]
    assert names == ["leg"]


def test_walk_bodies_finds_bodies_nested_in_frame_under_a_body() -> None:
    """A frame nested inside a regular body (not directly under worldbody) is also walked."""
    frame = Frame(pose=PoseQuat(pos=np.array((0.0, 1.0, 0.0))))
    frame.bodies.append(_leg_body("leg_a"))

    rocket = Body(name=BodyName("rocket"))
    rocket.frames.append(frame)

    worldbody = WorldBody()
    worldbody.bodies.append(rocket)

    names = sorted(b.name for b in worldbody.walk_bodies() if b.name is not None)
    assert names == ["leg_a", "rocket"]


def test_frame_walk_bodies_recurses_through_nested_frames() -> None:
    """Frame.walk_bodies() finds bodies through arbitrarily nested frames."""
    inner = Frame(pose=PoseQuat(pos=np.array((0.0, 0.0, 1.0))))
    inner.bodies.append(_leg_body("inner_leg"))

    outer = Frame(pose=PoseQuat(pos=np.array((1.0, 0.0, 0.0))))
    outer.bodies.append(_leg_body("outer_leg"))
    outer.frames.append(inner)

    names = sorted(b.name for b in outer.walk_bodies() if b.name is not None)
    assert names == ["inner_leg", "outer_leg"]


def test_pose_context_registers_bodies_and_sites_wrapped_in_a_frame() -> None:
    """PoseContext must register (and resolve local poses for) anything nested in a Frame."""
    frame = Frame(pose=PoseQuat(pos=np.array((1.0, 0.0, 0.0))))
    leg = _leg_body()
    frame.bodies.append(leg)
    anchor = SiteSphere(
        name=SiteName("anchor"), pose=PoseQuat(pos=np.array((0.0, 0.0, 0.5))), size=0.05
    )
    frame.sites.append(anchor)

    worldbody = WorldBody()
    worldbody.frames.append(frame)
    model = Mujoco(worldbody=worldbody)

    graph = model.pose_context
    assert id(frame) in graph._registered
    assert id(leg) in graph._registered
    assert id(anchor) in graph._registered

    local = graph.local_pose(leg, frame)
    assert np.allclose(local.pos, (0.0, 0.0, 1.0))
