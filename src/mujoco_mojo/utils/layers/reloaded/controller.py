import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from rich.markup import escape

import mujoco_mojo.runtime as rt
from mujoco_mojo.mj_state import MjState
from mujoco_mojo.utils.log import get_logger

from .backends.base import OnReloadCallback, ViewerBackend
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
    "speed_label",
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
    "explain ",
    "generate",
    "quit",
    "runtime",
    "run until time ",
    "run until step ",
    "pause",
    "step ",
    "speed ",
)
"""Command names offered as completions by the terminal UI."""

_HOLD_HELP = (
    "Type [bold]run[/bold] to carry on, [bold]step[/bold] or press Enter to advance, "
    "or [bold]stop[/bold] to end the run."
)
_MANUAL_HELP = (
    "Speed is 0, so the run steps only when you press Enter. "
    "Give a speed, as in [bold]run 1[/bold], to let it run."
)
_INVALID_TARGET = (
    "[bold red]Invalid target.[/bold red] Use: run until time <N> or run until step <N>"
)
_BUSY_HINT = (
    "[dim]A run is in progress - type [bold]stop[/bold] to cancel it, or "
    "[bold]pause[/bold], [bold]step[/bold], [bold]speed[/bold], or [bold]run[/bold] to control it.[/dim]"
)
_COMMAND_WORDS = (
    "gen",
    "generate",
    "run",
    "seed",
    "trial",
    "watch",
    "record",
    "dojo",
    "stop",
    "halt",
    "pause",
    "step",
    "speed",
    "help",
    "quit",
    "explain",
)
_ALIASES = {
    "gen": ("g", "generate"),
    "run": ("r", "runtime"),
    "watch": ("w",),
    "record": ("rec",),
    "stop": ("halt", "abort"),
    "help": ("h", "?"),
    "pause": ("p",),
}
"""Other words for each command that takes no argument."""
_CANONICAL = {
    alias: command for command, aliases in _ALIASES.items() for alias in aliases
}


def speed_label(speed: float) -> str:
    """A speed as it is written in the status bar and the log: `manual` for 0, which steps only on Enter, `inf` for as fast as the machine goes, and otherwise a multiple of real time such as `0.5x`."""
    if speed == 0:
        return "manual"
    if math.isinf(speed):
        return "inf"
    return f"{speed:g}x"


def _canonical(word: str) -> str:
    """The command a word stands for, so `g` and `generate` both read as `gen`. Anything that is not an alias comes back unchanged."""
    return _CANONICAL.get(word, word)


def _words(command: str) -> str:
    """A command and its aliases, as shown in the help."""
    return " / ".join((command, *_ALIASES[command]))


class RunState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
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
    run_control: rt.RunControl
    output_sink: Callable[[str], None] | None

    def generate_construct(
        self, use_runtime: bool, on_reload_callback: OnReloadCallback | None
    ) -> MjState: ...


def _discard(event: ControllerEvent) -> None:
    pass


@dataclass(eq=False)
class ReloadedController:
    """
    Holds the state of a Reloaded session and turns commands into jobs, without knowing how either is displayed.

    The terminal UI sends typed commands to `submit` and receives `ControllerEvent`s through the sink. The sink is called from whichever thread produced the event (the caller of `submit`, the job thread, or the file watcher), so it must be thread safe.
    """

    session: ReloadedSession
    """What the controller reads and changes, and whose `generate_construct` it runs."""
    backend: ViewerBackend
    """The viewer a generated model is shown in."""
    watch_path: Path = field(default_factory=Path.cwd, kw_only=True)
    """The directory watched for `*.py` changes when watching is on. Defaults to the current directory."""
    sink: EventSink = field(default=_discard, kw_only=True)
    """Receives every `ControllerEvent`, from whichever thread produced it."""

    _lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )
    _state: RunState = field(default=RunState.IDLE, init=False, repr=False)
    _last_command: str = field(init=False, repr=False)
    _last_duration: float | None = field(default=None, init=False, repr=False)
    _last_outcome: Outcome | None = field(default=None, init=False, repr=False)
    _job_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _watcher: FileWatcher | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._last_command = "run" if self.session.runtime else "gen"

    @property
    def has_runtime(self) -> bool:
        """Whether the session was given a runtime function, i.e. whether `run` has anything to run."""
        return bool(self.session.runtime)

    def status(self) -> ControllerStatus:
        with self._lock:
            return ControllerStatus(
                state=self._state,
                last_command=self._last_command,
                seed=self.session.seed,
                trial_num=self.session.trial_num,
                playback_speed=self.session.playback_speed,
                watch=self.session.watch,
                record=self.session.record,
                last_duration=self._last_duration,
                last_outcome=self._last_outcome,
            )

    def help_entries(self) -> list[tuple[str, str]]:
        """Command and description pairs for the help screen."""
        entries = [
            ("ENTER", "Repeat the last command, or step a paused run"),
            (_words("gen"), "Generate only"),
        ]
        if self.session.runtime:
            entries += [
                (
                    f"{_words('run')} [X]",
                    "Generate and run the runtime, at speed X if given (1.0 is real time, 0.5 is half). Carries a paused run on",
                ),
                (
                    "run [X] until time <N>",
                    "Run, then pause when the simulation time reaches N",
                ),
                (
                    "run [X] until step <N>",
                    "Run, then pause once N steps have been taken since the run began",
                ),
                (
                    "speed <X>",
                    "Set the playback speed, even during a run: a multiple of real time, 0 to step by hand with Enter, or inf for as fast as possible",
                ),
                (_words("pause"), "Hold the run in progress where it is"),
                (
                    "step [N]",
                    "Advance a run by N steps (1 if left out), pausing it first",
                ),
            ]
        entries += [
            ("seed <N>", "Set the seed (seed none clears it)"),
            ("trial <N>", "Set the trial number"),
            (_words("watch"), "Toggle reloading when *.py files change"),
            (
                _words("record"),
                "Toggle telemetry for mujoco-mojo dojo and video recording",
            ),
            ("dojo", "Print the command that opens the Dojo for this session"),
            ("explain <cmd>", "Say what a command would do, without running it"),
            ("<cmd>?", "The same, written as a question (a lone ? opens help)"),
            (_words("stop"), "Abort the run in progress"),
            (_words("help"), "Show this list"),
            ("quit", "Close Reloaded. To end a run, use stop"),
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

        # a command that takes no argument only matches on its own, so `gen now` is not `gen`
        command, _, arg = raw.partition(" ")
        command, arg = _canonical(command), arg.strip()

        if status.state is not RunState.IDLE:
            return self._describe_while_running(command, arg, status.state)

        match (command, arg):
            case ("", ""):
                if status.last_command == "gen":
                    return "Repeats gen: generates only."
                if not self.has_runtime:
                    return "Repeats run: generates only."
                if status.playback_speed == 0:
                    return "Repeats run: steps on Enter."
                return f"Repeats run at {speed_label(status.playback_speed)}."
            case ("gen", ""):
                return "Generates the model only."
            case ("run", _):
                return self._describe_run(arg, status.playback_speed)
            case ("quit", ""):
                return "Closes Reloaded."
            case ("help", ""):
                return "Opens help."
            case ("stop", ""):
                return "Nothing is running to stop."
            case ("pause", ""):
                return "Nothing is running to pause."
            case ("step", _):
                return "Nothing is running to step."
            case ("speed", _):
                return self._describe_speed(arg, running=False)
            case ("watch", ""):
                return f"Turns auto reload {'off' if status.watch else 'on'}."
            case ("record", ""):
                return f"Turns recording {'off' if status.record else 'on'}."
            case ("dojo", ""):
                return "Prints the Dojo command."
            case ("seed", _):
                return self._describe_seed(arg)
            case ("trial", _):
                return self._describe_trial(arg)
            case _:
                return self._describe_unknown(raw)

    def _describe_while_running(self, command: str, arg: str, state: RunState) -> str:
        paused = state is RunState.PAUSED
        match (command, arg):
            case ("stop", ""):
                return "Aborts the current run."
            case _ if state is RunState.STOPPING:
                return "The run is stopping."
            case ("", "") if paused:
                return "Advances 1 step."
            case ("pause", ""):
                return "Already paused." if paused else "Pauses the run."
            case ("run", _):
                return self._describe_run_in_progress(arg, paused)
            case ("step", _):
                return self._describe_step(arg, paused)
            case ("speed", _):
                return self._describe_speed(arg, running=True)
            case _:
                return (
                    "Paused. Try run, step, or stop."
                    if paused
                    else "A run is in progress. Try pause or stop."
                )

    @staticmethod
    def _describe_step(arg: str, paused: bool) -> str:
        try:
            count = int(arg or 1)
        except ValueError:
            count = 0
        if count < 1:
            return "Step takes a whole number, 1 or more."
        steps = "1 step" if count == 1 else f"{count} steps"
        return f"Advances {steps}." if paused else f"Pauses, then advances {steps}."

    def _describe_run(self, arg: str, current_speed: float) -> str:
        speed_text, target_words = self._split_run(arg)
        if problem := self._run_problem(speed_text, target_words):
            return problem
        speed = current_speed if speed_text is None else float(speed_text)
        if not self.has_runtime:
            return "No runtime given, so generates only."
        target = self._read_target(target_words) if target_words else None
        if speed == 0:
            return "Generates, then steps on Enter."
        if target is not None:
            return f"Runs at {speed_label(speed)}, pauses at {target.label}."
        return f"Generates, then runs at {speed_label(speed)}."

    def _describe_run_in_progress(self, arg: str, paused: bool) -> str:
        speed_text, target_words = self._split_run(arg)
        if problem := self._run_problem(speed_text, target_words):
            return problem
        if speed_text is not None and float(speed_text) == 0:
            return self._describe_speed(speed_text, running=True)
        if paused and speed_text is None and self.session.playback_speed == 0:
            return "Speed is 0, so it steps only on Enter."
        target = self._read_target(target_words) if target_words else None
        if target is not None and target.reached(*self.session.run_control.position):
            return f"Already at or past {target.label}."

        if target is None:
            if speed_text is None:
                return "Resumes the run." if paused else "The run is already going."
            if paused:
                return f"Resumes at {speed_label(float(speed_text))}."
            return self._describe_speed(speed_text, running=True)
        if speed_text is None:
            if paused:
                return f"Resumes, pausing at {target.label}."
            return f"Pauses when the run reaches {target.label}."
        speed = speed_label(float(speed_text))
        if paused:
            return f"Resumes at {speed}, pauses at {target.label}."
        return f"Sets speed to {speed}, pauses at {target.label}."

    def _run_problem(
        self, speed_text: str | None, target_words: list[str]
    ) -> str | None:
        """Why what follows `run` is not a speed and a target, or `None` if it is."""
        if speed_text is not None and (problem := self._speed_problem(speed_text)):
            return problem
        if target_words and self._read_target(target_words) is None:
            return "Use: run until time N or step N."
        return None

    def _describe_speed(self, arg: str, running: bool) -> str:
        if arg == "":
            return "Sets the speed, e.g. speed 0.5 for half."
        if problem := self._speed_problem(arg):
            return problem
        speed = float(arg)
        scope = "this" if running else "the next"
        if speed == 0:
            return f"Steps only on Enter for {scope} run."
        return f"Sets speed to {speed_label(speed)} for {scope} run."

    @classmethod
    def _speed_problem(cls, arg: str) -> str | None:
        """Why `arg` is not a speed, or `None` if it is one."""
        try:
            speed = float(arg)
        except ValueError:
            return "Speed must be a number."
        return None if cls._is_valid_speed(speed) else "Speed must be 0 or more."

    @staticmethod
    def _describe_seed(arg: str) -> str:
        if arg == "":
            return "Sets the seed, e.g. seed 42 or seed none."
        if arg in ("none", "null"):
            return "Clears the seed."
        try:
            return f"Sets the seed to {int(arg)}."
        except ValueError:
            return "Seed must be an integer or none."

    @staticmethod
    def _describe_trial(arg: str) -> str:
        if arg == "":
            return "Sets the trial number, e.g. trial 3."
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
        self.session.output_sink = self._on_session_output
        self.session.run_control.on_hold = self._on_hold
        if self.session.watch:
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
            self.session.stop_event.set()
            if thread is not None:
                thread.join(timeout=5)
        self.session.output_sink = None
        self.session.run_control.on_hold = None

    def submit(self, text: str) -> None:
        """Handles one line typed by the user. An empty line repeats the last command."""
        raw = text.strip().lower()

        target = self._explain_target(text)
        if target is not None:
            self._explain(target)
            return

        # a command that takes no argument only matches on its own, so `gen now` is not `gen`
        command, _, arg = raw.partition(" ")
        command, arg = _canonical(command), arg.strip()

        if self.status().state is not RunState.IDLE:
            self._submit_while_running(command, arg)
            return

        match (command, arg):
            case ("quit", ""):
                self._emit(ExitEvent())
            case ("stop", ""):
                self._log("[dim]No run is currently in progress.[/dim]")
            case ("pause", ""):
                self.pause()
            case ("step", _):
                self.step(arg)
            case ("speed", _):
                self.set_speed(arg)
            case ("help", ""):
                self._emit(HelpEvent())
            case ("watch", ""):
                self.toggle_watch()
            case ("dojo", ""):
                self._show_dojo_hint()
            case ("record", ""):
                self.toggle_record()
            case ("seed", _) if arg:
                self.set_seed(arg)
            case ("trial", _) if arg:
                self.set_trial(arg)
            case ("", ""):
                with self._lock:
                    last_command = self._last_command
                self._start(last_command)
            case ("gen", ""):
                self._start("gen")
            case ("run", _):
                self.run(arg)
            case _:
                self._log(
                    f"[bold red]Unknown command:[/bold red] '{escape(raw)}'. Type [bold cyan]help[/bold cyan] for the command list."
                )

    def _submit_while_running(self, command: str, arg: str) -> None:
        """What may be typed during a run: stop it, hold it, carry it on, step it, or change its speed. Enter steps a paused run. Anything else waits for it to end."""
        match (command, arg):
            case ("", "") if self.status().state is RunState.PAUSED:
                self.step("")
            case ("stop", ""):
                self._request_stop()
            case ("pause", ""):
                self.pause()
            case ("run", _):
                self.run(arg)
            case ("step", _):
                self.step(arg)
            case ("speed", _):
                self.set_speed(arg)
            case _:
                self._log(_BUSY_HINT)

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

    def run(self, arg: str = "") -> None:
        """
        Generates and runs the runtime, or carries a paused run on.

        `arg` is an optional speed followed by an optional target, as in `0.5`, `until time 3`, or `0.5 until step 500`. The speed is set first, so `run 0.5` is a run at half speed, and the run pauses itself when it reaches the target. For a run that is already going it only changes the speed or sets the target.
        """
        speed_text, target_words = self._split_run(arg)
        speed: float | None = None
        if speed_text is not None:
            speed = self._parse_speed(speed_text)
            if speed is None:
                return
        target: rt.RunTarget | None = None
        if target_words:
            target = self._read_target(target_words)
            if target is None:
                self._log(_INVALID_TARGET)
                return

        state = self.status().state
        if state is RunState.STOPPING:
            self._log(self._cannot(state, "run"))
            return
        if target is not None and state is not RunState.IDLE:
            if target.reached(*self.session.run_control.position):
                time_now, steps_now = self.session.run_control.position
                self._log(
                    f"[bold red]Already at or past {target.label}[/bold red] "
                    f"- the run is at time {time_now:g}, step {steps_now}."
                )
                return
        if speed is not None:
            self._apply_speed(speed)
        if target is not None:
            self._log(f"[dim]Will pause at {target.label}.[/dim]")

        match state:
            case RunState.IDLE:
                self._start("run", target)
            case RunState.PAUSED:
                if self.session.playback_speed == 0:
                    self._log(f"[dim]{_MANUAL_HELP}[/dim]")
                else:
                    self.session.run_control.run_until(target)
                    self.resume()
            case RunState.RUNNING:
                self.session.run_control.run_until(target)
                if speed is None and target is None:
                    self._log("[dim]The run is already going.[/dim]")
            case RunState.STOPPING:
                pass

    @staticmethod
    def _split_run(arg: str) -> tuple[str | None, list[str]]:
        """The speed written in `run`'s argument, if any, and the words of the target after it."""
        words = arg.split()
        if words and words[0] != "until":
            return words[0], words[1:]
        return None, words

    @staticmethod
    def _read_target(words: list[str]) -> rt.RunTarget | None:
        """The target `until time <N>` or `until step <N>` writes, or `None` if the words are anything else."""
        if len(words) != 3 or words[0] != "until":
            return None
        match words[1]:
            case "time":
                kind = rt.TargetKind.TIME
            case "step" | "steps":
                kind = rt.TargetKind.STEP
            case _:
                return None
        try:
            value = float(words[2])
        except ValueError:
            return None
        if not math.isfinite(value) or value < 0:
            return None
        if kind is rt.TargetKind.STEP and value != int(value):
            return None
        return rt.RunTarget(kind, value)

    def _start(self, command: str, target: rt.RunTarget | None = None) -> None:
        """Starts a generation, and the runtime too unless `command` is `gen`, and remembers `command` for the next ENTER. A run pauses itself at `target` if there is one."""
        with self._lock:
            self._last_command = command
        if command != "gen" and not self.session.runtime:
            self._log(
                "[dim]No runtime was given, so there is nothing to run. Generating only.[/dim]"
            )
        self._log("[dim]Processing...[/dim]")
        if (
            command != "gen"
            and self.session.runtime
            and self.session.playback_speed == 0
        ):
            self._log(f"[dim]{_MANUAL_HELP}[/dim]")
        self._start_job(use_runtime=command != "gen", target=target)

    def set_seed(self, arg: str) -> None:
        """Sets the seed from text. An empty string, `none`, or `null` clears it. Refused while a run is in progress."""
        if not self._idle_or_hint():
            return
        arg = arg.strip().lower()
        if arg in ("", "none", "null"):
            self.session.seed = None
            self._log("[dim]Seed cleared.[/dim]")
        else:
            try:
                self.session.seed = int(arg)
            except ValueError:
                self._log(
                    "[bold red]Invalid seed.[/bold red] Use: seed <integer> or seed none"
                )
                return
            self._log(f"[dim]Seed set to {self.session.seed}.[/dim]")
        self._emit_status()

    def set_trial(self, arg: str) -> None:
        """Sets the trial number from text. Refused while a run is in progress."""
        if not self._idle_or_hint():
            return
        try:
            self.session.trial_num = int(arg.strip())
        except ValueError:
            self._log("[bold red]Invalid trial number.[/bold red] Use: trial <integer>")
            return
        self._log(f"[dim]Trial number set to {self.session.trial_num}.[/dim]")
        self._emit_status()

    def set_speed(self, arg: str) -> None:
        """Sets the playback speed, without starting a run. 1.0 is real time and 0 runs as fast as possible. A run in progress picks the new speed up at its next step."""
        speed = self._parse_speed(arg)
        if speed is not None:
            self._apply_speed(speed)

    def _parse_speed(self, arg: str) -> float | None:
        """The speed `arg` writes, or `None` after saying why it is not one."""
        try:
            speed = float(arg.strip())
        except ValueError:
            self._log_invalid_speed()
            return None
        if not self._is_valid_speed(speed):
            self._log_invalid_speed()
            return None
        return speed

    def pause(self) -> None:
        """Holds a run in progress at its next step."""
        with self._lock:
            state = self._state
            if state is RunState.RUNNING:
                self._state = RunState.PAUSED
                self.session.run_control.pause()
        if state is RunState.RUNNING:
            self._log(f"[dim]Paused. {_HOLD_HELP}[/dim]")
            self._emit_status()
        else:
            self._log(self._cannot(state, "pause"))

    def resume(self) -> None:
        """Lets a paused run carry on."""
        with self._lock:
            state = self._state
            if state is RunState.PAUSED:
                self._state = RunState.RUNNING
                self.session.run_control.resume()
        if state is RunState.PAUSED:
            self._log("[dim]Resumed.[/dim]")
            self._emit_status()
        elif state is RunState.RUNNING:
            self._log("[dim]The run is not paused.[/dim]")
        else:
            self._log(self._cannot(state, "resume"))

    def toggle_pause(self) -> None:
        """Pauses a run that is going and resumes one that is paused, which is what a single pause key does."""
        if self.status().state is RunState.PAUSED:
            self.resume()
        else:
            self.pause()

    def step(self, arg: str = "") -> None:
        """Advances a run in progress by `arg` steps, or by one if it is empty, and leaves it paused. A run that is going is paused first."""
        try:
            count = int(arg.strip() or 1)
        except ValueError:
            count = 0
        if count < 1:
            self._log(
                "[bold red]Invalid step count.[/bold red] Use: step or step <whole number>"
            )
            return
        with self._lock:
            state = self._state
            if state in (RunState.RUNNING, RunState.PAUSED):
                self._state = RunState.PAUSED
                self.session.run_control.step(count)
        if state in (RunState.RUNNING, RunState.PAUSED):
            self._log(f"[dim]Stepping {count} step{'s' if count != 1 else ''}.[/dim]")
            if state is RunState.RUNNING:
                self._emit_status()
        else:
            self._log(self._cannot(state, "step"))

    @staticmethod
    def _cannot(state: RunState, action: str) -> str:
        """Why `action` did nothing in `state`."""
        if state is RunState.STOPPING:
            return "[dim]The run is stopping.[/dim]"
        if state is RunState.PAUSED:
            return "[dim]Already paused.[/dim]"
        if action == "resume":
            return "[dim]Nothing is paused.[/dim]"
        return f"[dim]Nothing is running to {action}.[/dim]"

    def toggle_record(self) -> None:
        """Turns telemetry recording on or off. Refused while a run is in progress."""
        if not self._idle_or_hint():
            return
        self.session.record = not self.session.record
        if self.session.record:
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
        self.session.watch = not self.session.watch
        if self.session.watch:
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
        return speed >= 0

    def _log_invalid_speed(self) -> None:
        self._log(
            "[bold red]Invalid speed.[/bold red] Use a number above 0 "
            "(1.0 is real time), 0 to step by hand with Enter, or inf to run as fast as possible."
        )

    def _apply_speed(self, speed: float) -> None:
        self.session.playback_speed = speed
        if self.status().state is not RunState.IDLE:
            self.session.run_control.set_speed(speed)
        if speed == 0:
            message = (
                "Playback speed set to 0: the run steps only when you press Enter."
            )
        elif math.isinf(speed):
            message = "Playback speed set to inf: as fast as possible."
        else:
            message = f"Playback speed set to {speed:g}x"
        self._log(f"[dim]{message}[/dim]")
        self._emit_status()

    def _show_dojo_hint(self) -> None:
        hint = (
            "\n[dim]Note: telemetry recording is currently off, so the "
            "Dojo won't have trial data until you enable [bold]record[/bold].[/dim]"
            if not self.session.record
            else ""
        )
        self._log(
            "[dim]Run this in another terminal to monitor this session:[/dim]\n"
            f'[bold cyan]mujoco-mojo dojo "{escape(str(self.session.workdir))}"[/bold cyan]'
            f"{hint}"
        )

    def _start_watcher(self) -> None:
        if self._watcher is None:
            self._watcher = FileWatcher(self.watch_path, self.on_file_change)
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
        self.session.stop_event.set()
        self._log("[bold yellow]Stopping the current run...[/bold yellow]")
        self._emit_status()

    def _start_job(self, use_runtime: bool, target: rt.RunTarget | None = None) -> None:
        """Runs a generation, and optionally the runtime, on a background thread, pausing the run at `target` if there is one. Does nothing if one is already running."""
        with self._lock:
            if self._state is not RunState.IDLE:
                return
            self.session.stop_event.clear()
            self.session.run_control.reset(self.session.playback_speed)
            self.session.run_control.run_until(target)
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
            new_state = self.session.generate_construct(
                use_runtime=use_runtime, on_reload_callback=self.backend.on_reload
            )
            self.backend.on_reload(new_state)
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
            self.session.stop_event.clear()
            self.session.run_control.reset()
            with self._lock:
                self._state = RunState.IDLE
                self._last_duration = time.time() - start
                self._last_outcome = outcome

        self._log(message)
        self._emit_status()

    def _on_hold(self, reason: str | None) -> None:
        """The run is about to be held, which is called from the job thread. A hold the user asked for, or manual stepping, has no reason, and one that came from reaching a target has the target's."""
        with self._lock:
            changed = self._state is RunState.RUNNING
            if changed:
                self._state = RunState.PAUSED
        if reason is not None:
            self._log(
                f"[bold yellow]Paused:[/bold yellow] {escape(reason)}. {_HOLD_HELP}"
            )
        if changed or reason is not None:
            self._emit_status()

    def _on_session_output(self, message: str) -> None:
        self._log(message)

    def _log(self, message: str, markup: bool = True) -> None:
        self._emit(LogEvent(message=message, markup=markup))

    def _emit_status(self) -> None:
        self._emit(StatusEvent(status=self.status()))

    def _emit(self, event: ControllerEvent) -> None:
        self.sink(event)
