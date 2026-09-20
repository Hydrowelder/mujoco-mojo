import pytest
from pydantic import ValidationError

from mujoco_mojo.utils.layers.dojo.plot_config import PlotConfig


def test_ref_frame_defaults_to_world() -> None:
    assert PlotConfig().ref_frame is None


def test_ref_frame_accepts_quat_and_origin_pair() -> None:
    cfg = PlotConfig.model_validate({"refFrame": ["Bodies/B/quat", "Bodies/B/xpos"]})
    assert cfg.ref_frame == ("Bodies/B/quat", "Bodies/B/xpos")
    assert cfg.model_dump()["refFrame"] == ("Bodies/B/quat", "Bodies/B/xpos")


def test_ref_frame_halves_are_independently_optional() -> None:
    """A quaternion alone only rotates and an origin alone only translates."""
    rotate_only = PlotConfig.model_validate({"refFrame": ["Bodies/B/quat", None]})
    translate_only = PlotConfig.model_validate({"refFrame": [None, "Bodies/B/xpos"]})
    assert rotate_only.ref_frame == ("Bodies/B/quat", None)
    assert translate_only.ref_frame == (None, "Bodies/B/xpos")


@pytest.mark.parametrize("legacy", ["Bodies/B/quat", "world", ""])
def test_ref_frame_rejects_the_old_string_form(legacy: str) -> None:
    with pytest.raises(ValidationError):
        PlotConfig.model_validate({"refFrame": legacy})


def test_ref_frame_rejects_a_single_element() -> None:
    with pytest.raises(ValidationError):
        PlotConfig.model_validate({"refFrame": ["Bodies/B/quat"]})
