from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Protocol, Self, runtime_checkable

import mujoco

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.runtime.load import Load
from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.runtime.tracer import Tracer
from mujoco_mojo.runtime.video_recorder import VideoRecorder
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.proximity import Proximity
from mujoco_mojo.visualization import ArrowConfig, LineConfig

logger = get_logger(__name__)

_current: ContextVar[RuntimeManager] = ContextVar("_current_runtime_manager")


class SimulationStopped(Exception):
    """Raised by `RuntimeManager.step` to unwind a running simulation when the user requests a stop."""


@runtime_checkable
class SyncHook(Protocol):
    def __call__(
        self,
        state: MjState,
        arrows: list[ArrowConfig],
        lines: list[LineConfig],
    ) -> Any: ...


@dataclass
class RuntimeManager:
    signal_manager: SignalManager | None = None

    loads: list[Load] = field(default_factory=list)
    proximities: list[Proximity] = field(default_factory=list)
    tracers: list[Tracer] = field(default_factory=list)
    video_recorders: list[VideoRecorder] = field(default_factory=list)

    playback_speed: float = 1.0
    _start_wall_time: float = field(default_factory=time.time, init=False)
    _start_sim_time: float = field(default=0.0, init=False)

    _sync_hook: SyncHook | None = None
    _skip_recording: bool = False
    _stop_event: threading.Event | None = None

    _resolved: bool = False
    _context_token: Token | None = field(default=None, init=False, repr=False)

    def __enter__(self) -> Self:
        """Prime the model and prepare results. Also makes this instance available via `RuntimeManager.current()` for the duration of the `with` block."""
        self._context_token = _current.set(self)
        return self

    def __exit__(self, exc_type, exc, tb):
        """Ensure all telemetry is flushed even if the simulation crashed. Also saves recordings"""
        assert self._context_token is not None
        _current.reset(self._context_token)
        self._context_token = None

        if self.signal_manager:
            self.signal_manager.close()

        if self.video_recorders:
            self.save_recordings()

    @classmethod
    def current(cls) -> RuntimeManager:
        """Returns the `RuntimeManager` of the innermost enclosing `with` block. Raises if called outside of one."""
        try:
            return _current.get()
        except LookupError:
            msg = "No active RuntimeManager context. Call this from within a `with runtime_manager as rm:` block, or pass the runtime_manager/signal_manager explicitly."
            logger.error(msg)
            raise RuntimeError(msg) from None

    def save_recordings(self):
        logger.info(f"Saving {len(self.video_recorders)} videos in parallel...")

        def _save_and_close(recorder: VideoRecorder):
            recorder.save()
            recorder.close()

        with ThreadPoolExecutor() as executor:
            for recorder in self.video_recorders:
                executor.submit(_save_and_close, recorder)

        logger.info("All video encoding tasks complete.")

    def resolve(self, state: MjState):
        """Call this once after mj_loadXML to prime the caches."""
        for load in self.loads:
            load.resolve_ids(state)
        self._resolved = True

    def add_load(self, load: Load):
        for _l in self.loads:
            if load.name == _l.name:
                logger.warning(
                    f"Load with name {load.name} has already been registered"
                )
        self.loads.append(load)

    def add_proximity(self, proximity: Proximity):
        # check if the pair is already being checked
        assert proximity.geom_1.name and proximity.geom_2.name

        search = sorted([proximity.geom_1.name, proximity.geom_2.name])
        for p in self.proximities:
            assert p.geom_1.name and p.geom_2.name
            if search == sorted([p.geom_1.name, p.geom_2.name]):
                logger.warning(
                    f"Proximities for {proximity.geom_1.name} and {proximity.geom_2.name} have already been registered"
                )

        self.proximities.append(proximity)

    def add_video_recorder(self, video_recorder: VideoRecorder):
        self.video_recorders.append(video_recorder)

    def add_tracer(self, tracer: Tracer):
        self.tracers.append(tracer)

    def step(
        self,
        state: MjState,
        clear_xfrc_applied: bool = True,
        clear_qfrc_applied: bool = True,
        clear_ctrl: bool = True,
    ):
        """
        Calculates forces, integratess physics, and handles telemetry.

        Args:
            state: The paired MuJoCo model and data instance.
            clear_xfrc_applied: If True, zero `xfrc_applied` (external forces) before applying loads.
            clear_qfrc_applied: If True, zero `qfrc_applied` (user-defined forces) before applying loads.
            clear_ctrl: If True, zero `ctrl` (actuator controls) before applying loads. Set to False if controls are set externally and should persist across steps, e.g. when not driven by an `ActuatorLoad` every timestep.

        """
        if self._stop_event is not None and self._stop_event.is_set():
            raise SimulationStopped("Simulation stopped by user request.")

        # clear buffers for next timestep
        if clear_xfrc_applied:
            state.data.xfrc_applied.fill(0)  # external forces
        if clear_qfrc_applied:
            state.data.qfrc_applied.fill(0)  # user-defined forces
        if clear_ctrl:
            state.data.ctrl.fill(0)  # actuator forces

        # sync state variables and clear render buffer
        mujoco.mj_forward(state.model, state.data)

        if state.data.time == 0.0 or self._start_sim_time == 0.0:
            self._start_sim_time = state.data.time
            self._start_wall_time = time.time()

        # resolve IDs and initial distances
        # it is critical this is done after mj_forward to update site positions
        if not self._resolved:
            self.resolve(state)

        # apply user forcing functions
        for load in self.loads:
            load.apply_load(state)

        # record data
        if self.signal_manager and not self._skip_recording:
            mujoco.mj_forward(state.model, state.data)
            self.signal_manager.record(state)

        # record any frames which are due
        all_arrows = None
        all_lines = None
        all_traces = None
        if self.video_recorders or self._sync_hook:
            # gather arrows for forcing functions
            all_arrows: list[ArrowConfig] | None = []
            all_lines: list[LineConfig] | None = []
            all_traces: list[LineConfig] | None = []

            for load in self.loads:
                all_arrows.extend(load.get_visuals(state))

            for proximity in self.proximities:
                visual = proximity.get_visuals(state, self.signal_manager)
                if visual is not None:
                    all_lines.append(visual)

            for tracer in self.tracers:
                tracer.update(state)
                all_traces.extend(tracer.get_visuals(state))

        if self.video_recorders:
            assert (
                all_arrows is not None
                and all_lines is not None
                and all_traces is not None
            )
            for recorder in self.video_recorders:
                recorder.capture_frame(
                    state=state,
                    custom_arrows=all_arrows,
                    custom_lines=all_lines,
                    custom_traces=all_traces,
                )

        # integrate physics and advance the time
        mujoco.mj_step(state.model, state.data)

        if self._sync_hook:
            assert (
                all_arrows is not None
                and all_lines is not None
                and all_traces is not None
            )
            # the live-viewer sync hook has no per-category toggle, so just merge everything it should draw
            self._sync_hook(state, all_arrows, all_lines + all_traces)

        if self.playback_speed > 0:
            sim_elapsed = state.data.time - self._start_sim_time

            # how much time we want to have passed
            target_wall_elapsed = sim_elapsed / self.playback_speed

            # how much time has actually passed
            actual_wall_elapsed = time.time() - self._start_wall_time

            sleep_time = target_wall_elapsed - actual_wall_elapsed
            if sleep_time > 0:
                if self._stop_event is not None:
                    # use wait() instead of sleep() so a stop request interrupts
                    # the pacing delay immediately, rather than after it elapses
                    self._stop_event.wait(timeout=sleep_time)
                else:
                    time.sleep(sleep_time)
