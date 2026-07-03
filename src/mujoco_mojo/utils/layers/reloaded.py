import logging
import os
import queue
import sys
import threading
import time
import types
from bdb import BdbQuit
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast, runtime_checkable

import mujoco
import numpy as np
import typer
from numpydantic import NDArray
from rich.console import Console
from rich.panel import Panel

import mujoco_mojo.runtime as rt
from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.stochas import DesignValueDict, DistributionDict, NamedValueDict
from mujoco_mojo.utils.defaults import (
    DEFAULT_WORKDIR,
    NAMED_VALUES_FNAME,
    STOCHAS_DIR_NAME,
    STOCHAS_DISTS_FNAME,
)
from mujoco_mojo.utils.log import get_logger, get_trial_log_handler
from mujoco_mojo.utils.runner import MojoGenerator, MojoRunner, MojoRuntime
from mujoco_mojo.utils.statusing import (
    JOB_STATUS_FNAME,
    TRIAL_STATUS_FNAME,
    Completion,
    ExecutionMode,
    JobStatus,
    JobType,
    Step,
    TrialStatus,
)
from mujoco_mojo.utils.utils import write_dojo_script
from mujoco_mojo.visualization import ArrowConfig, LineConfig

from .cli import UserInterface

logger = get_logger(__name__)
console = Console()


@runtime_checkable
class OnReloadCallback(Protocol):
    def __call__(self, state: MjState) -> Any: ...


@runtime_checkable
class IsRunningCheck(Protocol):
    def __call__(self) -> Any: ...


def _matrix_rain(duration: float = 1.5, fps: int = 20) -> None:
    """Plays a brief Matrix-style digital rain animation, e.g. on exit."""
    import random

    from rich.live import Live
    from rich.text import Text

    width, height = console.size
    if width <= 0 or height <= 0:
        return

    drops = [random.randint(-height, 0) for _ in range(width)]
    trail_length = 8

    with Live(console=console, refresh_per_second=fps, screen=True) as live:
        for _ in range(int(duration * fps)):
            frame = Text()
            for row in range(height):
                for col in range(width):
                    head = drops[col]
                    if row == head:
                        frame.append(random.choice("01"), style="bold white")
                    elif 0 <= head - row <= trail_length:
                        frame.append(random.choice("01"), style="green")
                    else:
                        frame.append(" ")
                if row < height - 1:
                    frame.append("\n")

            for col in range(width):
                drops[col] += 1
                if drops[col] - height > random.randint(0, height):
                    drops[col] = random.randint(-height, 0)

            live.update(frame)
            time.sleep(1 / fps)


def recursive_reload(module, project_root: Path, visited: set | None = None):
    """Recursively reloads modules, but only if they live inside project_root."""
    import importlib
    import sys

    if visited is None:
        visited = set()

    if module in visited:
        return
    visited.add(module)

    # skip reloading these
    BLOCKLIST = {"numpy", "scipy", "matplotlib", "PIL", "cv2", "mujoco"}

    if getattr(module, "__name__", "") in BLOCKLIST:
        return

    # collect all submodules of the package
    submoduels_to_reload = []
    if hasattr(module, "__path__"):
        module_name = module.__name__
        # find all submodules in sys modules that belong to this package
        for name, mod in list(sys.modules.items()):
            if mod is not None and name.startswith(module_name + "."):
                mod_file = getattr(mod, "__file__", None)
                if mod_file:
                    mod_path = Path(mod_file).resolve()
                    is_local = mod_path.is_relative_to(project_root)
                    is_library = (
                        "site-packages" in mod_path.parts
                        or "dist-packages" in mod_path.parts
                    )
                    if is_local and not is_library and mod not in visited:
                        submoduels_to_reload.append(mod)

    # recursively reload discovered submodules first
    for submod in submoduels_to_reload:
        recursive_reload(submod, project_root, visited)

    # check objects in module dict for cross-moduel references
    for name in list(module.__dict__.keys()):
        obj = module.__dict__[name]
        if hasattr(obj, "__module__"):
            child_module_name = obj.__module__
            child_module = sys.modules.get(child_module_name)

            if child_module and child_module not in visited:
                child_file = getattr(child_module, "__file__", None)

                if child_file:
                    child_path = Path(child_file).resolve()

                    # must be inside project root AND NOT inside site-packages
                    is_local = child_path.is_relative_to(project_root)
                    is_library = (
                        "site-packages" in child_path.parts
                        or "dist-packages" in child_path.parts
                    )

                    if is_local and not is_library:
                        recursive_reload(child_module, project_root, visited)

    try:
        importlib.reload(module)
    except Exception as e:
        # a failed reload leaves the previous version of the module in sys.modules,
        # so swallowing here would silently keep running stale code - the error
        # (e.g. a SyntaxError in the edited file) must reach the caller
        logger.error(f"Failed to reload {module.__name__}: {e}")
        raise


@dataclass
class MojoReloaded:
    generator: str | None
    runtime: str | None
    workdir: Path
    ui: UserInterface
    overrides_path: Path | None
    config_path: Path | None
    trial_num: int
    seed: int | None
    model_config_name: str | None
    xml_name: str
    gen_args: list[Any]
    gen_kwargs: dict[str, Any]
    run_args: list[Any]
    run_kwargs: dict[str, Any]
    host: str
    port: int

    watch: bool = False
    record: bool = False

    _sync_hook: rt.runtime_manager.SyncHook | None = None
    _viewer_lock: Callable[[], AbstractContextManager[Any]] | None = None
    _playback_speed: float = 1.0
    _last_command: str = "run"
    _current_trial_dir: Path | None = None
    _job_status: JobStatus | None = None
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _print_lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False, compare=False
    )
    _reprint_prompt: Callable[[], None] | None = field(
        default=None, repr=False, compare=False
    )
    _line_buffer: str = field(default="", init=False, repr=False)
    _line_cursor: int = field(default=0, init=False, repr=False)

    _trial_padding_style = "03d"

    def _clear_line(self):
        """Writes the clear-line escape directly, bypassing rich's markup/highlighting which otherwise mangles raw ANSI control sequences. Caller must hold `_print_lock`."""
        if self._reprint_prompt is not None:
            console.file.write("\r\x1b[2K")
            console.file.flush()

    def _redraw_line(self):
        """Reprints the prompt plus any in-progress input line (with the cursor restored to its column), so async output never wipes out what the user was mid-typing. No-op if there's no active prompt. Caller must hold `_print_lock`."""
        if self._reprint_prompt is None:
            return
        self._reprint_prompt()
        if self._line_buffer:
            console.file.write(self._line_buffer)
        trailing = len(self._line_buffer) - self._line_cursor
        if trailing > 0:
            console.file.write(f"\x1b[{trailing}D")
        console.file.flush()

    def _print(self, *args, **kwargs):
        """Prints a message, redrawing the persistent prompt below it if the interactive loop is active."""
        with self._print_lock:
            self._clear_line()
            console.print(*args, **kwargs)
            self._redraw_line()

    def trial_dir_for(self, trial_num: int) -> Path:
        """
        Per-trial output directory, mirroring the layout `Trial`/`MojoRunner` use.

        Keeping this layout lets `mujoco-mojo dojo` discover and plot reloaded runs the same way it discovers Monte Carlo / Optimize trials.
        """
        return (
            self.workdir / "trials" / f"trial_{trial_num:{self._trial_padding_style}}"
        ).resolve()

    def _infer_padding_style(self) -> str:
        """
        Detects the zero-padding width already used by `trial_*` folders on disk, so reconnecting `reloaded` to an existing workdir (e.g. one a Monte Carlo / Optimize job created) extends it with matching folder names instead of creating a mismatched width alongside them (e.g. 'trial_0042' next to existing 'trial_00042's).

        Falls back to the current default if the workdir has no trial folders yet.
        """
        widths: set[int] = set()
        for p in (self.workdir / "trials").glob("trial_*"):
            suffix = p.name.removeprefix("trial_")
            if p.is_dir() and suffix.isdigit():
                widths.add(len(suffix))

        if not widths:
            return self._trial_padding_style

        return f"0{max(widths)}d"

    def _ensure_job_status(
        self, gen_func: MojoGenerator | None, run_func: MojoRuntime | None
    ) -> JobStatus:
        """
        Lazily builds the `JobStatus` tracker for this session, the same way `MojoRunner` does for a job.

        Seeds `trial_nums` from any `trial_*` folders already on disk and refreshes the cache from their `trial_status.json` files, so relaunching reloaded against an existing workdir picks up prior trials instead of starting from a blank slate.
        """
        if self._job_status is not None:
            return self._job_status

        on_disk: set[int] = set()
        for p in (self.workdir / "trials").glob("trial_*"):
            suffix = p.name.removeprefix("trial_")
            if p.is_dir() and suffix.isdigit():
                on_disk.add(int(suffix))

        job_status = JobStatus(
            workdir=self.workdir,
            job_type=JobType.RELOADED,
            execution_mode=ExecutionMode.LOCAL,
            n_proc=1,
            seed=self.seed,
            padding_style=self._trial_padding_style,
            generator=MojoRunner.inspect_protocol(gen_func),
            runtime=MojoRunner.inspect_protocol(run_func),
            objective=("none defined", None, None),
            gen_args_used=bool(self.gen_args),
            gen_kwargs_used=bool(self.gen_kwargs),
            run_args_used=bool(self.run_args),
            run_kwargs_used=bool(self.run_kwargs),
            trial_nums=sorted(on_disk | {self.trial_num}),
        )
        job_status.refresh_from_disk()
        job_status.dump_to_path(self.workdir / JOB_STATUS_FNAME)
        self._job_status = job_status
        return job_status

    @staticmethod
    def _record_step(trial_status: TrialStatus | None, step_name: Step):
        """Wraps `TrialStatus.record_step` when recording is enabled, otherwise a no-op context manager."""
        if trial_status is None:
            return nullcontext()
        return trial_status.record_step(step_name=step_name)

    def validate(self):
        if self.generator and self.config_path:
            raise ValueError(
                "Generator option is mutually exclusive with the config option."
            )
        elif not self.generator and not self.config_path:
            raise ValueError("A generator option or config option must be provided.")

        paths = {
            "generator": self.generator,
            "runtime": self.runtime,
        }
        non_none = {k: v for k, v in paths.items() if v is not None}
        seen: dict[str, str] = {}
        for role, path in non_none.items():
            if path in seen:
                raise ValueError(
                    f"'{path}' is assigned to both '{seen[path]}' and '{role}'. "
                    "Each function must be unique."
                )
            seen[path] = role

        if self.config_path:
            self.config_path = self.config_path.resolve()
            if self.seed:
                logger.warning(
                    "Since running with a config path, your seed and trial num will be ignored!"
                )
            mojo_model = MojoModel.model_validate_json(self.config_path.read_text())
            self.seed = mojo_model.seed
            self.trial_num = mojo_model.trial_num

            if self.workdir == DEFAULT_WORKDIR:
                self.workdir = self.config_path.parent
                logger.info(f"Using config path folder ({self.workdir}) as workdir!")

    def generate_construct(
        self, use_runtime: bool, on_reload_callback: OnReloadCallback | None
    ) -> MjState:
        """Helper to run a generation."""
        from .cli import _load_func

        project_root = Path.cwd()

        def reload_with_check(path_str: str, label: str):
            """Internal helper to validate file existance before reloading."""
            try:
                # attempt to find the module the dotted path resolves against, which may be a
                # package `__init__` re-exporting a class/function defined in a submodule
                _, mod = _load_func(path_str, _return_module=True)

                if mod and hasattr(mod, "__file__") and mod.__file__:
                    source_file = Path(mod.__file__).resolve()

                    # edge case check: file no longer exists
                    if not source_file.exists():
                        self._print(
                            f"[bold red]Stop![/bold red] The source file for {label} is missing.\n"
                            f"Expected: [dim]{source_file}[/dim]\n"
                            f"[yellow]Hint:[/yellow] Did you rename [bold]'{source_file.name}'[/bold] or move it?"
                        )
                        raise FileNotFoundError(
                            f"Unable to find source file for {path_str}. Did you rename or move it?"
                        )

                    # reloading the entry module re-resolves any re-exported names (e.g.
                    # `from .robot import RobotGenerator`) after their source modules reload
                    recursive_reload(module=mod, project_root=project_root)

                # reload to get the reference
                return _load_func(path_str)

            except (ModuleNotFoundError, ImportError) as e:
                self._print(
                    f"[bold red]Error:[/bold red] Failed to import [bold green]{path_str}[/bold green]: {e}\n"
                    f"[yellow]Hint:[/yellow] Check the module path for typos, and check the imports inside your file."
                )
                raise

        gen_func: MojoGenerator | None = None
        if self.generator:
            gen_func = cast(
                MojoGenerator, reload_with_check(self.generator, "Generator")
            )

        run_func: MojoRuntime | None = None
        if self.runtime:
            run_func = cast(MojoRuntime, reload_with_check(self.runtime, "Runtime"))

        global_overrides = NamedValueDict[NDArray]()
        if self.overrides_path and self.overrides_path.exists():
            logger.info(
                f"Retrieving global NamedValue overrides from `{self.overrides_path}`"
            )
            global_overrides = NamedValueDict[NDArray].model_validate_json(
                self.overrides_path.read_text()
            )

            if len(global_overrides) == 0:
                logger.warning(
                    "Global NamedValue overrides had no entries. Continuing anyway."
                )
            else:
                logger.info(
                    f"Global NamedValue overrides had {len(global_overrides)} entries."
                )

        # each trial number gets its own output folder, mirroring the Runner's layout
        trial_dir = self.trial_dir_for(self.trial_num)
        trial_dir.mkdir(parents=True, exist_ok=True)
        self._current_trial_dir = trial_dir

        # set up a per-trial log file capturing everything logged during this run, mirroring
        # the Runner's mojo.log. Unlike the Runner, overwrite (rather than append) on each
        # reload, since the same trial_dir is reused across many reload/run iterations in a
        # single interactive session and appending would mix logs from unrelated runs.
        trial_log_handler = get_trial_log_handler(trial_dir / "mojo.log", mode="w")
        root_logger = logging.getLogger()
        root_logger.addHandler(trial_log_handler)

        # only worth tracking via TrialStatus/JobStatus if telemetry will actually be recorded
        trial_status: TrialStatus | None = None
        trial_status_path: Path | None = None
        if self.record:
            trial_status_path = trial_dir / TRIAL_STATUS_FNAME
            trial_status = TrialStatus(trial_num=self.trial_num)
            trial_status._path = trial_status_path
            with trial_status.record_step(step_name="pending"):
                pass

        runtime_manager: rt.RuntimeManager | None = None
        try:
            # execute generation
            start = time.time()
            with self._record_step(trial_status, "generating"):
                if self.generator:
                    assert gen_func
                    # explicitly reset all stochas registries, then reinsert overrides
                    mojo_model = MojoModel()
                    mojo_model.named = NamedValueDict[NDArray]()
                    mojo_model.dists = DistributionDict()
                    mojo_model.design = DesignValueDict()

                    mojo_model = (
                        mojo_model.with_overrides(overrides=global_overrides)
                        .with_seed(seed=self.seed)
                        .with_trial_num(self.trial_num)
                    )
                    mojo_model = gen_func(
                        mojo_model,
                        global_overrides,
                        *self.gen_args,
                        **self.gen_kwargs,
                    )
                    mojo_model._trial_dir = trial_dir
                    if self.model_config_name:
                        mojo_model.dump_to_path(trial_dir / self.model_config_name)
                    (trial_dir / NAMED_VALUES_FNAME).write_text(
                        mojo_model.named.model_dump_json()
                    )

                    # overwrite on every reload (rather than write-once like the
                    # Runner) since the user's generator, and therefore which
                    # distributions exist, can change between reloads
                    if mojo_model.dists:
                        stochas_dir = self.workdir / STOCHAS_DIR_NAME
                        stochas_dir.mkdir(exist_ok=True)
                        mojo_model.dists.to_tables(stochas_dir)
                        tmp = stochas_dir / "dists.tmp.json"
                        tmp.write_text(
                            mojo_model.dists.model_dump_json(), encoding="utf-8"
                        )
                        tmp.replace(stochas_dir / STOCHAS_DISTS_FNAME)
                else:
                    assert self.config_path
                    try:
                        mojo_model = MojoModel.model_validate_json(
                            self.config_path.read_text()
                        ).with_overrides(overrides=global_overrides)
                        mojo_model._trial_dir = trial_dir
                        logger.info(
                            f"Playback mode: Loaded frozen state from {self.config_path.name}"
                        )
                    except Exception as e:
                        msg = f"Failed to load model config: {e}"
                        logger.error(msg)
                        raise ValueError(msg)

                try:
                    state = mojo_model.mjcf.prep_for_sim(
                        save_path=trial_dir / self.xml_name, unit_system=mojo_model.us
                    )
                except Exception as e:
                    msg = f"Failed to compile with MuJoCo: {e}"
                    logger.error(msg)
                    raise ValueError(msg)

            # sync the viewer
            if on_reload_callback:
                on_reload_callback(state)

            self._print(
                f"[dim white]Model generated in [bold]{time.time() - start:.2f}s[/bold].[/dim white]"
            )

            # execute runtime
            with self._record_step(trial_status, "solving"):
                if run_func and use_runtime:
                    runtime_manager = rt.RuntimeManager(
                        signal_manager=rt.SignalManager(
                            export_path=trial_dir
                            / rt.SignalManager.default_output_name(),
                            unit_system=mojo_model.us,
                        ),
                        _sync_hook=self._sync_hook,
                        _viewer_lock=self._viewer_lock,
                        _skip_recording=not self.record,
                        playback_speed=self._playback_speed,
                        _stop_event=self._stop_event,
                    )
                    start = time.time()
                    run_func(
                        mojo_model,
                        runtime_manager,
                        state,
                        *self.run_args,
                        **self.run_kwargs,
                    )
                    self._print(
                        f"[dim white]Runtime completed in [bold]{time.time() - start:.2f}s[/bold].[/dim white]"
                    )
                else:
                    mujoco.mj_forward(state.model, state.data)
        except rt.RequirementSatisfied:
            # a live requirement ended the run early as a success; the outcome
            # is decided by the requirement results, then the caller prints it
            if trial_status is not None:
                trial_status.step = "done"
                if runtime_manager is not None:
                    trial_status.requirements = runtime_manager.requirement_results
                trial_status.completion = (
                    Completion.FAILURE
                    if trial_status.requirements
                    and not all(r.passed for r in trial_status.requirements)
                    else Completion.SUCCESS
                )
            raise
        except (BdbQuit, KeyboardInterrupt, rt.SimulationStopped):
            raise
        except Exception:
            if trial_status is not None:
                trial_status.step = "done"
                trial_status.completion = Completion.ERROR
            raise
        else:
            if trial_status is not None:
                trial_status.step = "done"
                trial_status.completion = Completion.SUCCESS
        finally:
            # persist the final trial status and fold it into the job-level tracker,
            # the same way `MojoRunner` calls `update_trial` after each trial completes
            if trial_status is not None and trial_status_path is not None:
                trial_status.dump_to_path(trial_status_path)
                job_status = self._ensure_job_status(gen_func, run_func)
                if self.trial_num not in job_status.trial_nums:
                    job_status.trial_nums = sorted(
                        {*job_status.trial_nums, self.trial_num}
                    )
                job_status.update_trial(status=trial_status)

            root_logger.removeHandler(trial_log_handler)
            trial_log_handler.close()

        return state

    def run(self):
        self.validate()

        self.workdir = self.workdir.resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        (self.workdir / ".gitignore").write_text("*")
        write_dojo_script(self.workdir)
        self._trial_padding_style = self._infer_padding_style()

        try:
            start = time.time()
            with console.status(
                "[bold magenta]Performing initial generation...[/bold magenta]"
            ):
                initial_state = self.generate_construct(
                    use_runtime=False, on_reload_callback=None
                )
            console.print(
                f"[dim white]Model reloaded in [bold]{time.time() - start:.2f}s[/bold].[/dim white]"
            )
        except Exception as e:
            console.print(f"[bold red]Initial Generation Failed:[/bold red] {e}")
            raise typer.Exit(1)
        match self.ui:
            case UserInterface.OPENGL:
                self.run_opengl(initial_state)
            case UserInterface.MJVISER | UserInterface.VISER:
                self.run_viser(initial_state)
            case _:
                console.print(f"Invalid viewer option selected {self.ui}")
        _matrix_rain()
        console.print("\n[bold yellow]Exiting MuJoCo Mojo Reloaded[/bold yellow]")

    def _print_help(self):
        runtime_cmd = (
            "- [bold cyan]Any float[/]: Generate and use runtime. Playback speed set by float [dim](i.e., 1.0 for real time, 0.5 for half speed)[/]\n"
            if self.runtime
            else ""
        )
        watch_status = "[bold blue]on[/bold blue]" if self.watch else "[dim]off[/dim]"
        record_status = "[bold blue]on[/bold blue]" if self.record else "[dim]off[/dim]"
        self._print(
            Panel(
                "[bold green]MuJoCo Mojo Reloaded is Live![/bold green]\n\n"
                "- [bold yellow]ENTER[/]: Repeat last command\n"
                "- [bold magenta]gen[/]: Generate only\n"
                f"{runtime_cmd}"
                "- [bold white]seed <N>[/]: Set seed to N [dim](use [bold]seed none[/bold] to clear)[/dim]\n"
                "- [bold white]trial <N>[/]: Set trial number to N\n"
                f"- [bold blue]watch[/bold blue]: Toggle auto-watch on [dim].py[/dim] changes (currently {watch_status})\n"
                f"- [bold blue]record[/bold blue]: Toggle telemetry recording for [dim]mujoco-mojo dojo[/dim] (currently {record_status})\n"
                "- [bold blue]dojo[/bold blue]: Print a command to launch the Dojo monitor for this session\n"
                "- [bold red]stop[/bold red] / [bold red]halt[/bold red]: Abort a run in progress\n"
                "- [bold cyan]h[/] / [bold cyan]help[/]: Show this panel\n"
                "- [bold red]exit[/] / [bold red]q[/]: Close",
                title="Interactive Controls",
                border_style="cyan",
                expand=False,
            )
        )

    def _interactive_loop(
        self, on_reload_callback: OnReloadCallback, is_running_check: IsRunningCheck
    ):
        event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        stop_event = threading.Event()
        watcher_stop_event: threading.Event | None = None
        busy_event = threading.Event()
        job_thread: threading.Thread | None = None

        def start_watcher() -> threading.Event | None:
            try:
                from watchfiles import PythonFilter
                from watchfiles import watch as wf_watch
            except ImportError:
                self._print(
                    "[bold yellow]Warning:[/bold yellow] watchfiles not installed. "
                    "Install [bold]mujoco-mojo[reloaded][/bold] to use --watch."
                )
                return None
            # silence watchfiles' own "N changes detected" log; we print our own below
            logging.getLogger("watchfiles").setLevel(logging.WARNING)

            evt = threading.Event()
            watch_path = Path.cwd()

            def _run():
                try:
                    for changes in wf_watch(
                        watch_path, watch_filter=PythonFilter(), stop_event=evt
                    ):
                        event_queue.put(("reload", str(len(changes))))
                except Exception:
                    pass

            threading.Thread(target=_run, daemon=True).start()
            return evt

        def stop_watcher():
            nonlocal watcher_stop_event
            if watcher_stop_event is not None:
                watcher_stop_event.set()
                watcher_stop_event = None

        def plain_stdin_reader():
            """Fallback used when raw mode isn't available (not a tty, or `termios` is missing, e.g. on Windows). No history/line-editing beyond whatever the terminal driver provides."""
            while not stop_event.is_set():
                try:
                    line = sys.stdin.readline()
                    if not line:
                        event_queue.put(("input", "exit"))
                        break
                    event_queue.put(("input", line.strip()))
                except (KeyboardInterrupt, EOFError):
                    event_queue.put(("input", "exit"))
                    break

        def raw_stdin_reader(fd: int):
            """
            Byte-level input reader that hand-rolls just enough line-editing to support Up/Down history navigation, alongside the Left/Right/Backspace editing a cooked tty already gives users for free.

            Runs with local echo and canonical mode off, so every visible character is one we wrote ourselves via `_redraw_line` - that's what lets history navigation (and async output from other threads) safely rewrite the in-progress line without fighting the tty driver's own buffering.
            """
            import select

            history: list[str] = []
            history_index: int | None = None
            pending_line = ""

            while not stop_event.is_set():
                try:
                    ch = os.read(fd, 1)
                except OSError:
                    # e.g. EINTR from a signal landing on this thread; just retry
                    continue
                if not ch:
                    event_queue.put(("input", "exit"))
                    break

                if ch == b"\x03":  # Ctrl-C (only reachable if ISIG is somehow off)
                    event_queue.put(("input", "exit"))
                    break

                if ch in (b"\r", b"\n"):
                    with self._print_lock:
                        console.file.write("\r\n")
                        console.file.flush()
                        line = self._line_buffer
                        self._line_buffer = ""
                        self._line_cursor = 0
                    if line and (not history or history[-1] != line):
                        history.append(line)
                    history_index = None
                    pending_line = ""
                    event_queue.put(("input", line.strip()))
                    continue

                if ch in (b"\x7f", b"\x08"):  # backspace
                    if self._line_cursor > 0:
                        with self._print_lock:
                            self._line_buffer = (
                                self._line_buffer[: self._line_cursor - 1]
                                + self._line_buffer[self._line_cursor :]
                            )
                            self._line_cursor -= 1
                            self._clear_line()
                            self._redraw_line()
                    continue

                if ch == b"\x1b":
                    # arrow keys (and other CSI sequences) arrive as ESC '[' <letter>;
                    # give the rest a brief window so a bare Escape keypress (which sends
                    # no follow-up bytes) doesn't block waiting for more input
                    rest = (
                        os.read(fd, 2) if select.select([fd], [], [], 0.05)[0] else b""
                    )

                    if rest == b"[A":  # up
                        if history:
                            if history_index is None:
                                pending_line = self._line_buffer
                                history_index = len(history) - 1
                            elif history_index > 0:
                                history_index -= 1
                            with self._print_lock:
                                self._line_buffer = history[history_index]
                                self._line_cursor = len(self._line_buffer)
                                self._clear_line()
                                self._redraw_line()
                    elif rest == b"[B":  # down
                        if history_index is not None:
                            if history_index < len(history) - 1:
                                history_index += 1
                                text = history[history_index]
                            else:
                                history_index = None
                                text = pending_line
                            with self._print_lock:
                                self._line_buffer = text
                                self._line_cursor = len(self._line_buffer)
                                self._clear_line()
                                self._redraw_line()
                    elif rest == b"[C":  # right
                        if self._line_cursor < len(self._line_buffer):
                            with self._print_lock:
                                self._line_cursor += 1
                                self._clear_line()
                                self._redraw_line()
                    elif rest == b"[D":  # left
                        if self._line_cursor > 0:
                            with self._print_lock:
                                self._line_cursor -= 1
                                self._clear_line()
                                self._redraw_line()
                    continue

                if ch < b"\x20":
                    # other control characters (tab, etc.) aren't supported; ignore
                    continue

                char = ch.decode("ascii", errors="ignore")
                if not char:
                    continue
                with self._print_lock:
                    self._line_buffer = (
                        self._line_buffer[: self._line_cursor]
                        + char
                        + self._line_buffer[self._line_cursor :]
                    )
                    self._line_cursor += 1
                    self._clear_line()
                    self._redraw_line()

        old_termios = None
        stdin_fd: int | None = None
        if sys.stdin.isatty():
            try:
                import atexit
                import termios

                fd = sys.stdin.fileno()
                old_termios = termios.tcgetattr(fd)
                new_termios = termios.tcgetattr(fd)
                new_termios[3] &= ~(termios.ICANON | termios.ECHO)
                termios.tcsetattr(fd, termios.TCSADRAIN, new_termios)
                # belt-and-suspenders: guarantees the terminal gets restored even if
                # this function exits via an exception that skips its normal cleanup
                atexit.register(termios.tcsetattr, fd, termios.TCSADRAIN, old_termios)
                stdin_fd = fd
            except Exception:
                old_termios = None
                stdin_fd = None

        def stdin_reader():
            if stdin_fd is not None:
                raw_stdin_reader(stdin_fd)
            else:
                plain_stdin_reader()

        threading.Thread(target=stdin_reader, daemon=True).start()

        if self.watch:
            watcher_stop_event = start_watcher()

        def print_prompt():
            if busy_event.is_set():
                console.print(
                    "[bold yellow]Running trial...[/bold yellow] "
                    "[dim](type stop/halt to abort)[/dim][white] > [/white]",
                    end="",
                )
                return

            watch_indicator = " | [bold blue]W[/bold blue]" if self.watch else ""
            console.print(
                f"[bold green]Awaiting command[/bold green] [dim](last: {self._last_command} | seed: {self.seed} | trial: {self.trial_num}{watch_indicator})[/dim][white] > [/white]",
                end="",
            )

        self._reprint_prompt = print_prompt
        self._print_help()

        # logging handlers write directly to the terminal, bypassing `self._print`'s
        # prompt-clearing - wrap them so log lines don't step on the prompt either
        root_logger = logging.getLogger()
        wrapped_handlers: list[
            tuple[logging.Handler, Callable[[logging.LogRecord], None]]
        ] = []

        def _wrap_handler(handler: logging.Handler):
            original_emit = handler.emit

            def emit(_self: logging.Handler, record: logging.LogRecord) -> None:
                with self._print_lock:
                    self._clear_line()
                    original_emit(record)
                    self._redraw_line()

            setattr(handler, "emit", types.MethodType(emit, handler))
            wrapped_handlers.append((handler, original_emit))

        for handler in root_logger.handlers:
            _wrap_handler(handler)

        def run_construct(use_runtime: bool):
            """Runs `generate_construct` in the background, blocking new runs/reloads until it finishes."""
            nonlocal job_thread

            def _job():
                try:
                    start = time.time()
                    new_state = self.generate_construct(
                        use_runtime=use_runtime, on_reload_callback=on_reload_callback
                    )
                    on_reload_callback(new_state)
                    msg = f"[dim white]Model Reloaded in [bold]{time.time() - start:.2f}s[/bold].[/dim white]"
                except rt.RequirementSatisfied as e:
                    msg = f"[bold green]Run ended early, requirement satisfied: {e}[/bold green]"
                except rt.RequirementTerminated as e:
                    msg = (
                        f"[bold yellow]Run terminated by requirement: {e}[/bold yellow]"
                    )
                except rt.SimulationStopped:
                    msg = "[bold yellow]Run stopped by user.[/bold yellow]"
                except Exception as e:
                    logger.exception(e)
                    msg = f"[bold red]Reload Failed:[/bold red]\n[white]{e}[/white]"
                finally:
                    self._stop_event.clear()

                # clear busy before printing so the redrawn prompt shows "Awaiting command"
                busy_event.clear()
                self._print(msg)

            self._stop_event.clear()
            busy_event.set()
            job_thread = threading.Thread(target=_job, daemon=True)
            job_thread.start()

        while is_running_check():
            try:
                event_type, data = event_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            except (KeyboardInterrupt, BdbQuit):
                break

            if event_type == "reload":
                count = int(data) if data.isdigit() else 0
                plural = "s" if count != 1 else ""

                if busy_event.is_set():
                    self._print(
                        f"\n[dim]{count} change{plural} detected, but a run is in "
                        "progress - ignoring. Save again once it finishes to "
                        "reload.[/dim]"
                    )
                    continue

                self._print(
                    f"\n[dim]{count} change{plural} detected, reloading with last command...[/dim]"
                )
                use_runtime = self._last_command != "gen"
                run_construct(use_runtime)
                continue

            raw = data.lower()

            if busy_event.is_set():
                if raw in ("stop", "halt"):
                    self._print(
                        "[bold yellow]Stopping the current run...[/bold yellow]"
                    )
                    self._stop_event.set()
                else:
                    self._print(
                        "[dim]A run is in progress - type [bold]stop[/bold] or "
                        "[bold]halt[/bold] to cancel it.[/dim]"
                    )
                continue

            if raw in ("exit", "quit", "q"):
                break

            if raw in ("stop", "halt"):
                self._print("[dim]No run is currently in progress.[/dim]")
                continue

            if raw in ("h", "help"):
                self._print_help()
                continue

            if raw in ["watch", "w"]:
                self.watch = not self.watch
                if self.watch:
                    watcher_stop_event = start_watcher()
                    if watcher_stop_event is None:
                        self.watch = False
                    else:
                        self._print("[dim]Auto-watch enabled[/dim]")
                else:
                    stop_watcher()
                    self._print("[dim]Auto-watch disabled[/dim]")
                continue

            if raw == "dojo":
                hint = (
                    "\n[dim]Note: telemetry recording is currently off, so the "
                    "Dojo won't have trial data until you enable [bold]record[/bold].[/dim]"
                    if not self.record
                    else ""
                )
                self._print(
                    "[dim]Run this in another terminal to monitor this session:[/dim]\n"
                    f'[bold cyan]mujoco-mojo dojo "{self.workdir}"[/bold cyan]'
                    f"{hint}"
                )
                continue

            if raw == "record":
                self.record = not self.record
                if self.record:
                    self._print(
                        "[dim]Telemetry recording enabled - "
                        "the next reload will be visible in `mujoco-mojo dojo`.[/dim]"
                    )
                else:
                    self._print("[dim]Telemetry recording disabled[/dim]")
                continue

            if raw.startswith("seed "):
                seed_arg = raw[5:].strip()
                if seed_arg in ("none", "null"):
                    self.seed = None
                    self._print("[dim]Seed cleared.[/dim]")
                else:
                    try:
                        self.seed = int(seed_arg)
                        self._print(f"[dim]Seed set to {self.seed}.[/dim]")
                    except ValueError:
                        self._print(
                            "[bold red]Invalid seed.[/bold red] Use: seed <integer> or seed none"
                        )
                continue

            if raw.startswith("trial "):
                try:
                    self.trial_num = int(raw[6:].strip())
                    self._print(f"[dim]Trial number set to {self.trial_num}.[/dim]")
                except ValueError:
                    self._print(
                        "[bold red]Invalid trial number.[/bold red] Use: trial <integer>"
                    )
                continue

            if raw and raw != "gen":
                try:
                    self._playback_speed = float(raw)
                    self._print(
                        f"[dim]Playback speed set to {self._playback_speed}x[/]"
                    )
                except ValueError:
                    self._print(
                        f"[bold red]Unknown command:[/bold red] '{raw}'. Type [bold cyan]h[/bold cyan] for help."
                    )
                    continue

            cmd = raw if raw else self._last_command
            self._last_command = cmd

            use_runtime = cmd != "gen"

            self._print("[dim]Processing...[/dim]")
            run_construct(use_runtime)

        stop_watcher()
        stop_event.set()

        if busy_event.is_set():
            self._stop_event.set()
            if job_thread is not None:
                job_thread.join(timeout=5)

        # restore the tty ourselves rather than relying on raw_stdin_reader's own
        # cleanup - it's a daemon thread blocked on os.read() until the next
        # keystroke, so it may never get a chance to run its own restore
        if old_termios is not None and stdin_fd is not None:
            import termios

            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_termios)

        self._reprint_prompt = None

        for handler, original_emit in wrapped_handlers:
            setattr(handler, "emit", original_emit)

    def run_opengl(self, state: MjState):
        import mujoco.viewer

        with mujoco.viewer.launch_passive(state.model, state.data) as viewer:

            def sync(
                s: MjState,
                arrows: list[ArrowConfig],
                lines: list[LineConfig],
            ):
                assert viewer.user_scn
                # the viewer's GUI thread reads user_scn while rendering, so edits
                # must happen under the viewer lock. viewer.sync() locks internally,
                # so it stays outside to avoid nesting
                with viewer.lock():
                    viewer.user_scn.ngeom = 0

                    for arrow in arrows:
                        arrow.draw_in_scene(mj_model=s.model, scene=viewer.user_scn)

                    for line in lines:
                        line.draw_in_scene(scene=viewer.user_scn)

                viewer.sync()

            def reload_handler(s: MjState):
                sim = viewer._get_sim()
                if sim:
                    assert self._current_trial_dir is not None
                    if viewer.user_scn and s.data.time == 0.0:
                        # ensure the custom visual layer is wiped on every model reload
                        with viewer.lock():
                            viewer.user_scn.ngeom = 0
                    sim.load(
                        s.model,
                        s.data,
                        str(self._current_trial_dir / self.xml_name),
                    )
                    viewer.sync()

            reload_handler(state)

            self._sync_hook = lambda state, arrows, lines: sync(state, arrows, lines)
            # the viewer's GUI thread reads model/data under this lock (e.g. the
            # sensor/profiler panels), so physics stepping must hold it too
            self._viewer_lock = viewer.lock
            self._interactive_loop(
                lambda state: reload_handler(state),
                is_running_check=viewer.is_running,
            )

    def run_viser(self, state: MjState):
        try:
            import viser
            from mjviser import ViserMujocoScene
        except ImportError:
            console.print(
                "The [bold]mjviser[/bold] UI option requires you to install [bold]mjviser[/bold] separately."
            )
            raise typer.Exit(1)
        import contextlib
        import io

        from mujoco_mojo.utils.color import Color
        from mujoco_mojo.utils.utils import get_local_ip

        class ViserState(TypedDict):
            scene: ViserMujocoScene
            arrow_handle: None | viser.LineSegmentsHandle

        for name in ["websockets", "matplotlib.font_manager"]:
            _l = logging.getLogger(name)
            _l.setLevel(logging.WARNING)
            _l.propagate = False

        def _print_connection_panel():
            local_ip = get_local_ip()

            connection_info = (
                f"Local: [bold cyan u]http://127.0.0.1:{self.port}[/bold cyan u]"
            )

            if self.host == "0.0.0.0":
                connection_info += f"\nMobile: [bold cyan u]http://{local_ip}:{self.port}[/bold cyan u]"
            else:
                connection_info += "\n\n[dim]Tip: To view on other devices, run with[/dim] [yellow]--host 0.0.0.0[/yellow]"

            console.print(
                Panel(
                    f"""{connection_info}\n\n[yellow]Press CTRL+C to stop[/yellow]""",
                    border_style="yellow",
                    title="Connection Info.",
                    expand=False,
                )
            )

        with contextlib.redirect_stdout(io.StringIO()):
            server = viser.ViserServer(
                host=self.host,
                port=self.port,
                label=f"MuJoCo Mojo Reloaded (seed: {self.seed}, trial: {self.trial_num})",
                verbose=False,
            )
        brand_rgb = (Color.CYAN_500.rgb * 255).round()
        # dark_mode is a server-wide setting broadcast to every client - viser has no
        # way to detect a client's browser/OS theme preference, so we default to dark.
        server.gui.configure_theme(
            dark_mode=True,
            show_logo=False,
            brand_color=(int(brand_rgb[0]), int(brand_rgb[1]), int(brand_rgb[2])),
        )

        server.scene.reset()

        # shared between the runtime job thread (which steps physics) and viser's
        # websocket thread (which runs GUI callbacks that re-render from live MjData,
        # e.g. contact decor). RuntimeManager holds it while mutating model/data
        runtime_lock = threading.RLock()

        viser_state: ViserState = {
            "scene": ViserMujocoScene(server=server, mj_model=state.model, num_envs=1),
            "arrow_handle": None,
        }

        def refresh_from_gui():
            # gui-triggered re-renders must hold the same lock as physics stepping,
            # mirroring how mjviser's own viewer wires its refresh handler
            with runtime_lock:
                viser_state["scene"].refresh_visualization()

        viser_state["scene"].set_refresh_handler(refresh_from_gui)
        # create_visualization_gui already includes the scene (camera) controls tab
        viser_state["scene"].create_visualization_gui()

        # cap how often scene updates are pushed to clients. the runtime calls the
        # sync hook on every physics step (often 1000+ Hz), and pushing a full scene
        # update plus a websocket flush at that rate overwhelms connected browsers as
        # soon as they also handle interaction such as camera movement. mjviser's own
        # viewer targets the same 60 Hz render rate
        min_frame_time = 1.0 / 60.0
        last_push = 0.0

        def clear_arrows():
            if viser_state["arrow_handle"] is not None:
                viser_state["arrow_handle"].remove()
                viser_state["arrow_handle"] = None

        def sync(
            s: MjState,
            arrows: list[ArrowConfig],
            lines: list[LineConfig],
        ):
            nonlocal last_push
            now = time.monotonic()
            if now - last_push < min_frame_time:
                return
            last_push = now

            viser_state["scene"].update_from_mjdata(s.data)

            if not arrows and not lines:
                # no arrows this frame; clear the batch and exit
                clear_arrows()
                return

            all_segments = []
            all_colors = []
            line_width = 2.0

            for arrow in arrows:
                seg_start, seg_end, w = arrow.resolve_arrow_coords(mj_model=s.model)

                line_width = w * 200.0
                all_segments.append(np.stack([seg_start, seg_end]))
                color_uint8 = tuple(int(x * 255) for x in arrow.color[:3])
                all_colors.append([color_uint8, color_uint8])

            for line in lines:
                line_width = line.width * 200.0
                all_segments.append(np.stack([line.pos1, line.pos2]))
                color_uint8 = tuple(int(x * 255) for x in line.color[:3])
                all_colors.append([color_uint8, color_uint8])

            points_batch = np.array(all_segments, dtype=np.float32)
            colors_batch = np.array(all_colors, dtype=np.uint8)

            viser_state["arrow_handle"] = server.scene.add_line_segments(
                name="mojo_arrows",
                points=points_batch,
                colors=colors_batch,
                line_width=line_width,
            )

        def update_scene(s: MjState):
            clear_arrows()
            viser_state["scene"] = ViserMujocoScene(
                server=server, mj_model=s.model, num_envs=1
            )
            viser_state["scene"].set_refresh_handler(refresh_from_gui)
            viser_state["scene"].update_from_mjdata(s.data)
            server.gui.set_panel_label(
                f"MuJoCo Mojo Reloaded (seed: {self.seed}, trial: {self.trial_num})"
            )
            return viser_state["scene"]

        # initial render
        update_scene(state)
        _print_connection_panel()

        self._sync_hook = lambda state, arrows, lines: sync(state, arrows, lines)
        self._viewer_lock = lambda: runtime_lock
        self._interactive_loop(lambda state: update_scene(state), lambda: True)
        server.stop()
