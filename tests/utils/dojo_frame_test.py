import pytest

from mujoco_mojo.utils.filters import RotationFilter, ScaleFilter
from mujoco_mojo.utils.layers.dojo.routers.mosaic import (
    _column_metadata_fields,
    _origin_for_positions_only,
)
from mujoco_mojo.utils.signal_metadata import ColumnMetadata


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


def test_signal_out_fields_cover_every_column_metadata_field() -> None:
    """The Lab's Signal Out node is generated from ColumnMetadata, so it cannot lag behind the model."""
    fields = _column_metadata_fields()
    assert [f["name"] for f in fields] == list(ColumnMetadata.model_fields)
    assert all(f["description"] for f in fields)


def test_signal_out_fields_offer_a_combo_only_for_fixed_choices() -> None:
    by_name = {f["name"]: f for f in _column_metadata_fields()}
    assert by_name["transform_type"]["options"] == ["point", "vector", "quaternion"]
    for free_text in ("unit", "dimension", "quantity"):
        assert by_name[free_text]["options"] is None
