"""Tests for SensAI's checked changes to versus mode (`sensai/versus.py`): which trials, the per-message cap, and the refusals."""

from collections.abc import Collection, Iterable, Sequence

import pytest

from mujoco_mojo.utils.layers.dojo.plot_config import VersusState
from mujoco_mojo.utils.layers.dojo.sensai.versus import (
    VersusChange,
    VersusError,
    change_versus,
    compared_trials,
    describe_versus,
)

OFF = VersusState(vs_enabled=False, vs_range=(0, 2), vs_pinned=[])
JOB = list(range(200))


def change(
    state: VersusState = OFF,
    *,
    room: int = 50,
    known: Collection[int] | None = JOB,
    enabled: bool | None = None,
    trial_range: Sequence[int] | None = None,
    no_range: bool = False,
    pin: Iterable[int] = (),
    unpin: Iterable[int] = (),
    clear_pins: bool = False,
) -> VersusChange:
    """A change with room for 50 trials and a 200-trial job, unless the test says otherwise."""
    return change_versus(
        state,
        room=room,
        known=known,
        enabled=enabled,
        trial_range=trial_range,
        no_range=no_range,
        pin=pin,
        unpin=unpin,
        clear_pins=clear_pins,
    )


class TestState:
    def test_a_range_is_put_in_order_and_pins_are_sorted_without_repeats(self) -> None:
        state = VersusState(vs_range=(9, 3), vs_pinned=[7, 2, 7])

        assert state.vs_range == (3, 9)
        assert state.vs_pinned == [2, 7]

    def test_no_range_is_kept(self) -> None:
        assert VersusState(vs_range=None).vs_range is None

    def test_the_browsers_lists_are_accepted(self) -> None:
        state = VersusState.model_validate(
            {"vsEnabled": True, "vsRange": [4, 1], "vsPinned": [3]}
        )

        assert state == VersusState(vs_enabled=True, vs_range=(1, 4), vs_pinned=[3])

    def test_it_is_sent_back_as_plain_json(self) -> None:
        assert VersusState(vs_range=None, vs_pinned=[1]).model_dump(mode="json") == {
            "vsEnabled": False,
            "vsRange": None,
            "vsPinned": [1],
        }


class TestComparedTrials:
    def test_the_range_and_the_pins_together(self) -> None:
        assert compared_trials(VersusState(vs_range=(1, 3), vs_pinned=[9]), JOB) == {
            1,
            2,
            3,
            9,
        }

    def test_a_trial_the_job_does_not_have_is_not_compared(self) -> None:
        assert compared_trials(VersusState(vs_range=(0, 500)), [0, 1, 2]) == {0, 1, 2}

    def test_with_no_job_the_range_is_every_number_in_it(self) -> None:
        assert compared_trials(VersusState(vs_range=(2, 4)), None) == {2, 3, 4}

    def test_a_huge_range_with_no_job_is_not_built_in_full(self) -> None:
        assert len(compared_trials(VersusState(vs_range=(0, 10**9)), None)) < 20_000


class TestChange:
    def test_pinning_turns_it_on(self) -> None:
        result = change(pin=[7, 5])

        assert result.state.vs_enabled
        assert result.state.vs_pinned == [5, 7]
        assert result.state.vs_range == OFF.vs_range

    def test_setting_a_range_turns_it_on_and_replaces_the_old_one(self) -> None:
        result = change(trial_range=[9, 4])

        assert result.state == VersusState(vs_enabled=True, vs_range=(4, 9))

    def test_it_can_be_turned_off_and_stays_set_up(self) -> None:
        on = VersusState(vs_enabled=True, vs_range=(0, 5), vs_pinned=[8])

        assert change(on, enabled=False).state == VersusState(
            vs_enabled=False, vs_range=(0, 5), vs_pinned=[8]
        )

    def test_enabled_false_wins_over_pinning(self) -> None:
        assert not change(pin=[3], enabled=False).state.vs_enabled

    def test_removing_or_clearing_pins_does_not_turn_it_on(self) -> None:
        pinned = VersusState(vs_enabled=False, vs_range=(0, 2), vs_pinned=[5, 6])

        assert not change(pinned, unpin=[5]).state.vs_enabled
        assert not change(pinned, clear_pins=True).state.vs_enabled

    def test_pins_add_to_the_ones_there(self) -> None:
        pinned = VersusState(vs_enabled=True, vs_range=(0, 2), vs_pinned=[5])

        assert change(pinned, pin=[9]).state.vs_pinned == [5, 9]

    def test_unpin_removes_only_those_and_clear_removes_all(self) -> None:
        pinned = VersusState(vs_enabled=True, vs_range=(0, 2), vs_pinned=[5, 6, 7])

        assert change(pinned, unpin=[6]).state.vs_pinned == [5, 7]
        assert change(pinned, clear_pins=True).state.vs_pinned == []

    def test_clear_then_pin_replaces_the_pins(self) -> None:
        pinned = VersusState(vs_enabled=True, vs_range=(0, 2), vs_pinned=[5, 6])

        assert change(pinned, clear_pins=True, pin=[9]).state.vs_pinned == [9]

    def test_no_range_leaves_only_the_pins(self) -> None:
        result = change(no_range=True, pin=[30, 31])

        assert result.state.vs_range is None
        assert compared_trials(result.state, JOB) == {30, 31}

    def test_an_unchanged_state_comes_back_equal(self) -> None:
        on = VersusState(vs_enabled=True, vs_range=(0, 2), vs_pinned=[5])

        assert change(on, pin=[5]).state == on


class TestTheCap:
    def test_pins_past_the_room_are_left_out_lowest_first_and_counted(self) -> None:
        result = change(pin=list(range(100, 160)), room=50)

        assert result.state.vs_pinned == list(range(100, 150))
        assert result.left_out == 10
        assert result.added == 50

    def test_a_trial_already_compared_costs_no_room(self) -> None:
        """Pins inside the range are free, so pinning the range's own trials never runs out."""
        result = change(pin=[0, 1, 2, 100], room=1)

        assert result.state.vs_pinned == [0, 1, 2, 100]
        assert result.left_out == 0
        assert result.added == 1

    def test_no_room_adds_nothing_and_leaves_every_pin_out(self) -> None:
        result = change(pin=[10, 11], room=0)

        assert result.state.vs_pinned == []
        assert result.left_out == 2

    def test_asking_again_adds_the_next_batch(self) -> None:
        """What the user does after being told some were left out."""
        wanted = list(range(100, 130))
        first = change(pin=wanted, room=20)
        second = change(first.state, pin=wanted, room=20)

        assert second.state.vs_pinned == wanted
        assert (first.left_out, second.left_out) == (10, 0)

    def test_a_range_that_adds_more_than_the_room_is_refused_not_cut_short(
        self,
    ) -> None:
        with pytest.raises(VersusError, match="at most 50"):
            change(trial_range=[0, 120], room=50)

    def test_only_trials_new_to_the_comparison_use_the_room(self) -> None:
        """Widening 0-2 to 0-40 adds 38 trials, not 41."""
        assert change(trial_range=[0, 40], room=38).added == 38
        with pytest.raises(VersusError):
            change(trial_range=[0, 40], room=37)

    def test_a_range_wider_than_the_job_counts_only_trials_it_has(self) -> None:
        assert change(trial_range=[0, 10_000], known=[0, 1, 2, 3], room=5).added == 1

    def test_a_huge_range_with_no_job_is_refused_by_the_cap(self) -> None:
        with pytest.raises(VersusError):
            change(trial_range=[0, 10**9], known=None, room=50)


class TestRefusals:
    def test_a_change_that_changes_nothing_is_refused_with_what_to_send(self) -> None:
        with pytest.raises(VersusError, match="Nothing to change"):
            change()

    def test_a_trial_the_job_does_not_have_is_refused_with_the_ones_it_has(
        self,
    ) -> None:
        with pytest.raises(VersusError, match=r"no trial 500.*0-199"):
            change(pin=[500])

    def test_with_no_job_any_trial_number_is_accepted(self) -> None:
        assert change(pin=[500], known=None).state.vs_pinned == [500]

    def test_a_range_is_two_numbers(self) -> None:
        with pytest.raises(VersusError, match="two trial numbers"):
            change(trial_range=[1, 2, 3])
        with pytest.raises(VersusError, match="two trial numbers"):
            change(trial_range=[4])

    def test_a_range_and_no_range_together_are_refused(self) -> None:
        with pytest.raises(VersusError, match="not both"):
            change(trial_range=[1, 2], no_range=True)

    def test_a_negative_trial_number_is_refused(self) -> None:
        with pytest.raises(VersusError, match="from 0 up"):
            change(pin=[-1])
        with pytest.raises(VersusError, match="from 0 up"):
            change(trial_range=[-3, 2])


class TestDescribe:
    def test_it_says_what_is_set_and_how_many_trials_that_compares(self) -> None:
        state = VersusState(vs_enabled=True, vs_range=(3, 9), vs_pinned=[12, 15])

        assert describe_versus(state, JOB) == (
            "Versus mode is on: range 3-9, 2 pinned (12, 15), comparing 9 trials."
        )

    def test_off_and_empty_are_plain(self) -> None:
        state = VersusState(vs_enabled=False, vs_range=None)

        assert describe_versus(state, JOB) == (
            "Versus mode is off: no range, none pinned, comparing 0 trials."
        )

    def test_one_trial_is_singular(self) -> None:
        assert "comparing 1 trial." in describe_versus(
            VersusState(vs_range=None, vs_pinned=[4]), JOB
        )

    def test_a_long_pin_list_is_cut_short(self) -> None:
        state = VersusState(vs_range=None, vs_pinned=list(range(0, 100, 2)))

        assert "and 30 more" in describe_versus(state, JOB)
