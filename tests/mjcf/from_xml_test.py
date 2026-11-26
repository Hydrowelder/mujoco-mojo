import logging
from pathlib import Path
from typing import Any, get_args

import mujoco
import numpy as np
import pytest

from mujoco_mojo.mjcf import Asset, Mujoco
from mujoco_mojo.mjcf.mujoco_attr.asset_attr.mesh import (
    AnyMesh,
    Mesh,
    MeshBox,
    MeshCone,
    MeshCylinder,
    MeshDisc,
    MeshEllipsoid,
    MeshGrid,
    MeshHemisphere,
    MeshPlate,
    MeshSphere,
    MeshSupersphere,
    MeshTorus,
    MeshWedge,
    MeshSquare,
)
from mujoco_mojo.mjcf.mujoco_attr.asset_attr.texture import Texture, TextureBuiltIn
from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import (
    GeomBox,
    GeomCapsule,
    GeomCylinder,
    GeomEllipsoid,
    GeomHField,
    GeomMesh,
    GeomPlane,
    GeomSphere,
)
from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import (
    SiteBox,
    SiteCapsule,
    SiteCylinder,
    SiteEllipsoid,
    SiteMesh,
    SiteSphere,
)
from mujoco_mojo.mjcf.mujoco_attr.equality_attr.connect import (
    EqualityConnectBody,
    EqualityConnectSite,
)
from mujoco_mojo.mjcf.mujoco_attr.equality_attr.weld import (
    EqualityWeldBody,
    EqualityWeldSite,
)
from mujoco_mojo.mjcf.pose import (
    PoseAxisAngle,
    PoseEuler,
    PoseQuat,
    PoseXYAxes,
    PoseZAxis,
)
from mujoco_mojo.typing import Angle, EulerSeq
from mujoco_mojo.utils.utils import to_pretty_xml

DOCS_MODELS = sorted(
    (Path(__file__).parents[2] / "docs" / "assets" / "models").glob("*/model.xml")
)

# written the way another tool would: no `type` on a sphere, short forms, no defaults spelled out
HAND_WRITTEN = """
<mujoco model="hand">
  <compiler angle="radian" eulerseq="XYZ"/>
  <option timestep="0.002"/>
  <asset>
    <texture name="grid" type="2d" builtin="checker" width="64" height="64" rgb1=".1 .2 .3" rgb2=".2 .3 .4"/>
    <material name="floor" texture="grid" texrepeat="4 4"/>
    <mesh name="tetra" vertex="0 0 0 1 0 0 0 1 0 0 0 1"/>
  </asset>
  <worldbody>
    <light pos="0 0 3" dir="0 0 -1"/>
    <geom name="floor" type="plane" size="2 2 .1" material="floor"/>
    <body name="arm" pos="0 0 1" euler="0 0 1.5707963">
      <joint name="hinge" axis="0 1 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 .5" size=".05"/>
      <site name="tip" pos="0 0 .5" size=".02"/>
      <body name="forearm" pos="0 0 .5" axisangle="0 1 0 .5">
        <joint name="elbow" axis="0 1 0"/>
        <geom type="box" size=".03 .03 .2" pos="0 0 .2"/>
        <geom size=".01"/>
        <geom type="mesh" mesh="tetra"/>
      </body>
    </body>
  </worldbody>
  <actuator>
    <motor name="drive" joint="hinge" gear="2"/>
  </actuator>
  <sensor>
    <jointpos name="angle" joint="hinge"/>
  </sensor>
</mujoco>
"""


def compiled(model: mujoco.MjModel) -> bytes:
    """The compiled model as MuJoCo saves it, which two models share only if every number and name in them agrees."""
    buffer = np.empty(mujoco.mj_sizeModel(model), dtype=np.uint8)
    mujoco.mj_saveModel(model, None, buffer)
    return bytes(buffer)


def written(model: Mujoco) -> str:
    return to_pretty_xml(
        model.to_xml(
            compiler_degrees=model.compiler_degree_settings,
            compiler_eulerseq=model.compiler_eulerseq_settings,
        )
    )


def body_with(attrs: str) -> Any:
    """The one body of a model that has only that."""
    model = Mujoco.from_xml(
        f"<mujoco><worldbody><body {attrs}/></worldbody></mujoco>", strict=True
    )
    assert model.worldbody is not None
    return model.worldbody.bodies[0]


def test_the_docs_models_are_found() -> None:
    assert DOCS_MODELS


@pytest.mark.parametrize("path", DOCS_MODELS, ids=lambda path: path.parent.name)
def test_a_model_mojo_wrote_compiles_to_the_same_model_when_read_back(
    path: Path,
) -> None:
    """The two docs models cover meshes, textures, sensors, frames, joints and a compiler setting."""
    original = mujoco.MjModel.from_xml_path(str(path))

    assert compiled(Mujoco.from_xml(path).to_mj_model()) == compiled(original)


@pytest.mark.parametrize("path", DOCS_MODELS, ids=lambda path: path.parent.name)
def test_writing_what_was_read_and_reading_it_again_changes_nothing(
    path: Path,
) -> None:
    once = written(Mujoco.from_xml(path))

    assert written(Mujoco.from_xml(once)) == once


def test_xml_written_by_hand_compiles_to_the_same_model() -> None:
    model = Mujoco.from_xml(HAND_WRITTEN)

    assert model.model == "hand"
    assert compiled(model.to_mj_model()) == compiled(
        mujoco.MjModel.from_xml_string(HAND_WRITTEN)
    )


def test_a_geom_with_no_type_is_a_sphere() -> None:
    model = Mujoco.from_xml(HAND_WRITTEN)

    assert model.worldbody is not None
    forearm = model.worldbody.bodies[0].bodies[0]
    assert [type(geom) for geom in forearm.geoms] == [GeomBox, GeomSphere, GeomMesh]


@pytest.mark.parametrize(
    ("attrs", "expected"),
    [
        pytest.param('type="plane" size="1 1 .1"', GeomPlane, id="plane"),
        pytest.param('type="hfield" hfield="h"', GeomHField, id="hfield"),
        pytest.param('type="sphere" size=".1"', GeomSphere, id="sphere"),
        pytest.param('type="capsule" size=".1 .2"', GeomCapsule, id="capsule"),
        pytest.param('type="ellipsoid" size=".1 .2 .3"', GeomEllipsoid, id="ellipsoid"),
        pytest.param('type="cylinder" size=".1 .2"', GeomCylinder, id="cylinder"),
        pytest.param('type="box" size=".1 .2 .3"', GeomBox, id="box"),
        pytest.param('type="mesh" mesh="m"', GeomMesh, id="mesh"),
    ],
)
def test_each_kind_of_geom_is_read_as_its_class(attrs: str, expected: type) -> None:
    model = Mujoco.from_xml(f"<mujoco><worldbody><geom {attrs}/></worldbody></mujoco>")

    assert model.worldbody is not None
    assert type(model.worldbody.geoms[0]) is expected


@pytest.mark.parametrize(
    ("attrs", "expected"),
    [
        pytest.param('size=".1"', SiteSphere, id="sphere-by-default"),
        pytest.param('type="capsule" size=".1 .2"', SiteCapsule, id="capsule"),
        pytest.param('type="ellipsoid" size=".1 .2 .3"', SiteEllipsoid, id="ellipsoid"),
        pytest.param('type="cylinder" size=".1 .2"', SiteCylinder, id="cylinder"),
        pytest.param('type="box" size=".1 .2 .3"', SiteBox, id="box"),
        pytest.param('type="mesh" mesh="m"', SiteMesh, id="mesh"),
    ],
)
def test_each_kind_of_site_is_read_as_its_class(attrs: str, expected: type) -> None:
    model = Mujoco.from_xml(f"<mujoco><worldbody><site {attrs}/></worldbody></mujoco>")

    assert model.worldbody is not None
    assert type(model.worldbody.sites[0]) is expected


@pytest.mark.parametrize(
    ("attrs", "expected"),
    [
        pytest.param("", PoseQuat, id="none"),
        pytest.param('quat="1 0 0 0"', PoseQuat, id="quat"),
        pytest.param('axisangle="0 0 1 90"', PoseAxisAngle, id="axisangle"),
        pytest.param('xyaxes="1 0 0 0 1 0"', PoseXYAxes, id="xyaxes"),
        pytest.param('zaxis="0 0 1"', PoseZAxis, id="zaxis"),
        pytest.param('euler="0 0 90"', PoseEuler, id="euler"),
    ],
)
def test_the_orientation_attribute_picks_the_pose(attrs: str, expected: type) -> None:
    body = body_with(f'pos="1 2 3" {attrs}')

    assert type(body.pose) is expected
    np.testing.assert_array_equal(body.pose.pos, (1, 2, 3))


def test_a_body_with_no_pose_attributes_keeps_the_default_pose() -> None:
    assert body_with('name="b"').pose == PoseQuat()


def test_the_compilers_angle_and_euler_sequence_go_to_the_orientations() -> None:
    model = Mujoco.from_xml(
        '<mujoco><compiler angle="radian" eulerseq="ZYX"/>'
        '<worldbody><body euler="0 0 1"/></worldbody></mujoco>'
    )

    assert model.worldbody is not None
    pose = model.worldbody.bodies[0].pose
    assert isinstance(pose, PoseEuler)
    assert pose.angle is Angle.RADIAN
    assert pose.eulerseq == EulerSeq("ZYX")


def test_angles_are_degrees_when_there_is_no_compiler() -> None:
    pose = body_with('euler="0 0 90"').pose

    assert isinstance(pose, PoseEuler)
    assert pose.angle is Angle.DEGREE


def test_the_compilers_must_agree_on_the_angle() -> None:
    with pytest.raises(ValueError, match="Inconsistent compiler angle"):
        Mujoco.from_xml(
            '<mujoco><compiler angle="radian"/><compiler angle="degree"/></mujoco>'
        )


def test_connects_and_welds_are_read_by_what_they_join() -> None:
    model = Mujoco.from_xml(
        """
        <mujoco><equality>
          <connect body1="a" body2="b" anchor="0 0 0"/>
          <connect site1="s" site2="t"/>
          <weld body1="a"/>
          <weld site1="s" site2="t"/>
        </equality></mujoco>
        """
    )

    equality = model.equalities[0]
    assert [type(c) for c in equality.connects] == [
        EqualityConnectBody,
        EqualityConnectSite,
    ]
    assert [type(w) for w in equality.welds] == [EqualityWeldBody, EqualityWeldSite]


def test_a_texture_is_built_in_when_its_builtin_is_not_none() -> None:
    model = Mujoco.from_xml(
        """
        <mujoco><asset>
          <texture name="a" type="2d" builtin="checker" width="8" height="8"/>
          <texture name="b" type="2d" builtin="none" file="b.png"/>
          <texture name="c" type="2d" file="c.png"/>
        </asset></mujoco>
        """
    )

    assert [type(t) for t in model.assets[0].textures] == [
        TextureBuiltIn,
        Texture,
        Texture,
    ]


def test_a_mesh_may_say_builtin_none() -> None:
    model = Mujoco.from_xml(
        '<mujoco><asset><mesh name="m" builtin="none" file="m.stl"/></asset></mujoco>'
    )

    assert type(model.assets[0].meshes[0]) is Mesh


SPACING = np.array((0.1, 0.2, 0.3))
BUILTIN_MESHES: list[AnyMesh] = [
    MeshSphere(name="m", subdivision=2),
    MeshHemisphere(name="m", resolution=3),
    MeshCone(name="m", nvert=5, radius=0.5),
    MeshSupersphere(name="m", resolution=4, e=1.5, n=2.5),
    MeshTorus(name="m", resolution=4, radius=0.5, s=1.5, t=2.5),
    MeshWedge(
        name="m", res_phi=3, res_theta=4, fov_phi=60.0, fov_theta=40.0, gamma=0.5
    ),
    MeshPlate(name="m", res_x=3, res_y=4),
    MeshGrid(name="m", count=(3, 4, 5), spacing=SPACING),
    MeshBox(name="m", count=(3, 4, 5), spacing=SPACING, dim=3),
    MeshCylinder(name="m", count=(3, 4, 5), spacing=SPACING, dim=3),
    MeshEllipsoid(name="m", count=(3, 4, 5), spacing=SPACING, dim=3),
    MeshSquare(name="m", count=(3, 4, 1), spacing=SPACING),
    MeshDisc(name="m", count=(3, 4, 1), spacing=SPACING),
]


@pytest.mark.parametrize(
    "mesh", BUILTIN_MESHES, ids=lambda mesh: type(mesh).__name__.removeprefix("Mesh")
)
def test_a_builtin_mesh_is_read_back_from_its_params(mesh: AnyMesh) -> None:
    """`params` packs the shape's own fields into one attribute, and reading it unpacks them."""
    xml = written(Mujoco(assets=[Asset(meshes=[mesh])]))

    read = Mujoco.from_xml(xml).assets[0].meshes[0]

    assert type(read) is type(mesh)
    for name in type(mesh).non_xml_fields:
        np.testing.assert_array_equal(getattr(read, name), getattr(mesh, name))


def test_every_builtin_mesh_is_covered_above() -> None:
    """The meshes above are every member of the mesh union but the one that is not built in, so a new one fails here until it is added."""
    builtin = set(get_args(get_args(AnyMesh)[0])) - {Mesh}

    assert len(builtin) == 13
    assert {type(mesh) for mesh in BUILTIN_MESHES} == builtin


def test_a_str_is_xml_and_not_a_file_name() -> None:
    with pytest.raises(ValueError, match="pass a Path to read a file"):
        Mujoco.from_xml("model.xml")


def test_xml_that_is_not_well_formed_is_refused() -> None:
    with pytest.raises(ValueError, match="not well formed"):
        Mujoco.from_xml("<mujoco><worldbody></mujoco>")


def test_the_root_has_to_be_a_mujoco_element() -> None:
    with pytest.raises(
        ValueError, match="Expected a <mujoco> element but found <body>"
    ):
        Mujoco.from_xml("<body/>")


def test_everything_that_cannot_be_read_is_listed_at_once() -> None:
    with pytest.raises(ValueError) as error:
        Mujoco.from_xml(
            """
            <mujoco>
              <default><geom size="1"/></default>
              <worldbody>
                <body name="arm"><geom size="1" nonsense="2"/></body>
                <geom type="blob"/>
              </worldbody>
            </mujoco>
            """
        )

    message = str(error.value)
    assert "mujoco/default[0]: unsupported element" in message
    assert (
        "mujoco/worldbody[0]/body 'arm'/geom[0]: unsupported attribute 'nonsense'"
        in message
    )
    assert "mujoco/worldbody[0]/geom[0]: type 'blob' is not one of" in message
    assert "strict=False" in message


def test_what_cannot_be_read_is_dropped_when_not_strict(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # a logger from `get_logger` does not propagate, which is where caplog listens
    monkeypatch.setattr(
        logging.getLogger("mujoco_mojo.mjcf.xml_reader"), "propagate", True
    )
    xml = '<mujoco><default><geom size="1"/></default><worldbody><geom size="2" nonsense="3"/></worldbody></mujoco>'

    with caplog.at_level(logging.WARNING, logger="mujoco_mojo.mjcf.xml_reader"):
        model = Mujoco.from_xml(xml, strict=False)

    assert model.worldbody is not None
    geom = model.worldbody.geoms[0]
    assert isinstance(geom, GeomSphere)
    assert geom.size == 2
    assert "mujoco/default[0]: unsupported element" in caplog.text
    assert "unsupported attribute 'nonsense'" in caplog.text


def test_an_element_that_may_appear_once_cannot_appear_twice() -> None:
    with pytest.raises(ValueError, match="only one is allowed"):
        Mujoco.from_xml("<mujoco><worldbody/><worldbody/></mujoco>")


def test_a_value_that_is_not_a_number_names_its_attribute() -> None:
    with pytest.raises(ValueError, match="attribute 'pos'"):
        body_with('pos="1 two 3"')


MESH_XML = '<mujoco>{compiler}<asset><mesh name="m" file="{file}"/></asset></mujoco>'


@pytest.mark.parametrize(
    ("compiler", "file", "expected"),
    [
        pytest.param("", "m.stl", "m.stl", id="beside-the-xml"),
        pytest.param(
            '<compiler meshdir="assets"/>', "m.stl", "assets/m.stl", id="meshdir"
        ),
        pytest.param(
            '<compiler assetdir="assets" meshdir="meshes"/>',
            "m.stl",
            "meshes/m.stl",
            id="meshdir-beats-assetdir",
        ),
        pytest.param(
            '<compiler meshdir="assets" strippath="true"/>',
            "deep/m.stl",
            "assets/m.stl",
            id="strippath",
        ),
        pytest.param("", "/elsewhere/m.stl", None, id="absolute-is-kept"),
    ],
)
def test_a_files_relative_paths_are_completed_from_its_own_folder(
    tmp_path: Path, compiler: str, file: str, expected: str | None
) -> None:
    xml = tmp_path / "model.xml"
    xml.write_text(MESH_XML.format(compiler=compiler, file=file), encoding="utf-8")

    mesh = Mujoco.from_xml(xml).assets[0].meshes[0]

    assert isinstance(mesh, Mesh)
    assert mesh.file == (Path(file) if expected is None else tmp_path / expected)


def test_text_has_no_folder_so_its_relative_paths_stay_as_written() -> None:
    mesh = (
        Mujoco.from_xml(
            MESH_XML.format(compiler='<compiler meshdir="assets"/>', file="m.stl")
        )
        .assets[0]
        .meshes[0]
    )

    assert isinstance(mesh, Mesh)
    assert mesh.file == Path("m.stl")
