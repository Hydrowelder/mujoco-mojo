from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mojo import Mojo
from mujoco_mojo.process_manager import NOMINAL_TRIAL_NUM, NamedValueDict

logger = logging.getLogger()

# TODO: add job statusing
# --- Protocols ---


class MojoGenerator(Protocol):
    """Definition of a function that generates a Mojo model instance."""

    def __call__(
        self, trial_num: int, overrides: NamedValueDict, *args: Any, **kwargs: Any
    ) -> Mojo: ...


class MojoRuntime(Protocol):
    """Definition of a function that executes a generated Mojo model."""

    def __call__(self, mojo: Mojo, *args: Any, **kwargs: Any) -> Any: ...


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
    """Handles the lifecycle of a single simulation run."""

    trial_num: int
    base_dir: Path
    xml_name: str
    model_config_name: str
    padding_style: str

    @property
    def trial_dir(self) -> Path:
        return (
            self.base_dir / f"trial_{self.trial_num:{self.padding_style}}"
        ).resolve()

    @property
    def xml_path(self) -> Path:
        return self.trial_dir / self.xml_name

    @property
    def model_config_path(self) -> Path:
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
    ) -> Any:
        """The full pipeline: Generate then Execute."""
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
        return mojo  # BUG not sure this should return mojo, I dont really know why i would care. Maybe when statusing is done this would return an enum with the state


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
