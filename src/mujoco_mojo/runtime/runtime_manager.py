import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Protocol, Self, runtime_checkable

import mujoco

from mujoco_mojo.runtime.load import Load
from mujoco_mojo.runtime.results_manager import SignalManager
from mujoco_mojo.runtime.video_recorder import ArrowConfig, VideoRecorder
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)


@runtime_checkable
class SyncHook(Protocol):
    def __call__(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        arrows: list[ArrowConfig],
    ) -> Any: ...


@dataclass
class RuntimeManager:
    results_manager: SignalManager | None = None

    loads: list[Load] = field(default_factory=list)
    video_recorders: list[VideoRecorder] = field(default_factory=list)

    playback_speed: float = 1.0
    _start_wall_time: float = field(default_factory=time.time, init=False)
    _start_sim_time: float = field(default=0.0, init=False)

    _sync_hook: SyncHook | None = None
    _skip_recording: bool = False

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
                executor.submit(recorder.save)  # TODO add playback speed argument

        logger.info("All video encoding tasks complete.")

    def resolve(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """Call this once after mj_loadXML to prime the caches."""
        for load in self.loads:
            load.resolve_ids(mj_model, mj_data)
        self._resolved = True

    def add_load(self, load: Load):
        self.loads.append(load)

    def add_video_recorder(self, video_recorder: VideoRecorder):
        self.video_recorders.append(video_recorder)

    def step(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """
        Calculates forces, integratess physics, and handles telemetry.
        """
        # clear buffers for next timestep
        mj_data.xfrc_applied.fill(0)  # external forces
        mj_data.qfrc_applied.fill(0)  # user-defined forces
        mj_data.ctrl.fill(0)  # actuator forces

        # sync state variables and clear render buffer
        mujoco.mj_forward(mj_model, mj_data)

        if mj_data.time == 0.0 or self._start_sim_time == 0.0:
            self._start_sim_time = mj_data.time
            self._start_wall_time = time.time()

        # resolve IDs and initial distances
        # it is critical this is done after mj_forward to update site positions
        if not self._resolved:
            self.resolve(mj_model, mj_data)

        # apply user forcing functions
        for load in self.loads:
            load.apply_load(mj_model, mj_data)

        # record data
        if self.results_manager and not self._skip_recording:
            mujoco.mj_forward(mj_model, mj_data)
            self.results_manager.record(mj_model, mj_data)
            self.results_manager.flush_ledger()

        # record any frames which are due
        all_arrows = None
        if self.video_recorders or self._sync_hook:
            # gather arrows for forcing functions
            all_arrows: list[ArrowConfig] | None = []

            for load in self.loads:
                all_arrows.extend(load.get_visuals(mj_model, mj_data))

        if self.video_recorders:
            assert all_arrows is not None
            for recorder in self.video_recorders:
                recorder.capture_frame(
                    mj_model=mj_model, mj_data=mj_data, custom_arrows=all_arrows
                )

        # integrate physics and advance the time
        mujoco.mj_step(mj_model, mj_data)

        if self._sync_hook:
            assert all_arrows is not None
            self._sync_hook(mj_model, mj_data, all_arrows)

        if self.playback_speed > 0:
            sim_elapsed = mj_data.time - self._start_sim_time

            # how much time we want to have passed
            target_wall_elapsed = sim_elapsed / self.playback_speed

            # how much time has actually passed
            actual_wall_elapsed = time.time() - self._start_wall_time

            sleep_time = target_wall_elapsed - actual_wall_elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
