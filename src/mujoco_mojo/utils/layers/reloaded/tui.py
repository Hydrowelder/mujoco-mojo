import asyncio
import logging
import threading
import time
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import ClassVar, Literal

from rich.console import Group, RenderableType
from rich.errors import MarkupError
from rich.logging import RichHandler
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, VerticalScroll
from textual.content import Content
from textual.css.query import NoMatches
from textual.markup import escape as escape_markup
from textual.message import Message
from textual.screen import ModalScreen
from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Button, Footer, Input, RichLog, Static

from mujoco_mojo.settings import ReloadedKeySettings
from mujoco_mojo.utils.log import TerminalFilter

from .backends.base import ConnectionInfo, ViewerBackend
from .controller import (
    COMMAND_SUGGESTIONS,
    ControllerEvent,
    ControllerStatus,
    ExitEvent,
    HelpEvent,
    LogEvent,
    Outcome,
    ReloadedController,
    RunState,
    StatusEvent,
    speed_label,
)
from .rain import RainScreen
from .theme import (
    ACCENT,
    DANGER,
    INFO,
    INK_BODY,
    INK_MUTED,
    INK_SECONDARY,
    INK_STRONG,
    LINK,
    MOJO_ANSI_THEME,
    MOJO_THEME,
    ON_ACCENT,
    SCRIM,
    SUCCESS,
    SURFACE_INSET,
    WARNING,
)

__all__ = ["ReloadedApp"]

APP_TITLE = "MuJoCo Mojo Reloaded"

LOG_FLUSH_SECONDS = 0.05
"""How often waiting lines are moved into the log pane. Anything that arrives in between is shown together."""
LOG_LINES_PER_FLUSH = 300
"""The most lines shown per flush, so a flood can never keep the UI from handling keys and clicks."""
LOG_BACKLOG = 5000
"""How many lines may wait to be shown. When a producer outruns the screen the oldest are skipped, with a notice, rather than growing without bound."""
VIEWER_CHECK_SECONDS = 0.5
"""How often to check that the viewer is still open, so closing its window ends the session."""

FieldKind = Literal["edit", "toggle", "info"]

_STATE_STYLES = {
    RunState.IDLE: ("IDLE", f"bold {ON_ACCENT} on {SUCCESS}"),
    RunState.RUNNING: ("RUNNING", f"bold {ON_ACCENT} on {WARNING}"),
    RunState.PAUSED: ("PAUSED", f"bold {ON_ACCENT} on {LINK}"),
    RunState.STOPPING: ("STOPPING", f"bold {ON_ACCENT} on {DANGER}"),
}

_OUTCOME_STYLES = {
    Outcome.SUCCESS: str(SUCCESS),
    Outcome.SATISFIED: str(SUCCESS),
    Outcome.TERMINATED: str(WARNING),
    Outcome.STOPPED: str(WARNING),
    Outcome.FAILED: f"bold {DANGER}",
}

# same meaning as the level colors in `mojo_theme`, which colors the plain terminal logs
_LEVEL_STYLES = {
    logging.DEBUG: f"bold {INFO}",
    logging.INFO: f"bold {SUCCESS}",
    logging.WARNING: f"bold {WARNING}",
    logging.ERROR: f"bold {DANGER}",
    logging.CRITICAL: f"bold {ON_ACCENT} on {DANGER}",
}

# what the footer's key bindings are not enough to teach
_EXTRA_KEY_HELP = [
    ("Enter", "Repeat the last command, when nothing is typed"),
    ("Click ?", "Show or hide the hint on what the typed command does"),
    ("Tab", "Complete the command being typed"),
    ("Up / Down", "Previous and next command"),
    ("Click seed, trial, speed", "Edit it. Enter applies and Esc cancels"),
    ("Click watch, record", "Switch it on or off"),
]


def render_markup(message: str) -> Text:
    """Rich markup to `Text`, falling back to the literal string if the markup is malformed (e.g. an array repr with square brackets)."""
    try:
        return Text.from_markup(message)
    except MarkupError:
        return Text(message)


def key_label(key: str) -> str:
    """Display form of a Textual key name, e.g. `ctrl+q` becomes `Ctrl+Q` and `f1` becomes `F1`."""
    return "+".join(part.capitalize() for part in key.split("+"))


def shortcut_bindings(keys: ReloadedKeySettings) -> list[Binding]:
    """One binding per configured key. The first key of an action is shown in the footer, and any others only work."""
    actions = (
        ("Generate", "submit('gen')", keys.generate),
        ("Run", "submit('run')", keys.run),
        ("Pause", "toggle_pause", keys.pause),
        ("Step", "submit('step')", keys.step),
        ("Watch", "submit('watch')", keys.watch),
        ("Record", "submit('record')", keys.record),
        ("Explain", "toggle_explain", keys.explain),
        ("Help", "help", keys.help),
        ("Stop", "submit('stop')", keys.stop),
        ("Quit", "quit", keys.quit),
    )
    return [
        Binding(
            key,
            action,
            description,
            show=position == 0,
            key_display="Esc" if key == "escape" else key_label(key),
        )
        for description, action, names in actions
        for position, key in enumerate(names)
    ]


@dataclass(frozen=True)
class FieldView:
    """How one value of the session appears in the status bar."""

    key: str
    label: str
    value: str
    style: str
    kind: FieldKind
    raw: str = ""
    """What the editor starts with when an editable field is clicked."""


def render_badge(state: RunState) -> Text:
    label, style = _STATE_STYLES[state]
    return Text(f" {label} ", style=style)


def status_fields(status: ControllerStatus) -> list[FieldView]:
    """The values shown in the status bar, in order. Fields marked `edit` open an editor when clicked and `toggle` fields flip."""

    def on_off(on: bool) -> tuple[str, str]:
        return ("on", f"bold {LINK}") if on else ("off", str(INK_MUTED))

    watch, watch_style = on_off(status.watch)
    record, record_style = on_off(status.record)
    speed = f"{status.playback_speed:g}"
    speed_shown = speed_label(status.playback_speed)

    fields = [
        FieldView(
            "seed",
            "seed",
            "none" if status.seed is None else str(status.seed),
            str(INK_MUTED) if status.seed is None else str(INK_STRONG),
            "edit",
            raw="" if status.seed is None else str(status.seed),
        ),
        FieldView(
            "trial",
            "trial",
            str(status.trial_num),
            str(INK_STRONG),
            "edit",
            raw=str(status.trial_num),
        ),
        FieldView("speed", "speed", speed_shown, str(INK_STRONG), "edit", raw=speed),
        FieldView("watch", "watch", watch, watch_style, "toggle"),
        FieldView("record", "record", record, record_style, "toggle"),
        FieldView("last", "last", status.last_command, str(INK_STRONG), "info"),
    ]
    return fields


def control_states(state: RunState, has_runtime: bool) -> dict[str, bool]:
    """Which control buttons apply in `state`, by the command each one types. A button that does not apply is greyed out."""
    idle = state is RunState.IDLE
    running = state is RunState.RUNNING
    paused = state is RunState.PAUSED
    return {
        "gen": idle,
        "run": has_runtime and (idle or paused),
        "pause": running,
        "step": running or paused,
        "stop": running or paused,
    }


def run_summary(status: ControllerStatus) -> Text | None:
    """How the most recent run ended, or `None` before the first one. Shown on the log's bottom border, where it has room."""
    if status.last_duration is None or status.last_outcome is None:
        return None
    return Text.assemble(
        (" last run ", INK_SECONDARY),
        (
            f"{status.last_duration:.2f}s {status.last_outcome.value} ",
            _OUTCOME_STYLES[status.last_outcome],
        ),
    )


def fit_title(title: str, subtitle: str, available: int) -> Text:
    """The app title for a status bar with `available` spare columns: with its subtitle if both fit, alone if only it fits, and nothing otherwise, so it is never cut in half."""
    brand = Text(title, style=f"bold {ACCENT}")
    full = Text.assemble(brand, (f"  {subtitle}", INK_MUTED)) if subtitle else brand
    if full.cell_len <= available:
        return full
    if brand.cell_len <= available:
        return brand
    return Text("")


def render_connection(info: ConnectionInfo) -> Text:
    """Where to open a browser viewer, how to tunnel to it, and any standing warning."""
    text = Text()
    text.append("Viewer ", style=INK_SECONDARY)
    text.append(info.url, style=f"bold underline {LINK}")
    if info.tunnel_command is not None:
        text.append("\nFrom your computer ", style=INK_SECONDARY)
        text.append(info.tunnel_command, style=INK_STRONG)
    if info.warning is not None:
        text.append("\n")
        text.append(info.warning, style=str(WARNING))
    return text


class ControllerMessage(Message):
    """Carries a controller event onto the app's event loop. Posting is thread safe and never blocks the sender."""

    def __init__(self, event: ControllerEvent) -> None:
        super().__init__()
        self.event = event


LogItem = logging.LogRecord | LogEvent | Text
"""Anything that can wait to be shown in the log pane: a logging record, a controller message, or ready made text."""

_FORMATTER = logging.Formatter()


def format_record(record: logging.LogRecord) -> Text:
    """One logging record as a line for the log pane: time, level, then the message."""
    text = Text()
    text.append(
        time.strftime("%H:%M:%S ", time.localtime(record.created)), style=INK_MUTED
    )
    text.append(f"{record.levelname:<9}", style=_LEVEL_STYLES.get(record.levelno, ""))
    text.append_text(render_markup(record.getMessage()))
    if record.exc_info:
        text.append(
            "\n" + _FORMATTER.formatException(record.exc_info), style=str(DANGER)
        )
    return text


def render_log_item(item: LogItem) -> Text:
    """Turns whatever was waiting into text, on the UI side so the thread that logged never pays for it."""
    try:
        if isinstance(item, Text):
            return item
        if isinstance(item, LogEvent):
            return render_markup(item.message) if item.markup else Text(item.message)
        return format_record(item)
    except Exception as error:
        return Text(f"(a log line could not be shown: {error})", style=str(DANGER))


@dataclass(eq=False)
class LogBuffer:
    """
    Thread safe, bounded queue between everything that writes to the log pane and the UI.

    Any thread can `put`, and it never blocks and never grows past `capacity`. When it is full the oldest item is dropped and counted. The UI `take`s a few at a time.
    """

    capacity: int = LOG_BACKLOG
    """How many items may wait. Past this the oldest are dropped."""
    _items: deque[LogItem] = field(default_factory=deque, init=False, repr=False)
    _dropped: int = field(default=0, init=False, repr=False)
    _lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False
    )

    def __len__(self) -> int:
        return len(self._items)

    def put(self, item: LogItem) -> None:
        with self._lock:
            if len(self._items) >= self.capacity:
                self._items.popleft()
                self._dropped += 1
            self._items.append(item)

    def take(self, limit: int) -> tuple[list[LogItem], int]:
        """Up to `limit` of the oldest items, and how many were dropped since the last call."""
        with self._lock:
            count = min(limit, len(self._items))
            items = [self._items.popleft() for _ in range(count)]
            dropped, self._dropped = self._dropped, 0
        return items, dropped


class TuiLogHandler(logging.Handler):
    """
    Sends logging records to the log pane in place of the terminal handler, which would otherwise write over the screen.

    `emit` only stores the record. Formatting happens later on the UI side, so a runtime that logs on every physics step pays almost nothing for being watched.
    """

    def __init__(self, buffer: LogBuffer) -> None:
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        self._buffer.put(record)


class FieldEditor(Input):
    """Inline editor that replaces a field's value while it is being edited."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel", show=False)
    ]

    class Cancelled(Message):
        """The user pressed Escape."""

    def action_cancel(self) -> None:
        self.post_message(self.Cancelled())


class ParamField(Horizontal):
    """
    One labeled value in the status bar.

    Clicking an `edit` field swaps its value for an editor, and clicking a `toggle` field flips it. The field only reports what the user did. The app passes it on to the controller, which decides whether the change is allowed.
    """

    class Edited(Message):
        """An edit was committed with Enter."""

        def __init__(self, key: str, text: str) -> None:
            super().__init__()
            self.key = key
            self.text = text

    class Toggled(Message):
        """A toggle field was clicked."""

        def __init__(self, key: str) -> None:
            super().__init__()
            self.key = key

    def __init__(self, key: str, kind: FieldKind) -> None:
        super().__init__(id=f"field-{key}", classes=f"-{kind}")
        self.key = key
        self.kind: FieldKind = kind
        self._raw = ""

    def compose(self) -> ComposeResult:
        yield Static(classes="label")
        yield Static(classes="value")
        yield FieldEditor(compact=True, select_on_focus=True, classes="editor")

    def on_mount(self) -> None:
        if self.kind == "edit":
            self.tooltip = "Click to edit"
        elif self.kind == "toggle":
            self.tooltip = "Click to switch on or off"

    def show(self, view: FieldView) -> None:
        self._raw = view.raw
        self.query_one(".label", Static).update(
            Text(f"{view.label} ", style=INK_SECONDARY)
        )
        self.query_one(".value", Static).update(Text(view.value, style=view.style))

    def on_click(self) -> None:
        if self.has_class("-editing"):
            return
        if self.kind == "toggle":
            self.post_message(self.Toggled(self.key))
        elif self.kind == "edit":
            editor = self.query_one(FieldEditor)
            editor.value = self._raw
            self.add_class("-editing")
            editor.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.post_message(self.Edited(self.key, event.value))
        self._finish_edit()

    def on_field_editor_cancelled(self, event: FieldEditor.Cancelled) -> None:
        event.stop()
        self._finish_edit()

    def on_descendant_blur(self) -> None:
        # clicking anywhere else abandons the edit
        self.remove_class("-editing")

    def _finish_edit(self) -> None:
        self.remove_class("-editing")
        self.app.query_one(CommandInput).focus()


class StatusBar(Horizontal):
    """State badge and the session's parameters, with the editable ones a click away."""

    LAYOUT: ClassVar[tuple[tuple[str, FieldKind], ...]] = (
        ("seed", "edit"),
        ("trial", "edit"),
        ("speed", "edit"),
        ("watch", "toggle"),
        ("record", "toggle"),
        ("last", "info"),
    )

    def __init__(
        self,
        status: ControllerStatus,
        *,
        title: str,
        subtitle: str = "",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._status = status
        self._title = title
        self._subtitle = subtitle

    def compose(self) -> ComposeResult:
        yield Static(id="badge")
        for key, kind in self.LAYOUT:
            yield ParamField(key, kind)
        yield Static(id="title")

    def on_mount(self) -> None:
        self.show(self._status)

    def on_resize(self) -> None:
        self._fit_title()

    def show(self, status: ControllerStatus) -> None:
        self._status = status
        self.query_one("#badge", Static).update(render_badge(status.state))
        views = {view.key: view for view in status_fields(status)}
        for param in self.query(ParamField):
            param.show(views[param.key])
        # the fields just changed width, which changes how much room the title has
        self.call_after_refresh(self._fit_title)

    def _fit_title(self) -> None:
        # the title takes whatever width the fields leave over
        try:
            title = self.query_one("#title", Static)
        except NoMatches:
            return
        title.update(fit_title(self._title, self._subtitle, title.size.width))


class ExplainButton(Button):
    """Shows and hides the short hint, on the command line, that says what the command being typed will do. It never takes focus, so typing carries on."""

    can_focus = False

    def __init__(self) -> None:
        super().__init__("?", id="explain-button")
        self.tooltip = "Say what the command you have typed will do"


class ControlButton(Button):
    """One of the buttons that control a run. Pressing it types its `command`. It never takes focus, so typing carries on."""

    can_focus = False

    def __init__(
        self, command: str, label: str, tooltip: str, *, disabled: bool
    ) -> None:
        super().__init__(
            label, id=f"control-{command}", compact=True, disabled=disabled
        )
        self.command = command
        self.tooltip = tooltip


class ControlBar(Horizontal):
    """The row of buttons that start, hold, step, and stop a run, each showing its key and lit only when it applies."""

    BUTTONS: ClassVar[tuple[tuple[str, str, str, str], ...]] = (
        # the command it types, its label, the action its key is bound to, and its tooltip
        ("gen", "Gen", "submit('gen')", "Generate the model without running it"),
        (
            "run",
            "Run",
            "submit('run')",
            "Generate and run the runtime, or carry a paused run on",
        ),
        ("pause", "Pause", "toggle_pause", "Hold the run where it is"),
        ("step", "Step", "submit('step')", "Advance the run by one step"),
        ("stop", "Stop", "submit('stop')", "Abort the run"),
    )

    def __init__(
        self,
        shortcuts: list[Binding],
        state: RunState,
        has_runtime: bool,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._shortcuts = shortcuts
        self._enabled = control_states(state, has_runtime)

    def compose(self) -> ComposeResult:
        for command, label, action, tooltip in self.BUTTONS:
            key = next(
                (
                    b.key_display
                    for b in self._shortcuts
                    if b.action == action and b.show
                ),
                None,
            )
            text = label if key is None else f"{label} [dim]{escape_markup(key)}[/dim]"
            yield ControlButton(
                command, text, tooltip, disabled=not self._enabled[command]
            )

    def show(self, state: RunState, has_runtime: bool) -> None:
        enabled = control_states(state, has_runtime)
        for button in self.query(ControlButton):
            button.disabled = not enabled[button.command]


class CommandSuggester(Suggester):
    """Completes the command being typed, and also the command after `explain`, so `explain hel` becomes `explain help`."""

    EXPLAIN = "explain "

    def __init__(self, commands: Iterable[str]) -> None:
        super().__init__(case_sensitive=False)
        self._commands = tuple(commands)

    async def get_suggestion(self, value: str) -> str | None:
        if value.startswith(self.EXPLAIN):
            rest = value.removeprefix(self.EXPLAIN)
            if not rest:
                return None
            return next(
                (
                    self.EXPLAIN + command
                    for command in self._commands
                    if command != self.EXPLAIN and command.startswith(rest)
                ),
                None,
            )
        return next(
            (command for command in self._commands if command.startswith(value)), None
        )


class CommandInput(Input):
    """Command line with Up and Down history and Tab completion."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "history_previous", "Previous command", show=False),
        Binding("down", "history_next", "Next command", show=False),
        Binding("tab", "complete", "Complete", show=False),
    ]

    PLACEHOLDER = "Type a command, enter to repeat previous, or help"

    def __init__(self, suggestions: Iterable[str], *, id: str | None = None) -> None:
        super().__init__(
            placeholder=self.PLACEHOLDER,
            suggester=CommandSuggester(suggestions),
            id=id,
        )
        self._history: list[str] = []
        self._cursor: int | None = None
        self._draft = ""

    def remember(self, value: str) -> None:
        if value and (not self._history or self._history[-1] != value):
            self._history.append(value)
        self._cursor = None
        self._draft = ""

    def action_complete(self) -> None:
        """Accepts the suggested completion, the same as pressing Right at the end of the line."""
        self.action_end()
        self.action_cursor_right()

    def action_history_previous(self) -> None:
        if not self._history:
            return
        if self._cursor is None:
            self._draft = self.value
            self._cursor = len(self._history) - 1
        elif self._cursor > 0:
            self._cursor -= 1
        self._show_history()

    def action_history_next(self) -> None:
        if self._cursor is None:
            return
        if self._cursor < len(self._history) - 1:
            self._cursor += 1
        else:
            self._cursor = None
        self._show_history()

    def _show_history(self) -> None:
        self.value = (
            self._draft if self._cursor is None else self._history[self._cursor]
        )
        self.cursor_position = len(self.value)


class HelpScreen(ModalScreen[None]):
    """Lists the commands and key bindings."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape,q", "dismiss", "Close")]

    def __init__(
        self,
        commands: list[tuple[str, str]],
        keys: list[tuple[str, str]],
        close_keys: list[str],
    ) -> None:
        """`close_keys` are the keys that opened the help, which close it too. A modal screen does not pass keys on to the app, so it has to bind them itself."""
        super().__init__()
        self._commands = commands
        self._keys = keys
        self._close_keys = close_keys

    def on_key(self, event: events.Key) -> None:
        if event.key in self._close_keys:
            event.stop()
            self.dismiss()

    def compose(self) -> ComposeResult:
        body = VerticalScroll(Static(self._render_body()), id="help-body")
        body.border_subtitle = "Esc to close"
        yield body

    def _render_body(self) -> RenderableType:
        def grid(rows: list[tuple[str, str]]) -> Table:
            table = Table.grid(padding=(0, 2))
            table.add_column(style=f"bold {LINK}", no_wrap=True)
            table.add_column(style=INK_BODY)
            for left, right in rows:
                table.add_row(left, right)
            return table

        return Group(
            Text("Commands", style=f"bold {INK_STRONG}"),
            grid(self._commands),
            Text(""),
            Text("Keys and mouse", style=f"bold {INK_STRONG}"),
            grid(self._keys),
        )


class ReloadedApp(App[None]):
    """
    Terminal UI for a Reloaded session.

    It owns no session logic. Everything the user types or clicks goes to the `ReloadedController`, and everything the controller reports comes back as events.
    """

    TITLE = APP_TITLE
    AUTO_FOCUS = "#command"
    CSS_PATH = "tui.tcss"
    # Ctrl+P is Quick Open in VS Code, and the palette has nothing of ours in it
    ENABLE_COMMAND_PALETTE = False

    def __init__(
        self,
        controller: ReloadedController,
        backend: ViewerBackend,
        *,
        keys: ReloadedKeySettings | None = None,
        subtitle: str = "",
        watch_css: bool = False,
        explain: bool = True,
        rain_seconds: float = 1.5,
    ) -> None:
        """`keys` are the keyboard shortcuts, `watch_css` re-applies `tui.tcss` the moment it is saved, for working on the layout, `explain` sets whether the hint on what the typed command does starts out showing, and `rain_seconds` is how long the digital rain plays on the way out, where 0 skips it."""
        super().__init__(watch_css=watch_css)
        self.shortcuts = shortcut_bindings(keys or ReloadedKeySettings())
        """The keys bound to actions, in the order the footer shows them."""
        for binding in self.shortcuts:
            self.bind(
                binding.key,
                binding.action,
                description=binding.description,
                show=binding.show,
                key_display=binding.key_display,
            )
        self._explain_at_start = explain
        self._rain_seconds = rain_seconds
        self._controller = controller
        self._backend = backend
        self.sub_title = subtitle
        self._saved_handlers: list[logging.Handler] = []
        self._log_handler: TuiLogHandler | None = None
        self._logs = LogBuffer()
        self._quitting = False
        controller.sink = self._deliver

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # the Run key has nothing to do without a runtime function, so grey it out
        if (
            action == "submit"
            and parameters == ("run",)
            and not self._controller.has_runtime
        ):
            return None
        # and Pause and Step have nothing to hold unless a run is going or paused
        if action == "toggle_pause" or (action == "submit" and parameters == ("step",)):
            running = self._controller.status().state in (
                RunState.RUNNING,
                RunState.PAUSED,
            )
            return True if running else None
        return True

    def get_theme_variable_defaults(self) -> dict[str, str]:
        # the stylesheet is parsed before the mojo theme is selected, so it needs a value for each custom variable it uses
        return {"surface-inset": str(SURFACE_INSET), "scrim": str(SCRIM)}

    def compose(self) -> ComposeResult:
        yield StatusBar(
            self._controller.status(),
            title=APP_TITLE,
            subtitle=self.sub_title,
            id="status",
        )
        yield ControlBar(
            self.shortcuts,
            self._controller.status().state,
            self._controller.has_runtime,
            id="controls",
        )
        connection = Static(id="connection")
        connection.border_title = "Browser viewer"
        yield connection
        log = RichLog(id="log", wrap=True, highlight=False, max_lines=10_000)
        log.border_title = "Log"
        yield log
        with Horizontal(id="command-row"):
            with Horizontal(id="command-box") as command_box:
                command_box.border_title = "Command"
                yield CommandInput(COMMAND_SUGGESTIONS, id="command")
                yield Static(id="hint")
            yield ExplainButton()
        yield Footer(compact=True)

    def on_mount(self) -> None:
        self.register_theme(MOJO_THEME)
        self.theme = MOJO_THEME.name
        self.ansi_theme_dark = MOJO_ANSI_THEME
        self.begin_capture_print(self)
        self._install_log_handler()
        self.set_interval(LOG_FLUSH_SECONDS, self._flush_logs)
        self.set_interval(VIEWER_CHECK_SECONDS, self._check_viewer)
        self._set_explain(self._explain_at_start)

        info = self._backend.connection_info()
        if info is not None:
            panel = self.query_one("#connection", Static)
            panel.update(render_connection(info))
            panel.display = True

        self._controller.start()

    def on_unmount(self) -> None:
        self.end_capture_print(self)
        self._remove_log_handler()
        self._controller.shutdown()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if not isinstance(event.input, CommandInput):
            return
        value = event.value
        event.input.clear()
        event.input.remember(value.strip())
        if value.strip():
            self._logs.put(
                Text.assemble(
                    ("> ", f"bold {ACCENT}"), (value.strip(), f"bold {INK_STRONG}")
                )
            )
        self._controller.submit(value)

    def on_input_changed(self, event: Input.Changed) -> None:
        if isinstance(event.input, CommandInput):
            self._refresh_explain()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if isinstance(event.button, ExplainButton):
            event.stop()
            self.action_toggle_explain()
        elif isinstance(event.button, ControlButton):
            event.stop()
            self._controller.submit(event.button.command)

    def on_param_field_edited(self, message: ParamField.Edited) -> None:
        match message.key:
            case "seed":
                self._controller.set_seed(message.text)
            case "trial":
                self._controller.set_trial(message.text)
            case "speed":
                self._controller.set_speed(message.text)

    def on_param_field_toggled(self, message: ParamField.Toggled) -> None:
        match message.key:
            case "watch":
                self._controller.toggle_watch()
            case "record":
                self._controller.toggle_record()

    async def on_controller_message(self, message: ControllerMessage) -> None:
        match message.event:
            case StatusEvent(status=status):
                self._apply_status(status)
            case HelpEvent():
                self.action_help()
            case ExitEvent():
                await self.action_quit()

    def on_print(self, event: events.Print) -> None:
        text = event.text.rstrip("\n")
        if text:
            self._logs.put(Text(text, style=str(DANGER) if event.stderr else INK_BODY))

    def action_help(self) -> None:
        labels: dict[str, list[str]] = {}
        for binding in self.shortcuts:
            labels.setdefault(binding.description, []).append(key_label(binding.key))
        keys = [(" / ".join(names), action) for action, names in labels.items()]
        self.push_screen(
            HelpScreen(
                self._controller.help_entries(),
                keys + _EXTRA_KEY_HELP,
                close_keys=[b.key for b in self.shortcuts if b.action == "help"],
            )
        )

    def action_submit(self, command: str) -> None:
        self._controller.submit(command)

    def action_toggle_pause(self) -> None:
        self._controller.toggle_pause()

    def action_toggle_explain(self) -> None:
        self._set_explain(not self.query_one("#hint", Static).display)
        self.query_one(CommandInput).focus()

    def action_help_quit(self) -> None:
        """Ctrl+C is left for copying text, so say how to quit rather than let Textual name Ctrl+Q, which some terminals never pass along."""
        quit_key = next(
            (
                binding.key_display or key_label(binding.key)
                for binding in self.shortcuts
                if binding.action == "quit" and binding.show
            ),
            None,
        )
        message = (
            "Type [b]exit[/b] to quit."
            if quit_key is None
            else f"Press [b]{quit_key}[/b], or type [b]exit[/b], to quit."
        )
        self.notify(
            message,
            title="Do you want to quit?",
        )

    async def action_quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        # stopping a run can take a moment, so keep the event loop free while it winds down
        await asyncio.to_thread(self._controller.shutdown)
        if self._rain_seconds > 0:
            self.push_screen(RainScreen(self._rain_seconds), self._leave)
        else:
            self.exit()

    def _leave(self, _result: None) -> None:
        self.exit()

    async def _check_viewer(self) -> None:
        if not self._backend.is_running():
            await self.action_quit()

    def _set_explain(self, shown: bool) -> None:
        self.query_one("#hint", Static).display = shown
        self.query_one(ExplainButton).set_class(shown, "-open")
        self._refresh_explain()
        self._refresh_placeholder()

    def _find[W: Widget](
        self, widget_type: type[W], selector: str | None = None
    ) -> W | None:
        """The widget, or `None` once the screen is being torn down. Late messages and timer ticks can still arrive then, and must not crash the app on its way out."""
        try:
            if selector is None:
                return self.query_one(widget_type)
            return self.query_one(selector, widget_type)
        except NoMatches:
            return None

    def _refresh_explain(self) -> None:
        hint = self._find(Static, "#hint")
        command = self._find(CommandInput)
        if hint is not None and command is not None and hint.display:
            hint.update(
                Text(self._controller.describe(command.value), style=INK_SECONDARY)
            )

    def _refresh_placeholder(self) -> None:
        # with the hint showing, it already says what Enter does
        command = self._find(CommandInput)
        hint = self._find(Static, "#hint")
        if command is None or hint is None:
            return
        if hint.display:
            command.placeholder = CommandInput.PLACEHOLDER
        elif self._controller.status().state is RunState.PAUSED:
            command.placeholder = "Press Enter to step, or type a command"
        else:
            last = self._controller.status().last_command
            command.placeholder = f"Press Enter to repeat '{last}', or type a command"

    def _apply_status(self, status: ControllerStatus) -> None:
        bar = self._find(StatusBar)
        if bar is not None:
            bar.show(status)
        self._refresh_placeholder()
        self._refresh_explain()
        self.refresh_bindings()
        controls = self._find(ControlBar)
        if controls is not None:
            controls.show(status.state, self._controller.has_runtime)
        log = self._find(RichLog)
        if log is not None:
            summary = run_summary(status)
            log.border_subtitle = (
                None if summary is None else Content.from_rich_text(summary)
            )

    def _deliver(self, event: ControllerEvent) -> None:
        # log lines share one ordered buffer with the logging records, so they cannot overtake each other
        if isinstance(event, LogEvent):
            self._logs.put(event)
        else:
            self.post_message(ControllerMessage(event))

    def _flush_logs(self) -> None:
        log = self._find(RichLog)
        if log is None:
            return
        items, dropped = self._logs.take(LOG_LINES_PER_FLUSH)
        lines = [render_log_item(item) for item in items]
        if dropped:
            lines.insert(
                0,
                Text(
                    f"{dropped} log lines were skipped because they arrived too fast to show.",
                    style=str(WARNING),
                ),
            )
        if lines:
            log.write(Text("\n").join(lines))

    def _install_log_handler(self) -> None:
        root = logging.getLogger()
        self._saved_handlers = [h for h in root.handlers if isinstance(h, RichHandler)]
        for handler in self._saved_handlers:
            root.removeHandler(handler)
        handler = TuiLogHandler(self._logs)
        handler.addFilter(TerminalFilter())
        root.addHandler(handler)
        self._log_handler = handler

    def _remove_log_handler(self) -> None:
        root = logging.getLogger()
        if self._log_handler is not None:
            root.removeHandler(self._log_handler)
            self._log_handler = None
        for handler in self._saved_handlers:
            root.addHandler(handler)
        self._saved_handlers = []
