from __future__ import annotations

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager, nullcontext
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, Self, runtime_checkable

import mujoco

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.runtime.load import Load
from mujoco_mojo.runtime.requirements_manager import (
    RequirementFn,
    RequirementsManager,
    SimulationStopped,
    _RequirementSpec,
)
from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.runtime.tracer import Tracer
from mujoco_mojo.runtime.video_recorder import VideoRecorder
from mujoco_mojo.stochas import BaseDict
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.proximity import Proximity
from mujoco_mojo.utils.statusing import RequirementResult
from mujoco_mojo.visualization import ArrowConfig, LineConfig

if TYPE_CHECKING:
    from mujoco_mojo.mojo_model import MojoModel

logger = get_logger(__name__)

__all__ = ["RuntimeManager", "SimulationStopped"]

_current: ContextVar[RuntimeManager] = ContextVar("_current_runtime_manager")


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
    requirements: RequirementsManager = field(default_factory=RequirementsManager)

    playback_speed: float = 1.0
    _start_wall_time: float = field(default_factory=time.time, init=False)
    _start_sim_time: float = field(default=0.0, init=False)

    _sync_hook: SyncHook | None = None
    _viewer_lock: Callable[[], AbstractContextManager[Any]] | None = None
    _skip_recording: bool = False
    _stop_event: threading.Event | None = None

    _resolved: bool = False
    _context_token: Token | None = field(default=None, init=False, repr=False)

    _mojo_model: MojoModel | None = field(default=None, init=False, repr=False)
    _last_state: MjState | None = field(default=None, init=False, repr=False)

    # --- backward-compat shims (thin delegation to self.requirements) ---

    @property
    def _requirements(self) -> BaseDict[_RequirementSpec]:
        return self.requirements._requirements

    @property
    def requirement_results(self) -> list[RequirementResult]:
        return self.requirements.results

    # --- context manager ---

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

        controlled_exit = exc_type is None or (
            exc_type is not None and issubclass(exc_type, SimulationStopped)
        )
        if (
            controlled_exit
            and self.requirements._requirements
            and self._mojo_model is not None
            and self.signal_manager is not None
            and self._last_state is not None
        ):
            self.requirements.run_end_of_trial_evaluation(
                self._last_state,
                signal_manager=self.signal_manager,
                mojo_model=self._mojo_model,
            )

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

    # --- requirements API ---

    def add_requirement(
        self,
        fn: RequirementFn,
        *,
        name: str | None = None,
        every: int | None = None,
        terminate_on_fail: bool = False,
        terminate_on_pass: bool = False,
        latch_on_fail: bool = True,
        latch_on_pass: bool = False,
        post_result: bool = True,
    ) -> None:
        """
        Register a named pass/fail check evaluated at end of trial and optionally during simulation.

        Args:
            fn: Callable `(MojoModel, MjState, MojoDataFrame | None) -> (passed, message)` where `passed` is `True`, `False`, or `None` (undetermined; only meaningful during live checks).
            name: Label for this check in results and telemetry. Defaults to `fn.__name__` when omitted or empty.
            every: If `None` (default), the check runs once at end of trial. If set to N, the check also runs every N steps during simulation, posting a telemetry signal under `Requirements/{name}:result`.
            terminate_on_fail: When `every` is set, a failing live check raises `RequirementTerminated` and the trial is marked `TERMINATED` (a requirement failure).
            terminate_on_pass: When `every` is set, a passing live check raises `RequirementSatisfied` and the trial completes early as a normal success (subject to the other requirements).
            latch_on_fail: When `every` is set, once a live check fails, `fn` is never called again (live or end-of-trial); the failing verdict is replayed. Defaults to `True` since it's a pure compute-saving option: a live failure already dooms the trial regardless of anything that happens afterward, so nothing about the outcome changes. Pass `False` to keep calling `fn` after a failure anyway (e.g. for logging/telemetry from later steps).
            latch_on_pass: When `every` is set, once a live check passes, `fn` is never called again; the passing verdict is replayed for the rest of the trial. Unlike `latch_on_fail`, this changes the outcome: without it, a later `False` would still fail the requirement even after an earlier `True` (any live failure is sticky); with it, no evaluation after the pass can ever produce that later failure. Defaults to `False` for this reason.
            post_result: Post a telemetry column to the signal manager after evaluating the requirement if True.

        """
        self.requirements.add(
            fn,
            name=name,
            every=every,
            terminate_on_fail=terminate_on_fail,
            terminate_on_pass=terminate_on_pass,
            latch_on_fail=latch_on_fail,
            latch_on_pass=latch_on_pass,
            post_result=post_result,
        )

    def requirement(
        self,
        name: str | None = None,
        *,
        every: int | None = None,
        terminate_on_fail: bool = False,
        terminate_on_pass: bool = False,
        latch_on_fail: bool = True,
        latch_on_pass: bool = False,
        post_result: bool = True,
    ) -> Callable[[RequirementFn], RequirementFn]:
        """
        Registers a pass/fail check that runs automatically when the trial ends. Results are collected in `requirements.results` and written to `requirements.json` alongside the trial telemetry.

        The decorated function must accept `(mojo_model: MojoModel, state: MjState, df: MojoDataFrame | None)` and return `(passed, message)` where `passed` is `True`, `False`, or `None` (undetermined yet; a no-op during live checks, a failure if still undetermined at end of trial). `mojo_model` provides access to user data and named values. `state` is the last simulation state. `df` is the full trial telemetry parquet at end-of-trial, or `None` during live evaluations (see `every`).

        Args:
            name: Label for this check in results and telemetry. Defaults to the function's `__name__`.
            every: When set, the check also runs inside `step()` every N steps, posting `1.0` (pass) or `0.0` (fail) under `Requirements/{name}:result` in the telemetry parquet. `df` is `None` during these live calls; use `state` instead.
            terminate_on_fail: When `every` is set, a failing live check raises `RequirementTerminated`, unwinds the simulation, and marks the trial `TERMINATED`.
            terminate_on_pass: When `every` is set, a passing live check raises `RequirementSatisfied`, unwinds the simulation, and lets the trial complete early as a normal success (subject to the other requirements).
            latch_on_fail: When `every` is set, once a live check fails, `fn` is never called again; the failing verdict is replayed for free. Defaults to `True`, purely a compute-saving option, since the trial's outcome is already identical to the default sticky-failure behavior regardless of latching. Pass `False` to keep calling `fn` after a failure anyway.
            latch_on_pass: When `every` is set, once a live check passes, `fn` is never called again; the passing verdict is replayed for the rest of the trial. This is the only way to get "once passed, stays passed" semantics without ending the whole simulation via `terminate_on_pass`. Defaults to `False` since, unlike `latch_on_fail`, it changes the outcome (a later failure would otherwise still be observed and would still fail the requirement).
            post_result: Post a telemetry column to the signal manager after evaluating the requirement if True.

        Example:
            `@rm.requirement(every=100, terminate_on_fail=True)`
            `def upright(mojo_model, state, df): return state.data.qpos[2] > 0.1, "ok"`

        """
        return self.requirements.decorator(
            name,
            every=every,
            terminate_on_fail=terminate_on_fail,
            terminate_on_pass=terminate_on_pass,
            latch_on_fail=latch_on_fail,
            latch_on_pass=latch_on_pass,
            post_result=post_result,
        )

    def last_passed(
        self, name_or_fn: str | RequirementFn, state: MjState
    ) -> bool | None:
        """
        Returns the cached live-check result for a requirement at the current sim time, or `None` if there is no verdict yet.

        Accepts either the requirement's name or the function itself. The decorator returns the original function unchanged, so the reference from `@rm.requirement(...)` can be passed directly instead of retyping its name. Passing a function that was never registered raises `ValueError`.

        `None` covers two cases callers can't tell apart: the check hasn't run at this exact sim time (`every > 1` only evaluates on some steps), or it ran and explicitly returned undetermined (`None`). Either way, treat `None` as "no verdict yet", not as failure.

        Example:
            ```python
            if rm.last_passed("upright", state) is False:
                apply_recovery()

            if rm.last_passed(upright, state) is False:  # or pass the function itself
                apply_recovery()
            ```

        """
        return self.requirements.last_passed(name_or_fn, state)

    def _evaluate_requirements(self) -> None:
        assert self.signal_manager is not None
        assert self._mojo_model is not None
        assert self._last_state is not None
        self.requirements.run_end_of_trial_evaluation(
            self._last_state,
            signal_manager=self.signal_manager,
            mojo_model=self._mojo_model,
        )

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
            clear_ctrl: If True, zero `ctrl` (actuator controls) before applying loads. Set to False if controls are set externally and should persist across steps, e.g. when not driven by an `ActuatorControl` every timestep.

        """
        logger.debug(f"Computing simulation step t={state.data.time:.6f}")

        if self._stop_event is not None and self._stop_event.is_set():
            logger.debug("'stop_event' is set; raising SimulationStopped")
            raise SimulationStopped("Simulation stopped by user request.")

        # while a live viewer is attached, its GUI thread can read model/data at any
        # time (e.g. re-rendering when the user interacts with the view), so all
        # physics mutations happen under the viewer lock. released again before the
        # sync hook and the pacing sleep so the GUI thread is never starved
        viewer_lock = (
            self._viewer_lock() if self._viewer_lock is not None else nullcontext()
        )
        with viewer_lock:
            # clear buffers for next timestep
            if clear_xfrc_applied:
                state.data.xfrc_applied.fill(0)  # external forces
            if clear_qfrc_applied:
                state.data.qfrc_applied.fill(0)  # user-defined forces
            if clear_ctrl:
                state.data.ctrl.fill(0)  # actuator forces

            # sync state variables and clear render buffer
            # invalidate first: mj_forward changes qacc, which cfrc_int/cacc are derived from
            state.invalidate_rne_post_constraint()
            mujoco.mj_forward(state.model, state.data)

            if state.data.time == 0.0 or self._start_sim_time == 0.0:
                self._start_sim_time = state.data.time
                self._start_wall_time = time.time()

            # resolve IDs and initial distances
            # it is critical this is done after mj_forward to update site positions
            if not self._resolved:
                logger.debug("First step; resolving load IDs")
                self.resolve(state)

            # apply user forcing functions
            for load in self.loads:
                load.apply_load(state)

            # record data
            if self.signal_manager and not self._skip_recording:
                # invalidate first: loads may have changed qfrc_applied/xfrc_applied since the last mj_forward
                state.invalidate_rne_post_constraint()
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

                # tracer.get_visuals() rebuilds its whole trail every call, which is only
                # cheap relative to *rendered frames* (tens per second), not physics steps
                # (potentially thousands per second) - so only pay for it on steps where
                # something will actually consume it. update() stays unconditional so the
                # trail's position history doesn't lose resolution between rendered frames.
                needs_traces = self._sync_hook is not None or any(
                    r.is_due(state) for r in self.video_recorders
                )
                for tracer in self.tracers:
                    tracer.update(state)
                    if needs_traces:
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
            state.invalidate_rne_post_constraint()
            mujoco.mj_step(state.model, state.data)
            logger.debug(f"Physics integrated; new t={state.data.time:.6f}")

        if self._sync_hook:
            assert (
                all_arrows is not None
                and all_lines is not None
                and all_traces is not None
            )
            # the live-viewer sync hook has no per-category toggle, so just merge everything it should draw
            self._sync_hook(state, all_arrows, all_lines + all_traces)

        # track last state and evaluate live requirements
        self._last_state = state
        self.requirements.step(
            state,
            signal_manager=self.signal_manager,
            mojo_model=self._mojo_model,
        )

        if self.playback_speed > 0:
            sim_elapsed = state.data.time - self._start_sim_time

            # how much time we want to have passed
            target_wall_elapsed = sim_elapsed / self.playback_speed

            # how much time has actually passed
            actual_wall_elapsed = time.time() - self._start_wall_time

            sleep_time = target_wall_elapsed - actual_wall_elapsed
            if sleep_time > 0:
                logger.debug(
                    f"Pacing sleep {sleep_time:.4f}s "
                    f"(sim={sim_elapsed:.6f}s, wall={actual_wall_elapsed:.6f}s)"
                )
                if self._stop_event is not None:
                    # use wait() instead of sleep() so a stop request interrupts
                    # the pacing delay immediately, rather than after it elapses
                    self._stop_event.wait(timeout=sleep_time)
                else:
                    time.sleep(sleep_time)
