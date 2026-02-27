from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.process_manager import NOMINAL_TRIAL_NUM, NamedValueDict

logger = logging.getLogger()

__all__ = ["MojoGenerator", "MojoRunner", "MojoRuntime", "MonteCarloConfig", "Trial"]

# TODO: add job statusing
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
    n_proc: int = 1

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
    ) -> Any | MojoModel:
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
            The output of the `runtime` function if provided; otherwise, the raw `MojoModel` object for the trial.

        """
        logger.info(f"Generating trial_num={self.trial_num}")

        # 1. Generate
        mojo = generator(self.trial_num, overrides, *gen_args, **gen_kwargs)

        # 2. Setup Workspace & Save Metadata
        logger.info(f"Saving trial_num={self.trial_num} to {self.trial_dir}")
        self.trial_dir.mkdir(parents=True, exist_ok=True)
        mojo.mjcf.write_xml(self.xml_path)
        self.model_config_path.write_text(mojo.model_dump_json(indent=4))

        # 3. Execute (if runtime provided)
        if runtime is not None:
            logger.info(f"Executing trial_num={self.trial_num} runtime")
            return runtime(mojo, *run_args, **run_kwargs)
        else:
            logger.info(
                f"No runtime definition was provided for trial_num={self.trial_num} so MuJoCo will not be run."
            )
            return mojo


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
        self, global_overrides: NamedValueDict | None = None
    ) -> list[Any]:
        """Orchestrates a Monte Carlo job."""
        overrides = global_overrides or NamedValueDict()

        logger.info(
            f"Running {self.config.n_trial} trials with {self.config.n_proc} processors."
        )
        if self.config.n_proc > 1:
            results = []
            with ProcessPoolExecutor(max_workers=self.config.n_proc) as executor:
                futures = [
                    executor.submit(self.execute_single_trial, tn, overrides)
                    for tn in self.config.trial_nums
                ]
                for f in futures:
                    try:
                        results.append(f.result())
                    except Exception as e:
                        logger.error(f"A trial failed with error: {e}")
                        results.append(None)
        else:
            results = [
                self.execute_single_trial(trial_num=tn, overrides=overrides)
                for tn in self.config.trial_nums
            ]

        return results
