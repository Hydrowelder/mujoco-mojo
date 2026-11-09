import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import mujoco
import pytest

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.runtime import (
    RunControl,
    RunTarget,
    RuntimeManager,
    SimulationStopped,
    TargetKind,
)

HELD = 0.05
"""Long enough that a thread which should be blocked has certainly had time to get past a gate that is not holding it. A thread is only given this long once it has started, so a slow machine cannot make a check pass by never getting to run."""


@dataclass
class Waiter:
    """Calls `wait_while_paused` on its own thread, the way a run does inside `step`."""

    control: RunControl
    stop: threading.Event | None = None
    sim_time: float = 0.0
    steps: int = 0
    held: list[float] = field(default_factory=list)
    done: threading.Event = field(default_factory=threading.Event)
    started: threading.Event = field(default_factory=threading.Event)

    def start(self) -> "Waiter":
        threading.Thread(target=self._wait, daemon=True).start()
        return self

    def _wait(self) -> None:
        self.started.set()
        self.held.append(
            self.control.wait_while_paused(self.stop, self.sim_time, self.steps)
        )
        self.done.set()

    def blocked(self) -> bool:
        assert self.started.wait(5)
        return not self.done.wait(HELD)


def test_a_run_that_is_not_held_goes_straight_through() -> None:
    assert RunControl().wait_while_paused() == 0.0


def test_a_paused_run_is_held_until_it_is_resumed_and_reports_how_long() -> None:
    control = RunControl()
    control.pause()
    waiter = Waiter(control).start()

    assert waiter.blocked()
    control.resume()

    assert waiter.done.wait(5)
    assert waiter.held[0] >= HELD


def test_steps_let_exactly_that_many_through_and_then_hold_again() -> None:
    control = RunControl()
    control.pause()
    control.step(2)

    control.wait_while_paused()
    control.wait_while_paused()
    third = Waiter(control).start()

    assert third.blocked()
    control.resume()
    assert third.done.wait(5)


def test_a_step_on_a_running_run_holds_it_after_that_step() -> None:
    control = RunControl()
    assert not control.paused

    control.step()
    control.wait_while_paused()
    next_step = Waiter(control).start()

    assert control.paused
    assert next_step.blocked()
    control.resume()
    assert next_step.done.wait(5)


def test_resuming_forgets_steps_still_owed() -> None:
    control = RunControl()
    control.step(5)
    control.resume()
    control.pause()

    assert Waiter(control).start().blocked()


def test_a_stop_request_frees_a_held_run() -> None:
    control = RunControl()
    stop = threading.Event()
    control.pause()
    waiter = Waiter(control, stop).start()

    assert waiter.blocked()
    stop.set()

    assert waiter.done.wait(5)


def test_the_pump_is_called_while_held_and_not_otherwise() -> None:
    control = RunControl()
    pumps: list[int] = []
    control.pump = lambda: pumps.append(1)

    control.wait_while_paused()
    assert pumps == []

    control.pause()
    waiter = Waiter(control).start()
    assert waiter.blocked()
    # a held run keeps being pumped, not just once
    wait_until(lambda: len(pumps) >= 3)
    control.resume()
    assert waiter.done.wait(5)


def test_a_speed_is_taken_once() -> None:
    control = RunControl()
    assert control.take_speed() is None

    control.set_speed(2.0)
    control.set_speed(0.5)

    assert control.take_speed() == 0.5
    assert control.take_speed() is None


def test_reset_clears_every_request() -> None:
    control = RunControl()
    control.pause()
    control.step(3)
    control.set_speed(4.0)

    control.reset()

    assert not control.paused
    assert control.take_speed() is None
    assert control.wait_while_paused() == 0.0


@pytest.fixture
def state(mj_setup: tuple[mujoco.MjModel, mujoco.MjData]) -> MjState:
    model, data = mj_setup
    return MjState(model, data)


@dataclass
class Stepper:
    """Steps a `RuntimeManager` on its own thread, as the job thread does, counting the steps that complete."""

    manager: RuntimeManager
    state: MjState
    steps: int = 0
    error: BaseException | None = None
    _thread: threading.Thread | None = None

    def start(self, count: int = 1000) -> "Stepper":
        self._thread = threading.Thread(target=self._run, args=(count,), daemon=True)
        self._thread.start()
        return self

    def _run(self, count: int) -> None:
        try:
            for _ in range(count):
                self.manager.step(self.state)
                self.steps += 1
        except BaseException as e:
            self.error = e

    def settle(self) -> int:
        """Waits long enough for any step that can happen to have happened, then says how many have."""
        time.sleep(HELD)
        return self.steps

    def finish(self) -> None:
        assert self._thread is not None
        self._thread.join(5)
        assert not self._thread.is_alive()


def wait_until(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 5
    while not condition():
        assert time.monotonic() < deadline, "condition was not met in time"
        time.sleep(0.005)


def test_a_paused_run_stops_stepping_and_picks_up_where_it_left_off(
    state: MjState,
) -> None:
    control = RunControl()
    stop = threading.Event()
    manager = RuntimeManager(playback_speed=0, _run_control=control, _stop_event=stop)
    stepper = Stepper(manager, state).start(count=10_000_000)
    wait_until(lambda: stepper.steps > 5)

    control.pause()
    frozen = stepper.settle()
    time_when_frozen = state.data.time
    assert stepper.settle() == frozen
    assert state.data.time == time_when_frozen

    control.resume()
    wait_until(lambda: stepper.steps > frozen + 5)
    stop.set()
    stepper.finish()
    assert state.data.time > time_when_frozen


def test_steps_advance_a_paused_run_by_exactly_that_many(state: MjState) -> None:
    control = RunControl()
    manager = RuntimeManager(playback_speed=0, _run_control=control)
    control.pause()
    stepper = Stepper(manager, state).start(count=10)
    assert stepper.settle() == 0

    control.step(3)
    wait_until(lambda: stepper.steps == 3)
    assert stepper.settle() == 3

    control.resume()
    stepper.finish()
    assert stepper.steps == 10


def test_a_stop_request_ends_a_paused_run_with_simulation_stopped(
    state: MjState,
) -> None:
    control = RunControl()
    stop = threading.Event()
    manager = RuntimeManager(playback_speed=0, _run_control=control, _stop_event=stop)
    control.pause()
    stepper = Stepper(manager, state).start()
    assert stepper.settle() == 0

    stop.set()
    stepper.finish()

    assert isinstance(stepper.error, SimulationStopped)
    assert stepper.steps == 0


def test_time_spent_paused_is_not_made_up_for_afterward(state: MjState) -> None:
    control = RunControl()
    manager = RuntimeManager(playback_speed=1.0, _run_control=control)
    for _ in range(3):
        manager.step(state)
    anchor_before = manager._start_wall_time

    control.pause()
    stepper = Stepper(manager, state).start(count=1)
    assert stepper.settle() == 0
    control.resume()
    stepper.finish()

    # the anchor moved forward by about as long as the run was held
    assert manager._start_wall_time - anchor_before >= HELD


def test_a_speed_asked_for_during_a_run_applies_at_the_next_step(
    state: MjState,
) -> None:
    control = RunControl()
    manager = RuntimeManager(playback_speed=0, _run_control=control)
    manager.step(state)

    control.set_speed(8.0)
    manager.step(state)

    assert manager.playback_speed == 8.0
    assert control.take_speed() is None


def test_changing_the_speed_anchors_pacing_at_the_current_time(
    state: MjState,
) -> None:
    manager = RuntimeManager(playback_speed=0)
    for _ in range(5):
        manager.step(state)
    now = state.data.time
    before = time.time()

    manager.set_playback_speed(4.0)

    assert manager.playback_speed == 4.0
    assert manager._start_sim_time == now
    assert manager._start_wall_time >= before


def test_changing_the_speed_before_any_step_just_sets_it() -> None:
    manager = RuntimeManager(playback_speed=1.0)

    manager.set_playback_speed(2.5)

    assert manager.playback_speed == 2.5


# --- pausing by itself at a target ---


def test_a_target_is_a_reading_since_the_run_began() -> None:
    by_time = RunTarget(TargetKind.TIME, 2.5)
    by_step = RunTarget(TargetKind.STEP, 500)

    assert not by_time.reached(2.499, 9999)
    assert by_time.reached(2.5, 0)
    assert not by_step.reached(99.0, 499)
    assert by_step.reached(0.0, 500)
    assert (by_time.label, by_step.label) == ("time 2.5", "step 500")


def test_a_run_that_reaches_its_target_holds_itself_and_says_why() -> None:
    control = RunControl()
    reasons: list[str | None] = []
    control.on_hold = reasons.append
    control.run_until(RunTarget(TargetKind.STEP, 3))

    for steps in range(3):
        control.wait_while_paused(None, steps * 0.1, steps)
    assert reasons == []

    held = Waiter(control, sim_time=0.3, steps=3).start()

    assert held.blocked()
    assert reasons == ["reached step 3 (time 0.3, step 3)"]
    assert control.paused
    assert control.target is None
    control.resume()
    assert held.done.wait(5)


def test_a_target_pauses_the_run_once_and_is_then_forgotten() -> None:
    control = RunControl()
    control.run_until(RunTarget(TargetKind.TIME, 1.0))
    held = Waiter(control, sim_time=1.0, steps=10).start()
    assert held.blocked()
    control.resume()
    assert held.done.wait(5)

    # carrying on does not pause it again at the same place
    assert control.wait_while_paused(None, 1.1, 11) == 0.0
    assert control.wait_while_paused(None, 5.0, 50) == 0.0


def test_a_new_target_replaces_the_old_one_and_none_clears_it() -> None:
    control = RunControl()
    control.run_until(RunTarget(TargetKind.STEP, 5))
    control.run_until(RunTarget(TargetKind.STEP, 50))
    assert control.wait_while_paused(None, 0.0, 5) == 0.0

    control.run_until(None)
    assert control.target is None
    assert control.wait_while_paused(None, 0.0, 50) == 0.0


def test_the_run_control_knows_where_the_run_is_and_reset_forgets_it() -> None:
    control = RunControl()
    control.run_until(RunTarget(TargetKind.TIME, 9.0))

    control.wait_while_paused(None, 0.4, 20)
    assert control.position == (0.4, 20)

    control.reset()
    assert control.position == (0.0, 0)
    assert control.target is None


def test_a_step_target_stops_the_real_run_after_exactly_that_many_steps(
    state: MjState,
) -> None:
    control = RunControl()
    stop = threading.Event()
    manager = RuntimeManager(playback_speed=0, _run_control=control, _stop_event=stop)
    control.run_until(RunTarget(TargetKind.STEP, 7))
    stepper = Stepper(manager, state).start(count=10_000_000)

    wait_until(lambda: control.paused)

    assert stepper.settle() == 7
    assert control.position[1] == 7
    control.resume()
    wait_until(lambda: stepper.steps > 20)
    stop.set()
    stepper.finish()


def test_a_time_target_stops_the_real_run_at_the_first_step_at_or_past_it(
    state: MjState,
) -> None:
    control = RunControl()
    stop = threading.Event()
    manager = RuntimeManager(playback_speed=0, _run_control=control, _stop_event=stop)
    timestep = state.model.opt.timestep
    target = timestep * 4.5
    control.run_until(RunTarget(TargetKind.TIME, target))
    stepper = Stepper(manager, state).start(count=10_000_000)

    wait_until(lambda: control.paused)

    held_at = stepper.settle()
    assert held_at == 5
    assert state.data.time >= target
    assert state.data.time - timestep < target
    stop.set()
    stepper.finish()


# --- manual stepping (speed 0) ---


def test_a_run_started_at_speed_zero_is_held_at_every_step() -> None:
    control = RunControl()
    control.reset(0)
    assert control.manual

    held = Waiter(control).start()
    assert held.blocked()

    control.step()
    assert held.done.wait(5)
    assert Waiter(control).start().blocked()


def test_each_step_let_through_manual_mode_is_one_step() -> None:
    control = RunControl()
    control.reset(0)

    control.step(2)
    control.wait_while_paused()
    control.wait_while_paused()

    assert Waiter(control).start().blocked()


def test_resume_does_not_end_manual_stepping() -> None:
    control = RunControl()
    control.reset(0)
    control.resume()

    assert Waiter(control).start().blocked()


def test_asking_for_speed_zero_makes_a_going_run_step_manually() -> None:
    control = RunControl()
    assert control.wait_while_paused() == 0.0

    control.set_speed(0)

    assert control.manual
    assert Waiter(control).start().blocked()


def test_leaving_manual_stepping_leaves_the_run_paused_not_going() -> None:
    control = RunControl()
    control.reset(0)

    control.set_speed(2.0)

    assert not control.manual
    assert control.paused
    waiter = Waiter(control).start()
    assert waiter.blocked()
    control.resume()
    assert waiter.done.wait(5)


@pytest.mark.parametrize("speed", [None, 1.0, 0.5, float("inf")])
def test_a_run_started_at_any_other_speed_is_not_manual(speed: float | None) -> None:
    control = RunControl()
    control.reset(speed)

    assert not control.manual
    assert control.wait_while_paused() == 0.0


def test_reset_ends_manual_stepping() -> None:
    control = RunControl()
    control.reset(0)

    control.reset()

    assert not control.manual


def test_on_hold_hears_about_every_hold_and_only_a_target_gives_a_reason() -> None:
    control = RunControl()
    heard: list[str | None] = []
    control.on_hold = heard.append

    control.reset(0)
    control.step()
    control.wait_while_paused()
    held = Waiter(control).start()
    assert held.blocked()
    control.step()
    assert held.done.wait(5)

    # the first call was let through at once, so only the second one was held
    assert heard == [None]

    control.reset()
    control.run_until(RunTarget(TargetKind.STEP, 1))
    target_hold = Waiter(control, steps=1).start()
    assert target_hold.blocked()
    assert heard[-1] == "reached step 1 (time 0, step 1)"
    control.resume()
    assert target_hold.done.wait(5)


def test_a_manual_run_takes_one_real_step_per_request(state: MjState) -> None:
    control = RunControl()
    control.reset(0)
    stop = threading.Event()
    manager = RuntimeManager(playback_speed=0, _run_control=control, _stop_event=stop)
    stepper = Stepper(manager, state).start(count=10_000_000)
    assert stepper.settle() == 0

    control.step()
    wait_until(lambda: stepper.steps == 1)
    assert stepper.settle() == 1

    control.step(4)
    wait_until(lambda: stepper.steps == 5)
    assert stepper.settle() == 5
    stop.set()
    stepper.finish()


def test_without_a_run_control_speed_zero_still_means_unpaced(state: MjState) -> None:
    manager = RuntimeManager(playback_speed=0)

    started = time.time()
    for _ in range(50):
        manager.step(state)

    assert time.time() - started < 5
    assert state.data.time > 0


def test_infinite_speed_is_unpaced(state: MjState) -> None:
    manager = RuntimeManager(playback_speed=float("inf"))

    started = time.time()
    for _ in range(50):
        manager.step(state)

    assert time.time() - started < 5
