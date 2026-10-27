"""The cross-section of a 1D flex, which MuJoCo 3.17.0 uses for its bending elasticity (`section` and `sectionsize` on `<elasticity>`)."""

import numpy as np
import pytest

from mujoco_mojo.mjcf import Mujoco, WorldBody
from mujoco_mojo.mjcf.mujoco_attr.body_attr.flexcomp import FlexComp
from mujoco_mojo.mjcf.mujoco_attr.body_attr.flexcomp_attr.elasticity import (
    FlexCompElasticity,
)
from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.flex_attr.elasticity import (
    FlexElasticity,
)
from mujoco_mojo.typing import Angle, EulerSeq, FlexSection

YOUNG = 1e5
"""A positive Young's modulus, which is what turns bending elasticity on for a 1D flex."""


def _attributes(element: FlexElasticity | FlexCompElasticity) -> dict[str, str]:
    return element.to_xml(
        compiler_degrees=Angle.DEGREE, compiler_eulerseq=EulerSeq.XYZ
    ).attrib


def _rod(
    *,
    young: float = YOUNG,
    section: FlexSection = FlexSection.CIRCLE,
    sectionsize: tuple[float, float] = (0.0, 0.0),
) -> Mujoco:
    """A straight 1D flexcomp of five vertices, with the given elasticity."""
    flexcomp = FlexComp(
        name="rod",
        dim=1,
        count=(5, 1, 1),
        spacing=np.array((0.1, 0.1, 0.1)),
        mass=1,
        elasticities=[
            FlexCompElasticity(
                young=young, section=section, sectionsize=np.array(sectionsize)
            )
        ],
    )
    worldbody = WorldBody()
    worldbody.flexcomps.append(flexcomp)
    return Mujoco(worldbody=worldbody)


def _bending(
    *,
    young: float = YOUNG,
    section: FlexSection = FlexSection.CIRCLE,
    sectionsize: tuple[float, float] = (0.0, 0.0),
) -> np.ndarray:
    model = _rod(young=young, section=section, sectionsize=sectionsize).to_mj_model()
    return np.asarray(model.flex_bending)


def test_the_section_attributes_are_omitted_at_their_defaults() -> None:
    assert not {"section", "sectionsize"} & set(_attributes(FlexElasticity()))


def test_a_flex_writes_the_section_with_mujocos_names() -> None:
    attributes = _attributes(
        FlexElasticity(
            young=YOUNG, section=FlexSection.BOX, sectionsize=np.array((0.01, 0.02))
        )
    )

    assert attributes["section"] == "box"
    assert attributes["sectionsize"] == "0.01 0.02"


def test_a_flexcomp_passes_the_section_through() -> None:
    attributes = _attributes(
        FlexCompElasticity(
            young=YOUNG, section=FlexSection.BOX, sectionsize=np.array((0.01, 0.02))
        )
    )

    assert attributes["section"] == "box"
    assert attributes["sectionsize"] == "0.01 0.02"


def test_the_flexcomp_defaults_follow_the_flex() -> None:
    flex, flexcomp = FlexElasticity(), FlexCompElasticity()

    assert flexcomp.section == flex.section == FlexSection.CIRCLE
    assert np.array_equal(flexcomp.sectionsize, flex.sectionsize)


def test_a_rod_has_no_bending_stiffness_without_a_young_modulus() -> None:
    assert _bending(young=0).size == 0


@pytest.mark.parametrize(
    ("section", "sectionsize"),
    [
        pytest.param(FlexSection.CIRCLE, (0.0, 0.0), id="circle"),
        pytest.param(FlexSection.BOX, (0.01, 0.02), id="box"),
    ],
)
def test_a_rod_with_a_young_modulus_bends_for_either_section(
    section: FlexSection, sectionsize: tuple[float, float]
) -> None:
    assert _bending(section=section, sectionsize=sectionsize).size > 0


def test_the_section_sets_how_stiff_the_rod_is() -> None:
    circle = _bending(young=YOUNG)
    box = _bending(young=YOUNG, section=FlexSection.BOX, sectionsize=(0.01, 0.02))
    thicker = _bending(young=YOUNG, section=FlexSection.BOX, sectionsize=(0.04, 0.05))

    assert not np.allclose(circle, box)
    assert not np.allclose(box, thicker)


def test_a_box_section_uses_the_weak_axis() -> None:
    """The half-sizes are interchangeable, because only the weaker of the two axes counts."""
    one_way = _bending(section=FlexSection.BOX, sectionsize=(0.01, 0.02))
    other_way = _bending(young=YOUNG, section=FlexSection.BOX, sectionsize=(0.02, 0.01))

    assert np.allclose(one_way, other_way)


def test_a_box_section_needs_a_sectionsize() -> None:
    """MuJoCo reports this itself, so mojo leaves the rule to the compiler."""
    with pytest.raises(ValueError, match="sectionsize"):
        _rod(young=YOUNG, section=FlexSection.BOX).to_mj_model()
