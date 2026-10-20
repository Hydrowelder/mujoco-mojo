from __future__ import annotations

import inspect
import itertools
import json
import logging
import math
import multiprocessing
import os
import re
import shutil
import stat
import subprocess
import sys
from bdb import BdbQuit
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from logging.handlers import QueueListener
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, Self

import numpy as np
from filelock import FileLock
from numpydantic import NDArray
from pydantic import Field, field_validator, model_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.stochas import (
    NOMINAL_TRIAL_NUM,
    DesignValueDict,
    NamedValue,
    NamedValueDict,
    ValueName,
)
from mujoco_mojo.typing import Direction, Sampler
from mujoco_mojo.utils.defaults import (
    DEFAULT_MC_N_TRIAL,
    DEFAULT_MODEL_CONFIG_NAME,
    DEFAULT_N_PROC,
    DEFAULT_OP_EVALS_PER_TRIAL,
    DEFAULT_OP_N_TRIAL,
    DEFAULT_OP_PRUNE_FAILED_TRIALS,
    DEFAULT_OP_REFINE_SEARCH_FACTOR,
    DEFAULT_OP_SAMPLER,
    DEFAULT_OP_STORAGE,
    DEFAULT_OP_STUDY_NAME,
    DEFAULT_OP_TIMEOUT,
    DEFAULT_RESUME,
    DEFAULT_RUNTIME,
    DEFAULT_SEED,
    DEFAULT_WORKDIR,
    DEFAULT_XML_NAME,
    NAMED_VALUES_FNAME,
    STOCHAS_DIR_NAME,
    STOCHAS_DISTS_FNAME,
)
from mujoco_mojo.utils.log import get_logger, get_trial_log_handler, worker_init
from mujoco_mojo.utils.slurm import (
    UNKNOWN_LIMIT,
    SlurmConfig,
    SlurmJob,
    SlurmSubmission,
    array_problem,
    build_submission_script,
    cpu_problem,
    mem_problem,
    normalize_to_mb,
    parse_job_id,
    slurm_time_to_seconds,
    time_problem,
)
from mujoco_mojo.utils.statusing import (
    JOB_STATUS_FNAME,
    TRIAL_STATUS_FNAME,
    Completion,
    ExecutionMode,
    JobStatus,
    JobType,
    TrialStatus,
)
from mujoco_mojo.utils.utils import write_dojo_script
from mujoco_mojo.utils.watching import watch_job

if TYPE_CHECKING:
    import optuna
    from rich.console import Console

    from mujoco_mojo.runtime.runtime_manager import RuntimeManager
    from mujoco_mojo.settings import SlurmExtraSettings

logger = get_logger(__name__)


def _print_slurm_extras(console: Console, slurm: SlurmExtraSettings) -> None:
    """
    Prints which settings files were read and the extra `#SBATCH` lines and environment variables that will be added to the submission script.

    Each file is listed with where it was looked for, since the project file is the nearest `.mujoco-mojo/settings.toml` found searching the current directory and its parents. Environment variable values are not printed, only their names, since they are often credentials or license servers; the values are in the generated script.
    """
    from rich.markup import escape

    from mujoco_mojo.settings import slurm_settings_sources

    sources = slurm_settings_sources()
    console.print("\n[bold cyan]SLURM settings[/bold cyan]")
    for source in sources:
        if source.error is not None:
            status = f"[red]could not be read: {escape(source.error)}[/red]"
        elif not source.exists:
            # the project file is searched for upward from here, so say where it started
            searched = (
                f" (searched {escape(str(Path.cwd()))} and its parent directories)"
                if source.label == "project"
                else ""
            )
            status = f"[yellow]not found[/yellow]{searched}"
        else:
            count = len(source.entries)
            status = f"{count} [dim]{'entry' if count == 1 else 'entries'} under \\[slurm][/dim]"
        console.print(
            f"  [white]{source.label:<8}[/white] {escape(str(source.path))}  {status}"
        )

    # a key set in both files takes the project value, so attribute it to the project
    project_keys = set(sources[-1].entries) if sources else set()

    def origin(key: str) -> str:
        return "project" if key in project_keys else "global"

    sbatch_keys = [k for k in slurm.root if k.startswith("sbatch.")]
    env_keys = [k for k in slurm.root if not k.startswith("sbatch.")]
    sbatch_lines = slurm.sbatch_lines()

    if not slurm.root:
        console.print(
            "\n[yellow]No extra SLURM settings were found.[/yellow] "
            'Add entries such as [italic]"sbatch.account" = "proj123"[/italic] under [bold]\\[slurm][/bold] '
            "in one of the files above (or run [italic]mujoco-mojo settings set --project slurm.sbatch.account proj123[/italic])."
        )
        logger.info("No extra SLURM settings were found.", extra={"file_only": True})
        return

    console.print("\n[bold]Extra lines added to the submission script:[/bold]")
    for key, line in zip(sbatch_keys, sbatch_lines, strict=True):
        console.print(f"  {escape(line)}  [dim]({origin(key)})[/dim]")
        logger.info(f"SLURM extra ({origin(key)}): {line}", extra={"file_only": True})
    for key in env_keys:
        console.print(
            f"  export {escape(key)}=[dim]<value hidden>[/dim]  [dim]({origin(key)})[/dim]"
        )
        logger.info(
            f"SLURM extra environment variable ({origin(key)}): {key}",
            extra={"file_only": True},
        )


__all__ = [
    "MojoGenerator",
    "MojoObjective",
    "MojoRunner",
    "MojoRuntime",
    "MonteCarloConfig",
    "OptimizerConfig",
    "Trial",
]


# --- Protocols ---


class MojoGenerator(Protocol):
    """Definition of a function that generates a MojoModel model instance."""

    def __call__(
        self, mojo_model: MojoModel, /, *args: Any, **kwargs: Any
    ) -> MojoModel: ...


class MojoRuntime(Protocol):
    """Definition of a function that executes a generated MojoModel model."""

    def __call__(
        self,
        mojo_model: MojoModel,
        runtime_manager: RuntimeManager,
        state: MjState,
        /,
        *args: Any,
        **kwargs: Any,
    ) -> MojoModel: ...


class MojoObjective(Protocol):
    """Definition of a function that scores a completed Mojo simulation."""

    def __call__(
        self,
        mojo_model: MojoModel,
        telemetry: Path,  # Path to the output file generated by TelemetryManager
        state: MjState,
        /,
        *args: Any,
        **kwargs: Any,
    ) -> float: ...


# --- shared arguments ---

GENERATOR_FIXED_ARGS = 2
"""Leading positional arguments the runner passes to a generator itself: the model and the overrides."""

RUNTIME_FIXED_ARGS = 3
"""Leading positional arguments the runner passes to a runtime itself: the model, the runtime manager, and the state."""

OBJECTIVE_FIXED_ARGS = 3
"""Leading positional arguments the runner passes to an objective itself: the model, the telemetry path, and the state."""


def accepted_kwarg_names(
    func: Callable[..., Any], n_fixed: int, args: Sequence[Any]
) -> set[str] | None:
    """
    The keyword names `func` can take once `n_fixed` leading arguments and the positional `args` are bound to it.

    A name bound positionally is excluded, since passing it again by keyword would raise. Returns `None` when `func` takes `**kwargs`, or its signature cannot be read, because it then accepts anything.
    """
    try:
        parameters = list(inspect.signature(func).parameters.values())
    except (TypeError, ValueError):
        return None
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters):
        return None

    positional = [
        p
        for p in parameters
        if p.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    bound = {p.name for p in positional[: n_fixed + len(args)]}
    named = {
        p.name
        for p in parameters
        if p.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    return named - bound


def select_kwargs(
    func: Callable[..., Any],
    n_fixed: int,
    args: Sequence[Any],
    kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    """The part of `kwargs` that `func` accepts (all of it if `func` takes `**kwargs`), so one shared set of keyword arguments can go to several functions with different signatures."""
    names = accepted_kwarg_names(func, n_fixed, args)
    if names is None:
        return dict(kwargs)
    return {key: value for key, value in kwargs.items() if key in names}


def validate_shared_kwargs(
    kwargs: Mapping[str, Any],
    args: Sequence[Any],
    targets: Mapping[str, tuple[Callable[..., Any], int]],
) -> None:
    """
    Raises `ValueError` if a keyword argument is accepted by none of `targets`, which maps a role (such as `"generator"`) to its function and its number of fixed leading arguments.

    A function that takes `**kwargs` accepts every key, so nothing is checked when any target does; this catches a misspelled key, which filtering would otherwise silently drop.
    """
    if not kwargs or not targets:
        return
    accepted: dict[str, set[str]] = {}
    for role, (func, n_fixed) in targets.items():
        names = accepted_kwarg_names(func, n_fixed, args)
        if names is None:
            return
        accepted[role] = names

    unknown = sorted(set(kwargs) - set().union(*accepted.values()))
    if not unknown:
        return
    detail = "; ".join(
        f"{role}: {sorted(names) if names else 'none'}"
        for role, names in accepted.items()
    )
    msg = f"Keyword argument(s) {unknown} are not accepted by the generator, runtime, or objective they are passed to. Keywords each one accepts - {detail}."
    logger.error(msg)
    raise ValueError(msg)


# --- Models ---


class BaseConfig(MojoBaseModel):
    n_trial: int

    n_proc: int = DEFAULT_N_PROC
    """Number of proccesses to allow.

    This value is used to determine how many parallel jobs can be run. It is also used for the discovery of trial status. Using a value of 1 will result in the slowest runtime, but highest reliability.

    Important:
        Be a good citizen. Use a reasonable number if you are working on a shared resource. You are a jerk if you use everything."""

    resume: bool = DEFAULT_RESUME
    """Whether to resume a study if the study already exists."""

    padding: int | None = Field(default=None, ge=1)
    """Zero-padding width of the trial folder names (for example `3` gives `trial_007`). When unset, the width is derived from `n_trial` so every trial in a job sorts consistently; set it when a process only knows about one trial of a larger job, such as a SLURM worker."""

    @property
    def is_parallel(self) -> bool:
        return self.n_proc > 1

    @staticmethod
    def _trial_nums(n_trial: int) -> list[int]:
        return (NOMINAL_TRIAL_NUM + np.arange(n_trial)).tolist()

    @property
    def trial_nums(self) -> list[int]:
        return self._trial_nums(self.n_trial)

    @property
    def padding_width(self) -> int:
        if self.padding is not None:
            return self.padding
        if self.n_trial == 0:
            return 1
        else:
            return len(str(max(self.trial_nums)))

    @property
    def padding_style(self) -> str:
        """
        This dynamically defines the padding style for trial numbers. This is helpful to ensure the filesystem consistently sorts the trials.

        Examples:
        - Suppose you n_trials is 2000 (and the nominal trial_num is 0)
        - This method would return `04d`
            - Trial number `0` maps to `0000`
            - Trial number `123` maps to `0123`
            - Trial number `1999` will still map to `1999`

        """
        return f"0{self.padding_width}d"

    @field_validator("n_trial", "n_proc")
    @classmethod
    def validate_greater_than_zero(cls, v: int) -> int:
        if v < 1:
            # coerce an invalid value to be able to run
            return 1
        return v


class MonteCarloConfig(BaseConfig):
    n_trial: int = DEFAULT_MC_N_TRIAL
    """Number of trials to run.

    You are able to resume a previous job and modify the number of runs desired by changing this value. A job already in progress will not be dynamically stopped though if you change this value at runtime."""


class OptimizerConfig(BaseConfig):
    n_trial: int = DEFAULT_OP_N_TRIAL
    """Number of trials to run."""

    study_name: str = DEFAULT_OP_STUDY_NAME
    """Unique identifier for the Optuna study."""

    direction: Direction
    """Whether we want to find the lowest or highest objective value."""

    timeout: float | None = DEFAULT_OP_TIMEOUT
    """Stop the study after this many seconds, regardless of trial count."""

    storage: str | None = DEFAULT_OP_STORAGE
    """Database URL (e.g., 'sqlite:///study.db') for multi-node persistence."""

    sampler: Sampler = DEFAULT_OP_SAMPLER
    """The search algorithm. TPE is generally best for noisy physics."""

    evals_per_trial: int = Field(default=DEFAULT_OP_EVALS_PER_TRIAL, ge=1)
    """
    Number of times to run the sim with different seeds per trial. The average score is returned to Optuna.

    Reduces 'lucky' trials in noisy physics.
    """

    refine_search_factor: float | None = Field(
        default=DEFAULT_OP_REFINE_SEARCH_FACTOR, gt=0, lt=1
    )
    """
    If set (e.g., 0.5), and resume is True, the Runner will shrink the search space bounds by this factor around the current best trial to focus on local refinement.

    Smaller values will more aggressively refine the search space.
    """

    prune_failed_trials: bool = DEFAULT_OP_PRUNE_FAILED_TRIALS
    """
    Whether to immediately stop trials that violate physical constraints (e.g., Mujoco instability) to save compute time.
    """

    @model_validator(mode="after")
    def validate_storage(self) -> Self:
        if self.n_proc > 1 and self.storage is None:
            msg = f"Optimization configuration had more than one proc ({self.n_proc}) but no storage location defined."
            logger.error(msg)
            raise ValueError(msg)
        return self

    def _get_sampler(self, seed: int | None) -> optuna.samplers.BaseSampler:
        """Translates the string config into an Optuna Sampler instance."""
        try:
            import optuna
        except ModuleNotFoundError:
            msg = "The `optuna` package is required for optimization. Install with `uv add mujoco-mojo[optimize]` or `pip install mujoco-mojo[optimize]`"
            logger.exception(msg)
            raise ModuleNotFoundError(msg)

        match self.sampler:
            case "tpe":
                return optuna.samplers.TPESampler(seed=seed)
            case "cmaes":
                return optuna.samplers.CmaEsSampler(seed=seed)
            case "random":
                return optuna.samplers.RandomSampler(seed=seed)
            case "nsgaii":
                return optuna.samplers.NSGAIISampler(seed=seed)
            case "nsgaiii":
                # NSGA-III is technically for 3+ objectives, but it works as a robust genetic algorithm for single-objective too.
                return optuna.samplers.NSGAIIISampler(seed=seed)
            case "qmc":
                # Quasi-Monte Carlo: Great for uniform coverage of design space
                return optuna.samplers.QMCSampler(seed=seed)
            case "gp":
                # Gaussian Process: Best for very expensive MuJoCo simulations where you can only afford a few dozen trials.
                return optuna.samplers.GPSampler(seed=seed)
            case "brute":
                # No seed supported for Brute Force
                return optuna.samplers.BruteForceSampler()
            case _:
                return optuna.samplers.TPESampler(seed=seed)


@dataclass
class Trial:
    """
    Handles the lifecycle of a single simulation run.

    The Trial object is responsible for the 'dirty work' of a Monte Carlo run:
    - Creating directories
    - Writing the MJCF XML
    - Saving the configuration snapshot
    - Triggering the physics runtime.

    """

    trial_num: int
    """Unique identifier for this trial iteration."""

    base_dir: Path
    """Root directory where all simulation trials are stored."""

    xml_name: str
    """Filename for the generated MJCF XML (e.g., 'model.xml')."""

    model_config_name: str | None
    """Filename for the serialized MojoModel configuration (e.g., 'config.json')."""

    padding_style: str
    """Format specifier for directory naming (e.g., '04d')."""

    @property
    def shared_asset_dir(self) -> Path:
        return self.base_dir.resolve() / "assets"

    @staticmethod
    def _trial_dir(workdir: Path, trial_num: int, padding_style: str) -> Path:
        return (workdir / "trials" / f"trial_{trial_num:{padding_style}}").resolve()

    @property
    def trial_dir(self) -> Path:
        """
        The absolute path to this trial's unique workspace.

        Example:
            If base_dir is './sims' and trial_num is 7 with '03d' padding,
            this returns './sims/trial_007'.

        """
        return self._trial_dir(self.base_dir, self.trial_num, self.padding_style)

    @property
    def xml_path(self) -> Path:
        """The full path to the MJCF XML file for this trial."""
        return self.trial_dir / self.xml_name

    @property
    def model_config_path(self) -> Path:
        """The full path to the JSON configuration file for this trial."""
        if self.model_config_name:
            return self.trial_dir / self.model_config_name
        else:
            msg = "No model config name was set. Unable to determine where it would be saved."
            logger.error(msg)
            raise ValueError(msg)

    @property
    def named_value_path(self) -> Path:
        """The full path to the JSON NamedValue file for this trial."""
        return self.trial_dir / NAMED_VALUES_FNAME

    def run(
        self,
        generator: MojoGenerator,
        runtime: MojoRuntime | None,
        seed: int | None,
        overrides: NamedValueDict[NDArray],
        args: Sequence[Any],
        kwargs: Mapping[str, Any],
    ) -> tuple[MojoModel | None, TrialStatus, MjState | None]:
        """
        Executes the complete simulation pipeline for this trial.

        This method coordinates three main phases:
        1.  **Generation**: Calls the user-provided generator to build a `MojoModel` model.
        2.  **Persistence**: Creates the workspace and writes the model/config to disk.
        3.  **Execution**: Triggers the physics runtime if one is provided.

        Args:
            generator: Function that returns a `MojoModel` instance.
            runtime: Optional function to run the simulation (MuJoCo).
            seed: Seed to use to define the trial.
            overrides: Key-value pairs that override random distributions.
            args: Positional arguments passed to the generator and the runtime.
            kwargs: Keyword arguments, each function receiving only the ones it accepts.

        Returns:
            The `MojoModel` object for the trial or None if there was a failure prior to generating the MojoModel and the status of the trial.

        """
        status = TrialStatus(trial_num=self.trial_num)
        status._path = self.trial_dir / TRIAL_STATUS_FNAME

        # set up a per-trial log file capturing everything logged during this trial
        self.trial_dir.mkdir(parents=True, exist_ok=True)
        trial_log_handler = get_trial_log_handler(self.trial_dir / "mojo.log")
        root_logger = logging.getLogger()
        root_logger.addHandler(trial_log_handler)

        with status.record_step(step_name="pending"):
            pass

        from mujoco_mojo.runtime.requirements_manager import RequirementSatisfied
        from mujoco_mojo.runtime.runtime_manager import SimulationStopped

        result = None
        state = None
        runtime_manager: RuntimeManager | None = None
        try:
            # 1. Generate
            with status.record_step(step_name="generating"):
                logger.info(f"Generating trial_num={self.trial_num}")
                mojo_model = (
                    MojoModel()
                    .with_overrides(overrides=overrides)
                    .with_seed(seed=seed)
                    .with_trial_num(self.trial_num)
                )
                mojo_model = generator(
                    mojo_model,
                    overrides,
                    *args,
                    **select_kwargs(generator, GENERATOR_FIXED_ARGS, args, kwargs),
                )
                mojo_model._trial_dir = self.trial_dir

                # 2. Setup Workspace & Save Metadata
                logger.info(f"Saving trial_num={self.trial_num} to {self.trial_dir}")

                # bundle assets, this remaps DepPath attributes to point to the shared asset dir
                rel_to_xml = Path(
                    os.path.relpath(self.shared_asset_dir, self.trial_dir)
                )
                mojo_model.mjcf.bundle_assets(
                    target_dir=self.shared_asset_dir, rel_to_xml=rel_to_xml
                )

                # save XML (with modified DepPath)
                if runtime is None:
                    mojo_model.mjcf.write_xml(self.xml_path)
                if self.model_config_name:
                    mojo_model.dump_to_path(self.model_config_path)
                self.named_value_path.write_text(mojo_model.named.model_dump_json())

            with status.record_step(step_name="solving"):
                # 3. Execute (if runtime provided)
                if runtime is not None:
                    logger.info(f"Executing trial_num={self.trial_num} runtime")
                    import mujoco_mojo.runtime as rt

                    runtime_manager = rt.RuntimeManager(
                        signal_manager=rt.SignalManager(
                            export_path=self.trial_dir
                            / rt.SignalManager.default_output_name(),
                            unit_system=mojo_model.us,
                        )
                    )
                    runtime_manager._mojo_model = mojo_model
                    state = mojo_model.mjcf.prep_for_sim(
                        self.xml_path, unit_system=mojo_model.us
                    )
                    result = runtime(
                        mojo_model,
                        runtime_manager,
                        state,
                        *args,
                        **select_kwargs(runtime, RUNTIME_FIXED_ARGS, args, kwargs),
                    )
                    status.requirements = runtime_manager.requirement_results
                else:
                    logger.info(
                        f"No runtime definition was provided for trial_num={self.trial_num} so MuJoCo will not be run."
                    )
                    result = mojo_model
                    state = None

            # serialize again in case new named values were added during the run
            if self.model_config_name:
                mojo_model.dump_to_path(self.model_config_path)
            self.named_value_path.write_text(mojo_model.named.model_dump_json())

            # clear unpicklable collision managers before returing to avoid multiprocessing serialization erros
            mojo_model.clear_unpickleable_data()

            status.step = "done"
            if status.requirements and not all(r.passed for r in status.requirements):
                status.completion = Completion.FAILURE
            else:
                status.completion = Completion.SUCCESS

        except (BdbQuit, KeyboardInterrupt):
            logger.warning("Quit command detected. Exiting execution...")
            raise
        except RequirementSatisfied:
            # a live requirement ended the trial early as a success: complete
            # normally, with the outcome decided by the requirement results
            status.step = "done"
            if runtime_manager is not None:
                status.requirements = runtime_manager.requirement_results
            if status.requirements and not all(r.passed for r in status.requirements):
                status.completion = Completion.FAILURE
            else:
                status.completion = Completion.SUCCESS
        except SimulationStopped:
            status.step = "done"
            status.completion = Completion.TERMINATED
            if runtime_manager is not None:
                status.requirements = runtime_manager.requirement_results
        except Exception as e:
            status.step = "done"
            status.completion = Completion.ERROR
            logger.exception(
                f"Trial {self.trial_num} failed with the following error: {e}"
            )
        finally:
            status.dump_to_path(status._path)
            root_logger.removeHandler(trial_log_handler)
            trial_log_handler.close()

        return result, status, state


@dataclass
class MojoRunner:
    generator: MojoGenerator
    generator_path: str | None = None  # e.g., "sim.generate"
    runtime: MojoRuntime | None = DEFAULT_RUNTIME
    runtime_path: str | None = None  # e.g., "sim.runtime"
    objective: MojoObjective | None = None
    objective_path: str | None = None
    seed: int | None = DEFAULT_SEED
    workdir: Path = DEFAULT_WORKDIR
    model_config_name: str | None = DEFAULT_MODEL_CONFIG_NAME
    xml_name: str = DEFAULT_XML_NAME
    config: MonteCarloConfig | OptimizerConfig = field(default_factory=MonteCarloConfig)

    args: list[Any] = field(default_factory=list)
    """Positional arguments passed to the generator, the runtime, and the objective."""

    kwargs: dict[str, Any] = field(default_factory=dict)
    """Keyword arguments shared by the generator, the runtime, and the objective. Each receives only the ones it accepts (all of them if it takes `**kwargs`)."""

    def shared_argument_flags(self) -> str:
        """The `--arg` and `--kwarg` options that hand this runner's arguments to another `mujoco-mojo` process, such as a SLURM worker."""
        flags = [f'--arg "{a}"' for a in self.args]
        flags += [f'--kwarg "{k}={v}"' for k, v in self.kwargs.items()]
        return " ".join(flags)

    def validate_kwargs(self) -> None:
        """
        Raises `ValueError` if a keyword argument is accepted by none of the generator, the runtime, and the objective.

        Each function is only given the keywords it accepts, so a misspelled one would otherwise be dropped silently. A function that takes `**kwargs` accepts everything, which turns the check off.
        """
        targets: dict[str, tuple[Callable[..., Any], int]] = {
            "generator": (self.generator, GENERATOR_FIXED_ARGS)
        }
        if self.runtime is not None:
            targets["runtime"] = (self.runtime, RUNTIME_FIXED_ARGS)
        if self.objective is not None:
            targets["objective"] = (self.objective, OBJECTIVE_FIXED_ARGS)
        validate_shared_kwargs(self.kwargs, self.args, targets)

    @staticmethod
    def inspect_protocol(
        func: MojoGenerator | MojoRuntime | MojoObjective | None,
    ) -> tuple[str, Path | None, int | None]:
        if func is None:
            return ("none defined", None, None)
        try:
            # 1. Get the file path
            gen_file = inspect.getfile(func)

            # 2. Get the qualified name (e.g., "Experiment.generate")
            # This gives you the class context automatically
            gen_name = getattr(func, "__qualname__", None) or getattr(
                func, "__name__", type(func).__name__
            )

            # 3. Get the line number
            # getsourcelines returns ([lines], starting_line_number)
            _, line_num = inspect.getsourcelines(func)

            return (f"{gen_name}", Path(gen_file).resolve(), line_num)

        except Exception as e:
            logger.exception(f"Failed to capture generator details: {e}")
            return (f"{func}", None, None)

    def capture_environment(self) -> None:
        req_path = self.workdir / "requirements.txt"

        # 1. Try 'uv' first (since it's the modern standard)
        try:
            result = subprocess.run(
                ["uv", "pip", "freeze"], capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout:
                req_path.write_text(result.stdout, encoding="utf-8")
                return
        except FileNotFoundError:
            pass

        # 2. Fallback to standard pip
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout:
                req_path.write_text(result.stdout, encoding="utf-8")
                return
        except Exception:
            pass

        # 3. Last resort: Record the Python version and basic info
        req_path.write_text(
            f"# Fallback: Could not use uv/pip\n# Python Version: {sys.version}\n",
            encoding="utf-8",
        )

    @staticmethod
    def force_remove_dir(countdown_from: int, path: Path):
        if not path.exists():
            return

        import time

        from rich.live import Live
        from rich.panel import Panel

        with Live(refresh_per_second=4) as live:
            for i in range(countdown_from, 0, -1):
                live.update(
                    Panel(
                        f"[bold red]DANGER:[/] clean_workdir is active. \n"
                        f"Deleting: [cyan]{path}[/]\n"
                        f"Continuing in [bold yellow]{i:>2}[/] seconds... ([bold yellow]Ctrl+C[/] to abort)",
                        title="Cleanup Countdown",
                        border_style="red",
                    )
                )
                time.sleep(1)
        logger.info(f"Countdown finished. Commencing cleanup of {path}")

        # On Windows, `dojo.sh` (written by write_dojo_script) stays checked out for as
        # long as a `mujoco-mojo dojo` monitoring session launched from it is still
        # running, even after the dojo.sh template was fixed to `exec` into the server
        # process instead of forking it (older workdirs still have the un-fixed
        # script). Rather than fail the whole cleanup over one harmless,
        # idempotently-regenerated launcher script, skip just that file if it's still
        # locked and let the rest of the workdir clear out normally.
        skipped_dojo_script = False

        def _on_rmtree_error(_func, error_path: str, exc: BaseException) -> None:
            nonlocal skipped_dojo_script
            error_path_obj = Path(error_path)
            if error_path_obj.name == "dojo.sh" and error_path_obj.parent == path:
                logger.warning(
                    f"{error_path_obj} is still locked (likely a running `mujoco-mojo "
                    "dojo` session); leaving it in place and continuing cleanup."
                )
                skipped_dojo_script = True
                return
            if error_path_obj == path and skipped_dojo_script:
                # path can't be rmdir'd because dojo.sh is still inside it. Expected
                # once we've already decided to leave that file behind above
                return
            raise exc

        # try to chmod and remove first
        try:
            for root, dirs, files in os.walk(path):
                for d in dirs:
                    d_path = os.path.join(root, d)
                    try:
                        os.chmod(d_path, os.stat(d_path).st_mode | stat.S_IRWXU)
                    except PermissionError:
                        pass  # move to rm -rf instead
                for f in files:
                    f_path = os.path.join(root, f)
                    try:
                        os.chmod(f_path, os.stat(f_path).st_mode | stat.S_IWUSR)
                    except PermissionError:
                        pass

            shutil.rmtree(path, onexc=_on_rmtree_error)
            return
        except Exception:
            logger.warning(
                f"Python-native cleanup failed for {path}. Attempting system rm -rf..."
            )

        # nuclear option!
        try:
            subprocess.run(["rm", "-rf", str(path.resolve())], check=True)
            logger.info(f"System rm -rf successfully cleared {path}")
        except subprocess.CalledProcessError as e:
            msg = f"Ultimate cleanup failure: {path} is being held by the system. Error: {e}"
            logger.error(msg)
            raise RuntimeError(msg)

    def _prepare_run(self, clean_workdir: bool, cleanup_delay: int) -> None:
        """The checks and workdir setup shared by every way of starting a job: running it, or submitting it to SLURM."""
        funcs = {
            "generator": self.generator,
            "runtime": self.runtime,
            "objective": self.objective,
        }
        non_none = {k: v for k, v in funcs.items() if v is not None}
        seen: dict[int, str] = {}
        for role, func in non_none.items():
            fid = id(func)
            if fid in seen:
                msg = f"'{getattr(func, '__qualname__', func)}' is assigned to both '{seen[fid]}' and '{role}'. Each function must be unique."
                logger.error(msg)
                raise ValueError(msg)
            seen[fid] = role

        self.validate_kwargs()

        if clean_workdir:
            if self.config.resume:
                msg = "clean_workdir and resume are mutually exclusive with one another. Use one or the other."
                logger.error(msg)
                raise ValueError(msg)

            self.force_remove_dir(countdown_from=cleanup_delay, path=self.workdir)

        self.workdir.mkdir(parents=True, exist_ok=True)
        if not (self.workdir / ".gitignore").exists():
            (self.workdir / ".gitignore").write_text("*", encoding="utf-8")

        # SLURM workers re-enter run() with execution_mode=LOCAL; these only need
        # to happen once, during orchestration, to avoid every worker racing to
        # write the same shared files
        if self.slurm_trial_id is None:
            write_dojo_script(self.workdir)
            self.capture_environment()

    def run(
        self,
        global_overrides: NamedValueDict[NDArray] = NamedValueDict[NDArray](),
        clean_workdir: bool = False,
        cleanup_delay: int = 10,
        execution_mode: ExecutionMode = ExecutionMode.LOCAL,
        trial_nums: list[int] | None = None,
    ) -> bool:
        """Vectors a job to be either computed locally or to be orchestrated by SLURM."""
        self._prepare_run(clean_workdir, cleanup_delay)

        match execution_mode:
            case ExecutionMode.LOCAL:
                return self.run_local(
                    global_overrides=global_overrides,
                    trial_nums=trial_nums,
                )
            case ExecutionMode.SLURM:
                return self.orchestrate_slurm(
                    global_overrides=global_overrides,
                    trial_nums=trial_nums,
                )
            case _:
                msg = f"No run command has been configured for execution mode {execution_mode}"
                logger.error(msg)
                raise NotImplementedError(msg)

    def run_local(
        self,
        global_overrides: NamedValueDict[NDArray] = NamedValueDict[NDArray](),
        trial_nums: list[int] | None = None,
    ) -> bool:
        if isinstance(self.config, MonteCarloConfig):
            had_fails = self.run_monte_carlo(
                global_overrides=global_overrides,
                trial_nums=trial_nums,
            )
        elif isinstance(self.config, OptimizerConfig):
            had_fails = self.run_optimization(
                global_overrides=global_overrides,
            )
        else:
            msg = f"A configuration for {self.config.__class__.__name__} has not been implemented."
            logger.error(msg)
            raise NotImplementedError(msg)
        return had_fails

    @property
    def slurm_trial_id(self) -> int | None:
        """Returns the current SLURM task ID if running as part of an array job."""
        tid = os.getenv("SLURM_ARRAY_TASK_ID")
        return int(tid) if tid is not None else None

    def orchestrate_slurm(
        self,
        global_overrides: NamedValueDict[NDArray],
        trial_nums: list[int] | None = None,
    ) -> bool:
        """Generates an sbatch script and submits the job array to SLURM for a given config."""
        (self.workdir / "logs").mkdir(exist_ok=True)

        from rich.console import Console

        Console().print(
            "[dim]Tip: set '[slurm]' entries in ~/.mujoco-mojo/settings.toml (or a project-local "
            "./.mujoco-mojo/settings.toml, via `mujoco-mojo settings set --project`) to auto-inject "
            "extra #SBATCH lines (prefix a key with 'sbatch.', e.g. 'sbatch.account') and/or "
            "environment variables (any other key) into the generated submission script.[/dim]"
        )

        if isinstance(self.config, MonteCarloConfig):
            try:
                had_fails = self.orchestrate_slurm_monte_carlo(
                    global_overrides=global_overrides,
                    trial_nums=trial_nums,
                )
            except (BdbQuit, KeyboardInterrupt):
                print("\n")
                logger.error("Aborted SLURM orchestration!")
                had_fails = True
        else:
            msg = f"A SLURM configuration for {self.config.__class__.__name__} has not been implemented."
            logger.error(msg)
            raise NotImplementedError(msg)
        return had_fails

    def _renumber_trial_folders(self, workdir: Path, new_padding_style: str) -> None:
        """
        Rename trial folders whose zero-padding no longer matches new_padding_style.

        This is needed when a job is resumed with a larger n_trial that widens the padding (e.g. 20 trials used 'trial_00'; expanding to 200 requires 'trial_000').

        Without renaming, the status scanner looks for 'trial_000' and misses 'trial_00', causing already-completed trials to be scheduled again.
        """
        trials_dir = workdir / "trials"
        if not trials_dir.exists():
            return

        for folder in sorted(trials_dir.iterdir()):
            if not folder.is_dir() or not folder.name.startswith("trial_"):
                continue
            suffix = folder.name[len("trial_") :]
            try:
                trial_num = int(suffix)
            except ValueError:
                continue
            expected_name = f"trial_{trial_num:{new_padding_style}}"
            if folder.name == expected_name:
                continue
            new_path = trials_dir / expected_name
            if new_path.exists():
                logger.warning(
                    f"Cannot renumber {folder.name} -> {expected_name}: target already exists. Skipping."
                )
                continue
            folder.rename(new_path)
            logger.info(f"Renumbered {folder.name} -> {expected_name}")

    def execute_single_trial(
        self, trial_num: int, seed: int | None, overrides_payload: dict
    ) -> tuple[MojoModel | None, TrialStatus, MjState | None]:
        """
        Helper to package a Trial and run it.

        The model and state are live in-process objects; callers that need to cross a ProcessPoolExecutor boundary (i.e. parallel MC) must use `_execute_trial_subprocess` instead, which drops the non-picklable objects before the result is serialized back.

        Returns `(mojo_model, trial_status, state)`.
        """
        overrides = NamedValueDict[NDArray].model_validate(overrides_payload)

        trial = Trial(
            trial_num=trial_num,
            base_dir=self.workdir,
            xml_name=self.xml_name,
            model_config_name=self.model_config_name,
            padding_style=self.config.padding_style,
        )

        mojo_model, trial_status, state = trial.run(
            generator=self.generator,
            runtime=self.runtime,
            seed=seed,
            overrides=overrides,
            args=self.args,
            kwargs=self.kwargs,
        )

        # write distribution tables from this process so they never need to
        # cross the pickle boundary; FileLock serializes concurrent workers,
        # and the inner exists() check ensures only the first one writes
        if mojo_model is not None and mojo_model.dists:
            stochas_dir = self.workdir / STOCHAS_DIR_NAME
            stochas_dir.mkdir(exist_ok=True)
            dists_json_path = stochas_dir / STOCHAS_DISTS_FNAME
            with FileLock(stochas_dir / ".dists.lock"):
                if not dists_json_path.exists():
                    mojo_model.dists.to_tables(stochas_dir)
                    tmp = stochas_dir / "dists.tmp.json"
                    tmp.write_text(mojo_model.dists.model_dump_json(), encoding="utf-8")
                    tmp.replace(dists_json_path)

        return mojo_model, trial_status, state

    def _execute_trial_subprocess(
        self, trial_num: int, seed: int | None, overrides_payload: dict
    ) -> TrialStatus:
        """
        Subprocess-safe wrapper around `execute_single_trial` for parallel MC.

        Runs the trial in-process (including stochas writes), then drops the non-picklable MojoModel and MjState before returning so the result can be serialized back across the ProcessPoolExecutor boundary.
        """
        _, trial_status, _ = self.execute_single_trial(
            trial_num, seed, overrides_payload
        )
        return trial_status

    def run_monte_carlo(
        self,
        global_overrides: NamedValueDict[NDArray] = NamedValueDict[NDArray](),
        trial_nums: list[int] | None = None,
    ) -> bool:
        """Orchestrates a Monte Carlo job."""
        if self.slurm_trial_id is not None:
            tn = self.slurm_trial_id
            logger.info(f"SLURM Worker detected. Executing Trial {tn}")
            _mojo_model, trial_status, _ = self.execute_single_trial(
                trial_num=tn,
                seed=self.seed,
                overrides_payload=global_overrides.model_dump(),
            )

            return trial_status.completion == Completion.ERROR

        job_trial_nums = trial_nums if trial_nums else self.config.trial_nums

        # initialize the status tracker
        status_tracker = JobStatus(
            workdir=self.workdir.resolve(),
            job_type=JobType.MONTE_CARLO,
            execution_mode=ExecutionMode.LOCAL,
            n_proc=self.config.n_proc,
            seed=self.seed,
            padding_style=self.config.padding_style,
            generator=MojoRunner.inspect_protocol(self.generator),
            runtime=MojoRunner.inspect_protocol(self.runtime),
            objective=MojoRunner.inspect_protocol(self.objective),
            args_used=bool(self.args),
            kwargs_used=bool(self.kwargs),
            trial_nums=job_trial_nums,
        )

        # decide which trials to execute
        if self.config.resume:
            self._renumber_trial_folders(
                self.workdir.resolve(), self.config.padding_style
            )
            status_tracker.refresh_from_disk(n_proc=self.config.n_proc)
        status_tracker.dump_to_path(self.workdir / JOB_STATUS_FNAME)

        to_run = status_tracker.pending_trial_nums

        if not to_run:
            logger.info("All trials were already completed. Nothing to do.")
            return bool(status_tracker.unsuccessful_trial_nums)

        if self.config.is_parallel:
            logger.info(
                f"Running {len(to_run)} trials with {self.config.n_proc} processors. {status_tracker.n_done}/{self.config.n_trial} ({status_tracker.progress:.2%}) trials completed."
            )
            # needed for logging on Windows
            with multiprocessing.Manager() as m:
                log_queue = m.Queue()

                parent_log_level = logging.getLogger().getEffectiveLevel()
                listener = QueueListener(log_queue, *logging.getLogger().handlers)
                listener.start()

                executor = ProcessPoolExecutor(
                    max_workers=self.config.n_proc,
                    initializer=worker_init,
                    initargs=(log_queue, parent_log_level),
                )
                try:
                    future_to_tn = {
                        executor.submit(
                            self._execute_trial_subprocess,
                            tn,
                            self.seed,
                            global_overrides.model_dump(),
                        ): tn
                        for tn in to_run
                    }
                    for f in as_completed(future_to_tn):
                        tn = future_to_tn[f]
                        try:
                            trial_status = f.result()
                            status_tracker.update_trial(status=trial_status)
                        except (BdbQuit, KeyboardInterrupt):
                            # user is quitting from breakpoint() or CTRL+C
                            raise
                        except Exception as e:
                            logger.exception(f"Trial {tn} failed: {e}")
                            status_tracker.update_trial(
                                status=TrialStatus(
                                    trial_num=tn, completion=Completion.ERROR
                                )
                            )
                        status_tracker.generate_report()
                except (BdbQuit, KeyboardInterrupt):
                    # allows killing the job with one CTRL+C
                    logger.warning("Interrupt recieved. Stopping all trials.")
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise
                finally:
                    listener.stop()
                    executor.shutdown(wait=True)
        else:
            for tn in to_run:
                try:
                    _, trial_status, _ = self.execute_single_trial(
                        trial_num=tn,
                        seed=self.seed,
                        overrides_payload=global_overrides.model_dump(),
                    )
                    status_tracker.update_trial(
                        status=trial_status,
                    )
                except (BdbQuit, KeyboardInterrupt):
                    # user is quitting from breakpoint() or CTRL+C
                    raise
                except Exception as e:
                    logger.exception(f"A trial failed with error: {e}")
                    status_tracker.update_trial(
                        status=TrialStatus(trial_num=tn, completion=Completion.ERROR)
                    )
                status_tracker.generate_report()

        status_tracker.generate_report(alert_generation=True)
        return bool(status_tracker.unsuccessful_trial_nums)

    def discover_design_space(
        self,
        global_overrides: NamedValueDict[NDArray] = NamedValueDict[NDArray](),
    ) -> DesignValueDict:
        logger.info("Performing discovery pass to map design space")
        mojo_model, _trial_status, _ = self.execute_single_trial(
            trial_num=NOMINAL_TRIAL_NUM,
            seed=self.seed,
            overrides_payload=global_overrides.model_dump(),
        )
        if mojo_model is None:
            msg = "MojoModel was not able to be generated successfully. Unable to continue with optimization."
            logger.error(msg)
            raise ValueError(msg)
        logger.info(f"Number of design space variables found: {len(mojo_model.design)}")

        # delete the workdir
        self.force_remove_dir(
            countdown_from=-1,
            path=Trial._trial_dir(
                workdir=self.workdir,
                trial_num=NOMINAL_TRIAL_NUM,
                padding_style=self.config.padding_style,
            ),
        )

        return mojo_model.design

    def run_optimization(
        self,
        global_overrides: NamedValueDict[NDArray] = NamedValueDict[NDArray](),
    ) -> bool:
        try:
            import joblib
            import optuna
        except ModuleNotFoundError:
            msg = "The `optuna` and `joblib` packages are required for optimization. Install with `uv add mujoco-mojo[optimize]` or `pip install mujoco-mojo[optimize]`"
            logger.exception(msg)
            raise ModuleNotFoundError(msg)

        assert isinstance(self.config, OptimizerConfig)
        if self.runtime is None:
            msg = "A runtime function must be provided for optimization."
            logger.error(msg)
            raise ValueError(msg)

        if self.objective is None:
            msg = "An objective function must be provided for optimization."
            logger.error(msg)
            raise ValueError(msg)

        # discovery pass to populate design space for optuna
        design_space = self.discover_design_space(global_overrides=global_overrides)

        # initialize the optimization study
        study = optuna.create_study(
            study_name=self.config.study_name,
            direction=self.config.direction.value,
            storage=self.config.storage,
            load_if_exists=self.config.resume,
            sampler=self.config._get_sampler(self.seed),
        )

        if self.config.resume and self.config.refine_search_factor is not None:
            try:
                best_params = study.best_params
                factor = self.config.refine_search_factor
                logger.info(
                    f"Refining float search space (factor: {factor}) around best trial."
                )

                for name, dv in design_space.items():
                    if name not in best_params:
                        continue

                    dv.refine(factor=factor, best_params=best_params)

            except ValueError:
                logger.warning(
                    "Refinement requested but no successful trials found. Using original bounds."
                )

        if not self.config.resume:
            nominal_params = {name: dv.value for name, dv in design_space.items()}
            study.enqueue_trial(nominal_params)
            logger.info("Enqueued nominal parameters as the Optuna Trial 0")

        status_tracker = JobStatus(
            workdir=self.workdir.resolve(),
            job_type=JobType.OPTIMIZE,
            execution_mode=ExecutionMode.LOCAL,
            n_proc=self.config.n_proc,
            seed=self.seed,
            padding_style=self.config.padding_style,
            generator=MojoRunner.inspect_protocol(self.generator),
            runtime=MojoRunner.inspect_protocol(self.runtime),
            objective=MojoRunner.inspect_protocol(self.objective),
            args_used=bool(self.args),
            kwargs_used=bool(self.kwargs),
            trial_nums=self.config.trial_nums,
        )

        if self.config.resume:
            status_tracker.refresh_from_disk(n_proc=self.config.n_proc)
        status_tracker.dump_to_path(self.workdir / JOB_STATUS_FNAME)

        # define an internal objective for optuna
        def optuna_objective(trial: optuna.Trial) -> float:
            assert isinstance(self.config, OptimizerConfig)

            suggestions = {
                name: dv.to_optuna(trial) for name, dv in design_space.items()
            }

            # prepare overrides for the trial
            # mash the suggestions into the global overrides
            trial_overrides = global_overrides.model_copy(deep=True)
            for name, val in suggestions.items():
                trial_overrides[name] = NamedValue[NDArray](
                    name=ValueName(name), stored_value=np.array([val])
                )

            trial_scores = []
            representative_status: TrialStatus | None = None
            for i in range(self.config.evals_per_trial):
                current_seed = self.seed + i if self.seed is not None else None

                # run the trial
                trial_num = trial.number
                mojo_model, iteration_status, state = self.execute_single_trial(
                    trial_num=trial_num,
                    seed=current_seed,
                    overrides_payload=trial_overrides.model_dump(),
                )

                representative_status = iteration_status

                # handle failures with maximum error if there was an epic fail
                if (
                    iteration_status.completion == Completion.ERROR
                    or mojo_model is None
                    or state is None
                ):
                    if self.config.prune_failed_trials:
                        status_tracker.update_trial(status=iteration_status)
                        return (
                            float("inf")
                            if self.config.direction == Direction.MINIMIZE
                            else float("-inf")
                        )
                    continue

                import mujoco_mojo.runtime as rt

                telemetry_path = (
                    self.workdir
                    / "trials"
                    / f"trial_{trial_num:{self.config.padding_style}}"
                    / rt.SignalManager.default_output_name()
                )

                assert self.objective
                score = self.objective(
                    mojo_model,
                    telemetry_path,
                    state,
                    *self.args,
                    **select_kwargs(
                        self.objective, OBJECTIVE_FIXED_ARGS, self.args, self.kwargs
                    ),
                )
                trial_scores.append(score)

            if representative_status is not None:
                status_tracker.update_trial(status=representative_status)
            else:
                # This branch is theoretically unreachable due to ge=1, but prevents the static analysis error.
                logger.error(f"Trial {trial.number} produced no status.")

            if not trial_scores:
                return (
                    float("inf")
                    if self.config.direction == "minimize"
                    else float("-inf")
                )

            status_tracker.generate_report()
            return float(np.mean(trial_scores))

        def logging_callback(
            study: optuna.study.Study, frozen_trial: optuna.trial.FrozenTrial
        ) -> None:
            t_num = frozen_trial.number

            logger.info(
                f"COMPLETED trial_{t_num:{self.config.padding_style}}, {frozen_trial.value:.5f} "
                f"| Best: trial_{study.best_trial.number:{self.config.padding_style}}, {study.best_value:.5f}"
            )

        try:
            if not self.config.resume:
                logger.info(
                    f"Processing trial_{0:{self.config.padding_style}} sequentially..."
                )
                study.optimize(
                    func=optuna_objective,
                    n_trials=1,
                    callbacks=[logging_callback],
                    timeout=self.config.timeout,
                    n_jobs=1,
                )

            remaining = self.config.n_trial - (0 if self.config.resume else 1)
            if remaining > 0:
                logger.info(
                    f"Processing remaining {remaining} trials with {self.config.n_proc} procs..."
                )
                study.optimize(
                    func=optuna_objective,
                    n_trials=remaining,
                    callbacks=[logging_callback],
                    timeout=self.config.timeout,
                    n_jobs=self.config.n_proc,
                )
        except (BdbQuit, KeyboardInterrupt):
            logger.warning("Optimization inturrupted by user")
            return True

        study_file = self.workdir / "study.pkl"
        joblib.dump(study, study_file)
        logger.info(f"Full Optuna study pickled to {study_file}")

        best_params_file = self.workdir / "best_params.json"
        best_params_file.write_text(json.dumps(study.best_params, indent=4))

        logger.info(
            f"Optimization finished. Best Trial: trial_{study.best_trial.number:{self.config.padding_style}}, best value: {study.best_value:.5f}"
        )
        logger.info(f"Best parameters saved to {best_params_file}")

        status_tracker.generate_report(alert_generation=True)
        return bool(status_tracker.unsuccessful_trial_nums)

    @staticmethod
    def get_slurm_array_string(ids: list[int]) -> str:
        """Collapses [0, 1, 2, 5, 6] into '0-2,5-6' for SLURM."""
        if not ids:
            return ""

        ranges = []
        # Identify groups of consecutive integers
        for _, group in itertools.groupby(
            enumerate(sorted(ids)), lambda x: x[1] - x[0]
        ):
            group = list(group)
            start = group[0][1]
            end = group[-1][1]
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")

        return ",".join(ranges)

    @staticmethod
    def get_slurm_partitions() -> tuple[list[str], str | None]:
        """Queries sinfo for available partitions and identifies the default."""
        try:
            result = subprocess.run(
                ["sinfo", "-h", "--format=%P"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                raw_partitions = [
                    p.strip() for p in result.stdout.splitlines() if p.strip()
                ]

                default_partition = None
                clean_partitions = []

                for p in raw_partitions:
                    if p.endswith("*"):
                        name = p.replace("*", "")
                        default_partition = name
                        clean_partitions.append(name)
                    else:
                        clean_partitions.append(p)

                return sorted(list(set(clean_partitions))), default_partition
        except Exception:
            pass
        return [], None

    @staticmethod
    def normalize_to_mb(mem_str: str) -> int:
        """Converts SLURM memory strings (e.g., '1000', '1G', '1024M', '125.9G') to integer MB, or 0 if the string isn't a recognizable size. See `mujoco_mojo.utils.slurm.normalize_to_mb`."""
        return normalize_to_mb(mem_str)

    @staticmethod
    def format_bytes(mb_value: int) -> str:
        """Scales MB back up to the most readable unit (G, T, etc.), with at most one decimal place. The value is rounded down, never up, so a limit shown to the user is never larger than the real limit; `normalize_to_mb` reads the result back."""
        units = ["M", "G", "T", "P"]
        value = float(mb_value)
        unit_index = 0

        # keep dividing by 1024 for as long as the next unit is reached
        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024
            unit_index += 1

        # floor to one decimal: rounding up could show more memory than the node has
        floored = math.floor(value * 10) / 10
        # if it's a whole number (like 1.0G), show it as 1G, otherwise one decimal place (like 1.5G)
        if floored.is_integer():
            return f"{int(floored)}{units[unit_index]}"
        return f"{floored:.1f}{units[unit_index]}"

    @staticmethod
    def get_slurm_node_mem_limit(partition_name: str) -> str:
        """Finds the MINIMUM RealMemory limit, normalized to MB."""
        try:
            # 1. Get nodes from partition
            part_info = subprocess.run(
                ["scontrol", "show", "partition", partition_name, "-o"],
                capture_output=True,
                text=True,
            ).stdout
            node_match = re.search(r"\bNodes=(\S+)", part_info)
            if not node_match:
                return "<UNKNOWN>"

            # 2. Get node info (can handle ranges like c[1-2])
            node_info = subprocess.run(
                ["scontrol", "show", "node", node_match.group(1), "-o"],
                capture_output=True,
                text=True,
            ).stdout

            # 3. Find all RealMemory values (capturing optional suffixes)
            # Regex captures digits and any trailing letters (like G or M)
            mem_matches = re.findall(r"\bRealMemory=(\d+(?:\.\d+)?[KMGTP]?)", node_info)
            if mem_matches:
                # Normalize every match to MB and find the lowest one
                min_mb = min(MojoRunner.normalize_to_mb(m) for m in mem_matches)
                return MojoRunner.format_bytes(min_mb)

        except Exception:
            pass

        return "<UNKNOWN>"

    @staticmethod
    def get_slurm_cpu_limit(partition_name: str) -> str:
        """Finds the minimum of the max allowed CPUs (CPUTot) among nodes in a partition."""
        try:
            # 1. Get the nodes in the partition
            part_cmd = ["scontrol", "show", "partition", partition_name, "-o"]
            part_info = subprocess.run(part_cmd, capture_output=True, text=True).stdout

            node_match = re.search(r"\bNodes=(\S+)", part_info)
            if not node_match:
                return "<UNKNOWN>"

            # 2. Get the node info
            node_cmd = ["scontrol", "show", "node", node_match.group(1), "-o"]
            nodes_info = subprocess.run(node_cmd, capture_output=True, text=True).stdout

            # 3. Find all CPUTot values (The total physical/logical CPUs on the node)
            cpu_values = re.findall(r"\bCPUTot=(\d+)", nodes_info)

            if cpu_values:
                # Find the minimum to ensure any node can handle the task
                return str(min(int(v) for v in cpu_values))

        except Exception:
            pass

        return "<UNKNOWN>"

    @staticmethod
    def slurm_time_to_seconds(time_str: str) -> int:
        """Converts a SLURM time limit to total seconds, or -1 for `UNLIMITED`. See `mujoco_mojo.utils.slurm.slurm_time_to_seconds`."""
        return slurm_time_to_seconds(time_str)

    @staticmethod
    def get_slurm_time_limit(partition_name: str) -> str:
        """Finds the MaxTime limit for a specific partition."""
        try:
            # Get partition info
            part_cmd = ["scontrol", "show", "partition", partition_name, "-o"]
            part_info = subprocess.run(part_cmd, capture_output=True, text=True).stdout

            # Look for MaxTime= followed by the time string (e.g., 1-00:00:00 or UNLIMITED)
            time_match = re.search(r"\bMaxTime=(\S+)", part_info)
            if time_match:
                return time_match.group(1)

        except Exception:
            pass

        return "<UNKNOWN>"

    @staticmethod
    def get_max_array_size() -> int:
        """Queries the global SLURM configuration for MaxArraySize."""
        try:
            result = subprocess.run(
                ["scontrol", "show", "config"], capture_output=True, text=True
            ).stdout
            match = re.search(r"MaxArraySize=(\d+)", result)
            return int(match.group(1)) if match else 1001
        except Exception:
            return 1001

    # --- SLURM submission ---
    #
    # `prepare_slurm_job`, `write_slurm_script`, and `submit_slurm_script` ask nothing, and
    # `submit_slurm` chains them for submitting from Python. The wizard below only gathers a
    # `SlurmConfig` from prompts and then uses the same three, so both paths produce the same job.

    @staticmethod
    def slurm_mojo_command() -> Path:
        """The `mujoco-mojo` executable next to the running interpreter, which the compute nodes use to run each trial."""
        return Path(sys.executable).parent.resolve() / "mujoco-mojo"

    def prepare_slurm_job(
        self,
        global_overrides: NamedValueDict[NDArray] = NamedValueDict[NDArray](),
        trial_nums: list[int] | None = None,
    ) -> SlurmJob | None:
        """
        Sets up the workdir for a SLURM submission without asking anything.

        Creates the logs folder, persists the global overrides for the workers, writes `job_status.json`, and works out which trials still need to run (honoring `resume`).

        Returns:
            The job, or `None` when every trial was already completed.

        """
        (self.workdir / "logs").mkdir(parents=True, exist_ok=True)

        # persist overrides so workers can access them
        overrides_path = self.workdir.resolve() / "global_overrides.json"
        has_overrides = len(global_overrides) > 0
        if has_overrides:
            logger.info(f"Persisting global overrides to {overrides_path}")
            overrides_path.write_text(global_overrides.model_dump_json())

        job_trial_nums = trial_nums if trial_nums else self.config.trial_nums
        status_tracker = JobStatus(
            workdir=self.workdir.resolve(),
            job_type=JobType.MONTE_CARLO,
            execution_mode=ExecutionMode.SLURM,
            n_proc=self.config.n_proc,
            seed=self.seed,
            padding_style=self.config.padding_style,
            generator=MojoRunner.inspect_protocol(self.generator),
            runtime=MojoRunner.inspect_protocol(self.runtime),
            objective=MojoRunner.inspect_protocol(self.objective),
            args_used=bool(self.args),
            kwargs_used=bool(self.kwargs),
            trial_nums=job_trial_nums,
        )

        # decide which trials to execute
        if self.config.resume:
            self._renumber_trial_folders(
                self.workdir.resolve(), self.config.padding_style
            )
            status_tracker.refresh_from_disk(n_proc=self.config.n_proc)
        status_tracker.dump_to_path(self.workdir / JOB_STATUS_FNAME)

        to_run = status_tracker.pending_trial_nums
        if not to_run:
            logger.info("All trials were already completed. Nothing to do.")
            return None
        logger.info(f"{len(to_run)} trials were identified for running.")

        return SlurmJob(
            status=status_tracker,
            to_run=to_run,
            overrides_path=overrides_path,
            has_overrides=has_overrides,
        )

    def slurm_worker_command(self, job: SlurmJob) -> str:
        """What each array task runs: one trial, picked by the array index, on a single process."""
        runtime_flag = f'--runtime "{self.runtime_path}"' if self.runtime_path else ""
        seed_flag = f"--seed {self.seed}" if self.seed is not None else ""
        overrides_flag = (
            f'--overrides "{job.overrides_path}"' if job.has_overrides else ""
        )
        return (
            f"{self.slurm_mojo_command()} run single "
            f'--generator "{self.generator_path}" '
            f"{runtime_flag} {seed_flag} {overrides_flag} "
            f'--workdir "{self.workdir.resolve()}" '
            f"{self.shared_argument_flags()} "
            f"--padding {self.config.padding_width} "  # name the trial folder like the orchestrator expects
            f"--trial-num $SLURM_ARRAY_TASK_ID "  # execute its own trial_num
            f"--execution-mode local "  # using local since slurm will just send us back to this method
            f"--n-proc 1"  # a worker only needs 1 process
        )

    def write_slurm_script(
        self, job: SlurmJob, config: SlurmConfig, console: Console
    ) -> Path:
        """Writes `mujoco_mojo_submit.sh` for `job`, adding the extra `#SBATCH` lines and environment variables from the settings files (and printing what they are)."""
        from mujoco_mojo.settings import MujocoMojoSettings

        slurm_settings = MujocoMojoSettings().slurm
        _print_slurm_extras(console, slurm_settings)

        script = build_submission_script(
            job_name=config.job_name or f"mojo-sim-{job.status.id}",
            array_range=self.get_slurm_array_string(job.to_run),
            workdir=self.workdir.resolve(),
            config=config,
            worker_command=self.slurm_worker_command(job),
            extra_sbatch_lines=slurm_settings.sbatch_lines(),
            extra_env_lines=slurm_settings.env_lines(),
        )
        script_path = (self.workdir / "mujoco_mojo_submit.sh").resolve()
        script_path.write_text(script, encoding="utf-8")
        logger.info(f"SLURM submission script written to {script_path}")
        return script_path

    def submit_slurm_script(self, job: SlurmJob, script_path: Path) -> SlurmSubmission:
        """Runs `sbatch` on the script and, once it is accepted, saves the SLURM job id in `job_status.json` so the job can be looked up (and watched) later."""
        logger.info(f"Submitting {len(job.to_run)} trials...")
        try:
            result = subprocess.run(
                ["sbatch", "--parsable", str(script_path)],
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            return SlurmSubmission(script_path, message=f"Could not run sbatch: {exc}")
        if result.returncode != 0:
            return SlurmSubmission(
                script_path, message=(result.stderr or result.stdout).strip()
            )

        job_id = parse_job_id(result.stdout)
        job.status.slurm_job_id = job_id
        job.status.dump_to_path(self.workdir / JOB_STATUS_FNAME)
        return SlurmSubmission(
            script_path,
            submitted=True,
            job_id=job_id,
            message=f"Submitted batch job {job_id}"
            if job_id
            else result.stdout.strip(),
        )

    def slurm_limit_problems(self, job: SlurmJob, config: SlurmConfig) -> list[str]:
        """Everything in the request that exceeds what the cluster reports (CPUs, memory, and time for the partition, and the array size). Limits SLURM cannot report are not checked."""
        partition = config.partition or ""
        checks = (
            cpu_problem(config.cpus_per_task, self.get_slurm_cpu_limit(partition)),
            mem_problem(config.mem, self.get_slurm_node_mem_limit(partition)),
            time_problem(config.time_limit, self.get_slurm_time_limit(partition)),
            array_problem(len(job.to_run), self.get_max_array_size()),
        )
        return [problem for problem in checks if problem is not None]

    def submit_slurm(
        self,
        config: SlurmConfig,
        global_overrides: NamedValueDict[NDArray] = NamedValueDict[NDArray](),
        trial_nums: list[int] | None = None,
        clean_workdir: bool = False,
        cleanup_delay: int = 10,
        *,
        submit: bool = True,
        skip_checks: bool = False,
        console: Console | None = None,
    ) -> SlurmSubmission | None:
        """
        Initializes a workdir and submits it to SLURM from a `SlurmConfig`, without asking anything.

        Args:
            config: The resources to request.
            global_overrides: Overrides persisted for the workers.
            trial_nums: Specific trials to run, instead of all of them.
            clean_workdir: Wipe the workdir first.
            cleanup_delay: Seconds of countdown before wiping.
            submit: Run `sbatch`. When `False` the workdir and script are written and nothing is submitted.
            skip_checks: Submit even if the request exceeds a limit the cluster reports.
            console: Where to print what happened.

        Returns:
            What was written and submitted, or `None` when every trial was already completed.

        Raises:
            ValueError: If `generator_path` is not set (or `runtime_path`, when there is a runtime), or the request exceeds a cluster limit and `skip_checks` is not set.

        """
        from rich.console import Console

        if not isinstance(self.config, MonteCarloConfig):
            msg = f"A SLURM configuration for {self.config.__class__.__name__} has not been implemented."
            logger.error(msg)
            raise NotImplementedError(msg)

        # the workers are separate `mujoco-mojo` processes that import each function by its dotted path
        missing = []
        if self.generator_path is None:
            missing.append("generator_path")
        if (
            self.runtime is not None
            and self.runtime is not DEFAULT_RUNTIME
            and self.runtime_path is None
        ):
            missing.append("runtime_path")
        if missing:
            msg = f"Set {' and '.join(missing)} (for example 'sim.generate') so the compute nodes can import the function."
            logger.error(msg)
            raise ValueError(msg)

        console = console or Console()
        self._prepare_run(clean_workdir, cleanup_delay)
        job = self.prepare_slurm_job(global_overrides, trial_nums)
        if job is None:
            console.print(
                "[green]All trials were already completed.[/] Nothing to submit."
            )
            return None

        if not skip_checks:
            problems = self.slurm_limit_problems(job, config)
            if problems:
                msg = (
                    "The request exceeds what the cluster reports:\n  - "
                    + "\n  - ".join(problems)
                    + "\nChange the request, or skip these checks to submit anyway."
                )
                logger.error(msg)
                raise ValueError(msg)

        script_path = self.write_slurm_script(job, config, console)
        if not submit:
            console.print(
                f"\n[yellow]Nothing was submitted.[/] The workdir is ready; submit it with:\n[bold green]sbatch {script_path}[/]"
            )
            return SlurmSubmission(script_path)

        submission = self.submit_slurm_script(job, script_path)
        if submission.submitted:
            console.print(f"\n[bold green]Success![/] {submission.message}")
        else:
            logger.error(f"SLURM Submission Failed: {submission.message}")
        return submission

    def orchestrate_slurm_monte_carlo(
        self,
        global_overrides: NamedValueDict[NDArray] = NamedValueDict[NDArray](),
        trial_nums: list[int] | None = None,
    ) -> bool:
        """
        Orchestrates a Monte Carlo SLURM submission interactively.

        Prompts for the resources (checking each against the partition's limits), collects them in a `SlurmConfig`, and then hands everything to the same code `submit_slurm` uses. Just before submitting it offers to keep watching the job, which keeps `job_status.json` and the runtime report current (see `watch_job`).
        """
        from rich.console import Console
        from rich.markup import escape
        from rich.prompt import Confirm, IntPrompt, Prompt

        console = Console()
        project_root = Path.cwd().resolve()

        job = self.prepare_slurm_job(global_overrides, trial_nums)
        if job is None:
            return False

        def proceed_despite(message: str, note: str = "") -> bool:
            console.print(f"\n[bold red]WARNING:[/] {message}")
            if note:
                console.print(f"[red]{note}[/]\n")
            return Confirm.ask("Do you want to proceed anyway?", default=False)

        # ask for sbatch settings with a bunch of console inputs with default values
        available_partitions, default_partition = self.get_slurm_partitions()

        console.print(
            "\n[bold cyan]MuJoCo Mojo Orchestrator: SLURM Resource Setup[/bold cyan]"
        )
        console.print(f"\t            [dim]Python:[/dim] {sys.executable}")
        console.print(f"\t              [dim]Root:[/dim] {project_root}")
        console.print(f"\t[dim]mujoco-mojo binary:[/dim] {self.slurm_mojo_command()}\n")

        # Standard colors only for Rich compatibility
        job_name = Prompt.ask(
            "  [white]Job Name[/]", default=f"mojo-sim-{job.status.id}"
        )
        if available_partitions:
            # Use the actual SLURM default if we found one, otherwise the first in list
            initial_default = (
                default_partition if default_partition else available_partitions[0]
            )

            partition = Prompt.ask(
                "  [white]Partition[/]",
                choices=available_partitions,
                default=initial_default,
            )
        else:
            partition = Prompt.ask(
                "  [white]Partition[/] [dim](optional)[/]", default=""
            )

        # === get partition limits ===
        cpu_limit = self.get_slurm_cpu_limit(partition)
        mem_limit = self.get_slurm_node_mem_limit(partition)
        time_limit_hint = self.get_slurm_time_limit(partition)

        # === get cpus per task ===
        cpus_per_task = max(
            1,
            IntPrompt.ask(
                f"  [white]CPUs per task[/] [dim](Node Limit: {cpu_limit})[/]",
                default=1,
            ),
        )
        if problem := cpu_problem(cpus_per_task, cpu_limit):
            if not proceed_despite(problem):
                return True

        # === get memory ===
        while True:
            mem_text = Prompt.ask(
                f"  [white]Memory per node[/] (e.g., 256M or 1.5G) [dim](Node Limit: {mem_limit})[/]",
                default="" if mem_limit == UNKNOWN_LIMIT else mem_limit,
            ).strip()
            if not mem_text or normalize_to_mb(mem_text) > 0:
                break
            console.print(
                f"[bold red]ERROR:[/] '{escape(mem_text)}' is not a memory size. "
                "Use a number with an optional unit, for example 512M or 1.5G."
            )
        mem = mem_text or None
        if problem := mem_problem(mem, mem_limit):
            if not proceed_despite(
                problem, "This job will likely be rejected by SLURM."
            ):
                return True

        # === get time ===
        while True:
            time_limit = Prompt.ask(
                f"  [white]Time limit[/] (e.g., 01:00:00 or 1-12:00:00) [dim](Partition Limit: {time_limit_hint})[/]",
                default="01:00:00",
            ).strip()
            try:
                slurm_time_to_seconds(time_limit)
                break
            except ValueError:
                console.print(
                    f"[bold red]ERROR:[/] '{escape(time_limit)}' is not a SLURM time limit."
                )
        if problem := time_problem(time_limit, time_limit_hint):
            if not proceed_despite(problem):
                return True

        # === get concurrency throttle ===
        max_concurrent_text = Prompt.ask(
            "  [white]Max concurrent tasks[/] [dim](blank = no limit, let SLURM decide)[/]",
            default="",
        )
        if max_concurrent_text and not max_concurrent_text.isdigit():
            console.print(
                f"\n[bold red]WARNING:[/] '{escape(max_concurrent_text)}' is not a number. Ignoring."
            )
            max_concurrent_text = ""
        max_concurrent = (
            int(max_concurrent_text) if max_concurrent_text.strip("0") else None
        )

        # === the project root ===
        add_root_to_pythonpath = True
        if str(project_root) not in os.getenv("PYTHONPATH", ""):
            console.print(
                f"\n[yellow]Warning:[/] Project root [italic]{project_root}[/] is not in your PYTHONPATH."
            )
            add_root_to_pythonpath = Confirm.ask(
                "Should Mojo automatically include it in the SLURM submission?",
                default=True,
            )

        config = SlurmConfig(
            job_name=job_name,
            partition=partition or None,
            cpus_per_task=cpus_per_task,
            mem=mem,
            time_limit=time_limit,
            max_concurrent=max_concurrent,
            add_root_to_pythonpath=add_root_to_pythonpath,
            project_root=project_root,
        )

        if problem := array_problem(len(job.to_run), self.get_max_array_size()):
            console.print(f"\n[bold red]ERROR:[/] {problem}")
            if not Confirm.ask("Proceed anyway?", default=False):
                return True

        script_path = self.write_slurm_script(job, config, console)

        watch_cmd = (
            f'mujoco-mojo run watch-workdir --workdir "{self.workdir.resolve()}"'
        )

        # final submission
        if not Confirm.ask(
            f"\n[cyan]Submit {len(job.to_run)} trials to SLURM now?[/]", default=True
        ):
            # deferred submission; the status file already exists, so the watcher works
            # for a job submitted by hand too
            console.print(
                f"\n[yellow]Orchestration complete.[/] Submit manually with:\n[bold green]sbatch {script_path}[/]"
            )
            console.print(
                f"\n[dim]To keep the status file and runtime report current once it is running, run:[/] [green]{watch_cmd}[/]"
            )
            return False

        # asked now because the status file the watcher keeps current already exists
        watch = Confirm.ask(
            "Keep the job status and runtime report up to date until the job finishes?",
            default=True,
        )

        submission = self.submit_slurm_script(job, script_path)
        if not submission.submitted:
            logger.error(f"SLURM Submission Failed: {submission.message}")
            console.print(
                f"\n[bold red]SLURM submission failed:[/] {escape(submission.message)}"
            )
            return True

        job_id = submission.job_id or "UNKNOWN"
        console.print(f"\n[bold green]Success![/] {submission.message}")

        # === Monitoring Dashboard ===
        console.print("\n[bold cyan]Monitoring Status:[/bold cyan]")
        console.print(f"  - [white]Check status:[/]       [green]squeue -j {job_id}[/]")
        console.print(
            f"  - [white]Watch live:[/]         [green]watch -n 1 squeue -j {job_id}[/]"
        )
        console.print(
            f"  - [white]View first log:[/]     [green]tail -f {self.workdir.resolve()}/logs/trial_0.log[/]"
        )
        console.print(f"  - [white]Cancel all trials:[/]  [green]scancel {job_id}[/]")
        console.print(
            f"\n[dim]Logs are being written to: {self.workdir.resolve()}/logs/[/]"
        )

        if not watch:
            console.print(
                f"\n[dim]To keep the status file and runtime report current later, run:[/] [green]{watch_cmd}[/]"
            )
            return False

        try:
            watch_job(self.workdir, n_proc=max(1, self.config.n_proc), console=console)
        except KeyboardInterrupt:
            console.print(
                f"\n[yellow]Stopped watching.[/] The job keeps running. Resume with: [green]{watch_cmd}[/]"
            )
        return False
