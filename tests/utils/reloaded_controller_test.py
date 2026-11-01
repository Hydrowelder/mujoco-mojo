import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from reloaded_fakes import (
    EventLog,
    FakeBackend,
    FakeSession,
    SteppingRuntime,
    wait_idle,
)

import mujoco_mojo.runtime as rt
from mujoco_mojo.utils.layers.reloaded.controller import (
    COMMAND_SUGGESTIONS,
    ExitEvent,
    HelpEvent,
    Outcome,
    ReloadedController,
    RunState,
    StatusEvent,
    speed_label,
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


def test_help_lists_run_only_with_a_runtime_and_no_bare_number_ever(
    controller: ReloadedController, session: FakeSession
) -> None:
    """Running makes no sense without a runtime function, so help leaves it out."""
    names = [name for name, _ in controller.help_entries()]
    assert "run / r / runtime [X]" in names
    assert "<float>" not in names

    session.runtime = None
    names = [name for name, _ in controller.help_entries()]
    assert "run / r / runtime [X]" not in names
    assert "<float>" not in names


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


@pytest.mark.parametrize("text", ["fast", "-1", "nan", "-inf", ""])
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


@pytest.mark.parametrize("text", ["speed -2", "run -2", "speed fast", "run fast"])
def test_a_bad_speed_is_reported_as_invalid_and_runs_nothing(
    controller: ReloadedController, session: FakeSession, log: EventLog, text: str
) -> None:
    controller.submit(text)

    assert session.calls == []
    assert session.playback_speed == 1.0
    assert any("Invalid speed" in m for m in log.messages())


@pytest.mark.parametrize("text", ["0.5", "2", "1.0", "-2"])
def test_a_bare_number_is_not_a_command(
    controller: ReloadedController, session: FakeSession, log: EventLog, text: str
) -> None:
    controller.submit(text)

    assert session.calls == []
    assert session.playback_speed == 1.0
    assert any("Unknown command" in m for m in log.messages())


def test_settings_cannot_change_while_a_run_is_in_progress(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    release = threading.Event()
    session.generation_behavior = lambda s: release.wait(5)
    controller.submit("gen")
    assert session.started.wait(5)

    controller.set_seed("99")
    controller.set_trial("5")
    controller.toggle_record()
    controller.toggle_watch()

    assert (session.seed, session.trial_num) == (1, 0)
    assert not session.record
    assert not session.watch
    assert sum("run is in progress" in m for m in log.messages()) == 4

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


@pytest.mark.parametrize("word", ["run", "r", "runtime", "RUN"])
def test_run_with_a_speed_sets_it_and_runs_the_runtime(
    controller: ReloadedController,
    session: FakeSession,
    backend: FakeBackend,
    word: str,
) -> None:
    controller.submit(f"{word} 0.5")
    wait_idle(controller)

    assert session.playback_speed == 0.5
    assert session.calls == [True]
    assert controller.status().last_command == "run"
    # shown once when generated and once more after the run
    assert len(backend.reloads) == 2


def test_enter_runs_again_at_the_speed_the_last_run_was_given(
    controller: ReloadedController, session: FakeSession
) -> None:
    seen: list[float] = []
    session.behavior = lambda s: seen.append(s.playback_speed)

    controller.submit("run 0.25")
    wait_idle(controller)
    controller.submit("")
    wait_idle(controller)

    assert seen == [0.25, 0.25]


def test_run_without_a_runtime_still_sets_the_speed_and_only_generates(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    session.runtime = None

    controller.submit("run 3")
    wait_idle(controller)

    assert session.playback_speed == 3.0
    assert any("No runtime was given" in m for m in log.messages())


def test_gen_generates_without_the_runtime(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.submit("gen")
    wait_idle(controller)

    assert session.calls == [False]
    assert controller.status().last_command == "gen"


@pytest.mark.parametrize("word", ["gen", "g", "generate", "G", " Generate "])
def test_every_word_for_generate_generates_without_the_runtime(
    controller: ReloadedController, session: FakeSession, word: str
) -> None:
    controller.submit(word)
    wait_idle(controller)

    assert session.calls == [False]
    assert controller.status().last_command == "gen"


@pytest.mark.parametrize("word", ["run", "r", "R"])
def test_every_word_for_run_runs_the_runtime(
    controller: ReloadedController, session: FakeSession, word: str
) -> None:
    controller.submit(word)
    wait_idle(controller)

    assert session.calls == [True]
    assert controller.status().last_command == "run"


@pytest.mark.parametrize(
    ("word", "command"),
    [
        ("w", "watch"),
        ("rec", "record"),
        ("h", "help"),
        ("?", "help"),
        ("q", "exit"),
        ("quit", "exit"),
    ],
)
def test_the_short_words_do_what_the_long_ones_do(
    controller: ReloadedController, log: EventLog, word: str, command: str
) -> None:
    assert controller.describe(word) == controller.describe(command)

    controller.submit(word)

    if command == "watch":
        assert controller.status().watch
    elif command == "record":
        assert controller.status().record
    elif command == "help":
        assert any(isinstance(event, HelpEvent) for event in log.events)
    else:
        assert any(isinstance(event, ExitEvent) for event in log.events)


@pytest.mark.parametrize("word", ["stop", "halt", "abort", "ABORT"])
def test_every_word_for_stop_interrupts_a_run_in_progress(
    controller: ReloadedController, session: FakeSession, word: str
) -> None:
    def wait_for_stop(s: FakeSession) -> None:
        assert s.stop_event.wait(5)
        raise rt.SimulationStopped

    session.behavior = wait_for_stop
    controller.submit("run")
    assert session.started.wait(5)
    assert controller.describe(word) == "Aborts the current run."

    controller.submit(word)
    wait_idle(controller)

    assert controller.status().last_outcome is Outcome.STOPPED


def test_an_alias_can_be_explained_like_the_command(
    controller: ReloadedController,
) -> None:
    assert controller.describe("g") == "Generates the model only."
    assert controller.describe("g?") == "Prints what that would do."
    assert controller.describe("explain generate") == "Prints what that would do."


def test_long_forms_are_offered_as_completions_after_the_short_ones() -> None:
    assert COMMAND_SUGGESTIONS.index("gen") < COMMAND_SUGGESTIONS.index("generate")
    assert COMMAND_SUGGESTIONS.index("exit") < COMMAND_SUGGESTIONS.index("quit")


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

    controller.submit("run 1.0")
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


def test_run_after_gen_runs_the_runtime_and_gen_goes_back_to_skipping_it(
    controller: ReloadedController, session: FakeSession
) -> None:
    ran: list[str] = []
    session.behavior = lambda s: ran.append("runtime")

    controller.submit("gen")
    wait_idle(controller)
    controller.submit("run 2")
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
    controller.submit("run")
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
    controller.submit("run")
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
    controller.submit("run")
    assert session.started.wait(5)

    controller.shutdown()

    assert controller.status().state is RunState.IDLE


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("gen", "Generates the model only."),
        ("run", "Generates, then runs at 1x."),
        ("run 0.5", "Generates, then runs at 0.5x."),
        ("r 2", "Generates, then runs at 2x."),
        ("runtime 0", "Generates, then steps on Enter."),
        ("run -3", "Speed must be 0 or more."),
        ("run fast", "Speed must be a number."),
        ("0.5", "Not a command. Try help."),
        ("-3", "Not a command. Try help."),
        ("seed 42", "Sets the seed to 42."),
        ("seed none", "Clears the seed."),
        ("seed abc", "Seed must be an integer or none."),
        ("seed", "Sets the seed, e.g. seed 42 or seed none."),
        ("trial 3", "Sets the trial to 3."),
        ("trial x", "Trial must be an integer."),
        ("trial", "Sets the trial number, e.g. trial 3."),
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
    assert controller.describe("run 2") == "No runtime given, so generates only."


def test_describe_while_a_run_is_in_progress(
    controller: ReloadedController, session: FakeSession
) -> None:
    release = threading.Event()
    session.generation_behavior = lambda s: release.wait(5)
    controller.submit("gen")
    assert session.started.wait(5)

    assert controller.describe("gen") == "A run is in progress. Try pause or stop."
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


@pytest.mark.parametrize(
    ("typed", "sentence"),
    [
        ("explain seed", "Sets the seed, e.g. seed 42 or seed none."),
        ("seed?", "Sets the seed, e.g. seed 42 or seed none."),
        ("explain trial", "Sets the trial number, e.g. trial 3."),
        ("trial?", "Sets the trial number, e.g. trial 3."),
    ],
)
def test_explaining_a_command_that_takes_a_number_does_not_need_the_number(
    controller: ReloadedController,
    session: FakeSession,
    log: EventLog,
    typed: str,
    sentence: str,
) -> None:
    controller.submit(typed)

    assert any(sentence in m for m in log.messages())
    assert session.seed == 1
    assert session.trial_num == 0


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

    assert any("A run is in progress. Try pause or stop." in m for m in log.messages())
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


# --- pause, resume, step, and live speed ---


def settled(runtime: SteppingRuntime) -> int:
    """How many steps the run has taken once it has had time to take any it was going to."""
    time.sleep(0.1)
    return runtime.steps


def wait_for_steps(runtime: SteppingRuntime, count: int) -> None:
    deadline = time.monotonic() + 5
    while runtime.steps < count:
        assert time.monotonic() < deadline, "the run did not take the steps in time"
        time.sleep(0.002)


@pytest.fixture
def stepping(
    controller: ReloadedController, session: FakeSession
) -> Iterator[SteppingRuntime]:
    """A run in progress that takes steps until it is told to stop."""
    runtime = SteppingRuntime()
    session.behavior = runtime
    controller.submit("run")
    assert session.started.wait(5)
    wait_for_steps(runtime, 3)
    yield runtime
    controller.submit("stop")
    wait_idle(controller)


def test_pause_holds_a_run_and_run_lets_it_carry_on(
    controller: ReloadedController, stepping: SteppingRuntime
) -> None:
    controller.submit("pause")

    assert controller.status().state is RunState.PAUSED
    frozen = settled(stepping)
    assert settled(stepping) == frozen

    controller.submit("run")

    assert controller.status().state is RunState.RUNNING
    wait_for_steps(stepping, frozen + 3)


def test_step_advances_a_paused_run_by_that_many_and_keeps_it_paused(
    controller: ReloadedController, stepping: SteppingRuntime
) -> None:
    controller.submit("pause")
    frozen = settled(stepping)

    controller.submit("step 3")
    wait_for_steps(stepping, frozen + 3)
    assert settled(stepping) == frozen + 3

    controller.submit("step")
    wait_for_steps(stepping, frozen + 4)
    assert settled(stepping) == frozen + 4
    assert controller.status().state is RunState.PAUSED


def test_step_on_a_run_that_is_going_pauses_it(
    controller: ReloadedController, stepping: SteppingRuntime
) -> None:
    controller.submit("step")

    assert controller.status().state is RunState.PAUSED
    frozen = settled(stepping)
    assert settled(stepping) == frozen


@pytest.mark.parametrize("arg", ["x", "0", "-2", "1.5"])
def test_a_step_count_that_is_not_a_whole_number_is_refused(
    controller: ReloadedController,
    stepping: SteppingRuntime,
    log: EventLog,
    arg: str,
) -> None:
    controller.submit("pause")
    frozen = settled(stepping)

    controller.submit(f"step {arg}")

    assert any("Invalid step count" in m for m in log.messages())
    assert settled(stepping) == frozen


def test_stop_ends_a_paused_run(
    controller: ReloadedController, stepping: SteppingRuntime, log: EventLog
) -> None:
    controller.submit("pause")
    settled(stepping)

    controller.submit("stop")
    wait_idle(controller)

    assert controller.status().last_outcome is Outcome.STOPPED
    assert any("stopped by user" in m for m in log.messages())


def test_the_next_run_starts_going_even_if_the_last_ended_paused(
    controller: ReloadedController, session: FakeSession
) -> None:
    first = SteppingRuntime()
    session.behavior = first
    controller.submit("run")
    assert session.started.wait(5)
    controller.submit("pause")
    controller.submit("stop")
    wait_idle(controller)

    second = SteppingRuntime()
    session.behavior = second
    session.started.clear()
    controller.submit("run")
    assert session.started.wait(5)

    assert controller.status().state is RunState.RUNNING
    wait_for_steps(second, 3)
    controller.submit("stop")
    wait_idle(controller)


def test_the_pause_key_pauses_a_run_and_resumes_a_paused_one(
    controller: ReloadedController, stepping: SteppingRuntime
) -> None:
    controller.toggle_pause()
    assert controller.status().state is RunState.PAUSED

    controller.toggle_pause()
    assert controller.status().state is RunState.RUNNING


@pytest.mark.parametrize("word", ["run", "r", "runtime", "RUN"])
def test_every_word_for_run_carries_a_paused_run_on(
    controller: ReloadedController, stepping: SteppingRuntime, word: str
) -> None:
    controller.submit("p")
    assert controller.status().state is RunState.PAUSED

    controller.submit(word)

    assert controller.status().state is RunState.RUNNING


def test_run_with_a_speed_carries_a_paused_run_on_at_that_speed(
    controller: ReloadedController, session: FakeSession, stepping: SteppingRuntime
) -> None:
    controller.submit("pause")

    controller.submit("run 2")

    assert controller.status().state is RunState.RUNNING
    assert session.playback_speed == 2.0
    assert session.run_control.take_speed() == 2.0
    assert session.calls == [True]


@pytest.mark.parametrize("word", ["resume", "continue", "c"])
def test_resume_is_not_a_command_because_run_does_that(
    controller: ReloadedController, log: EventLog, word: str
) -> None:
    controller.submit(word)

    assert any("Unknown command" in m for m in log.messages())


def test_speed_can_change_during_a_run_and_the_run_is_told(
    controller: ReloadedController,
    session: FakeSession,
    stepping: SteppingRuntime,
    log: EventLog,
) -> None:
    controller.submit("speed 2")

    assert session.playback_speed == 2.0
    assert session.run_control.take_speed() == 2.0
    assert controller.status().state is RunState.RUNNING
    assert any("Playback speed set to 2x" in m for m in log.messages())

    controller.submit("run 4")

    assert session.playback_speed == 4.0
    assert session.run_control.take_speed() == 4.0
    assert controller.status().state is RunState.RUNNING
    assert session.calls == [True]


def test_a_bare_number_during_a_run_changes_nothing(
    controller: ReloadedController,
    session: FakeSession,
    stepping: SteppingRuntime,
    log: EventLog,
) -> None:
    controller.submit("0.5")

    assert session.playback_speed == 1.0
    assert session.run_control.take_speed() is None
    assert any("run is in progress" in m for m in log.messages())


def test_a_bad_speed_during_a_run_is_refused_and_changes_nothing(
    controller: ReloadedController,
    session: FakeSession,
    stepping: SteppingRuntime,
    log: EventLog,
) -> None:
    controller.submit("speed fast")
    controller.submit("speed -1")

    assert session.playback_speed == 1.0
    assert session.run_control.take_speed() is None
    assert sum("Invalid speed" in m for m in log.messages()) == 2


def test_speed_while_idle_sets_it_for_the_next_run_without_starting_one(
    controller: ReloadedController, session: FakeSession
) -> None:
    controller.submit("speed 3")

    assert session.playback_speed == 3.0
    assert session.run_control.take_speed() is None
    assert session.calls == []
    assert controller.status().state is RunState.IDLE


@pytest.mark.parametrize(
    ("command", "said"),
    [
        ("pause", "Nothing is running to pause."),
        ("step", "Nothing is running to step."),
        ("step 4", "Nothing is running to step."),
    ],
)
def test_the_run_commands_say_so_when_nothing_is_running(
    controller: ReloadedController,
    session: FakeSession,
    log: EventLog,
    command: str,
    said: str,
) -> None:
    controller.submit(command)

    assert any(said in m for m in log.messages())
    assert controller.status().state is RunState.IDLE
    assert session.calls == []


def test_pausing_a_paused_run_and_running_one_that_is_going_say_so(
    controller: ReloadedController, stepping: SteppingRuntime, log: EventLog
) -> None:
    controller.submit("run")
    controller.submit("pause")
    controller.submit("pause")

    messages = log.messages()
    assert any("The run is already going." in m for m in messages)
    assert any("Already paused." in m for m in messages)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pause", "Pauses the run."),
        ("run", "The run is already going."),
        ("run 2", "Sets speed to 2x for this run."),
        ("run fast", "Speed must be a number."),
        ("step", "Pauses, then advances 1 step."),
        ("step 5", "Pauses, then advances 5 steps."),
        ("step x", "Step takes a whole number, 1 or more."),
        ("speed", "Sets the speed, e.g. speed 0.5 for half."),
        ("speed 2", "Sets speed to 2x for this run."),
        ("0.5", "A run is in progress. Try pause or stop."),
        ("speed fast", "Speed must be a number."),
        ("speed -1", "Speed must be 0 or more."),
        ("gen", "A run is in progress. Try pause or stop."),
    ],
)
def test_describe_while_a_run_is_going(
    controller: ReloadedController,
    stepping: SteppingRuntime,
    text: str,
    expected: str,
) -> None:
    assert controller.describe(text) == expected
    assert len(controller.describe(text)) <= 45


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pause", "Already paused."),
        ("run", "Resumes the run."),
        ("run 2", "Resumes at 2x."),
        ("run fast", "Speed must be a number."),
        ("step", "Advances 1 step."),
        ("step 3", "Advances 3 steps."),
        ("gen", "Paused. Try run, step, or stop."),
    ],
)
def test_describe_while_a_run_is_paused(
    controller: ReloadedController,
    stepping: SteppingRuntime,
    text: str,
    expected: str,
) -> None:
    controller.submit("pause")

    assert controller.describe(text) == expected
    assert len(controller.describe(text)) <= 45


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pause", "Nothing is running to pause."),
        ("step", "Nothing is running to step."),
        ("run", "Generates, then runs at 1x."),
        ("run 0.5", "Generates, then runs at 0.5x."),
        ("speed", "Sets the speed, e.g. speed 0.5 for half."),
        ("speed 2", "Sets speed to 2x for the next run."),
        ("speed fast", "Speed must be a number."),
    ],
)
def test_describe_when_idle(
    controller: ReloadedController, text: str, expected: str
) -> None:
    assert controller.describe(text) == expected


def test_help_lists_the_run_controls_only_with_a_runtime(
    controller: ReloadedController, session: FakeSession
) -> None:
    entries = ("pause / p", "step [N]", "speed <X>")
    names = [name for name, _ in controller.help_entries()]
    for entry in entries:
        assert entry in names
    assert not any("resume" in name for name in names)

    session.runtime = None
    names = [name for name, _ in controller.help_entries()]
    for entry in entries:
        assert entry not in names


def test_the_new_commands_are_offered_as_completions() -> None:
    for word in ("pause", "step ", "speed ", "runtime"):
        assert word in COMMAND_SUGGESTIONS
    assert "resume" not in COMMAND_SUGGESTIONS


@pytest.mark.parametrize(
    "text",
    ["gen now", "stop please", "exit now", "help me", "dojo x", "seeds 5"],
)
def test_extra_words_after_a_command_that_takes_none_are_not_that_command(
    controller: ReloadedController, text: str
) -> None:
    assert controller.describe(text) == "Not a command. Try help."


# --- run until ---


def wait_for_state(controller: ReloadedController, state: RunState) -> None:
    deadline = time.monotonic() + 5
    while controller.status().state is not state:
        assert time.monotonic() < deadline, f"never became {state.value}"
        time.sleep(0.005)


def test_run_until_step_pauses_the_run_by_itself_and_says_where(
    controller: ReloadedController,
    session: FakeSession,
    log: EventLog,
) -> None:
    runtime = SteppingRuntime()
    session.behavior = runtime

    controller.submit("run until step 10")
    wait_for_state(controller, RunState.PAUSED)

    assert settled(runtime) == 10
    assert any(
        "Paused" in m and "reached step 10" in m and "step 10" in m
        for m in log.messages()
    )

    controller.submit("run")
    wait_for_steps(runtime, 25)
    assert controller.status().state is RunState.RUNNING
    controller.submit("stop")
    wait_idle(controller)


def test_run_until_time_pauses_at_the_first_step_at_or_past_it(
    controller: ReloadedController, session: FakeSession
) -> None:
    runtime = SteppingRuntime(step_time=0.01)
    session.behavior = runtime

    controller.submit("run until time 0.205")
    wait_for_state(controller, RunState.PAUSED)

    assert settled(runtime) == 21
    controller.submit("stop")
    wait_idle(controller)


def test_run_can_set_the_speed_and_the_target_together(
    controller: ReloadedController, session: FakeSession
) -> None:
    runtime = SteppingRuntime()
    session.behavior = runtime

    controller.submit("r 4 until step 6")
    wait_for_state(controller, RunState.PAUSED)

    assert session.playback_speed == 4.0
    assert settled(runtime) == 6
    controller.submit("stop")
    wait_idle(controller)


def test_a_target_on_a_run_that_is_going_pauses_it_later(
    controller: ReloadedController, stepping: SteppingRuntime, session: FakeSession
) -> None:
    ahead = stepping.steps + 40

    controller.submit(f"run until step {ahead}")
    wait_for_state(controller, RunState.PAUSED)

    assert settled(stepping) == ahead
    assert session.calls == [True]


def test_a_target_on_a_paused_run_carries_it_on_to_that_point(
    controller: ReloadedController, stepping: SteppingRuntime
) -> None:
    controller.submit("pause")
    held = settled(stepping)

    controller.submit(f"run until step {held + 15}")

    wait_for_steps(stepping, held + 15)
    wait_for_state(controller, RunState.PAUSED)
    assert settled(stepping) == held + 15


@pytest.mark.parametrize("state", ["running", "paused"])
def test_a_target_already_passed_is_refused_and_changes_nothing(
    controller: ReloadedController,
    stepping: SteppingRuntime,
    session: FakeSession,
    log: EventLog,
    state: str,
) -> None:
    if state == "paused":
        controller.submit("pause")
        settled(stepping)

    controller.submit("run until step 1")

    assert any("Already at or past step 1" in m for m in log.messages())
    assert session.run_control.target is None
    assert controller.status().state is (
        RunState.PAUSED if state == "paused" else RunState.RUNNING
    )


@pytest.mark.parametrize(
    "text",
    [
        "run until",
        "run until time",
        "run until step",
        "run until time x",
        "run until step 1.5",
        "run until step -1",
        "run until time -1",
        "run until foo 3",
        "run until time 3 now",
        "run 2 until",
        "run until time inf",
    ],
)
def test_an_incomplete_or_bad_target_is_reported_and_runs_nothing(
    controller: ReloadedController, session: FakeSession, log: EventLog, text: str
) -> None:
    controller.submit(text)

    assert any("Invalid target" in m for m in log.messages())
    assert session.calls == []
    assert session.playback_speed == 1.0


def test_a_bad_speed_before_a_target_is_reported_as_a_bad_speed(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    controller.submit("run fast until step 5")

    assert any("Invalid speed" in m for m in log.messages())
    assert session.calls == []


def test_the_target_belongs_to_one_run(
    controller: ReloadedController, session: FakeSession
) -> None:
    first = SteppingRuntime()
    session.behavior = first
    controller.submit("run until step 5")
    wait_for_state(controller, RunState.PAUSED)
    controller.submit("stop")
    wait_idle(controller)

    second = SteppingRuntime()
    session.behavior = second
    session.started.clear()
    controller.submit("run")
    assert session.started.wait(5)
    wait_for_steps(second, 30)

    assert controller.status().state is RunState.RUNNING
    controller.submit("stop")
    wait_idle(controller)


@pytest.mark.parametrize("word", ["step", "steps"])
def test_steps_may_be_written_either_way(
    controller: ReloadedController, session: FakeSession, word: str
) -> None:
    runtime = SteppingRuntime()
    session.behavior = runtime

    controller.submit(f"run until {word} 4")
    wait_for_state(controller, RunState.PAUSED)

    assert settled(runtime) == 4
    controller.submit("stop")
    wait_idle(controller)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("run until time 2.5", "Runs at 1x, pauses at time 2.5."),
        ("run 0.5 until step 500", "Runs at 0.5x, pauses at step 500."),
        ("r until step 10", "Runs at 1x, pauses at step 10."),
        ("run until", "Use: run until time N or step N."),
        ("run until time x", "Use: run until time N or step N."),
        ("run fast until step 5", "Speed must be a number."),
    ],
)
def test_describe_a_run_with_a_target_when_idle(
    controller: ReloadedController, text: str, expected: str
) -> None:
    assert controller.describe(text) == expected
    assert len(controller.describe(text)) <= 45


def test_describe_a_run_with_no_runtime_ignores_the_target(
    controller: ReloadedController, session: FakeSession
) -> None:
    session.runtime = None

    assert (
        controller.describe("run until step 5")
        == "No runtime given, so generates only."
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("run until step 100000", "Pauses when the run reaches step 100000."),
        ("run 2 until step 100000", "Sets speed to 2x, pauses at step 100000."),
        ("run until step 1", "Already at or past step 1."),
        ("run until step x", "Use: run until time N or step N."),
    ],
)
def test_describe_a_target_during_a_run(
    controller: ReloadedController,
    stepping: SteppingRuntime,
    text: str,
    expected: str,
) -> None:
    assert controller.describe(text) == expected
    assert len(controller.describe(text)) <= 45


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("run until step 100000", "Resumes, pausing at step 100000."),
        ("run 2 until step 100000", "Resumes at 2x, pauses at step 100000."),
    ],
)
def test_describe_a_target_on_a_paused_run(
    controller: ReloadedController,
    stepping: SteppingRuntime,
    text: str,
    expected: str,
) -> None:
    controller.submit("pause")
    settled(stepping)

    assert controller.describe(text) == expected
    assert len(controller.describe(text)) <= 45


def test_help_and_completion_know_about_run_until(
    controller: ReloadedController,
) -> None:
    names = [name for name, _ in controller.help_entries()]

    assert "run [X] until time <N>" in names
    assert "run [X] until step <N>" in names
    assert "run until time " in COMMAND_SUGGESTIONS
    assert "run until step " in COMMAND_SUGGESTIONS


# --- manual stepping, inf, and Enter ---


@pytest.mark.parametrize(
    ("speed", "label"),
    [(0.0, "manual"), (1.0, "1x"), (0.5, "0.5x"), (2.0, "2x"), (float("inf"), "inf")],
)
def test_a_speed_is_written_the_way_the_status_bar_shows_it(
    speed: float, label: str
) -> None:
    assert speed_label(speed) == label


@pytest.mark.parametrize("text", ["inf", "INF", "infinity"])
def test_infinite_speed_means_as_fast_as_possible(
    controller: ReloadedController,
    session: FakeSession,
    log: EventLog,
    text: str,
) -> None:
    controller.submit(f"speed {text}")

    assert session.playback_speed == float("inf")
    assert controller.status().playback_speed == float("inf")
    assert any("inf: as fast as possible" in m for m in log.messages())


def test_speed_zero_is_announced_as_stepping_by_hand(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    controller.submit("speed 0")

    assert session.playback_speed == 0.0
    assert any("steps only when you press Enter" in m for m in log.messages())
    assert session.calls == []


@pytest.fixture
def manual(
    controller: ReloadedController, session: FakeSession
) -> Iterator[SteppingRuntime]:
    """A run started at speed 0, held before its first step."""
    runtime = SteppingRuntime()
    session.behavior = runtime
    controller.submit("speed 0")
    controller.submit("run")
    assert session.started.wait(5)
    wait_for_state(controller, RunState.PAUSED)
    yield runtime
    controller.submit("stop")
    wait_idle(controller)


def test_a_run_at_speed_zero_waits_for_enter_at_every_step(
    controller: ReloadedController, manual: SteppingRuntime, log: EventLog
) -> None:
    assert settled(manual) == 0
    assert any("steps only when you press Enter" in m for m in log.messages())

    for expected in (1, 2, 3):
        controller.submit("")
        wait_for_steps(manual, expected)
        assert settled(manual) == expected
        assert controller.status().state is RunState.PAUSED


def test_step_with_a_count_works_in_manual_mode_too(
    controller: ReloadedController, manual: SteppingRuntime
) -> None:
    controller.submit("step 4")

    wait_for_steps(manual, 4)
    assert settled(manual) == 4


def test_run_alone_does_not_let_a_manual_run_go_and_says_why(
    controller: ReloadedController, manual: SteppingRuntime, log: EventLog
) -> None:
    before = sum("steps only when you press Enter" in m for m in log.messages())

    controller.submit("run")

    assert controller.status().state is RunState.PAUSED
    assert settled(manual) == 0
    after = sum("steps only when you press Enter" in m for m in log.messages())
    assert after == before + 1


def test_run_with_a_speed_lets_a_manual_run_go(
    controller: ReloadedController, manual: SteppingRuntime, session: FakeSession
) -> None:
    controller.submit("run 1")

    assert controller.status().state is RunState.RUNNING
    assert session.playback_speed == 1.0
    wait_for_steps(manual, 5)


def test_changing_the_speed_of_a_manual_run_leaves_it_paused_until_run(
    controller: ReloadedController, manual: SteppingRuntime
) -> None:
    controller.submit("speed 2")

    assert controller.status().state is RunState.PAUSED
    assert settled(manual) == 0

    controller.submit("run")

    assert controller.status().state is RunState.RUNNING
    wait_for_steps(manual, 5)


def test_speed_zero_during_a_run_makes_it_wait_for_enter(
    controller: ReloadedController, stepping: SteppingRuntime
) -> None:
    controller.submit("speed 0")

    wait_for_state(controller, RunState.PAUSED)
    held = settled(stepping)
    assert settled(stepping) == held

    controller.submit("")
    wait_for_steps(stepping, held + 1)
    assert settled(stepping) == held + 1


def test_enter_steps_a_run_that_was_paused_the_usual_way(
    controller: ReloadedController, stepping: SteppingRuntime
) -> None:
    controller.submit("pause")
    held = settled(stepping)

    controller.submit("")

    wait_for_steps(stepping, held + 1)
    assert settled(stepping) == held + 1
    assert controller.status().state is RunState.PAUSED


def test_enter_while_a_run_is_going_only_reminds_you_what_you_can_do(
    controller: ReloadedController,
    stepping: SteppingRuntime,
    session: FakeSession,
    log: EventLog,
) -> None:
    controller.submit("")

    assert controller.status().state is RunState.RUNNING
    assert any("run is in progress" in m for m in log.messages())
    assert session.calls == [True]


def test_pausing_tells_you_how_to_end_the_run(
    controller: ReloadedController, stepping: SteppingRuntime, log: EventLog
) -> None:
    controller.submit("pause")

    message = next(m for m in log.messages() if m.startswith("[dim]Paused."))
    assert "stop" in message
    assert "run" in message
    assert "Enter" in message


def test_a_run_that_pauses_at_its_target_tells_you_how_to_end_it(
    controller: ReloadedController, session: FakeSession, log: EventLog
) -> None:
    runtime = SteppingRuntime()
    session.behavior = runtime

    controller.submit("run until step 3")
    wait_for_state(controller, RunState.PAUSED)

    message = next(m for m in log.messages() if "Paused:" in m)
    assert "reached step 3" in message
    assert "stop" in message
    controller.submit("stop")
    wait_idle(controller)


def test_stop_ends_a_run_paused_by_hand_by_target_or_by_manual_stepping(
    controller: ReloadedController, manual: SteppingRuntime
) -> None:
    controller.submit("stop")
    wait_idle(controller)

    assert controller.status().last_outcome is Outcome.STOPPED


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("speed 0", "Steps only on Enter for the next run."),
        ("speed inf", "Sets speed to inf for the next run."),
        ("run 0", "Generates, then steps on Enter."),
        ("run inf", "Generates, then runs at inf."),
        ("run 0 until step 5", "Generates, then steps on Enter."),
    ],
)
def test_describe_the_special_speeds(
    controller: ReloadedController, text: str, expected: str
) -> None:
    assert controller.describe(text) == expected


def test_describe_enter_when_the_last_run_was_manual(
    controller: ReloadedController, session: FakeSession
) -> None:
    session.playback_speed = 0.0

    assert controller.describe("") == "Repeats run: steps on Enter."


def test_describe_enter_and_run_during_manual_stepping(
    controller: ReloadedController, manual: SteppingRuntime
) -> None:
    assert controller.describe("") == "Advances 1 step."
    assert controller.describe("run") == "Speed is 0, so it steps only on Enter."
    assert controller.describe("run 0") == "Steps only on Enter for this run."
    assert controller.describe("run 2") == "Resumes at 2x."


def test_describe_enter_while_going_and_paused(
    controller: ReloadedController, stepping: SteppingRuntime
) -> None:
    assert controller.describe("") == "A run is in progress. Try pause or stop."

    controller.submit("pause")
    settled(stepping)

    assert controller.describe("") == "Advances 1 step."
