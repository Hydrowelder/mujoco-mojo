from dataclasses import dataclass, field
from typing import Self

import mujoco

from mujoco_mojo.runtime.forcing_function import ForcingFunction
from mujoco_mojo.runtime.results_manager import ResultsManager


@dataclass
class RuntimeManager:
    results_manager: ResultsManager | None = None

    forcing_functions: list[ForcingFunction] = field(default_factory=list)

    def __enter__(self) -> Self:
        """Prime the model and prepare results."""
        return self

    def __exit__(self, exc_type, exc, tb):
        """Ensure all telemetry is flushed even if the simulation crashed."""
        if self.results_manager:
            self.results_manager.close()

    def resolve(self, mj_model: mujoco.MjModel):
        """Call this once after mj_loadXML to prime the caches."""
        for load in self.forcing_functions:
            load.resolve_ids(mj_model)

    def add_load(self, load: ForcingFunction):
        self.forcing_functions.append(load)

    def step(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """
        Calculates and injects forces into qfrc_applied or xfrc_applied.

        1. Calls mj_step (physics)
        2. Calls apply_load (custom forces)
        3. Calls record (telemetry)
        """
        if self.results_manager:
            self.results_manager.flush_ledger()

        # integrate physics
        mujoco.mj_step(mj_model, mj_data)

        # phics objects post to the fresh ledger
        for load in self.forcing_functions:
            load.apply_load(mj_model, mj_data, self.results_manager)

        # telemetry objects harvest to the same ledger
        if self.results_manager:
            self.results_manager.record(mj_model, mj_data)
