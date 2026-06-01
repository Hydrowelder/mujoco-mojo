import mujoco
import pytest

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.equality_attr.weld import EqualityWeldBody
from mujoco_mojo.typing import BodyName, EqualityName


@pytest.fixture
def weld_setup() -> tuple[MjState, EqualityWeldBody]:
    """Two bodies connected by a weld equality constraint."""
    xml = """
    <mujoco>
        <worldbody>
            <body name="base"/>
            <body name="arm">
                <freejoint/>
                <geom type="sphere" size="0.1"/>
            </body>
        </worldbody>
        <equality>
            <weld name="lock" body1="base" body2="arm"/>
        </equality>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    constraint = EqualityWeldBody(
        name=EqualityName("lock"), body1=BodyName("base"), body2=BodyName("arm")
    )
    constraint.get_id(model)
    return MjState(model, data), constraint


def test_is_active_returns_true_by_default(
    weld_setup: tuple[MjState, EqualityWeldBody],
) -> None:
    """Equality constraints are active by default after compilation."""
    state, constraint = weld_setup
    assert constraint.is_active(state) is True


def test_disable_sets_inactive(
    weld_setup: tuple[MjState, EqualityWeldBody],
) -> None:
    """disable() sets eq_active to 0 at runtime."""
    state, constraint = weld_setup
    constraint.disable(state)
    assert constraint.is_active(state) is False


def test_enable_restores_active(
    weld_setup: tuple[MjState, EqualityWeldBody],
) -> None:
    """enable() sets eq_active back to 1 after it was disabled."""
    state, constraint = weld_setup
    constraint.disable(state)
    constraint.enable(state)
    assert constraint.is_active(state) is True


def test_set_active_false_then_true(
    weld_setup: tuple[MjState, EqualityWeldBody],
) -> None:
    """set_active() toggles the constraint state directly."""
    state, constraint = weld_setup
    constraint.set_active(state, False)
    assert constraint.is_active(state) is False
    constraint.set_active(state, True)
    assert constraint.is_active(state) is True
