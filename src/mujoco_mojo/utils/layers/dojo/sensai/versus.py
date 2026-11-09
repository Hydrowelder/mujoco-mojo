"""Checked changes to versus mode for SensAI. Every compared trial's data is loaded, so how many a message may add is capped."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence

from pydantic import BaseModel

from mujoco_mojo.utils.layers.dojo.plot_config import VersusState

from .job_report import trial_numbers

_MAX_NUMBERS_SHOWN = 20

# with no job to say which trials exist, a range is counted as every number in it, so it
# is only counted this far: anything wider is already more than a message may add
_UNKNOWN_SPAN = 10_000


class VersusChange(BaseModel):
    """A change's new state, how many trials it added, and how many pins it left out for want of room."""

    state: VersusState
    added: int = 0
    left_out: int = 0


class VersusError(ValueError):
    """A change that cannot be made, worded for the agent so it can correct itself."""


def compared_trials(state: VersusState, known: Collection[int] | None) -> set[int]:
    """The trial numbers the state compares, the range's and the pinned ones, limited to `known` (the job's trials) when given."""
    numbers: set[int] = set(state.vs_pinned)
    if state.vs_range is not None:
        low, high = state.vs_range
        numbers |= (
            {n for n in known if low <= n <= high}
            if known is not None
            else set(range(low, min(high, low + _UNKNOWN_SPAN) + 1))
        )
    return numbers if known is None else numbers & set(known)


def _non_negative(name: str, values: Iterable[int]) -> list[int]:
    numbers = list(values)
    if any(n < 0 for n in numbers):
        raise VersusError(f"{name} must be trial numbers from 0 up, not {numbers}.")
    return numbers


def change_versus(
    state: VersusState,
    *,
    room: int,
    known: Collection[int] | None = None,
    enabled: bool | None = None,
    trial_range: Sequence[int] | None = None,
    no_range: bool = False,
    pin: Iterable[int] = (),
    unpin: Iterable[int] = (),
    clear_pins: bool = False,
) -> VersusChange:
    """
    Applies a change to `state`: unpins and clears, sets the range, then adds pins lowest first while `room` trials remain.

    Pinning or setting a range turns versus mode on unless `enabled` says otherwise. A range that would add more than `room` is refused, since cutting it short picks a range nobody asked for; pins are cut short and the number left out is reported.
    """
    pins = _non_negative("pin", pin)
    unpins = _non_negative("unpin", unpin)
    if trial_range is not None:
        if len(trial_range) != 2:
            raise VersusError(
                f"trial_range must be two trial numbers, the first and the last, such as [3, 9], not {list(trial_range)}."
            )
        _non_negative("trial_range", trial_range)
        if no_range:
            raise VersusError("Send trial_range or no_range, not both.")
    if (
        enabled is None
        and trial_range is None
        and not (no_range or pins or unpins or clear_pins)
    ):
        raise VersusError(
            "Nothing to change: send enabled, trial_range, no_range, pin, unpin, failed_requirement or clear_pins."
        )
    if known is not None and (unknown := sorted(set(pins) - set(known))):
        span = f"{min(known)}-{max(known)}" if known else "none"
        raise VersusError(
            f"There is no trial {trial_numbers(unknown)} in this job. Its trials are {span}."
        )

    before = compared_trials(state, known)
    kept = set() if clear_pins else set(state.vs_pinned)
    kept -= set(unpins)
    if no_range:
        new_range = None
    elif trial_range is not None:
        new_range = (min(trial_range), max(trial_range))
    else:
        new_range = state.vs_range
    base = VersusState(
        vs_enabled=state.vs_enabled, vs_range=new_range, vs_pinned=list(kept)
    )
    counted = compared_trials(base, known)
    added = len(counted - before)
    if added > room:
        raise VersusError(
            f"That range would add {added} trials, and this message may add at most {room} more. Use a smaller range, and tell the user they can ask again for the rest or raise dojo.sensai.max_versus_trials in settings."
        )

    left_out = 0
    for n in sorted(set(pins) - kept):
        if n in counted:
            kept.add(n)
        elif added < room:
            kept.add(n)
            counted.add(n)
            added += 1
        else:
            left_out += 1

    turned_on = bool(trial_range is not None or pins)
    new_enabled = (
        enabled if enabled is not None else (True if turned_on else state.vs_enabled)
    )
    new_state = VersusState(
        vs_enabled=new_enabled, vs_range=new_range, vs_pinned=list(kept)
    )
    return VersusChange(state=new_state, added=added, left_out=left_out)


def describe_versus(state: VersusState, known: Collection[int] | None = None) -> str:
    """The state in words: on or off, its range and pins, and how many trials that compares."""
    if state.vs_range is None:
        selection = "no range"
    else:
        selection = f"range {state.vs_range[0]}-{state.vs_range[1]}"
    if state.vs_pinned:
        shown = trial_numbers(state.vs_pinned, _MAX_NUMBERS_SHOWN)
        pins = f"{len(state.vs_pinned)} pinned ({shown})"
    else:
        pins = "none pinned"
    count = len(compared_trials(state, known))
    plural = "trial" if count == 1 else "trials"
    return f"Versus mode is {'on' if state.vs_enabled else 'off'}: {selection}, {pins}, comparing {count} {plural}."
