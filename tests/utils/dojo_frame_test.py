import pytest

from mujoco_mojo.utils.filters import RotationFilter, ScaleFilter
from mujoco_mojo.utils.layers.dojo.routers.mosaic import _origin_for_positions_only


def _frame_filter() -> RotationFilter:
    return RotationFilter(
        quat_col="Bodies/B/quat", origin_col="Bodies/B/xpos", invert=True
    )


def test_origin_is_kept_for_position_columns() -> None:
    f = _frame_filter()
    assert _origin_for_positions_only(f, "point") is f


@pytest.mark.parametrize("transform_type", ["vector", "quaternion", None])
def test_origin_is_dropped_for_everything_else(transform_type: str | None) -> None:
    """Free vectors, and columns with no tag (older runs, custom signals, lab outputs), are only rotated."""
    f = _frame_filter()
    result = _origin_for_positions_only(f, transform_type)
    assert isinstance(result, RotationFilter)
    assert result.origin_col is None
    assert result.quat_col == "Bodies/B/quat"
    assert f.origin_col == "Bodies/B/xpos"  # the original filter is not mutated


def test_other_filters_are_untouched() -> None:
    f = ScaleFilter(factor=2.0, offset=0.0)
    assert _origin_for_positions_only(f, None) is f
