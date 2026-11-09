"""Tests for how SensAI edits the plot config: applying a small edit, the field list the agent reads, and the signal and filter lookups."""

import asyncio
import json
import re
from typing import Any

import pytest

from mujoco_mojo.utils.layers.dojo.plot_config import (
    PLOT_COLORS,
    GridMode,
    PlotConfig,
    XAxisConfig,
    YAxisConfig,
)
from mujoco_mojo.utils.layers.dojo.routers.mosaic import get_filter_schema
from mujoco_mojo.utils.layers.dojo.sensai.plot_config_catalog import (
    filter_catalog,
    find_signals,
    plot_config_catalog,
)
from mujoco_mojo.utils.layers.dojo.sensai.plot_config_delta import (
    PlotConfigDeltaError,
    apply_plot_config_delta,
    _merge_patch,
    compact_plot_config,
    remove_plot_signals,
)

COLUMNS = [
    "time",
    "Bodies/box1/xpos:x",
    "Bodies/box1/xpos:y",
    "Bodies/box1/xvelr:y",
    "Bodies/box2/xpos:x",
    "Sensors/contact",
]

UNIT_FILTER: dict[str, Any] = {
    "type": "unit",
    "enabled": True,
    "fromUnit": "rad/s",
    "toUnit": "deg/s",
}


FILTER_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "scale",
        "description": "Applies a linear transformation.",
        "params": [
            {"name": "factor", "type": "float", "default": 1.0},
            {"name": "offset", "type": "float", "default": 0.0},
        ],
    },
    {
        "type": "unit",
        "description": "Converts between units.",
        "params": [
            {"name": "fromUnit", "type": "string", "default": None},
            {"name": "toUnit", "type": "string", "default": None},
        ],
    },
    {"type": "abs", "description": "Absolute value.", "params": []},
]


def make_config(**over: Any) -> PlotConfig:
    """A config with one signal that has a filter, the way a user's plot looks after some editing."""
    data: dict[str, Any] = {
        "yAxes": {
            "Bodies/box1/xvelr:y": {"color": "#00bc7d", "filters": [UNIT_FILTER]}
        },
        "title": "Velocity",
    }
    data.update(over)
    return PlotConfig.model_validate(data)


def dump(config: PlotConfig) -> dict[str, Any]:
    return config.model_dump(mode="json")


class TestCompactPlotConfig:
    def test_a_default_config_is_empty(self) -> None:
        assert compact_plot_config(PlotConfig()) == {}

    def test_only_what_differs_from_the_defaults_is_kept(self) -> None:
        compact = compact_plot_config(make_config(grid="none"))

        assert compact["title"] == "Velocity"
        assert compact["grid"] == "none"
        assert "lineMode" not in compact
        assert "xAxis" not in compact

    def test_a_signal_keeps_its_color_and_loses_its_default_fields(self) -> None:
        signal = compact_plot_config(make_config())["yAxes"]["Bodies/box1/xvelr:y"]

        assert signal["color"] == "#00bc7d"
        assert "width" not in signal
        assert "dash" not in signal

    def test_a_filter_keeps_its_type(self) -> None:
        """The type is a default value on the filter model, so a naive exclude-defaults dump would leave an unreadable filter."""
        signal = compact_plot_config(make_config())["yAxes"]["Bodies/box1/xvelr:y"]

        assert signal["filters"] == [UNIT_FILTER]

    def test_a_changed_x_axis_is_kept(self) -> None:
        config = make_config(xAxis={"col": "Bodies/box1/xpos:x"})

        assert compact_plot_config(config)["xAxis"] == {"col": "Bodies/box1/xpos:x"}

    def test_the_result_is_json(self) -> None:
        json.dumps(compact_plot_config(make_config()))


class TestApplyingAnEdit:
    def test_an_empty_edit_changes_nothing(self) -> None:
        config = make_config()

        assert apply_plot_config_delta(config, {}, COLUMNS) == config

    def test_the_config_it_was_given_is_left_alone(self) -> None:
        config = make_config()
        before = dump(config)

        apply_plot_config_delta(
            config,
            {"title": "New", "yAxes": {"Bodies/box1/xvelr:y": {"color": "#ff0000"}}},
            COLUMNS,
        )

        assert dump(config) == before

    def test_a_field_is_set(self) -> None:
        edited = apply_plot_config_delta(make_config(), {"title": "hello"}, COLUMNS)

        assert edited.title == "hello"

    def test_nothing_else_changes_with_it(self) -> None:
        """Renaming the plot must not touch the signals, the filters, or any other field."""
        config = make_config()
        edited = apply_plot_config_delta(config, {"title": "hello"}, COLUMNS)

        expected = dump(config)
        expected["title"] = "hello"
        assert dump(edited) == expected

    def test_a_field_may_be_written_in_snake_case(self) -> None:
        edited = apply_plot_config_delta(
            make_config(), {"x_axis_title": "t (s)", "legendPos": "right"}, COLUMNS
        )

        assert edited.x_axis_title == "t (s)"
        assert edited.legend_pos.value == "right"

    def test_several_fields_change_in_one_edit(self) -> None:
        edited = apply_plot_config_delta(
            make_config(),
            {"grid": "none", "showSpike": False, "rangeX": [0, 5]},
            COLUMNS,
        )

        assert edited.grid is GridMode.NONE
        assert edited.show_spike is False
        assert edited.range_x == (0, 5)

    def test_a_field_that_allows_null_takes_it_as_a_value(self) -> None:
        """An automatic range is `null`, so that one is a real value and not an absence."""
        config = make_config(rangeX=[0, 5], xAxisTitle="x")

        edited = apply_plot_config_delta(config, {"rangeX": None}, COLUMNS)

        assert edited.range_x is None
        assert edited.x_axis_title == "x"

    def test_null_for_a_field_that_needs_a_value_is_refused(self) -> None:
        """A model writes `null` for "nothing here", which must not reset what the user set: it used to put the title and the grid back to their defaults."""
        config = make_config(grid="none")

        with pytest.raises(PlotConfigDeltaError, match="cannot be null") as err:
            apply_plot_config_delta(config, {"title": None, "grid": None}, COLUMNS)

        assert "Leave out any field you are not changing" in str(err.value)

    def test_the_refusal_of_a_null_says_what_the_default_is(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match='"all"'):
            apply_plot_config_delta(make_config(), {"grid": None}, COLUMNS)

    def test_no_field_is_ever_reset_by_null(self) -> None:
        """Whatever the field, `null` either is refused or is stored as `null`; it never quietly becomes something else."""
        config = make_config(title="Velocity")

        for name, info in PlotConfig.model_fields.items():
            alias = info.alias or name
            if alias in ("xAxis", "yAxes"):
                continue
            try:
                edited = apply_plot_config_delta(config, {alias: None}, COLUMNS)
            except PlotConfigDeltaError:
                continue
            assert dump(edited)[alias] is None, alias

    def test_setting_a_value_it_already_has_changes_nothing(self) -> None:
        config = make_config()

        assert apply_plot_config_delta(config, {"title": "Velocity"}, COLUMNS) == config

    def test_the_merge_keeps_a_null_as_a_value(self) -> None:
        """A JSON Merge Patch would delete the key. Here `null` is a value for the fields that allow it, which matters for one that is not `null` by default."""
        assert _merge_patch({"a": 1, "b": 2}, {"a": None}) == {"a": None, "b": 2}

    def test_a_list_replaces_the_one_there(self) -> None:
        config = make_config(annotations=[{"x": 1, "y": 2, "text": "a"}])

        edited = apply_plot_config_delta(config, {"annotations": []}, COLUMNS)

        assert edited.annotations == []


class TestEditingSignals:
    SIGNAL = "Bodies/box1/xvelr:y"

    def test_one_field_of_a_signal_changes_and_the_rest_stays(self) -> None:
        """The merge is deep: recoloring a signal does not drop its filters, which is what resending the whole entry used to risk."""
        edited = apply_plot_config_delta(
            make_config(), {"yAxes": {self.SIGNAL: {"color": "#ff0000"}}}, COLUMNS
        )

        signal = edited.y_axes[self.SIGNAL]
        assert signal.color == "#ff0000"
        assert [f.type for f in signal.filters] == ["unit"]

    def test_the_other_signals_are_left_alone(self) -> None:
        config = make_config(
            yAxes={
                self.SIGNAL: {"color": "#00bc7d"},
                "Bodies/box1/xpos:x": {"color": "#3080ff"},
            }
        )

        edited = apply_plot_config_delta(
            config, {"yAxes": {self.SIGNAL: {"width": 6}}}, COLUMNS
        )

        assert (
            edited.y_axes["Bodies/box1/xpos:x"] == config.y_axes["Bodies/box1/xpos:x"]
        )
        assert edited.y_axes[self.SIGNAL].width == 6

    def test_a_signal_is_added_by_its_name_alone(self) -> None:
        edited = apply_plot_config_delta(
            make_config(), {"yAxes": {"Bodies/box1/xpos:x": {}}}, COLUMNS
        )

        assert list(edited.y_axes) == [self.SIGNAL, "Bodies/box1/xpos:x"]

    def test_an_added_signal_gets_a_color_no_other_signal_has(self) -> None:
        edited = apply_plot_config_delta(
            make_config(), {"yAxes": {"Bodies/box1/xpos:x": {}}}, COLUMNS
        )

        colors = [y.color for y in edited.y_axes.values()]
        assert len(set(colors)) == 2
        assert edited.y_axes["Bodies/box1/xpos:x"].color in PLOT_COLORS

    def test_signals_added_together_each_get_their_own_color(self) -> None:
        """Added in one edit, none of them is in the config yet, so the colors in use have to include the ones just handed out."""
        edited = apply_plot_config_delta(
            make_config(),
            {"yAxes": {"Bodies/box1/xpos:x": {}, "Bodies/box1/xpos:y": {}}},
            COLUMNS,
        )

        colors = [y.color for y in edited.y_axes.values()]
        assert len(set(colors)) == 3

    def test_an_added_signal_keeps_the_color_it_was_given(self) -> None:
        edited = apply_plot_config_delta(
            make_config(),
            {"yAxes": {"Bodies/box1/xpos:x": {"color": "#123456"}}},
            COLUMNS,
        )

        assert edited.y_axes["Bodies/box1/xpos:x"].color == "#123456"

    def test_colors_run_out_gracefully(self) -> None:
        """Every color is in use, so the palette starts again from its first color, then its second."""
        signals = {f"s{i}": {"color": c} for i, c in enumerate(PLOT_COLORS)}
        config = make_config(yAxes=signals)

        edited = apply_plot_config_delta(
            config, {"yAxes": {"extra": {}, "more": {}}}, ()
        )

        assert edited.y_axes["extra"].color == PLOT_COLORS[0]
        assert edited.y_axes["more"].color == PLOT_COLORS[1 % len(PLOT_COLORS)]

    def test_signals_on_a_blank_plot_take_the_palette_in_order(self) -> None:
        """The same order the trial viewer's own next-color rule uses, so a signal SensAI adds looks like one added by hand."""
        names = [f"s{i}" for i in range(len(PLOT_COLORS))]

        edited = apply_plot_config_delta(
            make_config(yAxes={}), {"yAxes": {n: {} for n in names}}, ()
        )

        assert [edited.y_axes[n].color for n in names] == list(PLOT_COLORS)

    def test_a_color_that_was_freed_is_the_next_one_used(self) -> None:
        """The first palette color no signal uses, not the one after the last: removing the first signal makes the first color available again."""
        config = make_config(
            yAxes={
                "a": {"color": PLOT_COLORS[1]},
                "b": {"color": PLOT_COLORS[2]},
            }
        )

        edited = apply_plot_config_delta(config, {"yAxes": {"c": {}}}, ())

        assert edited.y_axes["c"].color == PLOT_COLORS[0]

    def test_a_color_a_signal_has_in_another_case_counts_as_used(self) -> None:
        config = make_config(yAxes={"a": {"color": PLOT_COLORS[0].upper()}})

        edited = apply_plot_config_delta(config, {"yAxes": {"b": {}}}, ())

        assert edited.y_axes["b"].color == PLOT_COLORS[1]

    def test_null_for_all_signals_is_refused(self) -> None:
        """The incident: an agent sent `{"yAxes": null}` to "add a signal", and the plot lost every signal."""
        with pytest.raises(PlotConfigDeltaError, match="yAxes cannot be null") as err:
            apply_plot_config_delta(make_config(), {"yAxes": None}, COLUMNS)

        assert "remove_signals" in str(err.value)

    def test_null_does_not_stop_plotting_a_signal(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="cannot be null") as err:
            apply_plot_config_delta(
                make_config(), {"yAxes": {self.SIGNAL: None}}, COLUMNS
            )

        assert "remove_signals" in str(err.value)

    def test_null_does_not_add_a_signal_and_the_refusal_shows_how(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="cannot be null") as err:
            apply_plot_config_delta(
                make_config(), {"yAxes": {"Bodies/box2/xpos:x": None}}, COLUMNS
            )

        assert '{"yAxes": {"Bodies/box2/xpos:x": {}}}' in str(err.value)

    def test_null_for_a_field_of_a_signal_is_refused(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="cannot be null"):
            apply_plot_config_delta(
                make_config(), {"yAxes": {self.SIGNAL: {"label": None}}}, COLUMNS
            )

    def test_adding_a_signal_keeps_the_ones_already_plotted(self) -> None:
        edited = apply_plot_config_delta(
            make_config(), {"yAxes": {"Bodies/box2/xpos:x": {}}}, COLUMNS
        )

        assert list(edited.y_axes) == [self.SIGNAL, "Bodies/box2/xpos:x"]
        assert edited.y_axes[self.SIGNAL] == make_config().y_axes[self.SIGNAL]

    def test_an_empty_signal_list_edit_changes_nothing(self) -> None:
        config = make_config()

        assert apply_plot_config_delta(config, {"yAxes": {}}, COLUMNS) == config

    def test_a_signal_the_trial_does_not_have_is_refused_with_close_matches(
        self,
    ) -> None:
        with pytest.raises(
            PlotConfigDeltaError, match="not a signal of this trial"
        ) as err:
            apply_plot_config_delta(
                make_config(), {"yAxes": {"Bodies/box1/xvel:y": {}}}, COLUMNS
            )

        assert "Bodies/box1/xvelr:y" in str(err.value)
        assert "find_signals" in str(err.value)

    def test_a_shortened_signal_name_is_not_accepted(self) -> None:
        """A name cut off at a folder, which a model that is copying carelessly produces, must not land in the plot."""
        with pytest.raises(PlotConfigDeltaError):
            apply_plot_config_delta(make_config(), {"yAxes": {"Bodies": {}}}, COLUMNS)

    def test_names_are_not_checked_when_the_trial_is_unknown(self) -> None:
        edited = apply_plot_config_delta(make_config(), {"yAxes": {"anything": {}}}, ())

        assert "anything" in edited.y_axes

    def test_a_plotted_signal_is_not_checked_against_the_trial_again(self) -> None:
        """Editing a signal that is already plotted works even if the trial's columns are not known to include it."""
        edited = apply_plot_config_delta(
            make_config(), {"yAxes": {self.SIGNAL: {"width": 5}}}, ["time"]
        )

        assert edited.y_axes[self.SIGNAL].width == 5

    def test_a_signal_field_that_does_not_exist_is_refused(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match='has no field "colour"') as err:
            apply_plot_config_delta(
                make_config(), {"yAxes": {self.SIGNAL: {"colour": "#fff000"}}}, COLUMNS
            )

        assert "Did you mean: color" in str(err.value)

    def test_a_color_that_is_not_hex_is_refused(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="color"):
            apply_plot_config_delta(
                make_config(), {"yAxes": {self.SIGNAL: {"color": "red"}}}, COLUMNS
            )

    def test_a_value_out_of_range_is_refused(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="opacity"):
            apply_plot_config_delta(
                make_config(), {"yAxes": {self.SIGNAL: {"opacity": 5}}}, COLUMNS
            )

    def test_signals_must_be_an_object(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="yAxes must be an object"):
            apply_plot_config_delta(make_config(), {"yAxes": ["a"]}, COLUMNS)

    def test_a_signal_entry_must_be_an_object(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="must be an object"):
            apply_plot_config_delta(
                make_config(), {"yAxes": {self.SIGNAL: "#ff0000"}}, COLUMNS
            )

    def test_the_filters_of_a_signal_are_replaced_as_a_list(self) -> None:
        edited = apply_plot_config_delta(
            make_config(), {"yAxes": {self.SIGNAL: {"filters": []}}}, COLUMNS
        )

        assert edited.y_axes[self.SIGNAL].filters == []

    def test_a_filter_of_an_unknown_type_is_refused_and_points_at_the_reference(
        self,
    ) -> None:
        with pytest.raises(PlotConfigDeltaError, match="describe_filters"):
            apply_plot_config_delta(
                make_config(),
                {"yAxes": {self.SIGNAL: {"filters": [{"type": "nonsense"}]}}},
                COLUMNS,
            )


class TestEditingTheXAxis:
    def test_the_column_is_set(self) -> None:
        edited = apply_plot_config_delta(
            make_config(), {"xAxis": {"col": "Bodies/box1/xpos:x"}}, COLUMNS
        )

        assert edited.x_axis.col == "Bodies/box1/xpos:x"

    def test_a_column_the_trial_does_not_have_is_refused(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="not a column of this trial"):
            apply_plot_config_delta(make_config(), {"xAxis": {"col": "nope"}}, COLUMNS)

    def test_null_is_refused_and_the_message_says_how_to_get_back_to_time(
        self,
    ) -> None:
        config = make_config(xAxis={"col": "Bodies/box1/xpos:x"})

        with pytest.raises(PlotConfigDeltaError, match="xAxis cannot be null") as err:
            apply_plot_config_delta(config, {"xAxis": None}, COLUMNS)

        assert '{"xAxis": {"col": "time"}}' in str(err.value)

    def test_going_back_to_time_is_a_column_edit(self) -> None:
        config = make_config(xAxis={"col": "Bodies/box1/xpos:x"})

        edited = apply_plot_config_delta(config, {"xAxis": {"col": "time"}}, COLUMNS)

        assert edited.x_axis == XAxisConfig()

    def test_null_for_a_field_of_it_is_refused(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="cannot be null"):
            apply_plot_config_delta(make_config(), {"xAxis": {"col": None}}, COLUMNS)

    def test_it_must_be_an_object(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="xAxis must be an object"):
            apply_plot_config_delta(make_config(), {"xAxis": "time"}, COLUMNS)

    def test_a_field_that_does_not_exist_is_refused(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match='xAxis has no field "column"'):
            apply_plot_config_delta(
                make_config(), {"xAxis": {"column": "time"}}, COLUMNS
            )


class TestRemovingSignals:
    FIRST = "Bodies/box1/xvelr:y"
    SECOND = "Bodies/box1/xpos:x"

    def two(self) -> PlotConfig:
        return make_config(
            yAxes={
                self.FIRST: {"color": "#00bc7d", "filters": [UNIT_FILTER]},
                self.SECOND: {"color": "#3080ff"},
                "Bodies/box2/xpos:x": {"color": "#fb2c36"},
            }
        )

    def test_the_named_signal_goes_and_the_others_stay_in_order(self) -> None:
        config = self.two()

        edited = remove_plot_signals(config, [self.SECOND])

        assert list(edited.y_axes) == [self.FIRST, "Bodies/box2/xpos:x"]
        assert edited.y_axes[self.FIRST] == config.y_axes[self.FIRST]

    def test_several_go_at_once_and_a_repeated_name_is_fine(self) -> None:
        edited = remove_plot_signals(self.two(), [self.FIRST, self.SECOND, self.FIRST])

        assert list(edited.y_axes) == ["Bodies/box2/xpos:x"]

    def test_the_rest_of_the_config_is_untouched(self) -> None:
        config = self.two()

        edited = remove_plot_signals(config, [self.SECOND])

        assert edited.title == config.title

    def test_the_config_it_was_given_is_left_alone(self) -> None:
        config = self.two()
        before = dump(config)

        remove_plot_signals(config, [self.SECOND])

        assert dump(config) == before

    def test_every_signal_can_be_removed(self) -> None:
        assert remove_plot_signals(self.two(), list(self.two().y_axes)).y_axes == {}

    def test_no_names_is_refused(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="at least one"):
            remove_plot_signals(self.two(), [])

    def test_a_signal_that_is_not_plotted_is_refused_and_the_plotted_ones_are_listed(
        self,
    ) -> None:
        with pytest.raises(PlotConfigDeltaError, match="Not plotted") as err:
            remove_plot_signals(self.two(), ["Bodies/box9/xpos:x"])

        assert "Bodies/box9/xpos:x" in str(err.value)
        assert self.FIRST in str(err.value)

    def test_one_missing_name_stops_the_whole_removal(self) -> None:
        """All or nothing: the model is told what was wrong and sends the corrected list."""
        config = self.two()

        with pytest.raises(PlotConfigDeltaError):
            remove_plot_signals(config, [self.SECOND, "nope"])

        assert list(config.y_axes) == [self.FIRST, self.SECOND, "Bodies/box2/xpos:x"]


class TestRefusedEdits:
    def test_a_field_the_config_does_not_have_is_refused(self) -> None:
        """The config model silently ignores unknown keys, so an invented field name would otherwise vanish without a trace."""
        with pytest.raises(PlotConfigDeltaError, match='has no field "bogus"'):
            apply_plot_config_delta(make_config(), {"bogus": 1}, COLUMNS)

    def test_the_refusal_lists_the_fields_and_suggests_one(self) -> None:
        with pytest.raises(PlotConfigDeltaError) as err:
            apply_plot_config_delta(make_config(), {"titel": "x"}, COLUMNS)

        message = str(err.value)
        assert "Did you mean: title" in message
        assert "legendPos" in message
        assert "yAxes" in message

    def test_a_value_that_is_not_a_choice_is_refused_and_names_the_field(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="grid") as err:
            apply_plot_config_delta(make_config(), {"grid": "bogus"}, COLUMNS)

        assert "major" in str(err.value)

    def test_a_value_of_the_wrong_type_is_refused(self) -> None:
        with pytest.raises(PlotConfigDeltaError, match="showSpike"):
            apply_plot_config_delta(make_config(), {"showSpike": "maybe"}, COLUMNS)

    def test_a_refused_edit_changes_nothing(self) -> None:
        config = make_config()
        before = dump(config)

        with pytest.raises(PlotConfigDeltaError):
            apply_plot_config_delta(config, {"title": "ok", "grid": "bogus"}, COLUMNS)

        assert dump(config) == before

    def test_a_long_list_of_problems_is_cut_short(self) -> None:
        bad = {
            "grid": "x",
            "lineMode": "x",
            "interp": "x",
            "hover": "nope",  # "x" is a valid hover mode
            "legendPos": "x",
            "xScale": "x",
            "yScale": "x",
        }

        with pytest.raises(PlotConfigDeltaError) as err:
            apply_plot_config_delta(make_config(), bad, COLUMNS)

        message = str(err.value)
        assert "(and 2 more)" in message
        assert message.count(": Input should be") == 5

    def test_a_few_problems_are_all_listed_with_no_note_about_more(self) -> None:
        with pytest.raises(PlotConfigDeltaError) as err:
            apply_plot_config_delta(
                make_config(), {"grid": "x", "lineMode": "x"}, COLUMNS
            )

        message = str(err.value)
        assert message.count(": Input should be") == 2
        assert "more)" not in message


class TestFindSignals:
    def test_every_word_has_to_match(self) -> None:
        assert find_signals(COLUMNS, "box1 xpos") == [
            "Bodies/box1/xpos:x",
            "Bodies/box1/xpos:y",
        ]

    def test_case_is_ignored(self) -> None:
        assert find_signals(COLUMNS, "CONTACT") == ["Sensors/contact"]

    def test_separators_split_words(self) -> None:
        assert find_signals(COLUMNS, "box1/xvelr:y") == ["Bodies/box1/xvelr:y"]
        assert find_signals(COLUMNS, "box2_xpos") == ["Bodies/box2/xpos:x"]

    def test_the_shortest_come_first(self) -> None:
        assert find_signals(["a/long/name:x", "a:x", "a/b:x"], "a") == [
            "a:x",
            "a/b:x",
            "a/long/name:x",
        ]

    def test_the_number_of_matches_is_limited(self) -> None:
        many = [f"sig{i}" for i in range(100)]

        assert len(find_signals(many, "sig")) == 25
        assert len(find_signals(many, "sig", limit=3)) == 3

    def test_the_closest_spellings_come_back_when_nothing_matches(self) -> None:
        assert "Bodies/box1/xvelr:y" in find_signals(COLUMNS, "Bodies/box1/xvelrr:y")

    def test_nothing_is_found_for_an_empty_query_or_no_columns(self) -> None:
        assert find_signals(COLUMNS, "") == []
        assert find_signals(COLUMNS, " / ") == []
        assert find_signals([], "time") == []


class TestPlotConfigCatalog:
    def test_it_lists_every_field_of_the_config(self) -> None:
        """Built from the models, so a field added to one shows up without anyone remembering to update a prompt."""
        catalog = plot_config_catalog()

        # xAxis and yAxes get a section each, which the next test checks
        for model, skipped in (
            (PlotConfig, {"x_axis", "y_axes"}),
            (XAxisConfig, set()),
            (YAxisConfig, set()),
        ):
            for name, info in model.model_fields.items():
                if name not in skipped:
                    assert f"- {info.alias or name}" in catalog

    def test_it_stays_small(self) -> None:
        """It goes into every plot-config run, so its size is a token cost. The schema it replaces is several times larger."""
        assert len(plot_config_catalog()) < 3500

    def test_the_choices_of_a_field_are_listed(self) -> None:
        assert "(none|major|all, default" in plot_config_catalog()

    def test_a_field_with_many_choices_lists_the_first_few(self) -> None:
        marker = next(
            line
            for line in plot_config_catalog().splitlines()
            if line.startswith("- marker")
        )

        assert "none|circle|square" in marker
        assert "|...," in marker
        assert "hexagram" not in marker

    def test_a_default_is_shown_as_json(self) -> None:
        catalog = plot_config_catalog()

        assert "default null" in catalog
        assert "default true" in catalog
        assert 'default "all"' in catalog

    def test_a_description_is_not_cut_at_an_abbreviation(self) -> None:
        color = next(
            line
            for line in plot_config_catalog().splitlines()
            if line.startswith("- color")
        )

        assert "(e.g. `#ff0000`)" in color

    def test_the_structured_fields_have_their_own_sections(self) -> None:
        catalog = plot_config_catalog()

        assert "xAxis (an object" in catalog
        assert "Signal fields (" in catalog
        listed = set(re.findall(r"^- (\w+)", catalog, flags=re.MULTILINE))
        assert not listed & {"xAxis", "yAxes"}


class TestFilterCatalog:
    def test_without_a_type_it_lists_each_type_on_a_line(self) -> None:
        assert filter_catalog(FILTER_SCHEMA).splitlines() == [
            "- scale: Applies a linear transformation.",
            "- unit: Converts between units.",
            "- abs: Absolute value.",
        ]

    def test_a_type_gets_its_parameters_and_how_to_write_it(self) -> None:
        text = filter_catalog(FILTER_SCHEMA, "scale")

        assert (
            "Parameters: factor (float, default 1.0), offset (float, default 0.0)"
            in text
        )
        assert '{"type": "scale", "factor": ..., "offset": ...}' in text
        assert "replaces the whole list" in text

    def test_a_parameter_with_no_default_shows_none(self) -> None:
        assert "fromUnit (string), toUnit (string)" in filter_catalog(
            FILTER_SCHEMA, "unit"
        )

    def test_a_type_with_no_parameters_says_so(self) -> None:
        assert "Parameters: none" in filter_catalog(FILTER_SCHEMA, "abs")

    def test_an_unknown_type_gets_close_matches(self) -> None:
        text = filter_catalog(FILTER_SCHEMA, "scal")

        assert 'no filter type "scal"' in text
        assert "Did you mean: scale" in text

    def test_an_unknown_type_with_nothing_close_points_at_the_list(self) -> None:
        text = filter_catalog(FILTER_SCHEMA, "zzzzzz")

        assert "Did you mean" not in text
        assert "describe_filters with no type" in text

    def test_the_real_filter_schema_is_covered(self) -> None:
        schema = asyncio.run(get_filter_schema())

        listing = filter_catalog(schema).splitlines()
        assert len(listing) == len(schema)
        unit = filter_catalog(schema, "unit")
        assert "fromUnit" in unit
        assert "toUnit" in unit
