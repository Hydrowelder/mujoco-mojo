import asyncio
import io
import logging
import sys
import threading
import time
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import pytest
from reloaded_fakes import FakeBackend, FakeSession
from rich.logging import RichHandler
from rich.text import Text
from textual.binding import Binding
from textual.pilot import Pilot
from textual.widgets import Header, RichLog, Static

from mujoco_mojo.utils.layers.reloaded.backends.base import ConnectionInfo
from mujoco_mojo.utils.layers.reloaded.controller import (
    ControllerStatus,
    Outcome,
    ReloadedController,
    RunState,
)
from mujoco_mojo.utils.layers.reloaded.tui import (
    CommandInput,
    ExplainButton,
    HelpScreen,
    LOG_BACKLOG,
    LogBuffer,
    ReloadedApp,
    TuiLogHandler,
    key_label,
    render_connection,
    ParamField,
    fit_title,
    render_badge,
    render_log_item,
    render_markup,
    run_summary,
    status_fields,
)


def run(scenario: Coroutine[Any, Any, None], timeout: float = 30.0) -> None:
    """Runs an async scenario to completion. Plain `asyncio` keeps `pytest-asyncio` out of the dev dependencies."""
    asyncio.run(asyncio.wait_for(scenario, timeout))


def make_app(
    tmp_path: Path,
    session: FakeSession | None = None,
    backend: FakeBackend | None = None,
    *,
    explain: bool = True,
) -> tuple[ReloadedApp, FakeSession]:
    session = session if session is not None else FakeSession()
    backend = backend if backend is not None else FakeBackend()
    controller = ReloadedController(session, backend, watch_path=tmp_path)
    return ReloadedApp(controller, backend, subtitle="test", explain=explain), session


def log_text(app: ReloadedApp) -> str:
    return "\n".join(line.text for line in app.query_one("#log", RichLog).lines)


async def wait_until(
    pilot: Pilot[None], predicate: Callable[[], bool], timeout: float = 5.0
) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise TimeoutError("condition was not met in time")
        await pilot.pause(0.02)


def status(**overrides: Any) -> ControllerStatus:
    fields: dict[str, Any] = {
        "state": RunState.IDLE,
        "last_command": "run",
        "seed": None,
        "trial_num": 0,
        "playback_speed": 1.0,
        "watch": False,
        "record": False,
        "last_duration": None,
        "last_outcome": None,
    }
    fields.update(overrides)
    return ControllerStatus(**fields)


def field_values(**overrides: Any) -> dict[str, str]:
    return {f.key: f.value for f in status_fields(status(**overrides))}


def test_status_fields_show_the_session() -> None:
    values = field_values(seed=42, trial_num=3, playback_speed=0.5, watch=True)

    assert values == {
        "seed": "42",
        "trial": "3",
        "speed": "0.5x",
        "watch": "on",
        "record": "off",
        "last": "run",
    }


def test_no_seed_reads_as_none_and_starts_the_editor_empty() -> None:
    seed = next(f for f in status_fields(status()) if f.key == "seed")

    assert seed.value == "none"
    assert seed.raw == ""


def test_last_run_summary_waits_for_the_first_run() -> None:
    assert run_summary(status()) is None

    summary = run_summary(status(last_duration=1.5, last_outcome=Outcome.FAILED))

    assert summary is not None
    assert summary.plain.strip() == "last run 1.50s failed"


def test_last_run_is_shown_on_the_log_border(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            log = app.query_one("#log", RichLog)
            assert log.border_subtitle is None

            await pilot.press(*"gen", "enter")
            await wait_until(pilot, lambda: log.border_subtitle is not None)

            assert "last run" in str(log.border_subtitle)
            assert "success" in str(log.border_subtitle)

    run(scenario())


def test_badge_names_the_state() -> None:
    assert render_badge(RunState.RUNNING).plain == " RUNNING "


def test_key_labels_are_readable() -> None:
    assert key_label("f1") == "F1"
    assert key_label("ctrl+q") == "Ctrl+Q"
    assert key_label("escape") == "Escape"


def test_malformed_markup_is_shown_literally() -> None:
    """An array repr like `[1, 2]` inside a message must not raise or vanish."""
    assert render_markup("bad [/nope] markup").plain == "bad [/nope] markup"
    assert render_markup("[bold]ok[/bold]").plain == "ok"


def test_connection_panel_text_includes_every_part() -> None:
    text = render_connection(
        ConnectionInfo(
            url="http://localhost:8000/",
            tunnel_command="ssh -L 8000:localhost:8000 me@box",
            warning="No authentication.",
        )
    ).plain

    assert "http://localhost:8000/" in text
    assert "ssh -L 8000:localhost:8000 me@box" in text
    assert "No authentication." in text


def test_typed_command_runs_and_is_echoed(tmp_path: Path) -> None:
    app, session = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press(*"gen", "enter")
            await wait_until(pilot, lambda: "Model Reloaded" in log_text(app))

            assert session.calls == [False]
            assert "> gen" in log_text(app)
            assert app.query_one(CommandInput).value == ""

    run(scenario())


def test_function_keys_drive_the_controller(tmp_path: Path) -> None:
    app, session = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press("f2")
            await wait_until(pilot, lambda: session.calls == [False])
            await wait_until(pilot, lambda: "Model Reloaded" in log_text(app))

            await pilot.press("f7")
            await wait_until(pilot, lambda: session.record is True)

    run(scenario())


@pytest.mark.parametrize("key", ["f9", "f1"])
def test_help_screen_opens_and_closes(tmp_path: Path, key: str) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press(key)
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)

            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, HelpScreen)

    run(scenario())


def test_help_command_opens_the_help_screen(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press(*"help", "enter")
            await wait_until(pilot, lambda: isinstance(app.screen, HelpScreen))

    run(scenario())


def test_up_and_down_walk_through_history(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press(*"seed 5", "enter")
            await pilot.press(*"trial 2", "enter")
            command = app.query_one(CommandInput)

            await pilot.press("up")
            assert command.value == "trial 2"
            await pilot.press("up")
            assert command.value == "seed 5"
            await pilot.press("down")
            assert command.value == "trial 2"
            await pilot.press("down")
            assert command.value == ""

    run(scenario())


def test_connection_panel_is_shown_only_for_browser_viewers(tmp_path: Path) -> None:
    info = ConnectionInfo(url="http://localhost:8000/", warning="Open to the network.")

    async def shown() -> None:
        app, _ = make_app(tmp_path, backend=FakeBackend(info))
        async with app.run_test():
            panel = app.query_one("#connection", Static)
            assert panel.display
            assert "http://localhost:8000/" in str(panel.render())

    async def hidden() -> None:
        app, _ = make_app(tmp_path)
        async with app.run_test():
            assert not app.query_one("#connection", Static).display

    run(shown())
    run(hidden())


def test_log_records_go_to_the_pane_and_the_terminal_handler_comes_back(
    tmp_path: Path,
) -> None:
    root = logging.getLogger()
    terminal = RichHandler()
    root.addHandler(terminal)
    before = list(root.handlers)
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            assert terminal not in root.handlers

            logging.getLogger("reloaded_tui_test").warning("heads up")
            await wait_until(pilot, lambda: "heads up" in log_text(app))
            assert "WARNING" in log_text(app)

    try:
        run(scenario())
        assert root.handlers == before
    finally:
        root.removeHandler(terminal)


def test_exit_command_closes_the_app_and_stops_the_run(tmp_path: Path) -> None:
    app, session = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press(*"exit", "enter")
            await wait_until(pilot, lambda: app.return_code is not None)

    run(scenario())
    assert app.return_code == 0
    assert session.output_sink is None


def test_print_output_lands_in_the_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # a headless Textual app also echoes captured prints to the real stdout, which would leak into the test report
    monkeypatch.setattr(sys, "__stdout__", io.StringIO())
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            print("printed by user code")
            await wait_until(pilot, lambda: "printed by user code" in log_text(app))

    run(scenario())


def test_clicking_a_value_edits_it_in_place(tmp_path: Path) -> None:
    app, session = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.click("#field-seed")
            assert app.query_one("#field-seed", ParamField).has_class("-editing")

            await pilot.press(*"42", "enter")
            await wait_until(pilot, lambda: session.seed == 42)

            assert not app.query_one("#field-seed", ParamField).has_class("-editing")
            assert app.focused is app.query_one(CommandInput)

    run(scenario())


def test_escape_abandons_an_edit_without_stopping_anything(tmp_path: Path) -> None:
    app, session = make_app(tmp_path, FakeSession(seed=7))

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.click("#field-seed")
            await pilot.press(*"99", "escape")
            await pilot.pause()

            assert session.seed == 7
            assert not app.query_one("#field-seed", ParamField).has_class("-editing")
            assert "No run is currently in progress" not in log_text(app)

    run(scenario())


def test_every_editable_value_reaches_the_controller(tmp_path: Path) -> None:
    app, session = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.click("#field-trial")
            await pilot.press(*"12", "enter")
            await wait_until(pilot, lambda: session.trial_num == 12)

            await pilot.click("#field-speed")
            await pilot.press(*"0.5", "enter")
            await wait_until(pilot, lambda: session.playback_speed == 0.5)

            assert session.calls == []

    run(scenario())


def test_an_invalid_edit_is_reported_in_the_log(tmp_path: Path) -> None:
    app, session = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.click("#field-seed")
            await pilot.press(*"abc", "enter")
            await wait_until(pilot, lambda: "Invalid seed" in log_text(app))

            assert session.seed is None

    run(scenario())


def test_clicking_a_toggle_flips_it(tmp_path: Path) -> None:
    app, session = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.click("#field-record")
            await wait_until(pilot, lambda: session.record is True)

            await pilot.click("#field-record")
            await wait_until(pilot, lambda: session.record is False)

    run(scenario())


def test_information_fields_are_not_clickable(tmp_path: Path) -> None:
    app, session = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.click("#field-last")
            await pilot.pause()

            assert session.calls == []
            assert not app.query_one("#field-last", ParamField).has_class("-editing")

    run(scenario())


def test_tab_completes_the_command_instead_of_leaving_the_box(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            command = app.query_one(CommandInput)
            await pilot.press("r", "e")
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()

            assert command.value == "record"
            assert app.focused is command

    run(scenario())


def test_tab_with_nothing_to_complete_keeps_focus(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press("z", "q", "tab")
            await pilot.pause()

            assert app.focused is app.query_one(CommandInput)
            assert app.query_one(CommandInput).value == "zq"

    run(scenario())


def test_f10_quits(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press("f10")
            await wait_until(pilot, lambda: app.return_code is not None)

    run(scenario())
    assert app.return_code == 0


def test_the_panels_are_titled(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test():
            assert app.query_one("#log", RichLog).border_title == "Log"
            assert app.query_one("#command-box").border_title == "Command"

    run(scenario())


def test_enter_after_gen_repeats_gen_and_does_not_run_the_runtime(
    tmp_path: Path,
) -> None:
    ran: list[str] = []
    app, session = make_app(tmp_path, FakeSession(behavior=lambda s: ran.append("x")))

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press("f2")
            await wait_until(pilot, lambda: session.calls == [False])
            await wait_until(pilot, lambda: "Model Reloaded" in log_text(app))

            await pilot.press("enter")
            await wait_until(pilot, lambda: session.calls == [False, False])
            await pilot.pause(0.1)

            assert ran == []

    run(scenario())


def test_run_key_generates_and_runs_the_runtime(tmp_path: Path) -> None:
    ran: list[str] = []
    app, session = make_app(tmp_path, FakeSession(behavior=lambda s: ran.append("x")))

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press("f3")
            await wait_until(pilot, lambda: session.calls == [True])
            await wait_until(pilot, lambda: ran == ["x"])

    run(scenario())


def test_run_uses_the_speed_set_in_the_bar(tmp_path: Path) -> None:
    seen: list[float] = []
    app, session = make_app(
        tmp_path, FakeSession(behavior=lambda s: seen.append(s.playback_speed))
    )

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.click("#field-speed")
            await pilot.press(*"0.25", "enter")
            await wait_until(pilot, lambda: session.playback_speed == 0.25)

            await pilot.press("f3")
            await wait_until(pilot, lambda: seen == [0.25])

    run(scenario())


def test_run_is_greyed_out_when_there_is_no_runtime(tmp_path: Path) -> None:
    with_runtime, _ = make_app(tmp_path, FakeSession(runtime="sim.runtime"))
    without_runtime, _ = make_app(tmp_path, FakeSession(runtime=None))

    assert with_runtime.check_action("submit", ("run",)) is True
    assert without_runtime.check_action("submit", ("run",)) is None
    assert without_runtime.check_action("submit", ("gen",)) is True


def test_with_the_hint_off_the_input_says_what_enter_will_repeat(
    tmp_path: Path,
) -> None:
    app, _ = make_app(tmp_path, explain=False)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            command = app.query_one(CommandInput)
            await wait_until(pilot, lambda: "'run'" in command.placeholder)

            await pilot.press(*"gen", "enter")
            await wait_until(pilot, lambda: "'gen'" in command.placeholder)

    run(scenario())


def test_title_shares_the_status_row_so_there_is_no_header(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test(size=(140, 30)) as pilot:
            title = app.query_one("#title", Static)
            await wait_until(
                pilot, lambda: "MuJoCo Mojo Reloaded" in str(title.render())
            )

            assert not app.query(Header)
            assert title.region.y == app.query_one("#badge").region.y

    run(scenario())


def test_title_gives_way_before_it_is_cut_in_half(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test(size=(70, 24)) as pilot:
            await pilot.pause(0.2)

            assert str(app.query_one("#title", Static).render()).strip() == ""

    run(scenario())


def test_fit_title_prefers_the_full_title_then_the_name_then_nothing() -> None:
    assert (
        fit_title("MuJoCo Mojo Reloaded", "studio | mojo-models", 60).plain
        == "MuJoCo Mojo Reloaded  studio | mojo-models"
    )
    assert (
        fit_title("MuJoCo Mojo Reloaded", "studio | mojo-models", 25).plain
        == "MuJoCo Mojo Reloaded"
    )
    assert fit_title("MuJoCo Mojo Reloaded", "studio | mojo-models", 10).plain == ""
    assert fit_title("MuJoCo Mojo Reloaded", "", 25).plain == "MuJoCo Mojo Reloaded"


def hint_text(app: ReloadedApp) -> str:
    return str(app.query_one("#hint", Static).render())


def test_the_hint_starts_on_and_says_what_enter_does(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            hint = app.query_one("#hint", Static)
            await wait_until(pilot, lambda: "Repeats run at 1x." in hint_text(app))

            assert hint.display
            assert app.query_one(ExplainButton).has_class("-open")

    run(scenario())


def test_the_hint_can_start_off(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, explain=False)

    async def scenario() -> None:
        async with app.run_test():
            assert not app.query_one("#hint", Static).display
            assert not app.query_one(ExplainButton).has_class("-open")

    run(scenario())


def test_the_hint_follows_the_draft_as_it_is_typed(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press(*"seed 42")
            await wait_until(pilot, lambda: "Sets the seed to 42." in hint_text(app))

            await pilot.press(*["backspace"] * len("seed 42"))
            await pilot.press(*"trial 3")
            await wait_until(pilot, lambda: "Sets the trial to 3." in hint_text(app))

    run(scenario())


def test_the_hint_sits_on_the_typing_line_at_the_right_end_of_the_box(
    tmp_path: Path,
) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test(size=(100, 24)) as pilot:
            await pilot.press(*"gen")
            await wait_until(
                pilot, lambda: "Generates the model only." in hint_text(app)
            )

            box = app.query_one("#command-box")
            command = app.query_one(CommandInput)
            hint = app.query_one("#hint", Static)

            assert hint.region.y == command.region.y
            assert hint.region.x > command.region.x
            # right justified: flush with the inside edge of the box, past its padding
            assert box.region.right - hint.region.right <= 2
            assert box.region.contains_region(hint.region)

    run(scenario())


def test_the_hint_is_cut_short_rather_than_wrapped_on_a_narrow_terminal(
    tmp_path: Path,
) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test(size=(50, 24)) as pilot:
            await pilot.press(*"seed abc")
            await wait_until(pilot, lambda: "Seed must" in hint_text(app))

            assert app.query_one("#hint", Static).region.height == 1

    run(scenario())


def test_the_button_and_f8_both_toggle_the_hint_without_taking_focus(
    tmp_path: Path,
) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            hint = app.query_one("#hint", Static)
            assert hint.display

            await pilot.click("#explain-button")
            await pilot.pause()
            assert not hint.display
            assert not app.query_one(ExplainButton).has_class("-open")
            assert app.focused is app.query_one(CommandInput)

            await pilot.press("f8")
            await pilot.pause()
            assert hint.display

            await pilot.press("f8")
            await pilot.pause()
            assert not hint.display

            await pilot.click("#explain-button")
            await pilot.pause()
            assert hint.display
            assert app.query_one(ExplainButton).has_class("-open")

    run(scenario())


def test_the_hint_follows_the_session_not_just_the_draft(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await wait_until(pilot, lambda: "Repeats run at 1x." in hint_text(app))

            await pilot.press("f2")
            await wait_until(pilot, lambda: "Repeats gen" in hint_text(app))

    run(scenario())


def test_the_placeholder_defers_to_the_hint_while_it_shows(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            command = app.query_one(CommandInput)
            await wait_until(
                pilot, lambda: command.placeholder == CommandInput.PLACEHOLDER
            )

            await pilot.press("f8")
            await wait_until(pilot, lambda: "repeat 'run'" in command.placeholder)

            await pilot.press("f8")
            await wait_until(
                pilot, lambda: command.placeholder == CommandInput.PLACEHOLDER
            )

    run(scenario())


def test_explaining_a_draft_does_not_run_it(tmp_path: Path) -> None:
    app, session = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press(*"gen")
            await wait_until(
                pilot, lambda: "Generates the model only." in hint_text(app)
            )
            await pilot.pause(0.1)

            assert session.calls == []

    run(scenario())


@pytest.mark.parametrize("typed", ["explain seed 42", "seed 42?"])
def test_explain_and_a_trailing_question_mark_print_the_sentence_in_the_log(
    tmp_path: Path, typed: str
) -> None:
    app, session = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press(*typed, "enter")
            await wait_until(pilot, lambda: "Sets the seed to 42." in log_text(app))

            assert session.seed is None
            assert session.calls == []
            assert f"> {typed}" in log_text(app)

    run(scenario())


def test_the_hint_says_a_question_prints_rather_than_runs(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press(*"gen?")
            await wait_until(
                pilot, lambda: "Prints what that would do." in hint_text(app)
            )

    run(scenario())


def test_ctrl_c_names_the_key_that_really_quits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _ = make_app(tmp_path)
    said: list[str] = []
    monkeypatch.setattr(app, "notify", lambda message, **kwargs: said.append(message))

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press("ctrl+c")
            await pilot.pause()

    run(scenario())

    assert said
    assert "F10" in said[0]
    assert "exit" in said[0]
    assert "Ctrl+Q" not in said[0]


def test_the_visible_keys_avoid_the_ones_an_editor_terminal_keeps(
    tmp_path: Path,
) -> None:
    """VS Code runs F1 (command palette), F5 and F10 (debugging), F6, F11 (full screen), Ctrl+P and Ctrl+Q itself, before a terminal program sees them. F10 stays only because it matters just during a VS Code debug session."""
    app, _ = make_app(tmp_path)
    taken = {"f1", "f5", "f6", "f11", "ctrl+p", "ctrl+q"}

    shown = [
        binding.key
        for binding in app.BINDINGS
        if isinstance(binding, Binding) and binding.show
    ]

    assert shown
    assert not taken & set(shown)


def test_the_log_buffer_hands_items_over_in_order_and_in_small_batches() -> None:
    buffer = LogBuffer(capacity=10)
    for i in range(5):
        buffer.put(Text(str(i)))

    items, dropped = buffer.take(3)

    assert [render_log_item(item).plain for item in items] == ["0", "1", "2"]
    assert dropped == 0
    assert len(buffer) == 2


def test_a_full_log_buffer_drops_the_oldest_and_counts_them() -> None:
    buffer = LogBuffer(capacity=3)
    for i in range(7):
        buffer.put(Text(str(i)))

    items, dropped = buffer.take(10)

    assert [render_log_item(item).plain for item in items] == ["4", "5", "6"]
    assert dropped == 4
    assert buffer.take(10) == ([], 0)


def test_the_log_buffer_can_be_filled_from_many_threads_at_once() -> None:
    buffer = LogBuffer(capacity=100_000)

    def fill() -> None:
        for _ in range(5000):
            buffer.put(Text("x"))

    threads = [threading.Thread(target=fill) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(buffer) == 40_000


def test_the_log_handler_only_stores_the_record_and_formats_it_later() -> None:
    """The thread that logs, which may be the physics thread, must not pay for formatting."""
    formatted: list[int] = []

    class Counted:
        def __str__(self) -> str:
            formatted.append(1)
            return "late"

    buffer = LogBuffer()
    handler = TuiLogHandler(buffer)
    record = logging.LogRecord(
        "demo", logging.INFO, __file__, 1, "value %s", (Counted(),), None
    )

    handler.emit(record)
    assert formatted == []

    items, _ = buffer.take(1)
    assert render_log_item(items[0]).plain.endswith("value late")
    assert formatted == [1]


def test_a_record_that_cannot_be_formatted_does_not_break_the_pane() -> None:
    record = logging.LogRecord(
        "demo", logging.INFO, __file__, 1, "needs %s and %s", ("one",), None
    )

    assert "could not be shown" in render_log_item(record).plain


def test_lines_from_the_runtime_and_from_the_controller_keep_their_order(
    tmp_path: Path,
) -> None:
    session = FakeSession(
        generation_behavior=lambda s: logging.getLogger("order").warning(
            "logged during generation"
        )
    )
    app, _ = make_app(tmp_path, session)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press(*"gen", "enter")
            await wait_until(pilot, lambda: "Model Reloaded" in log_text(app))

            text = log_text(app)
            assert (
                text.index("> gen")
                < text.index("Processing...")
                < text.index("logged during generation")
                < text.index("Model Reloaded")
            )

    run(scenario())


def test_a_flood_of_log_lines_is_skipped_with_a_notice(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)
    extra = 3000

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.pause(0.2)
            flood = logging.getLogger("flood")
            # no awaits in the loop, so the flush timer cannot run until the buffer has overflowed
            for i in range(LOG_BACKLOG + extra):
                flood.warning("line %d", i)

            await wait_until(
                pilot, lambda: f"{extra} log lines were skipped" in log_text(app)
            )
            assert len(app.query_one("#log", RichLog).lines) <= 10_000

    run(scenario())


def test_the_app_still_answers_keys_while_something_floods_the_log(
    tmp_path: Path,
) -> None:
    app, _ = make_app(tmp_path)
    stop = threading.Event()

    def flood() -> None:
        # about 20,000 lines a second, twice what froze the app before the log was buffered
        noisy = logging.getLogger("noisy")
        while not stop.is_set():
            for _ in range(200):
                noisy.warning("a line from a busy runtime")
            stop.wait(0.01)

    thread = threading.Thread(target=flood)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            thread.start()
            try:
                await pilot.pause(0.3)
                # keys are sent without waiting for an idle screen, which a flood never allows, just as a terminal sends them
                for key in "hello":
                    app.simulate_key(key)
                await wait_until(
                    pilot, lambda: app.query_one(CommandInput).value == "hello", 2.0
                )
            finally:
                stop.set()
                thread.join()

    run(scenario())
