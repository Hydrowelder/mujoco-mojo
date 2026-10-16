from xml.etree.ElementTree import Element

import numpy as np

from mujoco_mojo.mjcf import (
    Actuator,
    Body,
    Compiler,
    FreeJoint,
    GeomSphere,
    Joint,
    Mujoco,
    PoseQuat,
    WorldBody,
)
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.general import ActuatorGeneral
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.pid import ActuatorPid
from mujoco_mojo.typing import (
    ActuatorName,
    Angle,
    BodyName,
    DynType,
    EulerSeq,
    Fuse,
    JointName,
    JointType,
)

# attributes added in MuJoCo 3.16.0 that need no model of their own to test


def _xml(element: Body | Compiler | ActuatorGeneral | WorldBody) -> Element:
    return element.to_xml(compiler_degrees=Angle.DEGREE, compiler_eulerseq=EulerSeq.XYZ)


def _hinge_body() -> Body:
    body = Body(name=BodyName("arm"))
    body.joints.append(Joint(name=JointName("elbow"), type=JointType.HINGE))
    body.geoms.append(GeomSphere(size=0.1))
    return body


def test_compiler_save_attributes_are_omitted_at_their_defaults() -> None:
    assert not {"savecompiled", "savecanonical"} & set(_xml(Compiler()).attrib)


def test_compiler_writes_the_save_attributes_and_mujoco_accepts_them() -> None:
    compiler = Compiler(savecompiled=False, savecanonical=False)

    attributes = _xml(compiler).attrib

    assert attributes["savecompiled"] == "false"
    assert attributes["savecanonical"] == "false"
    Mujoco(compilers=[compiler], worldbody=WorldBody()).to_mj_model()


def _static_body_model(fuse: Fuse | None) -> tuple[Mujoco, Body]:
    """A model with the compiler fusing static bodies, and the static child body it contains."""
    parent = Body(name=BodyName("parent"))
    parent.geoms.append(GeomSphere(size=0.1))
    static = Body(name=BodyName("static"), pose=PoseQuat(pos=np.array((1.0, 0, 0))))
    static.geoms.append(GeomSphere(size=0.1))
    if fuse is not None:
        static.fuse = fuse
    parent.bodies.append(static)
    worldbody = WorldBody()
    worldbody.bodies.append(parent)
    return Mujoco(compilers=[Compiler(fusestatic=True)], worldbody=worldbody), static


def test_a_static_body_is_fused_by_default() -> None:
    for fuse in (None, Fuse.AUTO):
        model, _ = _static_body_model(fuse)

        assert model.to_mj_model().nbody == 1


def test_fuse_false_keeps_a_static_body() -> None:
    model, static = _static_body_model(Fuse.FALSE)

    assert _xml(static).attrib["fuse"] == "false"
    assert model.to_mj_model().nbody == 2


def test_general_actuator_writes_inheritrange_only_when_set() -> None:
    plain = ActuatorGeneral(name=ActuatorName("a"), joint=JointName("elbow"))
    inheriting = ActuatorGeneral(
        name=ActuatorName("a"),
        joint=JointName("elbow"),
        dyntype=DynType.INTEGRATOR,
        inheritrange=1.0,
    )

    assert "inheritrange" not in _xml(plain).attrib
    assert float(_xml(inheriting).attrib["inheritrange"]) == 1.0


def test_general_actuator_with_inheritrange_compiles() -> None:
    arm = _hinge_body()
    worldbody = WorldBody()
    worldbody.bodies.append(arm)
    actuator = ActuatorGeneral(
        name=ActuatorName("a"),
        joint=JointName("elbow"),
        dyntype=DynType.INTEGRATOR,
        inheritrange=1.0,
    )

    Mujoco(worldbody=worldbody, actuators=[Actuator(generals=[actuator])]).to_mj_model()


def test_a_default_pid_actuator_has_the_gain_mujoco_documents() -> None:
    """MuJoCo 3.16.0 gives a pid without kp the documented gain of 1, which is the default mojo declares (and so leaves out of the XML)."""
    worldbody = WorldBody()
    worldbody.bodies.append(_hinge_body())
    pid = ActuatorPid(name=ActuatorName("a"), joint=JointName("elbow"))

    mj_model = Mujoco(
        worldbody=worldbody, actuators=[Actuator(pids=[pid])]
    ).to_mj_model()

    assert pid.kp == 1
    # a pid keeps its proportional gain as the (negated) slope of the bias
    assert mj_model.actuator_biasprm[0][1] == -1


def test_the_worldbody_does_not_write_freejoints() -> None:
    """MuJoCo rejects a joint of any kind directly in the worldbody ("World body cannot have joints")."""
    assert "freejoints" not in WorldBody.children
    assert "freejoints" in Body.children

    worldbody = WorldBody()
    worldbody.freejoints.append(FreeJoint())

    assert "freejoint" not in {child.tag for child in _xml(worldbody)}
    Mujoco(worldbody=worldbody).to_mj_model()
