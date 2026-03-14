from dataclasses import dataclass, field

import mujoco

from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.runtime.forcing_function import ForcingFunction
from mujoco_mojo.runtime.result_manager import ResultsManager


@dataclass
class RuntimeManager:
    mojo_model: MojoModel

    results_manager: ResultsManager | None = None

    forcing_functions: list[ForcingFunction] = field(default_factory=list)

    def resolve(self, mj_model: mujoco.MjModel):
        """Call this once after mj_loadXML to prime the caches."""
        for load in self.forcing_functions:
            load.resolve_ids(mj_model)

    def add_load(self, load: ForcingFunction):
        self.forcing_functions.append(load)

    def apply_step(self, mj_model, mj_data):
        """Calculates and injects forces into qfrc_applied or xfrc_applied."""
        for load in self.forcing_functions:
            load.apply_load(mj_model, mj_data, self.results_manager)

        if self.results_manager:
            self.results_manager.record(mj_model, mj_data)
