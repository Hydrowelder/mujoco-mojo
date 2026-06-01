import mujoco
import numpy as np
import pytest

from mujoco_mojo.visualization import ArrowConfig, LineConfig


@pytest.fixture
def mj_model() -> mujoco.MjModel:
    """Minimal compiled model for reading vis/stat properties."""
    xml = "<mujoco><worldbody><body><geom type='sphere' size='0.1' mass='1'/></body></worldbody></mujoco>"
    return mujoco.MjModel.from_xml_string(xml)


class TestArrowConfig:
    def test_resolve_arrow_coords_force_returns_three_values(
        self, mj_model: mujoco.MjModel
    ) -> None:
        """resolve_arrow_coords() returns (start, end, width) for a force arrow."""
        arrow = ArrowConfig(
            pos=np.array([0.0, 0.0, 0.0]),
            vec=np.array([1.0, 0.0, 0.0]),
            color=np.array([1.0, 0.0, 0.0, 1.0]),
            is_torque=False,
        )
        start, end, width = arrow.resolve_arrow_coords(mj_model)

        assert start.shape == (3,)
        assert end.shape == (3,)
        assert isinstance(width, float)
        assert np.all(np.isfinite(start))
        assert np.all(np.isfinite(end))
        assert width > 0

    def test_resolve_arrow_coords_torque_returns_three_values(
        self, mj_model: mujoco.MjModel
    ) -> None:
        """resolve_arrow_coords() uses the torque scale when is_torque=True."""
        arrow = ArrowConfig(
            pos=np.array([1.0, 2.0, 3.0]),
            vec=np.array([0.0, 0.0, 5.0]),
            color=np.array([0.0, 1.0, 0.0, 1.0]),
            is_torque=True,
        )
        start, end, width = arrow.resolve_arrow_coords(mj_model)

        assert np.allclose(start, [1.0, 2.0, 3.0])
        assert np.all(np.isfinite(end))
        assert width > 0

    def test_start_equals_pos(self, mj_model: mujoco.MjModel) -> None:
        """The start point equals the arrow's pos field."""
        pos = np.array([3.0, -1.0, 2.0])
        arrow = ArrowConfig(
            pos=pos,
            vec=np.array([1.0, 0.0, 0.0]),
            color=np.array([1.0, 1.0, 0.0, 1.0]),
            is_torque=False,
        )
        start, _end, _width = arrow.resolve_arrow_coords(mj_model)
        assert np.allclose(start, pos)

    def test_zero_vec_produces_start_equals_end(self, mj_model: mujoco.MjModel) -> None:
        """A zero force vector produces an arrow where start == end."""
        arrow = ArrowConfig(
            pos=np.array([0.0, 0.0, 0.0]),
            vec=np.array([0.0, 0.0, 0.0]),
            color=np.array([1.0, 1.0, 1.0, 1.0]),
            is_torque=False,
        )
        start, end, _width = arrow.resolve_arrow_coords(mj_model)
        assert np.allclose(start, end)


class TestLineConfig:
    def test_fields_are_stored_correctly(self) -> None:
        """LineConfig stores pos1, pos2, color, and width as given."""
        p1 = np.array([0.0, 0.0, 0.0])
        p2 = np.array([1.0, 1.0, 1.0])
        color = np.array([0.5, 0.5, 0.5, 1.0])

        line = LineConfig(pos1=p1, pos2=p2, color=color, width=0.005)

        assert np.allclose(line.pos1, p1)
        assert np.allclose(line.pos2, p2)
        assert np.allclose(line.color, color)
        assert line.width == pytest.approx(0.005)
