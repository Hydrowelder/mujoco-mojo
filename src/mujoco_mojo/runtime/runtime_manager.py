from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Self

import mujoco

from mujoco_mojo.runtime.forcing_function import ForcingFunction
from mujoco_mojo.runtime.results_manager import ResultsManager
from mujoco_mojo.runtime.video_recorder import VideoRecorder
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)


@dataclass
class RuntimeManager:
    results_manager: ResultsManager | None = None

    forcing_functions: list[ForcingFunction] = field(default_factory=list)
    video_recorders: list[VideoRecorder] = field(default_factory=list)

    _resolved: bool = False

    def __enter__(self) -> Self:
        """Prime the model and prepare results."""
        return self

    def __exit__(self, exc_type, exc, tb):
        """Ensure all telemetry is flushed even if the simulation crashed. Also saves recordings"""
        if self.results_manager:
            self.results_manager.close()

        if self.video_recorders:
            self.save_recordings()

    def save_recordings(self):
        logger.info(f"Saving {len(self.video_recorders)} videos in parallel...")
        with ThreadPoolExecutor() as executor:
            for recorder in self.video_recorders:
                executor.submit(recorder.save)

        logger.info("All video encoding tasks complete.")

    def resolve(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """Call this once after mj_loadXML to prime the caches."""
        for load in self.forcing_functions:
            load.resolve_ids(mj_model, mj_data)
        self._resolved = True

    def add_load(self, load: ForcingFunction):
        self.forcing_functions.append(load)

    def add_video_recorder(self, video_recorder: VideoRecorder):
        self.video_recorders.append(video_recorder)

    def step(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """
        Calculates and injects forces into qfrc_applied or xfrc_applied.

        1. Calls apply_load (custom forces)
        2. Calls mj_step (physics)
        3. Calls record (telemetry)
        """
        if self.results_manager:
            self.results_manager.flush_ledger()

        # sync state variables and clear render buffer
        mujoco.mj_forward(mj_model, mj_data)
        mj_data.xfrc_applied.fill(0)

        # resolve IDs and initial distances
        if not self._resolved:
            self.resolve(mj_model, mj_data)

        for load in self.forcing_functions:
            load.apply_load(mj_model, mj_data)

        # record if t=0
        if mj_data.time == 0 and self.results_manager:
            mujoco.mj_forward(mj_model, mj_data)
            self.results_manager.record(mj_model, mj_data)
            self.results_manager.flush_ledger()

        # integrate physics (advances the time)
        mujoco.mj_step(mj_model, mj_data)

        # telemetry objects harvest to the same ledger
        if self.results_manager:
            self.results_manager.record(mj_model, mj_data)

        # record any frames which are due
        for recorder in self.video_recorders:
            recorder.capture_frame(mj_data)
