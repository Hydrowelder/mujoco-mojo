import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from reloaded_fakes import EventLog, FakeBackend, FakeSession, wait_idle

import mujoco_mojo.runtime as rt
from mujoco_mojo.utils.layers.reloaded.controller import (
    COMMAND_SUGGESTIONS,
    ExitEvent,
    HelpEvent,
    Outcome,
    ReloadedController,
    RunState,
    StatusEvent,
)


@pytest.fixture
def session() -> FakeSession:
    return FakeSession(seed=1)


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def log() -> EventLog:
    return EventLog()


@pytest.fixture
def controller(
    session: FakeSession, backend: FakeBackend, log: EventLog, tmp_path: Path
) -> Iterator[ReloadedController]:
    controller = ReloadedController(session, backend, watch_path=tmp_path, sink=log)
    controller.start()
    yield controller
    controller.shutdown()


def test_help_lists_the_float_command_only_with_a_runtime(
    controller: ReloadedController, session: FakeSession
) -> None:
    """A speed command makes no sense without a runtime function, so help leaves it out."""
    names = [name for name, _ in controller.help_entries()]
    assert "<float>" in names
    assert "run" in names

    session.runtime = None
    names = [name for name, _ in controller.help_entries()]
    assert "<float>" not in names
    assert "run" not in names


def test_seed_command_sets_and_clears_the_seed(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.submit("seed 7")
    assert session.seed == 7
    assert controller.status().seed == 7

    controller.submit("seed none")
    assert session.seed is None


def test_blank_seed_clears_it_so_a_field_can_submit_nothing(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.set_seed("")

    assert session.seed is None


def test_set_speed_changes_the_speed_without_running(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.set_speed("0.25")

    assert session.playback_speed == 0.25
    assert controller.status().playback_speed == 0.25
    assert session.calls == []


@pytest.mark.parametrize("text", ["fast", "-1", "nan", "inf", ""])
def test_set_speed_rejects_what_is_not_a_speed(
    controller: ReloadedController,
    session: FakeSession,
    log: EventLog,
    text: str,
) -> None:
    controller.set_speed(text)

    assert session.playback_speed == 1.0
    assert any("Invalid speed" in m for m in log.messages())


def test_zero_speed_is_allowed_and_means_unpaced(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.set_speed("0")

    assert session.playback_speed == 0.0


def test_typed_negative_speed_is_reported_as_invalid_not_unknown(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    controller.submit("-2")

    assert session.calls == []
    assert any("Invalid speed" in m for m in log.messages())


def test_settings_cannot_change_while_a_run_is_in_progress(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    release = threading.Event()
    session.generation_behavior = lambda s: release.wait(5)
    controller.submit("gen")
    assert session.started.wait(5)

    controller.set_seed("99")
    controller.set_trial("5")
    controller.set_speed("2")
    controller.toggle_record()
    controller.toggle_watch()

    assert (session.seed, session.trial_num, session.playback_speed) == (1, 0, 1.0)
    assert not session.record
    assert not session.watch
    assert sum("run is in progress" in m for m in log.messages()) == 5

    release.set()
    wait_idle(controller)


def test_invalid_seed_and_trial_leave_values_alone(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    controller.submit("seed abc")
    controller.submit("trial abc")

    assert session.seed == 1
    assert session.trial_num == 0
    assert any("Invalid seed" in m for m in log.messages())
    assert any("Invalid trial" in m for m in log.messages())


def test_trial_command_sets_the_trial_number(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.submit("trial 12")
    assert session.trial_num == 12


def test_record_command_toggles_recording(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.submit("record")
    assert session.record is True
    assert controller.status().record is True

    controller.submit("record")
    assert session.record is False


def test_watch_command_toggles_watching(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.submit("watch")
    assert session.watch is True
    assert controller.status().watch is True

    controller.submit("w")
    assert session.watch is False


def test_unknown_command_is_reported_and_does_not_run(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    controller.submit("frobnicate")

    assert session.calls == []
    assert any("Unknown command" in m for m in log.messages())


def test_unknown_command_text_is_not_read_as_markup(
    controller: ReloadedController, log: EventLog
) -> None:
    """Whatever the user typed is echoed back literally, even if it looks like rich markup."""
    controller.submit("[/bold]")

    assert any("Unknown command" in m and r"\[/bold]" in m for m in log.messages())


def test_float_sets_playback_speed_and_runs_the_runtime(
    controller: ReloadedController, session: FakeSession, backend: FakeBackend
) -> None:
    controller.submit("0.5")
    wait_idle(controller)

    assert session.playback_speed == 0.5
    assert session.calls == [True]
    # shown once when generated and once more after the run
    assert len(backend.reloads) == 2


def test_gen_generates_without_the_runtime(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.submit("gen")
    wait_idle(controller)

    assert session.calls == [False]
    assert controller.status().last_command == "gen"


def test_run_generates_and_runs_the_runtime_at_the_current_speed(
    controller: ReloadedController, session: FakeSession
) -> None:
    seen: list[float] = []
    session.behavior = lambda s: seen.append(s.playback_speed)
    controller.set_speed("0.5")

    controller.submit("run")
    wait_idle(controller)

    assert session.calls == [True]
    assert seen == [0.5]
    assert controller.status().last_command == "run"


def test_run_without_a_runtime_says_so_and_only_generates(
    session: FakeSession, backend: FakeBackend, log: EventLog, tmp_path: Path
) -> None:
    session.runtime = None
    controller = ReloadedController(session, backend, watch_path=tmp_path, sink=log)
    controller.start()

    assert not controller.has_runtime
    assert controller.status().last_command == "gen"

    controller.submit("run")
    wait_idle(controller)

    assert any("nothing to run" in m for m in log.messages())
    controller.shutdown()


def test_the_first_enter_runs_the_runtime_when_there_is_one(
    controller: ReloadedController, session: FakeSession
) -> None:
    assert controller.has_runtime
    assert controller.status().last_command == "run"

    controller.submit("")
    wait_idle(controller)

    assert session.calls == [True]


def test_gen_does_not_run_the_runtime(
    controller: ReloadedController, session: FakeSession
) -> None:
    ran: list[str] = []
    session.behavior = lambda s: ran.append("runtime")

    controller.submit("gen")
    wait_idle(controller)
    assert ran == []

    controller.submit("1.0")
    wait_idle(controller)
    assert ran == ["runtime"]


def test_repeating_gen_never_runs_the_runtime(
    controller: ReloadedController, session: FakeSession
) -> None:
    """ENTER, a file change, and the reload key all repeat the last command, so none of them may start the runtime once the last command was gen."""
    ran: list[str] = []
    session.behavior = lambda s: ran.append("runtime")
    controller.submit("gen")
    wait_idle(controller)

    controller.submit("")
    wait_idle(controller)
    controller.on_file_change(1)
    wait_idle(controller)

    assert session.calls == [False, False, False]
    assert ran == []


def test_a_speed_after_gen_runs_the_runtime_and_gen_goes_back_to_skipping_it(
    controller: ReloadedController, session: FakeSession
) -> None:
    ran: list[str] = []
    session.behavior = lambda s: ran.append("runtime")

    controller.submit("gen")
    wait_idle(controller)
    controller.submit("2")
    wait_idle(controller)
    controller.submit("")
    wait_idle(controller)
    assert ran == ["runtime", "runtime"]

    controller.submit("gen")
    wait_idle(controller)
    controller.submit("")
    wait_idle(controller)
    assert ran == ["runtime", "runtime"]


def test_empty_input_repeats_the_last_command(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.submit("gen")
    wait_idle(controller)
    controller.submit("")
    wait_idle(controller)

    assert session.calls == [False, False]


def test_finished_run_reports_outcome_and_duration(
    controller: ReloadedController,
) -> None:
    controller.submit("gen")
    wait_idle(controller)

    status = controller.status()
    assert status.state is RunState.IDLE
    assert status.last_outcome is Outcome.SUCCESS
    assert status.last_duration is not None


def test_stop_interrupts_a_run_in_progress(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    def wait_for_stop(s: FakeSession) -> None:
        assert s.stop_event.wait(5)
        raise rt.SimulationStopped

    session.behavior = wait_for_stop
    controller.submit("1.0")
    assert session.started.wait(5)
    assert controller.status().state is RunState.RUNNING

    controller.submit("stop")
    assert controller.status().state is RunState.STOPPING
    wait_idle(controller)

    assert controller.status().last_outcome is Outcome.STOPPED
    assert not session.stop_event.is_set()
    assert any("stopped by user" in m for m in log.messages())


def test_other_commands_are_refused_while_a_run_is_in_progress(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    release = threading.Event()
    session.generation_behavior = lambda s: release.wait(5)

    controller.submit("gen")
    assert session.started.wait(5)

    controller.submit("seed 99")
    assert session.seed == 1
    assert any("run is in progress" in m for m in log.messages())

    release.set()
    wait_idle(controller)


def test_stop_when_idle_says_nothing_is_running(
    controller: ReloadedController, log: EventLog
) -> None:
    controller.submit("stop")

    assert any("No run is currently in progress" in m for m in log.messages())
    assert controller.status().state is RunState.IDLE


def test_failed_run_is_reported_and_the_controller_stays_usable(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    def explode(s: FakeSession) -> None:
        raise ValueError("boom [bold]")

    session.generation_behavior = explode
    controller.submit("gen")
    wait_idle(controller)

    assert controller.status().last_outcome is Outcome.FAILED
    assert any("Reload Failed" in m and "boom" in m for m in log.messages())

    session.generation_behavior = None
    controller.submit("gen")
    wait_idle(controller)
    assert controller.status().last_outcome is Outcome.SUCCESS


@pytest.mark.parametrize(
    ("exception", "outcome"),
    [
        (rt.RequirementSatisfied("done"), Outcome.SATISFIED),
        (rt.RequirementTerminated("failed"), Outcome.TERMINATED),
    ],
)
def test_requirement_endings_have_their_own_outcome(
    controller: ReloadedController,
    session: FakeSession,
    exception: rt.SimulationStopped,
    outcome: Outcome,
) -> None:
    def end_early(s: FakeSession) -> None:
        raise exception

    session.behavior = end_early
    controller.submit("1.0")
    wait_idle(controller)

    assert controller.status().last_outcome is outcome


def test_file_change_reloads_with_the_last_command(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.submit("gen")
    wait_idle(controller)

    controller.on_file_change(2)
    wait_idle(controller)

    assert session.calls == [False, False]


def test_file_change_during_a_run_is_ignored(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    release = threading.Event()
    session.generation_behavior = lambda s: release.wait(5)
    controller.submit("gen")
    assert session.started.wait(5)

    controller.on_file_change(1)
    release.set()
    wait_idle(controller)

    assert session.calls == [False]
    assert any("a run is in progress - ignoring" in m for m in log.messages())


def test_session_messages_reach_the_sink_only_while_started(
    session: FakeSession, backend: FakeBackend, log: EventLog, tmp_path: Path
) -> None:
    controller = ReloadedController(session, backend, watch_path=tmp_path, sink=log)
    assert session.output_sink is None

    controller.start()
    assert session.output_sink is not None
    session.output_sink("hello from the session")
    assert "hello from the session" in log.messages()

    controller.shutdown()
    assert session.output_sink is None


def test_exit_and_help_are_events_for_the_ui_to_act_on(
    controller: ReloadedController, log: EventLog
) -> None:
    controller.submit("help")
    controller.submit("q")

    assert any(isinstance(e, HelpEvent) for e in log.events)
    assert any(isinstance(e, ExitEvent) for e in log.events)


def test_state_changes_are_reported_in_order(
    controller: ReloadedController, log: EventLog
) -> None:
    controller.submit("gen")
    wait_idle(controller)
    assert log.wait_for(
        lambda events: (
            [e.status.state for e in events if isinstance(e, StatusEvent)][-2:]
            == [RunState.RUNNING, RunState.IDLE]
        )
    )


def test_shutdown_stops_a_run_in_progress(
    session: FakeSession, backend: FakeBackend, log: EventLog, tmp_path: Path
) -> None:
    def wait_for_stop(s: FakeSession) -> None:
        assert s.stop_event.wait(5)
        raise rt.SimulationStopped

    session.behavior = wait_for_stop
    controller = ReloadedController(session, backend, watch_path=tmp_path, sink=log)
    controller.start()
    controller.submit("1.0")
    assert session.started.wait(5)

    controller.shutdown()

    assert controller.status().state is RunState.IDLE


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("gen", "Generates the model only."),
        ("run", "Generates, then runs at 1x."),
        ("0.5", "Sets speed to 0.5x, then runs."),
        ("2", "Sets speed to 2x, then runs."),
        ("0", "Sets speed to 0x, then runs."),
        ("-3", "Speed must be 0 or more."),
        ("seed 42", "Sets the seed to 42."),
        ("seed none", "Clears the seed."),
        ("seed abc", "Seed must be an integer or none."),
        ("seed", "Needs a number, or none."),
        ("trial 3", "Sets the trial to 3."),
        ("trial x", "Trial must be an integer."),
        ("trial", "Needs a number."),
        ("watch", "Turns auto reload on."),
        ("record", "Turns recording on."),
        ("dojo", "Prints the Dojo command."),
        ("stop", "Nothing is running to stop."),
        ("help", "Opens help."),
        ("exit", "Closes Reloaded."),
        ("se", "Press Tab to complete seed."),
        ("bogus", "Not a command. Try help."),
        ("[/bold]", "Not a command. Try help."),
        ("", "Repeats run at 1x."),
    ],
)
def test_describe_says_what_a_command_would_do(
    controller: ReloadedController, text: str, expected: str
) -> None:
    assert controller.describe(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "gen",
        "run",
        "0.5",
        "seed 12345",
        "seed abc",
        "trial 99",
        "watch",
        "se",
        "x",
        "explain",
        "explain gen",
        "gen?",
    ],
)
def test_describe_is_always_very_short(
    controller: ReloadedController, text: str
) -> None:
    sentence = controller.describe(text)

    assert len(sentence) <= 45
    assert "\n" not in sentence


def test_describe_uses_the_current_settings(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.set_speed("0.5")
    controller.toggle_record()
    controller.toggle_watch()

    assert controller.describe("run") == "Generates, then runs at 0.5x."
    assert controller.describe("") == "Repeats run at 0.5x."
    assert controller.describe("record") == "Turns recording off."
    assert controller.describe("watch") == "Turns auto reload off."


def test_describe_a_repeat_follows_the_last_command(
    controller: ReloadedController,
) -> None:
    controller.submit("gen")
    wait_idle(controller)

    assert controller.describe("") == "Repeats gen: generates only."


def test_describe_without_a_runtime_says_it_only_generates(
    controller: ReloadedController, session: FakeSession
) -> None:
    session.runtime = None

    assert controller.describe("run") == "No runtime given, so generates only."
    assert controller.describe("") == "Repeats run: generates only."
    assert controller.describe("2") == "Sets speed to 2x, then generates only."


def test_describe_while_a_run_is_in_progress(
    controller: ReloadedController, session: FakeSession
) -> None:
    release = threading.Event()
    session.generation_behavior = lambda s: release.wait(5)
    controller.submit("gen")
    assert session.started.wait(5)

    assert controller.describe("gen") == "A run is in progress. Only stop works."
    assert controller.describe("stop") == "Aborts the current run."

    release.set()
    wait_idle(controller)


def test_describe_has_no_side_effects(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    before = (
        session.seed,
        session.trial_num,
        session.playback_speed,
        session.record,
        session.watch,
    )
    events_before = len(log.events)

    for text in ("gen", "run", "seed 9", "trial 2", "5", "watch", "record", "exit", ""):
        controller.describe(text)

    assert (
        session.seed,
        session.trial_num,
        session.playback_speed,
        session.record,
        session.watch,
    ) == before
    assert session.calls == []
    assert len(log.events) == events_before


@pytest.mark.parametrize(
    "typed",
    ["explain seed 42", "EXPLAIN seed 42", "seed 42?", "seed 42 ?", "explain seed 42?"],
)
def test_explain_prints_the_sentence_and_changes_nothing(
    controller: ReloadedController,
    session: FakeSession,
    log: EventLog,
    typed: str,
) -> None:
    controller.submit(typed)

    assert any("seed 42" in m and "Sets the seed to 42." in m for m in log.messages())
    assert session.seed == 1
    assert session.calls == []
    assert controller.status().state is RunState.IDLE


def test_a_question_mark_explains_a_run_instead_of_starting_it(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    controller.submit("run?")
    controller.submit("gen?")

    assert session.calls == []
    assert any("Generates, then runs at 1x." in m for m in log.messages())
    assert any("Generates the model only." in m for m in log.messages())


def test_a_bare_explain_says_what_enter_does(
    controller: ReloadedController, log: EventLog
) -> None:
    controller.submit("explain")

    assert any("Enter" in m and "Repeats run at 1x." in m for m in log.messages())


def test_a_lone_question_mark_opens_help(
    controller: ReloadedController, log: EventLog
) -> None:
    controller.submit("?")

    assert any(isinstance(e, HelpEvent) for e in log.events)
    assert not any("Opens help." in m for m in log.messages())


def test_explaining_something_that_is_not_a_command_says_so(
    controller: ReloadedController, log: EventLog
) -> None:
    controller.submit("explain bogus")

    assert any("Not a command. Try help." in m for m in log.messages())


def test_explain_still_works_while_a_run_is_in_progress(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    release = threading.Event()
    session.generation_behavior = lambda s: release.wait(5)
    controller.submit("gen")
    assert session.started.wait(5)

    controller.submit("seed 42?")

    assert any("A run is in progress. Only stop works." in m for m in log.messages())
    assert session.seed == 1

    release.set()
    wait_idle(controller)


def test_the_hint_for_an_explain_is_what_enter_will_do(
    controller: ReloadedController, session: FakeSession
) -> None:
    assert controller.describe("explain seed 42") == "Prints what that would do."
    assert controller.describe("seed 42?") == "Prints what that would do."
    assert controller.describe("explain") == "Prints what Enter would do."
    assert controller.describe("?") == "Opens help."
    assert controller.describe("ex") == "Press Tab to complete exit."


def test_explain_is_offered_as_a_completion_and_listed_in_help(
    controller: ReloadedController,
) -> None:
    assert "explain " in COMMAND_SUGGESTIONS
    assert "explain <cmd>" in [name for name, _ in controller.help_entries()]
