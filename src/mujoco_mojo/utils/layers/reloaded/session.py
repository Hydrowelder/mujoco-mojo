import logging
import shutil
import sys
import threading
import time
import types
from bdb import BdbQuit
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, assert_never, cast

import mujoco
import typer
from numpydantic import NDArray
from rich.console import Console
from rich.markup import escape

import mujoco_mojo.runtime as rt
from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.settings import ReloadedKeySettings
from mujoco_mojo.stochas import DesignValueDict, DistributionDict, NamedValueDict
from mujoco_mojo.typing import StudioGraphics, UserInterface
from mujoco_mojo.utils.defaults import (
    DEFAULT_WORKDIR,
    NAMED_VALUES_FNAME,
    STOCHAS_DIR_NAME,
    STOCHAS_DISTS_FNAME,
)
from mujoco_mojo.utils.log import get_logger, get_trial_log_handler
from mujoco_mojo.utils.runner import (
    GENERATOR_FIXED_ARGS,
    RUNTIME_FIXED_ARGS,
    MojoGenerator,
    MojoRunner,
    MojoRuntime,
    select_kwargs,
    validate_shared_kwargs,
)
from mujoco_mojo.utils.statusing import (
    JOB_STATUS_FNAME,
    TRIAL_STATUS_FNAME,
    Completion,
    ExecutionMode,
    JobStatus,
    JobType,
    Step,
    TrialStatus,
    describe_args,
    describe_kwargs,
)
from mujoco_mojo.utils.utils import write_dojo_script

from ..crash_guard import CrashGuard
from .backends import (
    OnReloadCallback,
    OpenGLBackend,
    StudioBackend,
    ViewerBackend,
    ViewerUnavailableError,
    check_studio_available,
)
from .controller import ReloadedController
from .tui import ReloadedApp

logger = get_logger(__name__)
console = Console()


def recursive_reload(
    module, project_root: Path, visited: set[types.ModuleType] | None = None
) -> None:
    """Recursively reloads modules, but only if they live inside project_root."""
    import importlib

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
    args: list[Any]
    kwargs: dict[str, Any]
    host: str
    port: int

    gfx: StudioGraphics = StudioGraphics.DEFAULT
    watch: bool = False
    record: bool = False
    keys: ReloadedKeySettings = field(default_factory=ReloadedKeySettings)

    _sync_hook: rt.runtime_manager.SyncHook | None = None
    _viewer_lock: Callable[[], AbstractContextManager[Any]] | None = None
    playback_speed: float = 1.0
    _current_trial_dir: Path | None = None
    _job_status: JobStatus | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    run_control: rt.RunControl = field(default_factory=rt.RunControl)
    """How the interface pauses, steps, and changes the speed of a run in progress. Handed to every `RuntimeManager` this session creates."""
    output_sink: Callable[[str], None] | None = field(
        default=None, repr=False, compare=False
    )
    """When set, messages that would be printed to the terminal are passed to this callable as rich markup strings instead. The terminal UI uses it to show them in its log pane."""

    _trial_padding_style = "03d"

    def _print(self, *args, **kwargs) -> None:
        """Prints a message to the terminal, or, once the terminal UI has taken over the screen, hands it to `output_sink` as rich markup."""
        if self.output_sink is not None:
            self.output_sink(" ".join(str(a) for a in args))
            return
        console.print(*args, **kwargs)

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
            args_used=describe_args(self.args),
            kwargs_used=describe_kwargs(self.kwargs),
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

    def validate(self) -> None:
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
        from ..cli import _load_func

        project_root = Path.cwd()

        def reload_with_check(
            path_str: str, label: str
        ) -> Callable[..., Any] | tuple[Callable[..., Any], types.ModuleType]:
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

        # a misspelled --kwarg is dropped silently by the per-function filtering, so say so
        shared_targets: dict[str, tuple[Callable[..., Any], int]] = {}
        if gen_func is not None:
            shared_targets["generator"] = (gen_func, GENERATOR_FIXED_ARGS)
        if run_func is not None:
            shared_targets["runtime"] = (run_func, RUNTIME_FIXED_ARGS)
        try:
            validate_shared_kwargs(self.kwargs, self.args, shared_targets)
        except ValueError as e:
            self._print(f"[bold red]Error:[/bold red] {escape(str(e))}")
            raise

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
                        *self.args,
                        **select_kwargs(
                            gen_func, GENERATOR_FIXED_ARGS, self.args, self.kwargs
                        ),
                    )
                    mojo_model._trial_dir = trial_dir
                    if self.model_config_name:
                        mojo_model.dump_to_path(trial_dir / self.model_config_name)
                    (trial_dir / NAMED_VALUES_FNAME).write_text(
                        mojo_model.named.model_dump_json()
                    )

                    # clear and rebuild on every reload (rather than write-once like
                    # the Runner) since the user's generator, and therefore which
                    # distributions exist (or whether any exist at all), can change
                    # between reloads; wiping first means a dropped category/dist_type
                    # or an emptied dists dict doesn't leave stale files behind
                    stochas_dir = self.workdir / STOCHAS_DIR_NAME
                    shutil.rmtree(stochas_dir, ignore_errors=True)
                    if mojo_model.dists:
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
                        playback_speed=self.playback_speed,
                        _stop_event=self.stop_event,
                        _run_control=self.run_control,
                    )
                    start = time.time()
                    run_func(
                        mojo_model,
                        runtime_manager,
                        state,
                        *self.args,
                        **select_kwargs(
                            run_func, RUNTIME_FIXED_ARGS, self.args, self.kwargs
                        ),
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

    def run(self) -> None:
        self.validate()

        self.workdir = self.workdir.resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        (self.workdir / ".gitignore").write_text("*")
        write_dojo_script(self.workdir)
        self._trial_padding_style = self._infer_padding_style()

        # picked before the first generation, so a viewer that cannot run here fails at once instead of after the wait
        try:
            backend = self._create_backend()
        except ViewerUnavailableError as e:
            console.print(f"[bold red]Error:[/bold red] {escape(str(e))}")
            raise typer.Exit(1)

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

        try:
            self._run_tui(backend, initial_state)
        except ViewerUnavailableError as e:
            console.print(f"[bold red]Error:[/bold red] {escape(str(e))}")
            raise typer.Exit(1)
        console.print("\n[bold yellow]Exiting MuJoCo Mojo Reloaded[/bold yellow]")
        if backend.failure is not None:
            console.print(
                f"[bold red]The viewer stopped:[/bold red] {escape(backend.failure)}"
            )

    def _create_backend(self) -> ViewerBackend:
        """The viewer to show the model in, chosen by `ui`. The terminal UI drives every one of them the same way."""
        match self.ui:
            case UserInterface.OPENGL:
                return OpenGLBackend(xml_path=self._trial_xml_path)
            case UserInterface.STUDIO | UserInterface.WEB:
                check_studio_available(self.ui)
                return StudioBackend(
                    xml_path=self._trial_xml_path,
                    web=self.ui is UserInterface.WEB,
                    port=self.port,
                    gfx=self.gfx,
                )
            case _ as unreachable:
                assert_never(unreachable)

    def _trial_xml_path(self) -> Path:
        """The file the current model was written to."""
        assert self._current_trial_dir is not None
        return self._current_trial_dir / self.xml_name

    def _run_tui(self, backend: ViewerBackend, state: MjState) -> None:
        """Opens the viewer on `state` and runs the terminal UI over it until the user quits or the viewer is closed."""
        controller = ReloadedController(self, backend)
        backend.attach(controller)
        # if native code in the viewer crashes the process, this saves where, and puts the terminal right
        with CrashGuard(self.workdir / "crash.log"):
            backend.start(state)
            try:
                self._sync_hook = backend.sync_hook
                self._viewer_lock = backend.viewer_lock
                self.run_control.pump = backend.pump
                ReloadedApp(
                    controller,
                    backend,
                    keys=self.keys,
                    subtitle=f"{self.ui.value} | {self.workdir}",
                ).run()
            finally:
                self._sync_hook = None
                self._viewer_lock = None
                self.run_control.pump = None
                backend.close()
