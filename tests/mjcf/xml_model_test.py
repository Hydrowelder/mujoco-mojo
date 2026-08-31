from pathlib import Path

import mujoco
import numpy as np
import pytest
from pydantic import Field

from mujoco_mojo.mjcf.xml_model import XMLModel, _format_value
from mujoco_mojo.typing import Angle, EulerSeq, Vec4

# --- Dummy Subclasses for Testing ---


class SubModel(XMLModel):
    tag = "sub"
    attributes = ("name", "value", "rgba")
    _mjt_obj = mujoco.mjtObj.mjOBJ_SITE  # dummy site since this is a named class

    name: str | None = None
    value: float = 0.0
    rgba: Vec4 | None = None  # Added for warn_out_of_range_colors test


class MultiColorModel(XMLModel):
    """Mimics classes like Texture/Light/VisualHeadlight, whose color fields aren't named `rgba`."""

    tag = "multi_color"
    attributes = ("name", "primary", "secondary")
    color_fields = ("primary", "secondary")
    _mjt_obj = mujoco.mjtObj.mjOBJ_SITE

    name: str | None = None
    primary: Vec4 | None = None
    secondary: Vec4 | None = None


class ParentModel(XMLModel):
    tag = "parent"
    attributes = ("name", "sub")
    children = ("items",)
    _mjt_obj = mujoco.mjtObj.mjOBJ_BODY  # dummy site since this is a named class

    name: str = "test"
    sub: SubModel | None = None
    items: list[SubModel] = Field(default_factory=list)


class ExclusiveModel(XMLModel):
    tag = "excl"
    attributes = ("a", "b")
    __exclusive_groups__ = (("a", "b"),)
    a: int | None = None
    b: int | None = None


# --- Tests ---


def test_format_value():
    """Verify standard MJCF string formatting."""
    assert _format_value(True) == "true"
    assert _format_value(False) == "false"
    assert _format_value(np.asarray([1, 2, 3])) == "1 2 3"
    assert _format_value(1.23) == "1.23"


def test_basic_serialization():
    """Verify a simple model generates correct XML."""
    model = SubModel(value=1.5)
    el = model.to_xml(compiler_degrees=Angle.DEGREE, compiler_eulerseq=EulerSeq.XYZ)

    assert el.tag == "sub"
    assert el.get("value") == "1.5"


def test_exclude_default():
    """Verify that default values are omitted from XML when requested."""
    model = ParentModel(name="test")  # 'test' is default

    # With exclusion
    el_excl = model.to_xml(
        compiler_degrees=Angle.DEGREE,
        compiler_eulerseq=EulerSeq.XYZ,
        exclude_default=True,
    )
    assert "name" not in el_excl.attrib

    # Without exclusion
    el_incl = model.to_xml(
        compiler_degrees=Angle.DEGREE,
        compiler_eulerseq=EulerSeq.XYZ,
        exclude_default=False,
    )
    assert el_incl.get("name") == "test"


def test_recursive_flattening():
    """Verify that nested XMLModels in 'attributes' are flattened into the parent tag."""
    child = SubModel(value=5.0)
    parent = ParentModel(name="root", sub=child)

    el = parent.to_xml(compiler_degrees=Angle.DEGREE, compiler_eulerseq=EulerSeq.XYZ)

    # The 'value' from SubModel should now be an attribute of 'parent'
    assert el.tag == "parent"
    assert el.get("value") == "5.0"
    assert len(el) == 0  # Should not be a child element


def test_children_serialization():
    """Verify that fields in 'children' are appended as sub-elements."""
    child1 = SubModel(value=1.0)
    child2 = SubModel(value=2.0)
    parent = ParentModel(items=[child1, child2])

    el = parent.to_xml(compiler_degrees=Angle.DEGREE, compiler_eulerseq=EulerSeq.XYZ)

    assert len(el) == 2
    assert el[0].tag == "sub"
    assert el[1].get("value") == "2.0"


def test_exclusive_groups():
    """Verify that __exclusive_groups__ raises error on collision."""
    # Valid: only one set
    ExclusiveModel(a=1)
    ExclusiveModel(b=2)

    # FIX: Use a raw string (r"...") for the regex match pattern
    with pytest.raises(ValueError, match=r"Only one of .* may be specified"):
        ExclusiveModel(a=1, b=2)


def test_invalid_names():
    """Verify MuJoCo reserved character validation."""
    # FIX: SubModel now has a 'name' field defined
    with pytest.raises(ValueError, match="Invalid name"):
        SubModel(name="bad:name")

    with pytest.raises(ValueError, match="Invalid name"):
        SubModel(name="bad/name")


def test_rgba_warning(caplog):
    """Verify that warn_out_of_range_colors triggers a logger warning for values > 1."""
    # MuJoCo uses 0-1 range. 255 should trigger the warning validator.
    rgba_255 = np.asarray([255, 0, 0, 255])

    # This shouldn't raise an error, just log a warning
    SubModel(name="test_geom", rgba=rgba_255)

    assert "MuJoCo colors range from 0 to 1" in caplog.text
    assert "You entered rgba=array([255,   0,   0, 255])" in caplog.text


def test_color_fields_covers_non_rgba_named_fields(caplog):
    """
    Verify that `color_fields` generalizes the check beyond a field literally
    named `rgba` (regression test for classes like Texture/Light/VisualHeadlight,
    whose color fields have their own names).
    """
    # In range: no warning for either field
    MultiColorModel(
        primary=np.asarray([1, 0, 0, 1]), secondary=np.asarray([0, 1, 0, 1])
    )
    assert "MuJoCo colors range from 0 to 1" not in caplog.text

    # Out of range: only the offending field should be named in the warning
    MultiColorModel(
        primary=np.asarray([255, 0, 0, 255]), secondary=np.asarray([0, 1, 0, 1])
    )
    assert "MultiColorModel None.primary" in caplog.text
    assert "MultiColorModel None.secondary" not in caplog.text


def test_exclusive_groups_none_check():
    """Verify that exclusive groups pass if neither is set."""
    # This should be valid
    model = ExclusiveModel(a=None, b=None)
    assert model.a is None and model.b is None


def test_asset_bundling(tmp_path: Path):
    """Test the asset crawler and file copying logic."""
    from mujoco_mojo.mjcf.dependency_path import DepPath

    # Setup dummy asset
    asset_file = tmp_path / "mesh.stl"
    asset_file.write_text("dummy mesh data")

    target_dir = tmp_path / "bundle"
    rel_path = Path("assets")

    class MeshModel(XMLModel):
        tag = "mesh"
        attributes = ("file",)
        file: DepPath

    model = MeshModel(file=DepPath(asset_file))

    # Bundle it
    model.bundle_assets(target_dir, rel_path)

    # Check if file moved
    assert (target_dir / "mesh.stl").exists()
    # Check if path in model updated to the relative path
    assert model.file == rel_path / "mesh.stl"


def test_subclass_validation():
    """Verify that missing fields in attributes/children are caught at class definition."""
    with pytest.raises(TypeError, match="not defined as a field"):

        class BrokenModel(XMLModel):
            tag = "broken"
            attributes = ("ghost_field",)


def test_flattening_collision():
    """Verify collision detection when two sub-models define the same attribute name."""

    class CollisionChild(XMLModel):
        tag = "child"
        attributes = ("name",)
        name: str = "collision"
        _mjt_obj = mujoco.mjtObj.mjOBJ_BODY

    class CollisionParent(XMLModel):
        tag = "parent"
        attributes = ("name", "child")
        name: str = "parent_name"
        child: CollisionChild
        _mjt_obj = mujoco.mjtObj.mjOBJ_BODY

    # Provide a non-default name to the parent so it's actually written to el.attrib
    p = CollisionParent(name="explicit_parent", child=CollisionChild())

    with pytest.raises(ValueError, match=r"Attribute collision while flattening"):
        # You MUST call the method that triggers the logic!
        p.to_xml(
            compiler_degrees=Angle.DEGREE,
            compiler_eulerseq=EulerSeq.XYZ,
            exclude_default=True,  # Now 'explicit_parent' will collide with child's 'collision'
        )
