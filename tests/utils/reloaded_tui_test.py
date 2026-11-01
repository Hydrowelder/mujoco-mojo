import asyncio
import io
import logging
import sys
import threading
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from reloaded_fakes import FakeBackend, FakeSession
from rich.console import Console
from rich.logging import RichHandler
from rich.text import Text
from textual.pilot import Pilot
from textual.widgets import Header, RichLog, Static

from mujoco_mojo.settings import ReloadedKeySettings
from mujoco_mojo.utils.layers.reloaded.backends.base import ConnectionInfo
from mujoco_mojo.utils.layers.reloaded.controller import (
    COMMAND_SUGGESTIONS,
    ControllerStatus,
    Outcome,
    ReloadedController,
    RunState,
)
from mujoco_mojo.utils.layers.reloaded.rain import RainScreen
from mujoco_mojo.utils.layers.reloaded.tui import (
    CommandInput,
    CommandSuggester,
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
    keys: ReloadedKeySettings | None = None,
    rain_seconds: float = 0.0,
) -> tuple[ReloadedApp, FakeSession]:
    session = session if session is not None else FakeSession()
    backend = backend if backend is not None else FakeBackend()
    controller = ReloadedController(session, backend, watch_path=tmp_path)
    app = ReloadedApp(
        controller,
        backend,
        keys=keys,
        subtitle="test",
        explain=explain,
        rain_seconds=rain_seconds,
    )
    return app, session


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


def test_run_is_greyed_out_when_there_is_no_runtime(tmp_path: Path) -> None:
    with_runtime, _ = make_app(tmp_path, FakeSession(runtime="sim.runtime"))
    without_runtime, _ = make_app(tmp_path, FakeSession(runtime=None))

    assert with_runtime.check_action("submit", ("run",)) is True
    assert without_runtime.check_action("submit", ("run",)) is None
    assert without_runtime.check_action("submit", ("gen",)) is True


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


def test_the_visible_keys_avoid_the_ones_an_editor_terminal_keeps(
    tmp_path: Path,
) -> None:
    """VS Code runs F1 (command palette), F5 and F10 (debugging), F6, F11 (full screen), Ctrl+P and Ctrl+Q itself, before a terminal program sees them. F10 stays only because it matters just during a VS Code debug session."""
    app, _ = make_app(tmp_path)
    taken = {"f1", "f5", "f6", "f11", "ctrl+p", "ctrl+q"}

    shown = [binding.key for binding in app.shortcuts if binding.show]

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

    @dataclass
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


def test_the_ctrl_c_message_names_the_key_that_really_quits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _ = make_app(tmp_path)
    said: list[str] = []
    monkeypatch.setattr(app, "notify", lambda message, **kwargs: said.append(message))

    app.action_help_quit()

    assert "F10" in said[0]
    assert "exit" in said[0]
    assert "Ctrl+Q" not in said[0]


def test_the_default_keys_are_the_ones_the_footer_has_always_shown(
    tmp_path: Path,
) -> None:
    app, _ = make_app(tmp_path)

    assert [(b.key, b.show) for b in app.shortcuts] == [
        ("f2", True),
        ("f3", True),
        ("f4", True),
        ("f7", True),
        ("f8", True),
        ("f9", True),
        ("f1", False),
        ("escape", True),
        ("f10", True),
        ("ctrl+q", False),
    ]
    assert {b.key: b.key_display for b in app.shortcuts}["escape"] == "Esc"


def test_a_key_from_settings_runs_its_command_and_the_old_key_stops_working(
    tmp_path: Path,
) -> None:
    app, session = make_app(
        tmp_path, keys=ReloadedKeySettings(generate=["f12"], run=["ctrl+g"])
    )

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press("f2")
            await pilot.pause(0.1)
            assert session.calls == []

            await pilot.press("f12")
            await wait_until(pilot, lambda: session.calls == [False])
            await wait_until(
                pilot, lambda: app._controller.status().state is RunState.IDLE
            )

            await pilot.press("ctrl+g")
            await wait_until(pilot, lambda: session.calls == [False, True])

    run(scenario())


def test_the_help_lists_every_key_of_an_action_and_the_same_key_closes_it(
    tmp_path: Path,
) -> None:
    app, _ = make_app(tmp_path, keys=ReloadedKeySettings(help=["f12", "ctrl+h"]))

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("f12")
            await wait_until(pilot, lambda: isinstance(app.screen, HelpScreen))
            console = Console(width=100, record=True, file=io.StringIO())
            console.print(app.screen.query_one("#help-body").query_one(Static).content)
            assert "F12 / Ctrl+H" in console.export_text()

            await pilot.press("f12")
            await wait_until(pilot, lambda: not isinstance(app.screen, HelpScreen))

    run(scenario())


def test_without_a_quit_key_the_ctrl_c_message_says_to_type_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _ = make_app(tmp_path, keys=ReloadedKeySettings(quit=[]))
    said: list[str] = []
    monkeypatch.setattr(app, "notify", lambda message, **kwargs: said.append(message))

    app.action_help_quit()

    assert not [b for b in app.shortcuts if b.action == "quit"]
    assert said == ["Type [b]exit[/b] to quit."]


def test_it_starts_with_the_hint_on_and_every_panel_titled(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test(size=(140, 24)) as pilot:
            title = app.query_one("#title", Static)
            await wait_until(pilot, lambda: "Repeats run at 1x." in hint_text(app))
            await wait_until(
                pilot, lambda: "MuJoCo Mojo Reloaded" in str(title.render())
            )

            assert app.query_one("#hint", Static).display
            assert app.query_one(ExplainButton).has_class("-open")
            assert app.query_one(CommandInput).placeholder == CommandInput.PLACEHOLDER
            assert app.query_one("#log", RichLog).border_title == "Log"
            assert app.query_one("#command-box").border_title == "Command"
            # the title shares the status row, so there is no header row above it
            assert not app.query(Header)
            assert title.region.y == app.query_one("#badge").region.y

    run(scenario())


def test_the_connection_panel_is_shown_only_for_browser_viewers(
    tmp_path: Path,
) -> None:
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


def test_a_typed_command_runs_and_the_log_keeps_everything_in_order(
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
            command = app.query_one(CommandInput)
            log = app.query_one("#log", RichLog)

            await pilot.press(*"gen", "enter")
            await wait_until(pilot, lambda: "Model Reloaded" in log_text(app))

            # the echo, the controller's messages, and the runtime's logging share one ordered buffer
            text = log_text(app)
            assert (
                text.index("> gen")
                < text.index("Processing...")
                < text.index("logged during generation")
                < text.index("Model Reloaded")
            )
            assert session.calls == [False]
            assert command.value == ""

            # how the run ended goes on the log's bottom border
            await wait_until(pilot, lambda: log.border_subtitle is not None)
            assert "last run" in str(log.border_subtitle)
            assert "success" in str(log.border_subtitle)

    run(scenario())


def test_function_keys_generate_run_and_record(tmp_path: Path) -> None:
    app, session = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            await pilot.press("f2")
            await wait_until(pilot, lambda: log_text(app).count("Model Reloaded") == 1)
            assert session.calls == [False]

            await pilot.press("f3")
            await wait_until(pilot, lambda: log_text(app).count("Model Reloaded") == 2)
            assert session.calls == [False, True]

            await pilot.press("f7")
            await wait_until(pilot, lambda: session.record is True)

    run(scenario())


def test_clicking_a_value_edits_it_and_clicking_a_toggle_flips_it(
    tmp_path: Path,
) -> None:
    app, session = make_app(tmp_path, session=FakeSession(seed=7))

    async def scenario() -> None:
        async with app.run_test() as pilot:
            command = app.query_one(CommandInput)

            def editing(key: str) -> bool:
                return app.query_one(f"#field-{key}", ParamField).has_class("-editing")

            # Enter applies, and focus goes back to the command line
            await pilot.click("#field-trial")
            assert editing("trial")
            await pilot.press("1", "2", "enter")
            await wait_until(pilot, lambda: session.trial_num == 12)
            assert not editing("trial")
            assert app.focused is command

            # Escape abandons the edit without stopping anything
            await pilot.click("#field-seed")
            await pilot.press("9", "9", "escape")
            await wait_until(pilot, lambda: not editing("seed"))
            assert session.seed == 7
            assert "No run is currently in progress" not in log_text(app)

            await pilot.click("#field-record")
            await wait_until(pilot, lambda: session.record is True)

    run(scenario())


def test_the_hint_describes_the_draft_and_a_question_mark_prints_it_instead(
    tmp_path: Path,
) -> None:
    app, session = make_app(tmp_path, session=FakeSession(seed=1))

    async def scenario() -> None:
        async with app.run_test(size=(100, 24)) as pilot:
            command = app.query_one(CommandInput)
            hint = app.query_one("#hint", Static)
            box = app.query_one("#command-box")

            command.value = "seed 42"
            await wait_until(pilot, lambda: "Sets the seed to 42." in hint_text(app))
            # on the typing line, flush with the right end of the box
            assert hint.region.y == command.region.y
            assert hint.region.x > command.region.x
            assert box.region.right - hint.region.right <= 2
            assert box.region.contains_region(hint.region)

            # a trailing question mark explains instead of doing it
            command.value = "seed 42?"
            await wait_until(
                pilot, lambda: "Prints what that would do." in hint_text(app)
            )
            await pilot.press("enter")
            await wait_until(
                pilot, lambda: "seed 42: Sets the seed to 42." in log_text(app)
            )
            assert session.seed == 1
            assert session.calls == []

            # F8 hides the hint, and the placeholder then says what Enter repeats
            await pilot.press("f8")
            await wait_until(pilot, lambda: not hint.display)
            await wait_until(pilot, lambda: "repeat 'run'" in command.placeholder)

            await pilot.click("#explain-button")
            await wait_until(pilot, lambda: hint.display)
            assert app.focused is command

    run(scenario())


def test_history_and_tab_completion_work_on_the_command_line(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            command = app.query_one(CommandInput)

            await pilot.press(*"gen", "enter")
            await wait_until(pilot, lambda: "Model Reloaded" in log_text(app))
            await pilot.press("up")
            await wait_until(pilot, lambda: command.value == "gen")
            await pilot.press("down")
            await wait_until(pilot, lambda: command.value == "")

            # Tab completes rather than leaving the box, and does nothing when there is nothing to complete
            await pilot.press("r", "e")
            await pilot.press("tab")
            await wait_until(pilot, lambda: command.value == "record")
            command.value = ""
            await pilot.press("z", "tab")
            await pilot.pause(0)
            assert command.value == "z"
            assert app.focused is command

    run(scenario())


@pytest.mark.parametrize(
    ("typed", "completed"),
    [
        ("re", "record"),
        ("gene", "generate"),
        ("explain hel", "explain help"),
        ("explain g", "explain gen"),
        ("explain se", "explain seed "),
        ("explain gene", "explain generate"),
        ("explain zz", None),
        ("explain ", None),
        ("explain", "explain "),
        ("z", None),
    ],
)
def test_completion_offers_the_command_after_explain_too(
    typed: str, completed: str | None
) -> None:
    suggester = CommandSuggester(COMMAND_SUGGESTIONS)

    assert asyncio.run(suggester.get_suggestion(typed)) == completed


def test_tab_completes_the_command_being_explained(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            command = app.query_one(CommandInput)

            await pilot.press(*"explain hel", "tab")

            await wait_until(pilot, lambda: command.value == "explain help")

    run(scenario())


def test_help_opens_from_a_key_and_a_command_and_scrolls_on_a_short_terminal(
    tmp_path: Path,
) -> None:
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test(size=(80, 16)) as pilot:
            await pilot.press("f9")
            await wait_until(pilot, lambda: isinstance(app.screen, HelpScreen))
            body = app.screen.query_one("#help-body")
            await wait_until(pilot, lambda: body.max_scroll_y > 0)

            await pilot.press("escape")
            await wait_until(pilot, lambda: not isinstance(app.screen, HelpScreen))

            app.query_one(CommandInput).value = "help"
            await pilot.press("enter")
            await wait_until(pilot, lambda: isinstance(app.screen, HelpScreen))

    run(scenario())


@pytest.mark.parametrize("how", ["f10", "exit"])
def test_the_app_closes_and_stops_the_session(tmp_path: Path, how: str) -> None:
    app, session = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            if how == "exit":
                app.query_one(CommandInput).value = "exit"
                await pilot.press("enter")
            else:
                await pilot.press(how)
            await wait_until(pilot, lambda: app.return_code is not None)

    run(scenario())
    assert app.return_code == 0
    assert session.output_sink is None


@pytest.mark.parametrize("how", ["f10", "exit"])
def test_the_app_plays_the_rain_on_the_way_out_and_then_closes(
    tmp_path: Path, how: str
) -> None:
    app, session = make_app(tmp_path, rain_seconds=0.3)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            if how == "exit":
                app.query_one(CommandInput).value = "exit"
                await pilot.press("enter")
            else:
                await pilot.press(how)
            await wait_until(pilot, lambda: isinstance(app.screen, RainScreen))
            await wait_until(pilot, lambda: app.return_code is not None)

    run(scenario())
    assert app.return_code == 0
    assert session.output_sink is None


def test_the_app_closes_when_the_viewer_window_is_closed(tmp_path: Path) -> None:
    backend = FakeBackend()
    app, _ = make_app(tmp_path, backend=backend)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            backend.closed = True
            await wait_until(pilot, lambda: app.return_code is not None)

    run(scenario())
    assert app.return_code == 0


def test_logging_and_print_output_reach_the_log_and_the_terminal_handler_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # a headless Textual app also echoes captured prints to the real stdout, which would leak into the test report
    monkeypatch.setattr(sys, "__stdout__", io.StringIO())
    root = logging.getLogger()
    terminal = RichHandler()
    root.addHandler(terminal)
    before = list(root.handlers)
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            assert terminal not in root.handlers

            logging.getLogger("reloaded_tui_test").warning("heads up")
            print("printed by user code")
            await wait_until(
                pilot,
                lambda: (
                    "heads up" in log_text(app)
                    and "printed by user code" in log_text(app)
                ),
            )
            assert "WARNING" in log_text(app)

    try:
        run(scenario())
        assert root.handlers == before
    finally:
        root.removeHandler(terminal)


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
