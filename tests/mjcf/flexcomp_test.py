import pytest

from mujoco_mojo.mjcf.dependency_path import DepPath
from mujoco_mojo.mjcf.mujoco_attr.body_attr.flexcomp import FlexComp
from mujoco_mojo.typing import Angle, EulerSeq, FlexCompType, MeshName

MESH = MeshName("pad")


def _attributes(flexcomp: FlexComp) -> dict[str, str]:
    return flexcomp.to_xml(
        compiler_degrees=Angle.DEGREE, compiler_eulerseq=EulerSeq.XYZ
    ).attrib


def test_a_flexcomp_without_a_mesh_is_unchanged() -> None:
    flexcomp = FlexComp(name="f")

    assert flexcomp.type == FlexCompType.GRID
    assert "mesh" not in _attributes(flexcomp)


def test_a_flexcomp_that_names_a_mesh_defaults_to_the_mesh_type() -> None:
    """MuJoCo treats a flexcomp with a mesh asset and no type as type=mesh, so the default grid type must not be written over it."""
    flexcomp = FlexComp(name="f", mesh=MESH)

    assert flexcomp.type == FlexCompType.MESH
    assert _attributes(flexcomp)["mesh"] == "pad"
    assert _attributes(flexcomp)["type"] == "mesh"


@pytest.mark.parametrize("flexcomp_type", [FlexCompType.MESH, FlexCompType.GMSH])
def test_a_mesh_asset_can_be_used_with_the_mesh_and_gmsh_types(
    flexcomp_type: FlexCompType,
) -> None:
    flexcomp = FlexComp(name="f", mesh=MESH, type=flexcomp_type)

    assert flexcomp.type == flexcomp_type


@pytest.mark.parametrize(
    "flexcomp_type",
    [FlexCompType.GRID, FlexCompType.BOX, FlexCompType.DIRECT],
)
def test_a_mesh_asset_cannot_be_used_with_other_types(
    flexcomp_type: FlexCompType,
) -> None:
    with pytest.raises(
        ValueError, match="only be used with flexcomp type mesh or gmsh"
    ):
        FlexComp(name="f", mesh=MESH, type=flexcomp_type)


def test_a_flexcomp_cannot_use_both_a_mesh_asset_and_a_file() -> None:
    with pytest.raises(ValueError, match="either a mesh asset or a file"):
        FlexComp(name="f", mesh=MESH, file=DepPath("pad.obj"))
