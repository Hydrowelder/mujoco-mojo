from pathlib import Path
from xml.etree.ElementTree import Element

import numpy as np
import pytest
from PIL import Image

from mujoco_mojo.mjcf import (
    Actuator,
    Asset,
    Body,
    Compiler,
    FreeJoint,
    GeomSphere,
    Joint,
    Mujoco,
    PoseQuat,
    Statistic,
    Texture,
    WorldBody,
)
from mujoco_mojo.mjcf.dependency_path import DepPath
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.general import ActuatorGeneral
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.pid import ActuatorPid
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import (
    ActuatorName,
    Angle,
    BodyName,
    DynType,
    EulerSeq,
    Fuse,
    JointName,
    JointType,
    Passthrough,
    TextureEmbed,
    TextureName,
    TextureType,
)

# attributes added in MuJoCo 3.16.0 that need no model of their own to test


def _xml(element: XMLModel) -> Element:
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


def test_the_worldbody_rejects_freejoints_at_construction() -> None:
    with pytest.raises(ValueError, match="Put the FreeJoint on a Body"):
        WorldBody(freejoints=[FreeJoint()])


# attributes added in MuJoCo 3.17.0 that need no model of their own to test


def test_compiler_passthrough_is_omitted_at_its_default() -> None:
    assert "passthrough" not in _xml(Compiler()).attrib


def test_compiler_writes_passthrough_and_mujoco_accepts_it() -> None:
    compiler = Compiler(passthrough=Passthrough.TEXTURES)

    assert _xml(compiler).attrib["passthrough"] == "textures"
    Mujoco(compilers=[compiler], worldbody=WorldBody()).to_mj_model()


def _texture(
    png: Path, embed: TextureEmbed = TextureEmbed.AUTO, class_: str | None = None
) -> Texture:
    return Texture(
        name=TextureName("tile"),
        type=TextureType.D2,
        file=DepPath(png),
        embed=embed,
        class_=class_,
    )


@pytest.fixture
def png(tmp_path: Path) -> Path:
    path = tmp_path / "tile.png"
    Image.fromarray(np.full((8, 8, 3), 200, dtype=np.uint8)).save(path)
    return path


def _compile_texture(
    texture: Texture, passthrough: Passthrough | None = None
) -> tuple[int, int, int]:
    """Compiles a model holding only `texture`, and returns its `tex_adr`, `tex_width`, and `ntexdata`."""
    compilers = [] if passthrough is None else [Compiler(passthrough=passthrough)]
    model = Mujoco(
        compilers=compilers,
        assets=[Asset(textures=[texture])],
        worldbody=WorldBody(),
    ).to_mj_model()
    return int(model.tex_adr[0]), int(model.tex_width[0]), int(model.ntexdata)


def test_texture_embed_and_class_are_omitted_at_their_defaults(png: Path) -> None:
    assert not {"embed", "class"} & set(_xml(_texture(png)).attrib)


def test_a_texture_writes_embed_and_class(png: Path) -> None:
    attributes = _xml(_texture(png, embed=TextureEmbed.FALSE, class_="tiles")).attrib

    assert attributes["embed"] == "false"
    assert attributes["class"] == "tiles"


def test_a_texture_is_decoded_into_the_model_by_default(png: Path) -> None:
    adr, width, ntexdata = _compile_texture(_texture(png))

    assert (adr, width) == (0, 8)
    assert ntexdata == 8 * 8 * 3


def test_a_texture_with_embed_false_is_left_by_reference(png: Path) -> None:
    """The model holds the texture's path instead of its pixels."""
    adr, width, ntexdata = _compile_texture(_texture(png, embed=TextureEmbed.FALSE))

    assert (adr, width, ntexdata) == (-1, 0, 0)


def test_passthrough_leaves_a_texture_by_reference(png: Path) -> None:
    adr, width, ntexdata = _compile_texture(_texture(png), Passthrough.TEXTURES)

    assert (adr, width, ntexdata) == (-1, 0, 0)


def test_embed_true_overrides_passthrough(png: Path) -> None:
    adr, width, _ = _compile_texture(
        _texture(png, embed=TextureEmbed.TRUE), Passthrough.TEXTURES
    )

    assert (adr, width) == (0, 8)


def test_the_deprecated_meaninertia_is_still_written_and_compiles() -> None:
    """MuJoCo 3.17.0 deprecates it with a compile warning, which is not an error."""
    statistic = Statistic(meaninertia=2.0)

    assert _xml(statistic).attrib["meaninertia"] == "2.0"
    Mujoco(statistics=[statistic], worldbody=WorldBody()).to_mj_model()
