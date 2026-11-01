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
from reloaded_fakes import FakeBackend, FakeSession, SteppingRuntime
from rich.cells import cell_len
from rich.console import Console
from rich.logging import RichHandler
from rich.style import Style
from rich.text import Text
from textual.pilot import Pilot
from textual.widgets import RichLog, Static

import mujoco_mojo.utils.layers.reloaded.tui as tui_module

from mujoco_mojo.settings import ReloadedKeySettings
from mujoco_mojo.utils.layers.reloaded.backends.base import ConnectionInfo
from mujoco_mojo.utils.layers.reloaded.rain import RainScreen
from mujoco_mojo.utils.layers.reloaded.controller import (
    COMMAND_SUGGESTIONS,
    ControllerStatus,
    LogEvent,
    Outcome,
    ReloadedController,
    RunState,
)
from mujoco_mojo.utils.layers.reloaded.tui import (
    CommandInput,
    ExplainButton,
    FieldEditor,
    HelpScreen,
    ParamField,
    CommandSuggester,
    CONTROL_ICONS,
    ControlBar,
    ControlButton,
    LogBuffer,
    ReloadedApp,
    TuiLogHandler,
    key_label,
    render_connection,
    control_states,
    fit_title,
    render_badge,
    LOCATION_KEY,
    record_full_location,
    record_location,
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


@pytest.mark.parametrize("state", list(RunState))
def test_badge_names_the_state(state: RunState) -> None:
    assert render_badge(state).plain == f" {state.value.upper()} "


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
    assert "value late" in render_log_item(items[0]).plain
    assert formatted == [1]


def make_record(
    pathname: str, lineno: int, message: str = "hello", **kwargs: Any
) -> logging.LogRecord:
    return logging.LogRecord(
        "demo", logging.INFO, pathname, lineno, message, (), kwargs.get("exc_info")
    )


def test_a_log_line_ends_with_the_file_and_line_it_was_logged_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pkg").mkdir()

    line = render_log_item(make_record(str(tmp_path / "pkg" / "sim.py"), 42)).plain

    assert line.endswith("hello  pkg/sim.py:42")


def rendered_rows(text: Text, width: int) -> list[str]:
    """The rows `text` takes up in a pane `width` cells wide, without the padding Rich adds after them."""
    console = Console(width=width, record=True, file=io.StringIO())
    console.print(text, end="")
    return [row.rstrip() for row in console.export_text(styles=False).split("\n")]


def test_the_location_sits_flush_with_the_right_edge_when_it_fits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    text = render_log_item(make_record(str(tmp_path / "sim.py"), 9), 60)
    (row,) = rendered_rows(text, 60)

    assert len(row) == 60
    assert row.endswith("  sim.py:9")
    assert row.startswith(time.strftime("%H"))


def test_a_message_that_wraps_keeps_the_location_on_its_last_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    record = make_record(str(tmp_path / "sim.py"), 9, "word " * 20)

    rows = rendered_rows(render_log_item(record, 40), 40)

    assert len(rows) > 1
    assert rows[-1].endswith("sim.py:9")
    assert len(rows[-1]) == 40
    assert all("sim.py" not in row for row in rows[:-1])


def test_a_location_with_no_room_beside_the_message_gets_a_row_of_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    record = make_record(str(tmp_path / "sim.py"), 9, "x" * 20)

    rows = rendered_rows(render_log_item(record, 40), 40)

    assert len(rows) == 2
    assert "sim.py" not in rows[0]
    assert rows[1].strip() == "sim.py:9"
    assert len(rows[1]) == 40


def test_a_file_outside_the_working_directory_keeps_its_full_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "project"
    work.mkdir()
    monkeypatch.chdir(work)

    assert record_location(make_record("/opt/lib/site.py", 7)) == "/opt/lib/site.py:7"
    assert record_location(make_record(str(tmp_path / "other.py"), 3)) == (
        str(tmp_path / "other.py") + ":3"
    )


def test_the_location_follows_the_working_directory_when_it_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a").mkdir()
    record = make_record(str(tmp_path / "a" / "sim.py"), 5)

    monkeypatch.chdir(tmp_path)
    assert record_location(record) == "a/sim.py:5"

    monkeypatch.chdir(tmp_path / "a")
    assert record_location(record) == "sim.py:5"


def test_a_traceback_comes_after_the_location_not_before_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    try:
        raise ValueError("boom")
    except ValueError:
        record = make_record(str(tmp_path / "sim.py"), 9, exc_info=sys.exc_info())

    lines = render_log_item(record).plain.split("\n")

    assert lines[0].endswith("hello  sim.py:9")
    assert any("ValueError: boom" in line for line in lines[1:])


@pytest.mark.parametrize("width", [None, 60])
def test_a_click_copies_the_full_path_while_the_line_shows_the_short_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, width: int | None
) -> None:
    monkeypatch.chdir(tmp_path)
    record = make_record(str(tmp_path / "sim.py"), 9)

    text = render_log_item(record, width)

    copies = {
        span.style.meta.get(LOCATION_KEY)
        for span in text.spans
        if isinstance(span.style, Style) and span.style.meta
    }
    assert copies == {f"{tmp_path / 'sim.py'}:9"}
    assert copies == {record_full_location(record)}
    assert text.plain.rstrip().endswith(" sim.py:9")
    assert str(tmp_path) not in text.plain


def test_messages_that_did_not_come_from_logging_have_no_location() -> None:
    text = render_log_item(LogEvent("a controller message"))

    assert text.plain == "a controller message"
    assert not any(
        isinstance(span.style, Style) and span.style.meta for span in text.spans
    )


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
    assert "quit" in said[0]
    assert "Ctrl+Q" not in said[0]


def test_the_default_keys_are_the_ones_the_footer_has_always_shown(
    tmp_path: Path,
) -> None:
    app, _ = make_app(tmp_path)

    assert [(b.key, b.show) for b in app.shortcuts] == [
        ("f2", True),
        ("f3", True),
        ("f12", True),
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


@pytest.mark.parametrize(
    ("state", "has_runtime", "enabled"),
    [
        (RunState.IDLE, True, {"gen", "run"}),
        (RunState.IDLE, False, {"gen"}),
        (RunState.RUNNING, True, {"pause", "step", "stop"}),
        (RunState.PAUSED, True, {"run", "step", "stop"}),
        (RunState.PAUSED, False, {"step", "stop"}),
        (RunState.STOPPING, True, set()),
    ],
)
def test_the_control_buttons_apply_only_when_they_make_sense(
    state: RunState, has_runtime: bool, enabled: set[str]
) -> None:
    states = control_states(state, has_runtime)

    assert set(states) == {"gen", "run", "pause", "step", "stop"}
    assert {command for command, on in states.items() if on} == enabled


def button_labels(app: ReloadedApp) -> dict[str, str]:
    return {b.command: str(b.label) for b in app.query(ControlButton)}


def test_every_control_button_has_its_own_icon() -> None:
    commands = {command for command, *_ in ControlBar.BUTTONS}

    assert set(CONTROL_ICONS) == commands
    assert len(set(CONTROL_ICONS.values())) == len(CONTROL_ICONS)


@pytest.mark.parametrize("command", list(CONTROL_ICONS))
def test_an_icon_is_one_cell_wide_or_the_row_stops_lining_up(command: str) -> None:
    assert cell_len(CONTROL_ICONS[command]) == 1


def disabled_buttons(app: ReloadedApp) -> set[str]:
    return {b.command for b in app.query(ControlButton) if b.disabled}


def test_the_pause_and_step_keys_are_greyed_out_when_nothing_is_running(
    tmp_path: Path,
) -> None:
    app, _ = make_app(tmp_path)

    assert app.check_action("toggle_pause", ()) is None
    assert app.check_action("submit", ("step",)) is None
    assert app.check_action("submit", ("gen",)) is True


def test_without_a_quit_key_the_ctrl_c_message_says_to_type_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _ = make_app(tmp_path, keys=ReloadedKeySettings(quit=[]))
    said: list[str] = []
    monkeypatch.setattr(app, "notify", lambda message, **kwargs: said.append(message))

    app.action_help_quit()

    assert not [b for b in app.shortcuts if b.action == "quit"]
    assert said == ["Type [b]quit[/b] to quit."]


def test_the_connection_panel_shows_the_address_and_the_warning_for_browser_viewers(
    tmp_path: Path,
) -> None:
    info = ConnectionInfo(url="http://localhost:8000/", warning="Open to the network.")

    async def scenario() -> None:
        app, _ = make_app(tmp_path, backend=FakeBackend(info))
        async with app.run_test():
            panel = app.query_one("#connection", Static)
            assert panel.display
            text = str(panel.render())
            assert "http://localhost:8000/" in text
            assert "Open to the network." in text

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


@pytest.mark.parametrize(
    ("speed", "shown", "raw"),
    [
        (1.0, "1x", "1"),
        (0.5, "0.5x", "0.5"),
        (0.0, "manual", "0"),
        (float("inf"), "inf", "inf"),
    ],
)
def test_the_speed_field_shows_manual_and_inf_by_name(
    speed: float, shown: str, raw: str
) -> None:
    field = next(
        f for f in status_fields(status(playback_speed=speed)) if f.key == "speed"
    )

    assert field.value == shown
    assert field.raw == raw


# --- the app itself ---
#
# Every test below launches the app, which costs about a fifth of a second before it does anything, so each one covers a whole area and nothing here is repeated. Whatever can be checked without the app is checked in the tests above and in the controller tests, which take milliseconds. Set a value rather than typing it key by key (each key press waits for the app to go idle), and wait for the thing that should happen rather than sleeping.


def badge_text(app: ReloadedApp) -> str:
    return str(app.query_one("#badge", Static).render()).strip()


def test_the_app_starts_with_its_panels_the_hint_and_a_control_row(
    tmp_path: Path,
) -> None:
    keys = ReloadedKeySettings(stop=["f11"], step=["ctrl+n"], pause=[])
    app, _ = make_app(tmp_path, keys=keys)

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
            assert title.region.y == app.query_one("#badge").region.y

            # the control row sits right under it, with the keys from settings, and only what applies is lit
            assert button_labels(app) == {
                "gen": f"{CONTROL_ICONS['gen']} Gen F2",
                "run": f"{CONTROL_ICONS['run']} Run F3",
                "pause": f"{CONTROL_ICONS['pause']} Pause",
                "step": f"{CONTROL_ICONS['step']} Step Ctrl+N",
                "stop": f"{CONTROL_ICONS['stop']} Stop F11",
            }
            row = app.query_one("#status").region.y + 1
            for button in app.query(ControlButton):
                assert button.region.height == 1
                assert button.region.y == row
                assert button.region.right <= 140
            assert disabled_buttons(app) == {"pause", "step", "stop"}
            # there is no connection panel without a browser viewer
            assert not app.query_one("#connection", Static).display

    run(scenario())


def test_a_run_is_paused_stepped_carried_on_and_stopped_from_keys_buttons_and_commands(
    tmp_path: Path,
) -> None:
    runtime = SteppingRuntime()
    session = FakeSession(behavior=runtime)
    app, _ = make_app(tmp_path, session, keys=ReloadedKeySettings(step=["ctrl+n"]))

    async def frozen(pilot: Pilot[None]) -> int:
        """The step count of a held run, once it has had time to take any step it was going to."""
        await pilot.pause(0.03)
        first = runtime.steps
        await pilot.pause(0.03)
        assert runtime.steps == first
        return first

    async def scenario() -> None:
        async with app.run_test(size=(100, 24)) as pilot:
            await pilot.press("f3")
            await wait_until(pilot, lambda: runtime.steps > 3)
            assert badge_text(app) == "RUNNING"
            assert disabled_buttons(app) == {"gen", "run"}
            assert app.check_action("toggle_pause", ()) is True

            await pilot.press("f12")
            await wait_until(pilot, lambda: badge_text(app) == "PAUSED")
            held = await frozen(pilot)
            assert disabled_buttons(app) == {"gen", "pause"}

            # the Step key from settings lets one step through
            await pilot.press("ctrl+n")
            await wait_until(pilot, lambda: runtime.steps == held + 1)
            assert await frozen(pilot) == held + 1

            # a typed target carries the run on, and it holds itself there and says so
            target = held + 20
            app.query_one(CommandInput).value = f"run until step {target}"
            await pilot.press("enter")
            await wait_until(pilot, lambda: f"reached step {target}" in log_text(app))
            assert await frozen(pilot) == target
            assert badge_text(app) == "PAUSED"

            # every control button types its command the same way, so one click shows the wiring
            await pilot.click("#control-run")
            await wait_until(pilot, lambda: badge_text(app) == "RUNNING")
            await wait_until(pilot, lambda: runtime.steps > target + 5)

            await pilot.press("escape")
            await wait_until(pilot, lambda: badge_text(app) == "IDLE")
            assert disabled_buttons(app) == {"pause", "step", "stop"}

    run(scenario())
    assert session.calls == [True]


def test_the_command_line_runs_remembers_completes_and_explains(tmp_path: Path) -> None:
    session = FakeSession(
        seed=1,
        generation_behavior=lambda s: logging.getLogger("order").warning(
            "logged during generation"
        ),
    )
    app, _ = make_app(tmp_path, session)

    async def complete(pilot: Pilot[None], typed: str) -> str:
        command = app.query_one(CommandInput)
        command.value = typed
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        return command.value

    async def scenario() -> None:
        async with app.run_test(size=(100, 24)) as pilot:
            command = app.query_one(CommandInput)
            log = app.query_one("#log", RichLog)
            hint = app.query_one("#hint", Static)

            # a typed command runs, and the echo, the controller's messages, and the runtime's logging share one ordered log
            command.value = "gen"
            await pilot.press("enter")
            await wait_until(pilot, lambda: "Model Reloaded" in log_text(app))
            text = log_text(app)
            assert (
                text.index("> gen")
                < text.index("Processing...")
                < text.index("logged during generation")
                < text.index("Model Reloaded")
            )
            assert session.calls == [False]
            assert command.value == ""
            await wait_until(pilot, lambda: log.border_subtitle is not None)
            assert "success" in str(log.border_subtitle)

            # Up brings back the last command
            await pilot.press("up")
            await wait_until(pilot, lambda: command.value == "gen")

            # Tab completes, also the command after `explain`, and keeps the focus in the box rather than leaving it
            assert await complete(pilot, "explain hel") == "explain help"
            assert app.focused is command

            # the hint sits flush right on the typing line and describes the draft
            command.value = "seed 42"
            await wait_until(pilot, lambda: "Sets the seed to 42." in hint_text(app))
            box = app.query_one("#command-box")
            assert hint.region.y == command.region.y
            assert box.region.right - hint.region.right <= 2

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
            assert session.calls == [False]

    run(scenario())


def test_clicking_a_status_value_edits_it_and_enter_applies_it(tmp_path: Path) -> None:
    app, session = make_app(tmp_path, session=FakeSession(seed=7))

    def editing(key: str) -> bool:
        return app.query_one(f"#field-{key}", ParamField).has_class("-editing")

    async def scenario() -> None:
        async with app.run_test() as pilot:
            # Enter applies, and focus goes back to the command line
            await pilot.click("#field-trial")
            assert editing("trial")
            app.query_one("#field-trial .editor", FieldEditor).value = "12"
            await pilot.press("enter")
            await wait_until(pilot, lambda: session.trial_num == 12)
            assert not editing("trial")
            assert app.focused is app.query_one(CommandInput)

    run(scenario())


def test_help_opens_from_a_configured_key_and_a_command_and_closes_again(
    tmp_path: Path,
) -> None:
    app, _ = make_app(tmp_path, keys=ReloadedKeySettings(help=["f11", "ctrl+h"]))

    async def shown(pilot: Pilot[None]) -> bool:
        await wait_until(pilot, lambda: isinstance(app.screen, HelpScreen))
        return True

    async def scenario() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("f11")
            assert await shown(pilot)
            console = Console(width=100, record=True, file=io.StringIO())
            console.print(app.screen.query_one("#help-body").query_one(Static).content)
            # every key of an action is listed
            assert "F11 / Ctrl+H" in console.export_text()

            # a modal screen passes no keys on, so the screen closes on the key that opened it
            await pilot.press("ctrl+h")
            await wait_until(pilot, lambda: not isinstance(app.screen, HelpScreen))

    run(scenario())


def test_log_output_shows_where_it_came_from_and_clicking_that_copies_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # a headless Textual app also echoes captured prints to the real stdout, which would leak into the test report
    monkeypatch.setattr(sys, "__stdout__", io.StringIO())
    here = Path(__file__).resolve()
    # as in real use, the file is inside the working directory, so its location is short
    monkeypatch.chdir(here.parents[2])
    root = logging.getLogger()
    terminal = RichHandler()
    root.addHandler(terminal)
    before = list(root.handlers)
    app, _ = make_app(tmp_path)

    async def scenario() -> None:
        async with app.run_test(size=(140, 30)) as pilot:
            # the terminal handler steps aside while the app owns the screen
            assert terminal not in root.handlers

            logging.getLogger("reloaded_tui_test").warning("look here")
            print("printed by user code")
            await wait_until(
                pilot,
                lambda: (
                    "look here" in log_text(app)
                    and "printed by user code" in log_text(app)
                ),
            )
            assert "WARNING" in log_text(app)

            log = app.query_one("#log", RichLog)
            row, line = next(
                (i, strip.text)
                for i, strip in enumerate(log.lines)
                if "look here" in strip.text
            )
            location = line.rstrip().split("  ")[-1].strip()
            assert location.startswith("tests/utils/")
            assert location.rsplit(":", 1)[0].endswith(here.name)
            # and it ends flush with the right edge of the pane
            assert len(line.rstrip()) == log.scrollable_content_region.width

            # the log has a border and a column of padding, so its text starts at (2, 1)
            await pilot.click("#log", offset=(line.index(location) + 4, row + 1))
            # the line shows the short path and a click copies the full one
            full = f"{here}:{location.rsplit(':', 1)[1]}"
            assert full != location
            await wait_until(pilot, lambda: app.clipboard == full)

    try:
        run(scenario())
        assert root.handlers == before
    finally:
        root.removeHandler(terminal)


def test_quit_plays_the_rain_then_closes_and_stops_the_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, session = make_app(tmp_path, rain_seconds=0.1)
    pushed: list[object] = []
    push_screen = app.push_screen

    def spy(screen: Any, *args: Any, **kwargs: Any) -> Any:
        pushed.append(screen)
        return push_screen(screen, *args, **kwargs)

    monkeypatch.setattr(app, "push_screen", spy)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            app.query_one(CommandInput).value = "quit"
            await pilot.press("enter")
            await wait_until(pilot, lambda: app.return_code is not None)

    run(scenario())
    assert any(isinstance(screen, RainScreen) for screen in pushed)
    assert app.return_code == 0
    assert session.output_sink is None


def test_closing_the_viewer_window_closes_reloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tui_module, "VIEWER_CHECK_SECONDS", 0.02)
    backend = FakeBackend()
    app, _ = make_app(tmp_path, backend=backend)

    async def scenario() -> None:
        async with app.run_test() as pilot:
            backend.closed = True
            await wait_until(pilot, lambda: app.return_code is not None)

    run(scenario())
    assert app.return_code == 0
