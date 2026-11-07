"""Plasticity: springs on joints, tendons and flexes that yield, and the state that records how far they have. The XML mojo writes for these attributes is checked in `attributes_test.py`; these check what MuJoCo makes of it."""

from collections.abc import Callable

import numpy as np
import pytest

from mujoco_mojo.mjcf import (
    Body,
    Fixed,
    FlexComp,
    GeomSphere,
    Joint,
    Key,
    Keyframe,
    Mujoco,
    Option,
    SiteSphere,
    Spatial,
    Tendon,
    WorldBody,
)
from mujoco_mojo.mjcf.mujoco_attr.body_attr.flexcomp_attr.elasticity import (
    FlexCompElasticity,
)
from mujoco_mojo.mjcf.mujoco_attr.tendon_attr.fixed_attr.joint import TendonJoint
from mujoco_mojo.mjcf.mujoco_attr.tendon_attr.spatial_attr.site import SpatialSite
from mujoco_mojo.typing import (
    BodyName,
    FlexCompType,
    FlexElastic2D,
    Integrator,
    JointName,
    JointType,
    SiteName,
)


def _world(*bodies: Body) -> WorldBody:
    worldbody = WorldBody()
    worldbody.bodies.extend(bodies)
    return worldbody


def _hinge_body(name: str, *, springyield: float | None = None) -> Body:
    """A body on a hinge, whose joint spring yields at `springyield` when given."""
    body = Body(name=BodyName(name))
    joint = Joint(name=JointName(f"{name}_joint"), type=JointType.HINGE)
    if springyield is not None:
        joint.springyield = springyield
    body.joints.append(joint)
    body.geoms.append(GeomSphere(size=0.1))
    return body


def test_a_joint_spring_with_a_yield_creates_plastic_state() -> None:
    plain = Mujoco(worldbody=_world(_hinge_body("arm"))).to_mj_model()
    yielding = Mujoco(
        worldbody=_world(_hinge_body("arm", springyield=0.5))
    ).to_mj_model()

    assert plain.nplastic == 0
    assert yielding.nplastic == 1
    # a hinge's angles are in degrees unless the compiler says otherwise, and the model holds radians
    assert yielding.jnt_springyield[0] == pytest.approx(np.radians(0.5))


def _fixed_tendon_model() -> Mujoco:
    joint = TendonJoint(joint=JointName("arm_joint"), coef=1.0)
    tendon = Tendon(fixeds=[Fixed(name="t", springyield=0.5, joints=[joint])])
    return Mujoco(worldbody=_world(_hinge_body("arm")), tendons=[tendon])


def _spatial_tendon_model() -> Mujoco:
    bodies: list[Body] = []
    for name in ("a", "b"):
        body = _hinge_body(name)
        body.sites.append(SiteSphere(name=SiteName(f"site_{name}"), size=0.01))
        bodies.append(body)
    sites = [SpatialSite(site=SiteName(f"site_{name}")) for name in ("a", "b")]
    tendon = Tendon(spatials=[Spatial(name="t", springyield=0.5, sites=sites)])
    return Mujoco(worldbody=_world(*bodies), tendons=[tendon])


@pytest.mark.parametrize("make_model", [_fixed_tendon_model, _spatial_tendon_model])
def test_a_tendon_spring_with_a_yield_creates_plastic_state(
    make_model: Callable[[], Mujoco],
) -> None:
    model = make_model().to_mj_model()

    assert model.tendon_springyield[0] == pytest.approx(0.5)
    assert model.tendon_plasticadr[0] >= 0


def test_a_keyframe_carries_plastic_state() -> None:
    keyframe = Keyframe(keys=[Key(name="k", plastic=np.array((0.25,)))])
    worldbody = _world(_hinge_body("arm", springyield=0.5))

    model = Mujoco(worldbody=worldbody, keyframes=[keyframe]).to_mj_model()

    assert model.nplastic == 1
    assert model.key_plastic.tolist() == [[0.25]]


def _shell(elastic2d: FlexElastic2D, yield_: tuple[float, float] | None) -> Mujoco:
    """A small 2D shell with stretching and/or bending elasticity, which plasticity needs."""
    elasticity = FlexCompElasticity(
        young=1e4, poisson=0.2, thickness=0.01, elastic2d=elastic2d
    )
    if yield_ is not None:
        elasticity.yield_ = np.array(yield_)
    worldbody = WorldBody()
    worldbody.flexcomps.append(
        FlexComp(
            name="cloth",
            dim=2,
            type=FlexCompType.GRID,
            count=(3, 3, 1),
            spacing=np.array((0.1, 0.1, 0.1)),
            mass=1,
            elasticities=[elasticity],
        )
    )
    return Mujoco(options=[Option(integrator=Integrator.DISCRETE)], worldbody=worldbody)


BEND, STRETCH = 1, 2
"""The bits of `flex_plasticmode`."""


@pytest.mark.parametrize(
    ("elastic2d", "yield_", "mode"),
    [
        pytest.param(FlexElastic2D.BOTH, None, 0, id="no-yield"),
        pytest.param(FlexElastic2D.BOTH, (0.01, 0.0), STRETCH, id="stretch-only"),
        pytest.param(FlexElastic2D.BOTH, (0.0, 0.02), BEND, id="bend-only"),
        pytest.param(FlexElastic2D.BOTH, (0.01, 0.02), STRETCH | BEND, id="both"),
        pytest.param(FlexElastic2D.STRETCH, (0.01, 0.02), STRETCH, id="stretch-shell"),
        pytest.param(FlexElastic2D.BEND, (0.01, 0.02), BEND, id="bend-shell"),
    ],
)
def test_a_shell_is_plastic_in_the_modes_its_yield_strains_ask_for(
    elastic2d: FlexElastic2D, yield_: tuple[float, float] | None, mode: int
) -> None:
    """The yield is `(stretching, bending)`, and a zero for one of them leaves that mode elastic."""
    model = _shell(elastic2d, yield_).to_mj_model()

    assert int(model.flex_plasticmode[0]) == mode
    assert (int(model.flex_plasticadr[0]) >= 0) is (mode != 0)
