import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from rich.markup import escape

import mujoco_mojo.runtime as rt
from mujoco_mojo.mj_state import MjState
from mujoco_mojo.utils.log import get_logger

from .backends.base import ViewerBackend
from .session import OnReloadCallback
from .watcher import FileWatcher

logger = get_logger(__name__)

__all__ = [
    "COMMAND_SUGGESTIONS",
    "ControllerEvent",
    "ControllerStatus",
    "EventSink",
    "ExitEvent",
    "HelpEvent",
    "LogEvent",
    "Outcome",
    "ReloadedController",
    "ReloadedSession",
    "RunState",
    "StatusEvent",
]

COMMAND_SUGGESTIONS = (
    "gen",
    "run",
    "seed ",
    "trial ",
    "watch",
    "record",
    "dojo",
    "stop",
    "help",
    "exit",
    "explain ",
)
"""Command names offered as completions by the terminal UI."""

_BUSY_HINT = (
    "[dim]A run is in progress - type [bold]stop[/bold] or "
    "[bold]halt[/bold] to cancel it.[/dim]"
)
_COMMAND_WORDS = (
    "gen",
    "run",
    "seed",
    "trial",
    "watch",
    "record",
    "dojo",
    "stop",
    "halt",
    "help",
    "exit",
    "quit",
    "explain",
)
_STOP_WORDS = ("stop", "halt")
_EXIT_WORDS = ("exit", "quit", "q")
_HELP_WORDS = ("h", "help", "?")
_WATCH_WORDS = ("watch", "w")


class RunState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"


class Outcome(StrEnum):
    """How the most recent job ended."""

    SUCCESS = "success"
    SATISFIED = "satisfied"
    TERMINATED = "terminated"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True)
class ControllerStatus:
    """Snapshot of everything the terminal UI shows about the session."""

    state: RunState
    last_command: str
    seed: int | None
    trial_num: int
    playback_speed: float
    watch: bool
    record: bool
    last_duration: float | None
    last_outcome: Outcome | None


@dataclass(frozen=True)
class LogEvent:
    """A line for the log pane."""

    message: str
    markup: bool = True
    """Whether `message` is rich markup (the default) or plain text."""


@dataclass(frozen=True)
class StatusEvent:
    status: ControllerStatus


@dataclass(frozen=True)
class HelpEvent:
    """The user asked for the command list."""


@dataclass(frozen=True)
class ExitEvent:
    """The user asked to close Reloaded."""


ControllerEvent = LogEvent | StatusEvent | HelpEvent | ExitEvent
EventSink = Callable[[ControllerEvent], None]


class ReloadedSession(Protocol):
    """The slice of `MojoReloaded` the controller reads, writes, and calls."""

    runtime: str | None
    workdir: Path
    seed: int | None
    trial_num: int
    watch: bool
    record: bool
    playback_speed: float
    stop_event: threading.Event
    output_sink: Callable[[str], None] | None

    def generate_construct(
        self, use_runtime: bool, on_reload_callback: OnReloadCallback | None
    ) -> MjState: ...


class ReloadedController:
    """
    Holds the state of a Reloaded session and turns commands into jobs, without knowing how either is displayed.

    The terminal UI sends typed commands to `submit` and receives `ControllerEvent`s through the sink. The sink is called from whichever thread produced the event (the caller of `submit`, the job thread, or the file watcher), so it must be thread safe.
    """

    def __init__(
        self,
        session: ReloadedSession,
        backend: ViewerBackend,
        *,
        watch_path: Path | None = None,
        sink: EventSink | None = None,
    ) -> None:
        self._session = session
        self._backend = backend
        self._watch_path = watch_path if watch_path is not None else Path.cwd()
        self._sink: EventSink = sink if sink is not None else _discard

        self._lock = threading.RLock()
        self._state = RunState.IDLE
        self._last_command = "run" if session.runtime else "gen"
        self._last_duration: float | None = None
        self._last_outcome: Outcome | None = None
        self._job_thread: threading.Thread | None = None
        self._watcher: FileWatcher | None = None

    @property
    def has_runtime(self) -> bool:
        """Whether the session was given a runtime function, i.e. whether `run` has anything to run."""
        return bool(self._session.runtime)

    def set_sink(self, sink: EventSink) -> None:
        self._sink = sink

    def status(self) -> ControllerStatus:
        with self._lock:
            return ControllerStatus(
                state=self._state,
                last_command=self._last_command,
                seed=self._session.seed,
                trial_num=self._session.trial_num,
                playback_speed=self._session.playback_speed,
                watch=self._session.watch,
                record=self._session.record,
                last_duration=self._last_duration,
                last_outcome=self._last_outcome,
            )

    def help_entries(self) -> list[tuple[str, str]]:
        """Command and description pairs for the help screen."""
        entries = [
            ("ENTER", "Repeat the last command"),
            ("gen", "Generate only"),
        ]
        if self._session.runtime:
            entries += [
                ("run", "Generate and run the runtime at the current speed"),
                (
                    "<float>",
                    "Set the speed, then generate and run (1.0 is real time, 0.5 is half speed)",
                ),
            ]
        entries += [
            ("seed <N>", "Set the seed (seed none clears it)"),
            ("trial <N>", "Set the trial number"),
            ("watch", "Toggle reloading when *.py files change"),
            ("record", "Toggle telemetry for mujoco-mojo dojo and video recording"),
            ("dojo", "Print the command that opens the Dojo for this session"),
            ("explain <cmd>", "Say what a command would do, without running it"),
            ("<cmd>?", "The same, written as a question (a lone ? opens help)"),
            ("stop / halt", "Abort the run in progress"),
            ("help", "Show this list"),
            ("exit / q", "Close Reloaded"),
        ]
        return entries

    def describe(self, text: str) -> str:
        """
        Says in one very short plain sentence what submitting `text` would do right now.

        It only reads the session's state and changes nothing, so the terminal UI can call it on every keystroke.
        """
        raw = text.strip().lower()
        status = self.status()

        target = self._explain_target(text)
        if target is not None:
            return (
                "Prints what Enter would do."
                if target == ""
                else "Prints what that would do."
            )

        if status.state is not RunState.IDLE:
            if raw in _STOP_WORDS:
                return "Aborts the current run."
            return "A run is in progress. Only stop works."

        if raw == "":
            if status.last_command == "gen":
                return "Repeats gen: generates only."
            if not self.has_runtime:
                return "Repeats run: generates only."
            return f"Repeats run at {status.playback_speed:g}x."
        if raw == "gen":
            return "Generates the model only."
        if raw == "run":
            if not self.has_runtime:
                return "No runtime given, so generates only."
            return f"Generates, then runs at {status.playback_speed:g}x."
        if raw in _EXIT_WORDS:
            return "Closes Reloaded."
        if raw in _HELP_WORDS:
            return "Opens help."
        if raw in _STOP_WORDS:
            return "Nothing is running to stop."
        if raw in _WATCH_WORDS:
            return f"Turns auto reload {'off' if status.watch else 'on'}."
        if raw == "record":
            return f"Turns recording {'off' if status.record else 'on'}."
        if raw == "dojo":
            return "Prints the Dojo command."
        if raw == "seed" or raw.startswith("seed "):
            return self._describe_seed(raw[4:].strip())
        if raw == "trial" or raw.startswith("trial "):
            return self._describe_trial(raw[5:].strip())

        try:
            speed = float(raw)
        except ValueError:
            return self._describe_unknown(raw)
        if not self._is_valid_speed(speed):
            return "Speed must be 0 or more."
        if not self.has_runtime:
            return f"Sets speed to {speed:g}x, then generates only."
        return f"Sets speed to {speed:g}x, then runs."

    @staticmethod
    def _describe_seed(arg: str) -> str:
        if arg == "":
            return "Needs a number, or none."
        if arg in ("none", "null"):
            return "Clears the seed."
        try:
            return f"Sets the seed to {int(arg)}."
        except ValueError:
            return "Seed must be an integer or none."

    @staticmethod
    def _describe_trial(arg: str) -> str:
        if arg == "":
            return "Needs a number."
        try:
            return f"Sets the trial to {int(arg)}."
        except ValueError:
            return "Trial must be an integer."

    @staticmethod
    def _describe_unknown(raw: str) -> str:
        matches = [word for word in _COMMAND_WORDS if word.startswith(raw)]
        if matches:
            return f"Press Tab to complete {matches[0]}."
        return "Not a command. Try help."

    def start(self) -> None:
        """Routes the session's own messages to the sink and starts the file watcher if enabled."""
        self._session.output_sink = self._on_session_output
        if self._session.watch:
            self._start_watcher()
        self._log(
            "[bold green]MuJoCo Mojo Reloaded is live.[/bold green] Type [bold cyan]help[/bold cyan] for commands."
        )
        self._emit_status()

    def shutdown(self) -> None:
        """Stops the watcher and any run in progress. Safe to call more than once."""
        self._stop_watcher()
        with self._lock:
            thread = self._job_thread
            busy = self._state is not RunState.IDLE
        if busy:
            self._session.stop_event.set()
            if thread is not None:
                thread.join(timeout=5)
        self._session.output_sink = None

    def submit(self, text: str) -> None:
        """Handles one line typed by the user. An empty line repeats the last command."""
        raw = text.strip().lower()

        target = self._explain_target(text)
        if target is not None:
            self._explain(target)
            return

        if self.status().state is not RunState.IDLE:
            if raw in _STOP_WORDS:
                self._request_stop()
            else:
                self._log(_BUSY_HINT)
            return

        if raw in _EXIT_WORDS:
            self._emit(ExitEvent())
        elif raw in _STOP_WORDS:
            self._log("[dim]No run is currently in progress.[/dim]")
        elif raw in _HELP_WORDS:
            self._emit(HelpEvent())
        elif raw in _WATCH_WORDS:
            self.toggle_watch()
        elif raw == "dojo":
            self._show_dojo_hint()
        elif raw == "record":
            self.toggle_record()
        elif raw.startswith("seed "):
            self.set_seed(raw[5:])
        elif raw.startswith("trial "):
            self.set_trial(raw[6:])
        else:
            self._run_command(raw)

    def on_file_change(self, count: int) -> None:
        """Reloads with the last command when watched source files change, unless a run is in progress."""
        plural = "s" if count != 1 else ""
        with self._lock:
            busy = self._state is not RunState.IDLE
            last_command = self._last_command

        if busy:
            self._log(
                f"[dim]{count} change{plural} detected, but a run is in "
                "progress - ignoring. Save again once it finishes to reload.[/dim]"
            )
            return

        self._log(
            f"[dim]{count} change{plural} detected, reloading with last command...[/dim]"
        )
        self._start_job(use_runtime=last_command != "gen")

    @staticmethod
    def _explain_target(text: str) -> str | None:
        """The command to explain if `text` asks for an explanation (`explain seed 42`, `seed 42?`), the empty string for a bare `explain`, or `None` if it is an ordinary command."""
        stripped = text.strip()
        lowered = stripped.lower()
        if lowered == "explain":
            return ""
        if lowered.startswith("explain "):
            return stripped[len("explain ") :].strip().removesuffix("?").strip()
        if lowered.endswith("?") and lowered != "?":
            return stripped.removesuffix("?").strip()
        return None

    def _explain(self, target: str) -> None:
        label = escape(target) if target else "Enter"
        self._log(f"[bold]{label}[/bold]: {escape(self.describe(target))}")

    def _run_command(self, raw: str) -> None:
        if raw not in ("", "gen", "run"):
            try:
                speed = float(raw)
            except ValueError:
                self._log(
                    f"[bold red]Unknown command:[/bold red] '{escape(raw)}'. Type [bold cyan]help[/bold cyan] for the command list."
                )
                return
            if not self._is_valid_speed(speed):
                self._log_invalid_speed()
                return
            self._apply_speed(speed)

        with self._lock:
            command = raw if raw else self._last_command
            self._last_command = command

        if command != "gen" and not self._session.runtime:
            self._log(
                "[dim]No runtime was given, so there is nothing to run. Generating only.[/dim]"
            )
        self._log("[dim]Processing...[/dim]")
        self._start_job(use_runtime=command != "gen")

    def set_seed(self, arg: str) -> None:
        """Sets the seed from text. An empty string, `none`, or `null` clears it. Refused while a run is in progress."""
        if not self._idle_or_hint():
            return
        arg = arg.strip().lower()
        if arg in ("", "none", "null"):
            self._session.seed = None
            self._log("[dim]Seed cleared.[/dim]")
        else:
            try:
                self._session.seed = int(arg)
            except ValueError:
                self._log(
                    "[bold red]Invalid seed.[/bold red] Use: seed <integer> or seed none"
                )
                return
            self._log(f"[dim]Seed set to {self._session.seed}.[/dim]")
        self._emit_status()

    def set_trial(self, arg: str) -> None:
        """Sets the trial number from text. Refused while a run is in progress."""
        if not self._idle_or_hint():
            return
        try:
            self._session.trial_num = int(arg.strip())
        except ValueError:
            self._log("[bold red]Invalid trial number.[/bold red] Use: trial <integer>")
            return
        self._log(f"[dim]Trial number set to {self._session.trial_num}.[/dim]")
        self._emit_status()

    def set_speed(self, arg: str) -> None:
        """Sets the playback speed for the next run, without starting one. 1.0 is real time and 0 runs as fast as possible. Refused while a run is in progress."""
        if not self._idle_or_hint():
            return
        try:
            speed = float(arg.strip())
        except ValueError:
            self._log_invalid_speed()
            return
        if not self._is_valid_speed(speed):
            self._log_invalid_speed()
            return
        self._apply_speed(speed)

    def toggle_record(self) -> None:
        """Turns telemetry recording on or off. Refused while a run is in progress."""
        if not self._idle_or_hint():
            return
        self._session.record = not self._session.record
        if self._session.record:
            self._log(
                "[dim]Telemetry recording enabled - "
                "the next reload will be visible in `mujoco-mojo dojo`.[/dim]"
            )
        else:
            self._log("[dim]Telemetry recording disabled[/dim]")
        self._emit_status()

    def toggle_watch(self) -> None:
        """Turns reloading on file changes on or off. Refused while a run is in progress."""
        if not self._idle_or_hint():
            return
        self._session.watch = not self._session.watch
        if self._session.watch:
            self._start_watcher()
            self._log("[dim]Auto-watch enabled[/dim]")
        else:
            self._stop_watcher()
            self._log("[dim]Auto-watch disabled[/dim]")
        self._emit_status()

    def _idle_or_hint(self) -> bool:
        """Whether a setting may change now. If a run is in progress, says so in the log and returns `False`."""
        if self.status().state is RunState.IDLE:
            return True
        self._log(_BUSY_HINT)
        return False

    @staticmethod
    def _is_valid_speed(speed: float) -> bool:
        return math.isfinite(speed) and speed >= 0

    def _log_invalid_speed(self) -> None:
        self._log(
            "[bold red]Invalid speed.[/bold red] Use a number of 0 or more "
            "(1.0 is real time, 0 runs as fast as possible)."
        )

    def _apply_speed(self, speed: float) -> None:
        self._session.playback_speed = speed
        self._log(f"[dim]Playback speed set to {speed:g}x[/dim]")
        self._emit_status()

    def _show_dojo_hint(self) -> None:
        hint = (
            "\n[dim]Note: telemetry recording is currently off, so the "
            "Dojo won't have trial data until you enable [bold]record[/bold].[/dim]"
            if not self._session.record
            else ""
        )
        self._log(
            "[dim]Run this in another terminal to monitor this session:[/dim]\n"
            f'[bold cyan]mujoco-mojo dojo "{escape(str(self._session.workdir))}"[/bold cyan]'
            f"{hint}"
        )

    def _start_watcher(self) -> None:
        if self._watcher is None:
            self._watcher = FileWatcher(self._watch_path, self.on_file_change)
        self._watcher.start()

    def _stop_watcher(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None

    def _request_stop(self) -> None:
        with self._lock:
            if self._state is RunState.IDLE:
                return
            self._state = RunState.STOPPING
        self._session.stop_event.set()
        self._log("[bold yellow]Stopping the current run...[/bold yellow]")
        self._emit_status()

    def _start_job(self, use_runtime: bool) -> None:
        """Runs a generation, and optionally the runtime, on a background thread. Does nothing if one is already running."""
        with self._lock:
            if self._state is not RunState.IDLE:
                return
            self._session.stop_event.clear()
            self._state = RunState.RUNNING
            thread = threading.Thread(
                target=self._job,
                args=(use_runtime,),
                daemon=True,
                name="reloaded-job",
            )
            self._job_thread = thread
        self._emit_status()
        thread.start()

    def _job(self, use_runtime: bool) -> None:
        start = time.time()
        outcome = Outcome.FAILED
        try:
            new_state = self._session.generate_construct(
                use_runtime=use_runtime, on_reload_callback=self._backend.on_reload
            )
            self._backend.on_reload(new_state)
            outcome = Outcome.SUCCESS
            message = f"[dim white]Model Reloaded in [bold]{time.time() - start:.2f}s[/bold].[/dim white]"
        except rt.RequirementSatisfied as e:
            outcome = Outcome.SATISFIED
            message = f"[bold green]Run ended early, requirement satisfied: {escape(str(e))}[/bold green]"
        except rt.RequirementTerminated as e:
            outcome = Outcome.TERMINATED
            message = f"[bold yellow]Run terminated by requirement: {escape(str(e))}[/bold yellow]"
        except rt.SimulationStopped:
            outcome = Outcome.STOPPED
            message = "[bold yellow]Run stopped by user.[/bold yellow]"
        except Exception as e:
            logger.exception(e)
            message = (
                f"[bold red]Reload Failed:[/bold red]\n[white]{escape(str(e))}[/white]"
            )
        finally:
            self._session.stop_event.clear()
            with self._lock:
                self._state = RunState.IDLE
                self._last_duration = time.time() - start
                self._last_outcome = outcome

        self._log(message)
        self._emit_status()

    def _on_session_output(self, message: str) -> None:
        self._log(message)

    def _log(self, message: str, markup: bool = True) -> None:
        self._emit(LogEvent(message=message, markup=markup))

    def _emit_status(self) -> None:
        self._emit(StatusEvent(status=self.status()))

    def _emit(self, event: ControllerEvent) -> None:
        self._sink(event)


def _discard(event: ControllerEvent) -> None:
    pass
