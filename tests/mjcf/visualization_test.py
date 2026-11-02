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

    def test_width_is_capped_relative_to_length(self, mj_model: mujoco.MjModel) -> None:
        """A short torque vector gets a capped width instead of the disk-like native width."""
        arrow = ArrowConfig(
            pos=np.array([0.0, 0.0, 0.0]),
            vec=np.array([0.0, 0.0, 1e-3]),
            color=np.array([0.0, 1.0, 0.0, 1.0]),
            is_torque=True,
        )
        start, end, width = arrow.resolve_arrow_coords(mj_model)
        length = float(np.linalg.norm(end - start))
        assert width <= length * arrow._MAX_WIDTH_TO_LENGTH_RATIO + 1e-9

    def test_length_scale_multiplies_arrow_length(
        self, mj_model: mujoco.MjModel
    ) -> None:
        """A custom `length_scale` enlarges (or shrinks) the resolved length independently of width."""
        base = ArrowConfig(
            pos=np.array([0.0, 0.0, 0.0]),
            vec=np.array([10.0, 0.0, 0.0]),
            color=np.array([1.0, 0.0, 0.0, 1.0]),
            is_torque=False,
        )
        scaled = ArrowConfig(
            pos=np.array([0.0, 0.0, 0.0]),
            vec=np.array([10.0, 0.0, 0.0]),
            color=np.array([1.0, 0.0, 0.0, 1.0]),
            is_torque=False,
            length_scale=3.0,
        )
        _, base_end, base_width = base.resolve_arrow_coords(mj_model)
        _, scaled_end, scaled_width = scaled.resolve_arrow_coords(mj_model)
        assert np.allclose(scaled_end, base_end * 3.0)
        assert scaled_width == pytest.approx(base_width)

    def test_width_scale_multiplies_arrow_width(self, mj_model: mujoco.MjModel) -> None:
        """A custom `width_scale` thickens (or thins) the resolved width independently of length, as long as it stays below the disk-avoidance cap."""
        base = ArrowConfig(
            pos=np.array([0.0, 0.0, 0.0]),
            vec=np.array([10.0, 0.0, 0.0]),
            color=np.array([1.0, 0.0, 0.0, 1.0]),
            is_torque=False,
        )
        thinner = ArrowConfig(
            pos=np.array([0.0, 0.0, 0.0]),
            vec=np.array([10.0, 0.0, 0.0]),
            color=np.array([1.0, 0.0, 0.0, 1.0]),
            is_torque=False,
            width_scale=0.5,
        )
        _, base_end, base_width = base.resolve_arrow_coords(mj_model)
        _, thinner_end, thinner_width = thinner.resolve_arrow_coords(mj_model)
        assert np.allclose(thinner_end, base_end)
        assert thinner_width == pytest.approx(base_width * 0.5)


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


class TestFillGeom:
    """A viewer that keeps its own list of decorative geoms fills standalone `MjvGeom`s, and the classic viewer fills slots of a scene, so both must come out the same."""

    @staticmethod
    def an_arrow() -> ArrowConfig:
        return ArrowConfig(
            pos=np.array([1.0, 2.0, 3.0]),
            vec=np.array([0.0, 0.0, 5.0]),
            color=np.array([0.2, 0.8, 0.3, 0.9]),
            is_torque=False,
        )

    @staticmethod
    def a_line() -> LineConfig:
        return LineConfig(
            pos1=np.array([0.0, 0.0, 0.0]),
            pos2=np.array([1.0, 2.0, 3.0]),
            color=np.array([0.0, 1.0, 0.0, 1.0]),
            width=2.0,
        )

    def test_an_arrow_fills_a_standalone_geom(self, mj_model: mujoco.MjModel) -> None:
        geom = mujoco.MjvGeom()

        self.an_arrow().fill_geom(geom, mj_model)

        assert geom.type == mujoco.mjtGeom.mjGEOM_ARROW
        assert np.allclose(geom.rgba, [0.2, 0.8, 0.3, 0.9])
        assert np.all(geom.size > 0)

    def test_a_line_fills_a_standalone_geom(self) -> None:
        geom = mujoco.MjvGeom()

        self.a_line().fill_geom(geom)

        assert geom.type == mujoco.mjtGeom.mjGEOM_LINE
        assert np.allclose(geom.rgba, [0.0, 1.0, 0.0, 1.0])

    def test_a_scene_slot_comes_out_the_same_as_a_standalone_geom(
        self, mj_model: mujoco.MjModel
    ) -> None:
        scene = mujoco.MjvScene(mj_model, maxgeom=10)
        arrow, line = self.an_arrow(), self.a_line()
        alone_arrow, alone_line = mujoco.MjvGeom(), mujoco.MjvGeom()

        arrow.draw_in_scene(mj_model, scene)
        line.draw_in_scene(scene)
        arrow.fill_geom(alone_arrow, mj_model)
        line.fill_geom(alone_line)

        assert scene.ngeom == 2
        for in_scene, alone in (
            (scene.geoms[0], alone_arrow),
            (scene.geoms[1], alone_line),
        ):
            assert in_scene.type == alone.type
            assert np.allclose(in_scene.pos, alone.pos)
            assert np.allclose(in_scene.mat, alone.mat)
            assert np.allclose(in_scene.size, alone.size)
            assert np.allclose(in_scene.rgba, alone.rgba)

    def test_a_full_scene_gets_nothing_more_and_says_so(
        self, mj_model: mujoco.MjModel
    ) -> None:
        scene = mujoco.MjvScene(mj_model, maxgeom=1)

        self.an_arrow().draw_in_scene(mj_model, scene)
        self.an_arrow().draw_in_scene(mj_model, scene)
        self.a_line().draw_in_scene(scene)

        assert scene.ngeom == 1
