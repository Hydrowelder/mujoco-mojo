import warnings
from typing import Any

import numpy as np
import pytest
from pydantic import TypeAdapter

from mujoco_mojo.mjcf import (
    Asset,
    Body,
    GeomMesh,
    GeomSphere,
    Joint,
    Mujoco,
    WorldBody,
)
from mujoco_mojo.mjcf.mujoco_attr.asset_attr.mesh import (
    AnyMesh,
    MeshBox,
    MeshCylinder,
    MeshDisc,
    MeshEllipsoid,
    MeshGrid,
    MeshSquare,
)
from mujoco_mojo.mjcf.mujoco_attr.body_attr.flexcomp import FlexComp
from mujoco_mojo.typing import Angle, BodyName, EulerSeq, JointName, JointType, MeshName

BuiltinMesh = MeshGrid | MeshBox | MeshCylinder | MeshEllipsoid | MeshSquare | MeshDisc

SPACING = np.array((0.1, 0.1, 0.1))
NAME = MeshName("m")


def _model(mesh: BuiltinMesh, *, as_flexcomp: bool) -> Mujoco:
    """A model whose only use of `mesh` is as a geom (convex hull) or as the source of a flexcomp."""
    body = Body(name=BodyName("b"))
    if as_flexcomp:
        # a flexcomp needs a parent body that has mass and can move
        body.geoms.append(GeomSphere(size=0.1))
        body.joints.append(
            Joint(name=JointName("j"), type=JointType.SLIDE, axis=np.array((1, 0, 0)))
        )
        body.flexcomps.append(FlexComp(name="f", mesh=NAME, mass=1))
    else:
        body.geoms.append(GeomMesh(mesh=NAME))
    worldbody = WorldBody()
    worldbody.bodies.append(body)
    return Mujoco(assets=[Asset(meshes=[mesh])], worldbody=worldbody)


def _compile(model: Mujoco) -> Any:
    with warnings.catch_warnings():
        # a flex with no equality constraints or passive forces warns, which is irrelevant here
        warnings.simplefilter("ignore")
        return model.to_mj_model()


VOLUMETRIC = [
    pytest.param(MeshGrid, (3, 3, 3), id="grid"),
    pytest.param(MeshBox, (3, 3, 3), id="box"),
    pytest.param(MeshCylinder, (3, 3, 3), id="cylinder"),
    pytest.param(MeshEllipsoid, (3, 3, 3), id="ellipsoid"),
]


@pytest.mark.parametrize(("cls", "count"), VOLUMETRIC)
def test_a_volumetric_builtin_mesh_compiles_as_a_geom(
    cls: type[BuiltinMesh], count: tuple[int, int, int]
) -> None:
    mesh = cls(name=NAME, count=count, spacing=SPACING)

    mj_model = _compile(_model(mesh, as_flexcomp=False))

    assert mj_model.nmeshvert == 27


@pytest.mark.parametrize(
    ("cls", "kwargs", "expected_vertices", "expected_dim"),
    [
        pytest.param(MeshGrid, {"count": (3, 3, 3)}, 27, 3, id="grid-3d"),
        pytest.param(MeshGrid, {"count": (3, 3, 1), "dim": 2}, 9, 2, id="grid-2d"),
        pytest.param(MeshBox, {"count": (3, 3, 3)}, 27, 3, id="box-3d"),
        pytest.param(MeshBox, {"count": (3, 3, 3), "dim": 2}, 25, 2, id="box-2d"),
        pytest.param(MeshCylinder, {"count": (3, 3, 3)}, 27, 3, id="cylinder-3d"),
        pytest.param(MeshEllipsoid, {"count": (3, 3, 3)}, 27, 3, id="ellipsoid-3d"),
        pytest.param(MeshSquare, {"count": (3, 3, 1)}, 9, 2, id="square"),
        pytest.param(MeshDisc, {"count": (3, 3, 1)}, 9, 2, id="disc"),
    ],
)
def test_every_builtin_mesh_can_feed_a_flexcomp(
    cls: type[BuiltinMesh],
    kwargs: dict[str, Any],
    expected_vertices: int,
    expected_dim: int,
) -> None:
    """The surface-only meshes cannot be geoms (no convex hull), but all of them can be flexcomp sources."""
    mesh = cls(name=NAME, spacing=SPACING, **kwargs)

    mj_model = _compile(_model(mesh, as_flexcomp=True))

    assert mj_model.nflexvert == expected_vertices
    assert int(mj_model.flex_dim[0]) == expected_dim


def test_a_builtin_mesh_writes_its_parameters_as_one_params_attribute() -> None:
    box = MeshBox(name=NAME, count=(3, 4, 5), spacing=SPACING, dim=2)
    square = MeshSquare(name=NAME, count=(3, 4, 1), spacing=SPACING)

    box_el = box.to_xml(compiler_degrees=Angle.DEGREE, compiler_eulerseq=EulerSeq.XYZ)
    square_el = square.to_xml(
        compiler_degrees=Angle.DEGREE, compiler_eulerseq=EulerSeq.XYZ
    )

    assert box_el.attrib["builtin"] == "box"
    assert box_el.attrib["params"] == "3 4 5 0.1 0.1 0.1 2"
    # square and disc take exactly six parameters, with no dim
    assert square_el.attrib["builtin"] == "square"
    assert square_el.attrib["params"] == "3 4 1 0.1 0.1 0.1"


def test_builtin_meshes_are_picked_by_their_builtin_keyword() -> None:
    adapter = TypeAdapter(AnyMesh)

    mesh = adapter.validate_python(
        {"builtin": "disc", "name": "m", "count": (3, 3, 1), "spacing": SPACING}
    )

    assert isinstance(mesh, MeshDisc)


@pytest.mark.parametrize(
    ("cls", "kwargs", "message"),
    [
        pytest.param(MeshGrid, {"count": (0, 3, 3)}, "must be positive", id="grid-0"),
        pytest.param(
            MeshGrid,
            {"count": (3, 3, 2), "dim": 2},
            "must be 1 along the axes beyond dim",
            id="grid-2d-extra-axis",
        ),
        pytest.param(
            MeshGrid,
            {"count": (3, 3, 1)},
            "at least 2 along the axes within dim",
            id="grid-3d-flat",
        ),
        pytest.param(MeshBox, {"count": (1, 3, 3)}, "at least 2", id="box"),
        pytest.param(MeshCylinder, {"count": (3, 1, 3)}, "at least 2", id="cylinder"),
        pytest.param(MeshEllipsoid, {"count": (3, 3, 1)}, "at least 2", id="ellipsoid"),
        pytest.param(
            MeshBox, {"count": (3, 3, 3), "dim": 4}, "2 or 3", id="box-bad-dim"
        ),
        pytest.param(
            MeshSquare, {"count": (3, 3, 2)}, r"count\[2\] must be 1", id="square-z"
        ),
        pytest.param(
            MeshSquare, {"count": (0, 3, 1)}, "must be positive", id="square-0"
        ),
        pytest.param(MeshDisc, {"count": (3, 0, 1)}, "must be positive", id="disc-0"),
    ],
)
def test_invalid_builtin_mesh_counts_are_rejected_like_mujoco_does(
    cls: type[BuiltinMesh], kwargs: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        cls(name=NAME, spacing=SPACING, **kwargs)
