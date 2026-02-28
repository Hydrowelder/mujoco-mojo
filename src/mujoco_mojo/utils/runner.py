from __future__ import annotations

import inspect
import logging
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from pydantic import field_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.process_manager import NOMINAL_TRIAL_NUM, NamedValueDict
from mujoco_mojo.utils.statusing import STATUS_FNAME, Completion, JobStatus, TrialStatus

logger = logging.getLogger()

__all__ = ["MojoGenerator", "MojoRunner", "MojoRuntime", "MonteCarloConfig", "Trial"]


# --- Protocols ---


class MojoGenerator(Protocol):
    """Definition of a function that generates a MojoModel model instance."""

    def __call__(
        self, trial_num: int, overrides: NamedValueDict, *args: Any, **kwargs: Any
    ) -> MojoModel: ...


class MojoRuntime(Protocol):
    """Definition of a function that executes a generated MojoModel model."""

    def __call__(self, mojo: MojoModel, *args: Any, **kwargs: Any) -> Any: ...


# --- Models ---


class MonteCarloConfig(MojoBaseModel):
    n_trial: int = 2
    """Number of trials to run.

    You are able to resume a previous job and modify the number of runs desired by changing this value. A job already in progress will not be dynamically stopped though if you change this value at runtime."""

    n_proc: int = 1
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

    @property
    def trial_nums(self) -> np.ndarray:
        return NOMINAL_TRIAL_NUM + np.arange(self.n_trial)

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
    def trial_dir(self) -> Path:
        """
        The absolute path to this trial's unique workspace.

        Example:
            If base_dir is './sims' and trial_num is 7 with '03d' padding,
            this returns './sims/trial_007'.

        """
        return (
            self.base_dir / f"trial_{self.trial_num:{self.padding_style}}"
        ).resolve()

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
        overrides: NamedValueDict,
        gen_args: list[Any],
        gen_kwargs: dict[str, Any],
        run_args: list[Any],
        run_kwargs: dict[str, Any],
    ) -> Any | MojoModel | None:
        """
        Executes the complete simulation pipeline for this trial.

        This method coordinates three main phases:
        1.  **Generation**: Calls the user-provided generator to build a `MojoModel` model.
        2.  **Persistence**: Creates the workspace and writes the model/config to disk.
        3.  **Execution**: Triggers the physics runtime if one is provided.

        Args:
            generator: Function that returns a `MojoModel` instance.
            runtime: Optional function to run the simulation (MuJoCo).
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

        self.trial_dir.mkdir(parents=True, exist_ok=True)
        status.dump_to_path(status._path)

        result = None
        try:
            # 1. Generate
            with status.record_step():
                logger.info(f"Generating trial_num={self.trial_num}")
                mojo = generator(self.trial_num, overrides, *gen_args, **gen_kwargs)

                # 2. Setup Workspace & Save Metadata
                logger.info(f"Saving trial_num={self.trial_num} to {self.trial_dir}")
                self.trial_dir.mkdir(parents=True, exist_ok=True)
                mojo.mjcf.write_xml(self.xml_path)
                self.model_config_path.write_text(mojo.model_dump_json(indent=4))

            with status.record_step():
                # 3. Execute (if runtime provided)
                if runtime is not None:
                    logger.info(f"Executing trial_num={self.trial_num} runtime")
                    result = runtime(mojo, *run_args, **run_kwargs)
                else:
                    logger.info(
                        f"No runtime definition was provided for trial_num={self.trial_num} so MuJoCo will not be run."
                    )
                    result = mojo

            status.completion = Completion.SUCCESS

        except Exception as e:
            status.completion = Completion.FAILED
            logger.error(f"Trail {self.trial_num} failed with the following error: {e}")
        finally:
            status.dump_to_path(status._path)

        return result


@dataclass
class MojoRunner:
    generator: MojoGenerator
    runtime: MojoRuntime | None = None
    workdir: Path = Path("./mojo_models")
    model_config_name: str = "model_config.json"
    xml_name: str = "model.xml"
    config: MonteCarloConfig = field(default_factory=MonteCarloConfig)

    gen_args: list[Any] = field(default_factory=list)
    gen_kwargs: dict[str, Any] = field(default_factory=dict)
    run_args: list[Any] = field(default_factory=list)
    run_kwargs: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def inspect_protocol(func: MojoGenerator | MojoRuntime | None) -> str:
        if func is None:
            return "none defined"
        try:
            gen_file = inspect.getfile(func)
            gen_name = func.__name__  # pyright: ignore[reportAttributeAccessIssue]
            return f"{gen_name} (defined in: {gen_file})"
        except Exception:
            logger.error(
                "Failed to caputre generator name. Falling back to raw generator name."
            )
            return str(func)

    def capture_environment(self):
        req_path = self.workdir / "requirements.txt"

        # 1. Try 'uv' first (since it's the modern standard)
        try:
            result = subprocess.run(
                ["uv", "pip", "freeze"], capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout:
                req_path.write_text(result.stdout)
                return
        except FileNotFoundError:
            pass

        # 2. Fallback to standard pip
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout:
                req_path.write_text(result.stdout)
                return
        except Exception:
            pass

        # 3. Last resort: Record the Python version and basic info
        req_path.write_text(
            f"# Fallback: Could not use uv/pip\n# Python Version: {sys.version}\n"
        )

    def run(
        self, global_overrides: NamedValueDict | None = None, resume: bool = True
    ) -> list[Any]:
        self.capture_environment()
        if isinstance(self.config, MonteCarloConfig):
            result = self.run_monte_carlo(
                global_overrides=global_overrides, resume=resume
            )
        else:
            msg = f"A configuration for {self.config.__class__.__name__} has not been implemented/"
            logger.error(msg)
            raise NotImplementedError(msg)
        return result

    def execute_single_trial(self, trial_num: int, overrides: NamedValueDict) -> Any:
        """Helper to package a Trial and run it."""
        trial = Trial(
            trial_num=trial_num,
            base_dir=self.workdir,
            xml_name=self.xml_name,
            model_config_name=self.model_config_name,
            padding_style=self.config.padding_style,
        )

        return trial.run(
            self.generator,
            self.runtime,
            overrides,
            self.gen_args,
            self.gen_kwargs,
            self.run_args,
            self.run_kwargs,
        )

    def run_monte_carlo(
        self, global_overrides: NamedValueDict | None = None, resume: bool = True
    ) -> list[Any]:
        """Orchestrates a Monte Carlo job."""
        overrides = global_overrides or NamedValueDict()

        # initialize the status tracker
        status_tracker = JobStatus(
            workdir=self.workdir,
            n_trial=self.config.n_trial,
            padding_style=self.config.padding_style,
            generator=MojoRunner.inspect_protocol(self.generator),
            runtime=MojoRunner.inspect_protocol(self.runtime),
        )
        status_tracker._trial_nums = list(self.config.trial_nums)

        # decide which trials to execute
        if resume:
            status_tracker.refresh_from_disk(n_proc=self.config.n_proc)

        to_run = status_tracker.pending_trial_nums

        results = []
        if not to_run:
            logger.info("All trials were already completed. Nothing to do.")
            return results

        if self.config.is_parallel:
            logger.info(
                f"Running {len(to_run)} trials with {self.config.n_proc} processors. {status_tracker.n_done}/{self.config.n_trial} ({status_tracker.progress:.2%}) trials completed."
            )
            with ProcessPoolExecutor(max_workers=self.config.n_proc) as executor:
                future_to_tn = {
                    executor.submit(self.execute_single_trial, tn, overrides): tn
                    for tn in to_run
                }
                for f in as_completed(future_to_tn):
                    tn = future_to_tn[f]
                    try:
                        result = f.result()
                        results.append(result)
                        status_tracker.update_trial(tn, Completion.SUCCESS)
                    except Exception as e:
                        logger.error(f"Trial {tn} failed: {e}")
                        results.append(None)
                        status_tracker.update_trial(tn, Completion.FAILED)
        else:
            for tn in to_run:
                try:
                    result = self.execute_single_trial(
                        trial_num=tn, overrides=overrides
                    )
                    results.append(result)
                    status_tracker.update_trial(
                        trial_num=tn, completion=Completion.SUCCESS
                    )
                except Exception as e:
                    logger.error(f"A trial failed with error: {e}")
                    results.append(None)
                    status_tracker.update_trial(
                        trial_num=tn, completion=Completion.FAILED
                    )

        status_tracker.generate_report()
        return results
