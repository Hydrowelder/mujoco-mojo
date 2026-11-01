import random

from rich.style import Style
import pytest

import mujoco_mojo.utils.layers.reloaded.rain as rain_module
from mujoco_mojo.utils.layers.reloaded.rain import (
    BLANK_STYLE,
    WORD,
    repeating_text,
    HEAD_STYLE,
    TRAIL_STYLES,
    Drop,
    RESTART_WITHIN,
    Rain,
)
from mujoco_mojo.utils.layers.reloaded.theme import CANVAS, LINK

WIDTH = 40
HEIGHT = 24


def make_rain(seed: int = 1) -> Rain:
    return Rain(WIDTH, HEIGHT, random.Random(seed))


def visible_cells(rain: Rain) -> list[tuple[int, int]]:
    return [
        (row, column)
        for row in range(rain.height)
        for column in range(rain.width)
        if rain.trail(row, column) is not None
    ]


def test_every_spaced_column_carries_a_drop() -> None:
    rain = make_rain()

    assert set(rain.drops) == set(range(0, WIDTH, rain_module.COLUMN_SPACING))
    assert all(drop.head < 0 for drop in rain.drops.values())


def test_a_wider_spacing_leaves_the_columns_between_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rain_module, "COLUMN_SPACING", 3)
    rain = make_rain()

    for _ in range(80):
        rain.step()
        assert all(column % 3 == 0 for _, column in visible_cells(rain))

    assert set(rain.drops) == set(range(0, WIDTH, 3))


def test_the_rain_is_neither_empty_nor_solid_once_it_is_going() -> None:
    rain = make_rain()
    for _ in range(100):
        rain.step()

    lit = []
    for _ in range(200):
        rain.step()
        lit.append(len(visible_cells(rain)) / (WIDTH * HEIGHT))

    assert 0.05 < sum(lit) / len(lit) < 0.5


def test_a_drop_that_has_left_starts_again_close_behind_and_off_the_screen() -> None:
    rain = make_rain()
    rain.drops[0] = Drop(head=HEIGHT + 100, length=6, period=1)

    rain.step()

    assert -int(HEIGHT * RESTART_WITHIN) <= rain.drops[0].head <= -1


def test_a_drop_is_a_head_with_a_trail_behind_it_and_nothing_ahead() -> None:
    rain = make_rain()
    column = 0
    drop = rain.drops[column]
    drop.head, drop.length = 10, 6

    assert rain.trail(10, column) == (0, 6)
    assert rain.trail(9, column) == (1, 6)
    assert rain.trail(4, column) == (6, 6)
    assert rain.trail(3, column) is None
    assert rain.trail(11, column) is None
    assert rain.trail(10, column + 1) is None


def test_a_letter_holds_still_while_its_trail_fades_instead_of_flickering() -> None:
    rain = make_rain()
    column = 0
    rain.drops[column] = Drop(head=5, length=10, period=1)
    before = [rain.letters[row][column] for row in range(HEIGHT)]

    for _ in range(3):
        rain.step()

    after = [rain.letters[row][column] for row in range(HEIGHT)]
    # only the rows the head reached meanwhile may change
    changed = {row for row in range(HEIGHT) if before[row] != after[row]}
    assert changed <= {6, 7, 8}


def test_every_lit_cell_holds_a_letter_of_the_word() -> None:
    rain = make_rain()

    for _ in range(60):
        rain.step()

    lit = visible_cells(rain)
    assert lit
    assert {rain.letters[row][column] for row, column in lit} <= set(repeating_text())


def test_a_trail_spells_the_word_from_the_bottom_up() -> None:
    rain = make_rain()
    for _ in range(60):
        rain.step()

    spelled = []
    for column in rain.drops:
        rows = [row for row in range(HEIGHT) if rain.trail(row, column) is not None]
        top_to_bottom = "".join(rain.letters[row][column] for row in rows)
        spelled.append(top_to_bottom[::-1])

    assert any(len(text.strip()) >= 6 for text in spelled)
    assert all(text in repeating_text() * 5 for text in spelled)


def test_the_head_sets_the_letter_before_the_one_above_it() -> None:
    """Going down a row steps back a letter in the text, which is what makes it read upward."""
    rain = make_rain()
    column = 0
    rain.drops[column] = Drop(head=-1, length=11, period=1, phase=4)

    for _ in range(6):
        rain.step()

    bottom_up = "".join(rain.letters[row][column] for row in range(5, -1, -1))
    assert bottom_up in repeating_text() * 2


def test_without_a_gap_the_word_runs_straight_into_the_next_and_nothing_is_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rain_module, "WORD_GAP", 0)
    rain = make_rain()

    for _ in range(80):
        rain.step()
        lit = visible_cells(rain)
        assert {rain.letters[row][column] for row, column in lit} <= set(WORD)

    assert repeating_text() == WORD


@pytest.mark.parametrize("gap", [0, 1, 4])
def test_the_gap_sets_how_many_blank_cells_separate_the_readings(
    monkeypatch: pytest.MonkeyPatch, gap: int
) -> None:
    monkeypatch.setattr(rain_module, "WORD_GAP", gap)
    rain = make_rain()
    column = 0
    rain.drops[column] = Drop(head=-1, length=60, period=1, phase=0)

    for _ in range(HEIGHT):
        rain.step()

    bottom_up = "".join(rain.letters[row][column] for row in range(HEIGHT - 2, -1, -1))
    assert bottom_up in repeating_text() * 4
    assert repeating_text() == WORD + " " * gap


def test_neighboring_columns_do_not_all_spell_it_in_step() -> None:
    rain = make_rain()

    assert len({drop.phase for drop in rain.drops.values()}) > 1


def test_rain_keeps_falling_forever() -> None:
    rain = make_rain()
    seen_by_stretch: list[int] = []

    for _ in range(10):
        for _ in range(HEIGHT):
            rain.step()
        seen_by_stretch.append(len(visible_cells(rain)))

    assert all(count > 0 for count in seen_by_stretch)
    assert len(rain.drops) == len(range(0, WIDTH, rain_module.COLUMN_SPACING))


def test_the_rain_is_the_same_for_the_same_seed() -> None:
    first, second = make_rain(7), make_rain(7)

    for _ in range(25):
        first.step()
        second.step()

    assert visible_cells(first) == visible_cells(second)
    assert first.letters == second.letters


def color_hex(style: Style) -> str:
    assert style.color is not None
    return style.color.get_truecolor().hex.upper()


def background_hex(style: Style) -> str:
    assert style.bgcolor is not None
    return style.bgcolor.get_truecolor().hex.upper()


def test_the_trail_fades_from_the_link_color_into_the_background() -> None:
    assert color_hex(TRAIL_STYLES[0]) == str(LINK).upper()
    assert color_hex(TRAIL_STYLES[-1]) == str(CANVAS).upper()
    assert HEAD_STYLE.bold


def test_every_cell_sits_on_the_canvas_so_no_patch_shows_through() -> None:
    for style in (*TRAIL_STYLES, HEAD_STYLE, BLANK_STYLE):
        assert background_hex(style) == str(CANVAS).upper()
