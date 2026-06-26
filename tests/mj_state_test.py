from unittest.mock import patch

import mujoco
import pytest

from mujoco_mojo.mj_state import MjState

XML = """
<mujoco>
    <worldbody>
        <body name="body1" pos="0 0 0">
            <joint name="joint1" type="slide" axis="1 0 0"/>
            <geom type="sphere" size="0.1"/>
        </body>
    </worldbody>
</mujoco>
"""


@pytest.fixture
def state() -> MjState:
    model = mujoco.MjModel.from_xml_string(XML)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return MjState(model, data)


def test_ensure_rne_post_constraint_calls_on_first_read(state: MjState):
    with patch("mujoco_mojo.mj_state.mujoco.mj_rnePostConstraint") as mock_rne:
        state.ensure_rne_post_constraint()
    mock_rne.assert_called_once_with(state.model, state.data)


def test_ensure_rne_post_constraint_skips_repeat_reads(state: MjState):
    """A second call before any invalidation reuses the already-fresh result."""
    with patch("mujoco_mojo.mj_state.mujoco.mj_rnePostConstraint") as mock_rne:
        state.ensure_rne_post_constraint()
        state.ensure_rne_post_constraint()
    mock_rne.assert_called_once_with(state.model, state.data)


def test_invalidate_forces_recompute_on_next_read(state: MjState):
    with patch("mujoco_mojo.mj_state.mujoco.mj_rnePostConstraint") as mock_rne:
        state.ensure_rne_post_constraint()
        state.invalidate_rne_post_constraint()
        state.ensure_rne_post_constraint()
    assert mock_rne.call_count == 2
