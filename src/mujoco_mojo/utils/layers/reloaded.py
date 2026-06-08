import logging
import queue
import sys
import threading
import time
from bdb import BdbQuit
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict, runtime_checkable

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
from mujoco_mojo.utils.defaults import DEFAULT_WORKDIR
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.runner import MojoGenerator, MojoRunner, MojoRuntime
from mujoco_mojo.utils.utils import write_dojo_script
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


def is_dark_mode() -> bool:
    """Determine if the system is in dark mode using only the standard library."""
    import platform
    import subprocess

    system = platform.system()

    try:
        if system == "Windows":
            import winreg

            # Look at the 'Personalize' key for AppsUseLightTheme
            path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:  # pyright: ignore[reportAttributeAccessIssue]
                # 0 = Dark, 1 = Light
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")  # pyright: ignore[reportAttributeAccessIssue]
                return value == 0

        elif system == "Darwin":  # macOS
            # 'defaults read -g AppleInterfaceStyle' returns 'Dark' or errors out if Light
            cmd = ["defaults", "read", "-g", "AppleInterfaceStyle"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return "Dark" in result.stdout

        elif system == "Linux":
            # Check GNOME/GTK settings (most common)
            cmd = ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return "dark" in result.stdout.lower()

    except Exception:
        # Fallback to Light Mode if anything fails (e.g. old Windows versions)
        return False

    return False


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
    except (ImportError, ModuleNotFoundError) as e:
        logger.error(f"Failed to reload {module.__name__}: {e}")
        raise e
    except Exception:
        # some modules (like namespace packages) can be finicky
        pass


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
    model_config_name: str
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
    _playback_speed: float = 1.0
    _last_command: str = "run"
    _current_trial_dir: Path | None = None
    _job_status: JobStatus | None = None

    _trial_padding_style = "03d"

    def trial_dir_for(self, trial_num: int) -> Path:
        """
        Per-trial output directory, mirroring the layout `Trial`/`MojoRunner` use.

        Keeping this layout lets `mujoco-mojo dojo` discover and plot reloaded runs the same way it discovers Monte Carlo / Optimize trials.
        """
        return (
            self.workdir / "trials" / f"trial_{trial_num:{self._trial_padding_style}}"
        ).resolve()

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
                # attempt to find
                func = _load_func(path_str)
                mod = sys.modules.get(func.__module__)

                if mod and hasattr(mod, "__file__") and mod.__file__:
                    source_file = Path(mod.__file__).resolve()

                    # edge case check: file no longer exists
                    if not source_file.exists():
                        console.print(
                            f"[bold red]Stop![/bold red] The source file for {label} is missing.\n"
                            f"Expected: [dim]{source_file}[/dim]\n"
                            f"[yellow]Hint:[/yellow] Did you rename [bold]'{source_file.name}'[/bold] or move it?"
                        )
                        raise FileNotFoundError(
                            f"Unable to find source file for {path_str}. Did you rename or move it?"
                        )

                    recursive_reload(module=mod, project_root=project_root)

                # reload to get the reference
                return _load_func(path_str)

            except (ModuleNotFoundError, ImportError):
                console.print(
                    f"[bold red]Error:[/bold red] Could not find [bold green]{path_str}[/bold green].\n"
                    f"[yellow]Hint:[/yellow] Check your spelling or ensure the module path is correct."
                )
                raise

        gen_func: MojoGenerator | None = None
        if self.generator:
            gen_func = reload_with_check(self.generator, "Generator")

        run_func: MojoRuntime | None = None
        if self.runtime:
            run_func = reload_with_check(self.runtime, "Runtime")

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

        # only worth tracking via TrialStatus/JobStatus if telemetry will actually be recorded
        trial_status: TrialStatus | None = None
        trial_status_path: Path | None = None
        if self.record:
            trial_status_path = trial_dir / TRIAL_STATUS_FNAME
            trial_status = TrialStatus(trial_num=self.trial_num)
            trial_status._path = trial_status_path
            with trial_status.record_step(step_name="pending"):
                pass

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
                    mojo_model.dump_to_path(trial_dir / self.model_config_name)
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
                        save_path=trial_dir / self.xml_name
                    )
                except Exception as e:
                    msg = f"Failed to compile with MuJoCo: {e}"
                    logger.error(msg)
                    raise ValueError(msg)

            # sync the viewer
            if on_reload_callback:
                on_reload_callback(state)

            console.print(
                f"[dim white]Model generated in [bold]{time.time() - start:.2f}s[/bold].[/dim white]"
            )

            # execute runtime
            with self._record_step(trial_status, "solving"):
                if run_func and use_runtime:
                    runtime_manager = rt.RuntimeManager(
                        signal_manager=rt.SignalManager(
                            export_path=trial_dir
                            / rt.SignalManager.default_output_name()
                        ),
                        _sync_hook=self._sync_hook,
                        _skip_recording=not self.record,
                        playback_speed=self._playback_speed,
                    )
                    start = time.time()
                    run_func(
                        mojo_model,
                        runtime_manager,
                        state,
                        *self.run_args,
                        **self.run_kwargs,
                    )
                    console.print(
                        f"[dim white]Runtime completed in [bold]{time.time() - start:.2f}s[/bold].[/dim white]"
                    )
                else:
                    mujoco.mj_forward(state.model, state.data)
        except (BdbQuit, KeyboardInterrupt):
            raise
        except Exception:
            if trial_status is not None:
                trial_status.step = "done"
                trial_status.completion = Completion.FAILED
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

        return state

    def run(self):
        self.validate()

        self.workdir = self.workdir.resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        (self.workdir / ".gitignore").write_text("*")
        write_dojo_script(self.workdir)

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
        console.print("\n[bold yellow]Exiting MuJoCo Mojo Reloaded[/bold yellow]")

    def _print_help(self):
        runtime_cmd = (
            "- [bold cyan]Any float[/]: Generate and use runtime. Playback speed set by float [dim](i.e., 1.0 for real time, 0.5 for half speed)[/]\n"
            if self.runtime
            else ""
        )
        watch_status = "[bold blue]on[/bold blue]" if self.watch else "[dim]off[/dim]"
        record_status = "[bold blue]on[/bold blue]" if self.record else "[dim]off[/dim]"
        console.print(
            Panel(
                "[bold green]MuJoCo Mojo Reloaded is Live![/bold green]\n\n"
                "- [bold yellow]ENTER[/]: Repeat last command\n"
                "- [bold magenta]gen[/]: Generate only\n"
                f"{runtime_cmd}"
                "- [bold white]seed <N>[/]: Set seed to N\n"
                "- [bold white]trial <N>[/]: Set trial number to N\n"
                f"- [bold blue]watch[/bold blue]: Toggle auto-watch on [dim].py[/dim] changes (currently {watch_status})\n"
                f"- [bold blue]record[/bold blue]: Toggle telemetry recording for [dim]mujoco-mojo dojo[/dim] (currently {record_status})\n"
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

        def start_watcher() -> threading.Event | None:
            try:
                from watchfiles import PythonFilter
                from watchfiles import watch as wf_watch
            except ImportError:
                console.print(
                    "[bold yellow]Warning:[/bold yellow] watchfiles not installed. "
                    "Install [bold]mujoco-mojo[reloaded][/bold] to use --watch."
                )
                return None
            evt = threading.Event()
            watch_path = Path.cwd()

            def _run():
                try:
                    for _ in wf_watch(
                        watch_path, watch_filter=PythonFilter(), stop_event=evt
                    ):
                        event_queue.put(("reload", ""))
                except Exception:
                    pass

            threading.Thread(target=_run, daemon=True).start()
            return evt

        def stop_watcher():
            nonlocal watcher_stop_event
            if watcher_stop_event is not None:
                watcher_stop_event.set()
                watcher_stop_event = None

        def stdin_reader():
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

        threading.Thread(target=stdin_reader, daemon=True).start()

        if self.watch:
            watcher_stop_event = start_watcher()

        self._print_help()

        def print_prompt():
            watch_indicator = " [bold blue]W[/bold blue]" if self.watch else ""
            console.print(
                f"[bold green]Awaiting command[/bold green]"
                f"[dim](last: {self._last_command} | seed: {self.seed} | trial: {self.trial_num})[/dim]"
                f"{watch_indicator}[white] > [/white]",
                end="",
            )

        print_prompt()

        while is_running_check():
            try:
                event_type, data = event_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            except (KeyboardInterrupt, BdbQuit):
                break

            if event_type == "reload":
                console.print(
                    "\n[dim]File change detected, reloading with last command...[/dim]"
                )
                use_runtime = self._last_command != "gen"
                try:
                    start = time.time()
                    new_state = self.generate_construct(
                        use_runtime=use_runtime, on_reload_callback=on_reload_callback
                    )
                    on_reload_callback(new_state)
                    console.print(
                        f"[dim white]Model Reloaded in [bold]{time.time() - start:.2f}s[/bold].[/dim white]"
                    )
                except Exception as e:
                    logger.exception(e)
                    console.print(
                        f"[bold red]Reload Failed:[/bold red]\n[white]{e}[/white]"
                    )
                print_prompt()
                continue

            raw = data.lower()

            if raw in ("exit", "quit", "q"):
                break

            if raw in ("h", "help"):
                self._print_help()
                print_prompt()
                continue

            if raw == "watch":
                self.watch = not self.watch
                if self.watch:
                    watcher_stop_event = start_watcher()
                    if watcher_stop_event is None:
                        self.watch = False
                    else:
                        console.print("[dim]Auto-watch enabled[/dim]")
                else:
                    stop_watcher()
                    console.print("[dim]Auto-watch disabled[/dim]")
                print_prompt()
                continue

            if raw == "record":
                self.record = not self.record
                if self.record:
                    console.print(
                        "[dim]Telemetry recording enabled - "
                        "the next reload will be visible in `mujoco-mojo dojo`.[/dim]"
                    )
                else:
                    console.print("[dim]Telemetry recording disabled[/dim]")
                print_prompt()
                continue

            if raw.startswith("seed "):
                try:
                    self.seed = int(raw[5:].strip())
                    console.print(f"[dim]Seed set to {self.seed}.[/dim]")
                except ValueError:
                    console.print(
                        "[bold red]Invalid seed.[/bold red] Use: seed <integer>"
                    )
                print_prompt()
                continue

            if raw.startswith("trial "):
                try:
                    self.trial_num = int(raw[6:].strip())
                    console.print(f"[dim]Trial number set to {self.trial_num}.[/dim]")
                except ValueError:
                    console.print(
                        "[bold red]Invalid trial number.[/bold red] Use: trial <integer>"
                    )
                print_prompt()
                continue

            if raw and raw != "gen":
                try:
                    self._playback_speed = float(raw)
                    console.print(
                        f"[dim]Playback speed set to {self._playback_speed}x[/]"
                    )
                except ValueError:
                    console.print(
                        f"[bold red]Unknown command:[/bold red] '{raw}'. Type [bold cyan]h[/bold cyan] for help."
                    )
                    print_prompt()
                    continue

            cmd = raw if raw else self._last_command
            self._last_command = cmd

            use_runtime = cmd != "gen"

            try:
                start = time.time()
                console.print("[bold]Processing...[/bold]")
                new_state = self.generate_construct(
                    use_runtime=use_runtime, on_reload_callback=on_reload_callback
                )
                on_reload_callback(new_state)
                console.print(
                    f"[dim white]Model Reloaded in [bold]{time.time() - start:.2f}s[/bold].[/dim white]"
                )
            except Exception as e:
                logger.exception(e)
                console.print(
                    f"[bold red]Reload Failed:[/bold red]\n[white]{e}[/white]"
                )

            print_prompt()

        stop_watcher()
        stop_event.set()

    def run_opengl(self, state: MjState):
        import mujoco.viewer

        with mujoco.viewer.launch_passive(state.model, state.data) as viewer:

            def sync(
                s: MjState,
                arrows: list[ArrowConfig],
                lines: list[LineConfig],
            ):
                assert viewer.user_scn
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
                        viewer.user_scn.ngeom = 0
                    sim.load(
                        s.model,
                        s.data,
                        str(self._current_trial_dir / self.xml_name),
                    )
                    viewer.sync()

            reload_handler(state)

            self._sync_hook = lambda state, arrows, lines: sync(state, arrows, lines)
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

        for name in ["websockets"]:
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
                )
            )

        with contextlib.redirect_stdout(io.StringIO()):
            server = viser.ViserServer(
                host=self.host,
                port=self.port,
                label=f"MuJoCo Mojo Reloaded (seed: {self.seed}, trial: {self.trial_num})",
                verbose=False,
            )
        server.configure_theme(  # pyright: ignore[reportAttributeAccessIssue]
            dark_mode=is_dark_mode(),
            show_logo=False,
            brand_color=tuple(int(x) for x in (Color.CYAN_500.rgb * 255).round()),
        )

        server.scene.reset()

        viser_state: ViserState = {
            "scene": ViserMujocoScene(server=server, mj_model=state.model, num_envs=1),
            "arrow_handle": None,
        }
        viser_state["scene"].create_visualization_gui()
        viser_state["scene"].create_scene_gui()

        def sync(
            s: MjState,
            arrows: list[ArrowConfig],
            lines: list[LineConfig],
        ):
            viser_state["scene"].update_from_mjdata(s.data)
            node_name = "mojo_arrows"

            if not arrows and not lines:
                # If no arrows this frame, clear the batch and exit
                server.scene.remove_by_name(node_name)
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

            server.scene.add_line_segments(
                name=node_name,
                points=points_batch,
                colors=colors_batch,
                line_width=line_width,
            )

        def update_scene(s: MjState):
            viser_state["scene"] = ViserMujocoScene(
                server=server, mj_model=s.model, num_envs=1
            )
            viser_state["scene"].update_from_mjdata(s.data)
            return viser_state["scene"]

        # initial render
        update_scene(state)
        _print_connection_panel()

        self._sync_hook = lambda state, arrows, lines: sync(state, arrows, lines)
        self._interactive_loop(lambda state: update_scene(state), lambda: True)
        server.stop()
