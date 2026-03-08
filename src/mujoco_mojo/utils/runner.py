from __future__ import annotations

import inspect
import os
import shutil
import subprocess
import sys
from bdb import BdbQuit
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpydantic import NDArray
from pydantic import field_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.process_manager import NOMINAL_TRIAL_NUM, NamedValueDict
from mujoco_mojo.utils.defaults import (
    DEFAULT_MC_N_PROC,
    DEFAULT_MC_N_TRIAL,
    DEFAULT_MODEL_CONFIG_NAME,
    DEFAULT_RESUME,
    DEFAULT_RUNTIME,
    DEFAULT_SEED,
    DEFAULT_WORKDIR,
    DEFAULT_XML_NAME,
)
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.statusing import (
    STATUS_FNAME,
    Completion,
    ExecutionMode,
    JobStatus,
    JobType,
    TrialStatus,
)

logger = get_logger(__name__)

__all__ = ["MojoGenerator", "MojoRunner", "MojoRuntime", "MonteCarloConfig", "Trial"]


# --- Protocols ---


class MojoGenerator(Protocol):
    """Definition of a function that generates a MojoModel model instance."""

    def __call__(
        self, mojo_model: MojoModel, /, *args: Any, **kwargs: Any
    ) -> MojoModel: ...


class MojoRuntime(Protocol):
    """Definition of a function that executes a generated MojoModel model."""

    def __call__(self, mojo_model: MojoModel, /, *args: Any, **kwargs: Any) -> Any: ...


# --- Models ---


class MonteCarloConfig(MojoBaseModel):
    n_trial: int = DEFAULT_MC_N_TRIAL
    """Number of trials to run.

    You are able to resume a previous job and modify the number of runs desired by changing this value. A job already in progress will not be dynamically stopped though if you change this value at runtime."""

    n_proc: int = DEFAULT_MC_N_PROC
    """Number of proccesses to allow.

    This value is used to determine how many parallel jobs can be run. It is also used for the discovery of trial status. Using a value of 1 will result in the slowest runtime, but highest reliability.

    Important:
        Be a good citizen. Use a reasonable number if you are working on a shared resource. You are a jerk if you use everything."""

    @field_validator("n_trial", "n_proc")
    @classmethod
    def validate_greater_than_zero(cls, v: int) -> int:
        if v < 1:
            # coerce an invalid value to be able to run
            return 1
        return v

    @staticmethod
    def _trial_nums(n_trial: int) -> list[int]:
        return (NOMINAL_TRIAL_NUM + np.arange(n_trial)).tolist()

    @property
    def trial_nums(self) -> list[int]:
        return self._trial_nums(self.n_trial)

    @property
    def padding_width(self) -> int:
        if self.n_trial == 0:
            return 1
        else:
            return len(str(max(self.trial_nums)))

    @property
    def padding_style(self) -> str:
        """
        This dynamically defines the padding style for trial numbers. This is helpful to ensure the filesystem consistently sorts the trials.

        Examples:
        * Suppose you n_trials is 2000 (and the nominal trial_num is 0)
        * This method would return `04d`
            * Trial number `0` maps to `0000`
            * Trial number `123` maps to `0123`
            * Trial number `1999` will still map to `1999`

        """
        return f"0{self.padding_width}d"

    @property
    def is_parallel(self) -> bool:
        return self.n_proc > 1


@dataclass
class Trial:
    """
    Handles the lifecycle of a single simulation run.

    The Trial object is responsible for the 'dirty work' of a Monte Carlo run:
    creating directories, writing the MJCF XML, saving the configuration
    snapshot, and triggering the physics runtime.

    By isolating this logic into a dataclass, it can be safely pickled and
    shipped to worker processes for parallel execution.
    """

    trial_num: int
    """Unique identifier for this trial iteration."""

    base_dir: Path
    """Root directory where all simulation trials are stored."""

    xml_name: str
    """Filename for the generated MJCF XML (e.g., 'model.xml')."""

    model_config_name: str
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
        return self.trial_dir / self.model_config_name

    def run(
        self,
        generator: MojoGenerator,
        runtime: MojoRuntime | None,
        seed: int | None,
        overrides: NamedValueDict[NDArray],
        gen_args: list[Any],
        gen_kwargs: dict[str, Any],
        run_args: list[Any],
        run_kwargs: dict[str, Any],
    ) -> tuple[Any | MojoModel | None, TrialStatus]:
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
            gen_args: Positional arguments for the generator.
            gen_kwargs: Keyword arguments for the generator.
            run_args: Positional arguments for the runtime.
            run_kwargs: Keyword arguments for the runtime.

        Returns:
            The output of the `runtime` function if provided; otherwise, the raw `MojoModel` object for the trial or None if there was a failure prior to generating the MojoModel.

        """
        status = TrialStatus(trial_num=self.trial_num)
        status._path = self.trial_dir / STATUS_FNAME

        with status.record_step(step_name="pending"):
            pass

        result = None
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
                mojo_model = generator(mojo_model, overrides, *gen_args, **gen_kwargs)

                # 2. Setup Workspace & Save Metadata
                logger.info(f"Saving trial_num={self.trial_num} to {self.trial_dir}")
                self.trial_dir.mkdir(parents=True, exist_ok=True)

                # bundle assets, this remaps DepPath attributes to point to the shared asset dir
                rel_to_xml = Path(
                    os.path.relpath(self.shared_asset_dir, self.trial_dir)
                )
                mojo_model.mjcf.bundle_assets(
                    target_dir=self.shared_asset_dir, rel_to_xml=rel_to_xml
                )

                # save XML (with modified DepPath)
                mojo_model.mjcf.write_xml(self.xml_path)
                self.model_config_path.write_text(
                    mojo_model.model_dump_json(indent=4), encoding="utf-8"
                )

            with status.record_step(step_name="solving"):
                # 3. Execute (if runtime provided)
                if runtime is not None:
                    logger.info(f"Executing trial_num={self.trial_num} runtime")
                    result = runtime(mojo_model, *run_args, **run_kwargs)
                else:
                    logger.info(
                        f"No runtime definition was provided for trial_num={self.trial_num} so MuJoCo will not be run."
                    )
                    result = mojo_model

            status.step = "done"
            status.completion = Completion.SUCCESS

        except (BdbQuit, KeyboardInterrupt):
            logger.warning("Quit command detected. Exiting execution...")
            raise
        except Exception as e:
            status.step = "done"
            status.completion = Completion.FAILED
            logger.exception(
                f"Trial {self.trial_num} failed with the following error: {e}"
            )
        finally:
            status.dump_to_path(status._path)

        return result, status


@dataclass
class MojoRunner:
    generator: MojoGenerator
    generator_path: str | None = None  # e.g., "sim.generate"
    runtime: MojoRuntime | None = DEFAULT_RUNTIME
    runtime_path: str | None = None  # e.g., "sim.runtime"
    seed: int | None = DEFAULT_SEED
    workdir: Path = DEFAULT_WORKDIR
    model_config_name: str = DEFAULT_MODEL_CONFIG_NAME
    xml_name: str = DEFAULT_XML_NAME
    config: MonteCarloConfig = field(default_factory=MonteCarloConfig)

    gen_args: list[Any] = field(default_factory=list)
    gen_kwargs: dict[str, Any] = field(default_factory=dict)
    run_args: list[Any] = field(default_factory=list)
    run_kwargs: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def inspect_protocol(
        func: MojoGenerator | MojoRuntime | None,
    ) -> tuple[str, Path | None, int | None]:
        if func is None:
            return ("none defined", None, None)
        try:
            # 1. Get the file path
            gen_file = inspect.getfile(func)

            # 2. Get the qualified name (e.g., "Experiment.generate")
            # This gives you the class context automatically
            gen_name = getattr(func, "__qualname__", func.__name__)  # pyright: ignore[reportAttributeAccessIssue]

            # 3. Get the line number
            # getsourcelines returns ([lines], starting_line_number)
            _, line_num = inspect.getsourcelines(func)

            return (f"{gen_name}", Path(gen_file).resolve(), line_num)

        except Exception as e:
            logger.exception(f"Failed to capture generator details: {e}")
            return (f"{func}", None, None)

    def capture_environment(self):
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

    def run(
        self,
        global_overrides: NamedValueDict[NDArray] = NamedValueDict[NDArray](),
        resume: bool = DEFAULT_RESUME,
        clean_workdir: bool = False,
        execution_mode: ExecutionMode = ExecutionMode.LOCAL,
        trial_ids: list[int] | None = None,
    ) -> tuple[list[Any], bool]:
        match execution_mode:
            case ExecutionMode.LOCAL:
                return self.run_local(
                    global_overrides=global_overrides,
                    resume=resume,
                    clean_workdir=clean_workdir,
                    trial_ids=trial_ids,
                )
            case ExecutionMode.SLURM:
                return self.run_slurm(
                    global_overrides=global_overrides,
                    resume=resume,
                    clean_workdir=clean_workdir,
                    trial_ids=trial_ids,
                )
            case _:
                msg = f"No run command has been configured for execution mode {execution_mode}"
                logger.error(msg)
                raise NotImplementedError(msg)

    def run_local(
        self,
        global_overrides: NamedValueDict[NDArray] = NamedValueDict[NDArray](),
        resume: bool = DEFAULT_RESUME,
        clean_workdir: bool = False,
        trial_ids: list[int] | None = None,
    ) -> tuple[list[Any], bool]:

        if clean_workdir and resume:
            msg = "clean_workdir and resume are mutually exclusive with one another. Use one or the other."
            logger.error(msg)
            raise ValueError(msg)

        if clean_workdir:
            try:
                shutil.rmtree(self.workdir)
            except Exception as e:
                msg = f"Failed to delete workdir {self.workdir}: {e}"
                logger.exception(msg)
                raise RuntimeError(msg)

        self.workdir.mkdir(parents=True, exist_ok=True)
        if not (self.workdir / ".gitignore").exists():
            (self.workdir / ".gitignore").write_text("*", encoding="utf-8")
        self.capture_environment()

        if isinstance(self.config, MonteCarloConfig):
            result, had_fails = self.run_monte_carlo(
                global_overrides=global_overrides,
                resume=resume,
                trial_ids=trial_ids,
            )
        else:
            msg = f"A configuration for {self.config.__class__.__name__} has not been implemented."
            logger.error(msg)
            raise NotImplementedError(msg)
        return result, had_fails

    @property
    def slurm_trial_id(self) -> int | None:
        """Returns the current SLURM task ID if running as part of an array job."""
        tid = os.getenv("SLURM_ARRAY_TASK_ID")
        return int(tid) if tid is not None else None

    def run_slurm(
        self,
        global_overrides: NamedValueDict | None = None,
        resume: bool = DEFAULT_RESUME,
        clean_workdir: bool = False,
        trial_ids: list[int] | None = None,
    ) -> tuple[list[Any], bool]:
        """Generates an sbatch script and submits the job array to SLURM for a given config."""
        msg = "SLURM is not implemented"
        logger.error(msg)
        raise NotImplementedError(msg)

        self.workdir.mkdir(parents=True, exist_ok=True)
        (self.workdir / "logs").mkdir(parents=True, exist_ok=True)

        self.capture_environment()

        if isinstance(self.config, MonteCarloConfig):
            result, had_fails = self.run_slurm_monte_carlo(
                global_overrides=global_overrides,
                resume=resume,
                trial_ids=trial_ids,
            )
        else:
            msg = f"A SLURM configuration for {self.config.__class__.__name__} has not been implemented."
            logger.error(msg)
            raise NotImplementedError(msg)
        return result, had_fails

    def execute_single_trial(
        self, trial_num: int, overrides_payload: dict
    ) -> tuple[Any | MojoModel | None, TrialStatus]:
        """Helper to package a Trial and run it."""
        overrides = NamedValueDict[NDArray].model_validate(overrides_payload)

        trial = Trial(
            trial_num=trial_num,
            base_dir=self.workdir,
            xml_name=self.xml_name,
            model_config_name=self.model_config_name,
            padding_style=self.config.padding_style,
        )

        return trial.run(
            generator=self.generator,
            runtime=self.runtime,
            seed=self.seed,
            overrides=overrides,
            gen_args=self.gen_args,
            gen_kwargs=self.gen_kwargs,
            run_args=self.run_args,
            run_kwargs=self.run_kwargs,
        )

    def run_monte_carlo(
        self,
        global_overrides: NamedValueDict[NDArray] = NamedValueDict[NDArray](),
        resume: bool = True,
        trial_ids: list[int] | None = None,
    ) -> tuple[list[Any], bool]:
        """
        Orchestrates a Monte Carlo job.

        """
        if self.slurm_trial_id is not None:
            tn = self.slurm_trial_id
            logger.info(f"SLURM Worker detected. Executing Trial {tn}")
            result, trial_status = self.execute_single_trial(
                trial_num=tn, overrides_payload=global_overrides.model_dump()
            )

            return [result], trial_status.completion == Completion.FAILED

        # initialize the status tracker
        status_tracker = JobStatus(
            workdir=self.workdir.resolve(),
            job_type=JobType.MONTE_CARLO,
            execution_mode=ExecutionMode.LOCAL,
            n_trial=self.config.n_trial,
            n_proc=self.config.n_proc,
            seed=self.seed,
            padding_style=self.config.padding_style,
            generator=MojoRunner.inspect_protocol(self.generator),
            runtime=MojoRunner.inspect_protocol(self.runtime),
            gen_args_used=bool(self.gen_args),
            gen_kwargs_used=bool(self.gen_kwargs),
            run_args_used=bool(self.run_args),
            run_kwargs_used=bool(self.run_kwargs),
        )
        if trial_ids:
            status_tracker._registry = dict(
                [(tn, Completion.INCOMPLETE) for tn in trial_ids]
            )
        else:
            status_tracker._registry = dict(
                [(tn, Completion.INCOMPLETE) for tn in self.config.trial_nums]
            )

        # decide which trials to execute
        if resume:
            status_tracker.refresh_from_disk(n_proc=self.config.n_proc)
        to_run = status_tracker.pending_trial_nums

        results = []
        if not to_run:
            logger.info("All trials were already completed. Nothing to do.")
            return results, bool(status_tracker.failed_trial_nums)

        if self.config.is_parallel:
            logger.info(
                f"Running {len(to_run)} trials with {self.config.n_proc} processors. {status_tracker.n_done}/{self.config.n_trial} ({status_tracker.progress:.2%}) trials completed."
            )
            executor = ProcessPoolExecutor(max_workers=self.config.n_proc)
            try:
                future_to_tn = {
                    executor.submit(
                        self.execute_single_trial,
                        tn,
                        global_overrides.model_dump(),
                    ): tn
                    for tn in to_run
                }
                for f in as_completed(future_to_tn):
                    tn = future_to_tn[f]
                    try:
                        result, trial_status = f.result()
                        results.append(result)
                        status_tracker.update_trial(
                            trial_num=tn,
                            trial_timedelta=trial_status.td,
                            completion=trial_status.completion,
                        )
                    except (BdbQuit, KeyboardInterrupt):
                        # user is quitting from breakpoint() or CTRL+C
                        raise
                    except Exception as e:
                        logger.exception(f"Trial {tn} failed: {e}")
                        results.append(None)
                        status_tracker.update_trial(
                            trial_num=tn,
                            trial_timedelta=None,
                            completion=Completion.FAILED,
                        )
                    status_tracker.generate_report(n_proc=self.config.n_proc)
            except (BdbQuit, KeyboardInterrupt):
                # allows killing the job with one CTRL+C
                logger.warning("Interrupt recieved. Stopping all trials.")
                executor.shutdown(wait=False, cancel_futures=True)
                raise
            finally:
                executor.shutdown(wait=True)
        else:
            for tn in to_run:
                try:
                    result, trial_status = self.execute_single_trial(
                        trial_num=tn,
                        overrides_payload=global_overrides.model_dump(),
                    )
                    results.append(result)
                    status_tracker.update_trial(
                        trial_num=tn,
                        trial_timedelta=trial_status.td,
                        completion=trial_status.completion,
                    )
                except (BdbQuit, KeyboardInterrupt):
                    # user is quitting from breakpoint() or CTRL+C
                    raise
                except Exception as e:
                    logger.exception(f"A trial failed with error: {e}")
                    results.append(None)
                    status_tracker.update_trial(
                        trial_num=tn,
                        trial_timedelta=None,
                        completion=Completion.FAILED,
                    )
                status_tracker.generate_report(n_proc=self.config.n_proc)

        status_tracker.generate_report(n_proc=self.config.n_proc, alert_generation=True)
        return results, bool(status_tracker.failed_trial_nums)

    def run_slurm_monte_carlo(
        self,
        global_overrides: NamedValueDict | None = None,
        resume: bool = True,
        trial_ids: list[int] | None = None,
    ) -> tuple[list[Any], bool]:
        """Orchestrates a Monte Carlo SLURM submission."""
        msg = "SLURM is not implemented"
        logger.error(msg)
        raise NotImplementedError(msg)
        # initialize the status tracker

        if trial_ids:
            to_run = trial_ids
        else:
            status_tracker = JobStatus(
                workdir=self.workdir.resolve(),
                job_type=JobType.MONTE_CARLO,
                execution_mode=ExecutionMode.SLURM,
                n_trial=self.config.n_trial,
                n_proc=self.config.n_proc,
                padding_style=self.config.padding_style,
                generator=MojoRunner.inspect_protocol(self.generator),
                runtime=MojoRunner.inspect_protocol(self.runtime),
                gen_args_used=bool(self.gen_args),
                gen_kwargs_used=bool(self.gen_kwargs),
                run_args_used=bool(self.run_args),
                run_kwargs_used=bool(self.run_kwargs),
            )

            # decide which trials to execute
            if resume:
                status_tracker.refresh_from_disk(n_proc=self.config.n_proc)
            to_run = status_tracker.pending_trial_nums

        if not to_run:
            logger.info("All trials were already completed. Nothing to do.")
            return [], False

        # generate the .sh script
        array_range = ",".join(map(str, to_run))
        script_path = self.workdir / "mujoco_mojo_submit.sh"

        runtime_str = f'--runtime "{self.runtime_path}"' if self.runtime_path else ""
        project_root = Path.cwd().resolve()
        cmd = (
            f"{sys.executable} -m mujoco_mojo run monte-carlo "
            f'--generator "{self.generator_path}" '
            f"{runtime_str} "
            f'--workdir "{self.workdir.resolve()}" '
            f"--trial-id $SLURM_ARRAY_TASK_ID "
            f"--execution-mode local"  # The worker runs its specific trial locally
        )
        sbatch_content = f"""#!/bin/bash
#SBATCH --job-name=mojo
#SBATCH --array={array_range}
#SBATCH --output={self.workdir.resolve()}/logs/trial_%a.log
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00

# Move to where the code lives
cd {project_root}

# Ensure local modules are importable
export PYTHONPATH=$PYTHONPATH:{project_root}

# Execute the worker
{cmd}
"""

        script_path.write_text(sbatch_content, encoding="utf-8")

        # submit to sbatch
        logger.info(f"Submitting {len(to_run)} trials to SLURM...")
        result = subprocess.run(
            ["sbatch", str(script_path)], capture_output=True, text=True
        )

        if result.returncode == 0:
            logger.info(f"SLURM Job submitted: {result.stdout.strip()}")
            return [], False
        else:
            logger.error(f"SLURM Submission Failed: {result.stderr}")
            return [], True
