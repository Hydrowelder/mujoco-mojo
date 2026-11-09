"""Tests for the signal color palette: the one list in Python that the trial viewer and SensAI both use."""

import re
from pathlib import Path

import mujoco_mojo
from mujoco_mojo.utils.layers.dojo.plot_config import PLOT_COLORS, YAxisConfig

GENERATED_TS = (
    Path(mujoco_mojo.__file__).parent
    / "utils/layers/dojo/templates/static/ts/src/lib/plot-config.generated.ts"
)


def generated_palette() -> list[str]:
    """The colors in the `PLOT_COLORS` constant of the generated TypeScript, in order."""
    text = GENERATED_TS.read_text(encoding="utf-8")
    match = re.search(r"export const PLOT_COLORS[^=]*=\s*\[(.*?)\];", text, re.DOTALL)
    assert match is not None, "PLOT_COLORS is missing from plot-config.generated.ts"
    return [str(color) for color in re.findall(r'"([^"]*)"', match.group(1))]


def test_the_generated_typescript_has_the_same_palette_in_the_same_order() -> None:
    """Adding or reordering a color in Python reaches the color picker only once `python scripts/gen_ts_models.py` has been run, so this fails until it has."""
    assert generated_palette() == list(PLOT_COLORS)


def test_there_are_colors() -> None:
    assert len(PLOT_COLORS) >= 1


def test_every_color_is_a_six_digit_hex_string_the_plot_config_accepts() -> None:
    for color in PLOT_COLORS:
        assert re.fullmatch(r"#[0-9a-f]{6}", color), color
        assert YAxisConfig(color=color).color == color


def test_no_color_is_listed_twice() -> None:
    """A repeated color would make the next-color rule hand out the same color twice."""
    assert len({color.lower() for color in PLOT_COLORS}) == len(PLOT_COLORS)
