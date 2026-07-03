from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.stochas import BaseDict
from mujoco_mojo.typing import SignalCategory
from mujoco_mojo.utils.dataframe import MojoDataFrame
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.statusing import REQUIREMENTS_FNAME, RequirementResult

if TYPE_CHECKING:
    from mujoco_mojo.runtime.signal_manager import SignalManager

type RequirementFn = Callable[
    [MojoModel, MjState, MojoDataFrame | None], tuple[bool | None, str]
]
"""A requirement check. Returns `(passed, message)` where `passed` is `True` (satisfied), `False` (violated), or `None` (undetermined yet; only meaningful during live checks)."""

logger = get_logger(__name__)

__all__ = [
    "RequirementFn",
    "RequirementSatisfied",
    "RequirementTerminated",
    "RequirementsManager",
    "SimulationStopped",
]


class SimulationStopped(Exception):
    """Raised by `RuntimeManager.step` to unwind a running simulation when the user requests a stop."""


class RequirementTerminated(SimulationStopped):
    """Raised when one or more live requirements with `terminate_on_fail=True` fail. Subclasses `SimulationStopped` so existing catch blocks need no changes."""


class RequirementSatisfied(SimulationStopped):
    """Raised when one or more live requirements with `terminate_on_pass=True` pass, ending the trial early as a normal (successful) completion rather than a failure."""


@dataclass(frozen=True)
class _RequirementSpec:
    name: str
    fn: RequirementFn
    every: int | None = None  # None = end-of-trial only; N = check every N steps (live)
    terminate_on_fail: bool = False
    terminate_on_pass: bool = False
    latch_on_fail: bool = False
    latch_on_pass: bool = False
    post_result: bool = True


@dataclass
class RequirementsManager:
    """Owns all requirement registration, live-step evaluation, and end-of-trial evaluation for a simulation trial."""

    _requirements: BaseDict[_RequirementSpec] = field(
        default_factory=BaseDict[_RequirementSpec], init=False, repr=False
    )
    """Registered requirements keyed by name (via `stochas.BaseDict`, which stores by `.name` and raises on duplicate keys), preventing two requirements from silently sharing a name."""
    _live_cache: dict[tuple[str, float], bool | None] = field(
        default_factory=dict, init=False, repr=False
    )
    """Every live evaluation's verdict keyed by (name, sim_time), including undetermined (`None`) ones -- so a cache hit means "evaluated at this exact time", distinct from a miss ("never evaluated at this time")."""
    _last_live_result: dict[str, bool] = field(
        default_factory=dict, init=False, repr=False
    )
    _first_live_failure: dict[str, tuple[float, str]] = field(
        default_factory=dict, init=False, repr=False
    )
    """Maps requirement name to (sim_time, message) of its first failed live check. A requirement that ever failed live is failed for the trial, even if its end-of-trial evaluation passes."""
    _latched: dict[str, tuple[bool, str, float]] = field(
        default_factory=dict, init=False, repr=False
    )
    """Maps requirement name to (verdict, message, sim_time) once `latch_on_pass`/`latch_on_fail` locks in a final verdict. The check function is never called again afterward (neither live nor at end-of-trial); the locked verdict is replayed instead."""
    _step_count: int = field(default=0, init=False, repr=False)
    _termination_reason: str | None = field(default=None, init=False, repr=False)
    results: list[RequirementResult] = field(default_factory=list, init=False)

    @property
    def _live_requirements(self) -> list[_RequirementSpec]:
        return [s for s in self._requirements.values() if s.every is not None]

    def add(
        self,
        fn: RequirementFn,
        *,
        name: str | None = None,
        every: int | None = None,
        terminate_on_fail: bool = False,
        terminate_on_pass: bool = False,
        latch_on_fail: bool = False,
        latch_on_pass: bool = False,
        post_result: bool = True,
    ) -> None:
        resolved_name = name or getattr(fn, "__name__", repr(fn))

        if every:
            every = max(0, every)
        else:
            if terminate_on_fail or terminate_on_pass:
                logger.warning(
                    f"Requirement {resolved_name} was set to terminate the simulation but its function will only be evaluated at the end of the simulation"
                )
            if latch_on_fail or latch_on_pass:
                logger.warning(
                    f"Requirement {resolved_name} was set to latch but its function will only be evaluated once, at the end of the simulation"
                )

        try:
            self._requirements.update(
                _RequirementSpec(
                    name=resolved_name,
                    fn=fn,
                    every=every,
                    terminate_on_fail=terminate_on_fail,
                    terminate_on_pass=terminate_on_pass,
                    latch_on_fail=latch_on_fail,
                    latch_on_pass=latch_on_pass,
                    post_result=post_result,
                )
            )
        except KeyError:
            raise ValueError(
                f"A requirement named '{resolved_name}' has already been registered"
            ) from None

    def decorator(
        self,
        name: str | None = None,
        *,
        every: int | None = None,
        terminate_on_fail: bool = False,
        terminate_on_pass: bool = False,
        latch_on_fail: bool = False,
        latch_on_pass: bool = False,
        post_result: bool = True,
    ) -> Callable[[RequirementFn], RequirementFn]:
        def _wrap(fn: RequirementFn) -> RequirementFn:
            self.add(
                fn,
                name=name,
                every=every,
                terminate_on_fail=terminate_on_fail,
                terminate_on_pass=terminate_on_pass,
                latch_on_fail=latch_on_fail,
                latch_on_pass=latch_on_pass,
                post_result=post_result,
            )
            return fn

        return _wrap

    def last_passed(
        self, name_or_fn: str | RequirementFn, state: MjState
    ) -> bool | None:
        return self._live_cache.get((self._resolve_name(name_or_fn), state.data.time))

    def _resolve_name(self, name_or_fn: str | RequirementFn) -> str:
        if isinstance(name_or_fn, str):
            return name_or_fn
        for spec in self._requirements.values():
            if spec.fn is name_or_fn:
                return spec.name
        fn_repr = getattr(name_or_fn, "__name__", repr(name_or_fn))
        raise ValueError(f"{fn_repr} is not registered as a requirement")

    def step(
        self,
        state: MjState,
        *,
        signal_manager: SignalManager | None,
        mojo_model: MojoModel | None,
    ) -> None:
        """Evaluates live requirements for the current step, posts telemetry, and raises `SimulationStopped` if a terminating check fails."""
        if not self._live_requirements or mojo_model is None:
            return

        self._step_count += 1
        terminate_msgs: list[str] = []
        satisfied_msgs: list[str] = []

        for spec in self._live_requirements:
            assert spec.every is not None

            if self._step_count % spec.every == 0:
                already_latched = self._latched.get(spec.name)
                if already_latched is not None:
                    # verdict already locked in: replay it instead of paying
                    # to call (possibly expensive) fn again
                    passed, req_msg, latch_time = already_latched
                    logger.debug(
                        f"requirement '{spec.name}' at t={state.data.time:.6f}: "
                        f"replaying latched {'pass' if passed else 'fail'} from t={latch_time:.6f} "
                        f"(evaluation skipped)"
                    )
                else:
                    req_msg = ""
                    try:
                        passed, req_msg = spec.fn(mojo_model, state, None)
                    except Exception as e:
                        logger.warning(
                            f"Requirement {spec.name} raised an exception during its evaluation: {e}"
                        )
                        passed = False
                    logger.debug(
                        f"requirement '{spec.name}' evaluated at t={state.data.time:.6f}: "
                        f"{'undetermined' if passed is None else 'passed' if passed else 'failed'} "
                        f"({req_msg or 'no message'})"
                    )

                # cache every verdict, including undetermined (None), so
                # last_passed() can tell "evaluated, no verdict yet" apart
                # from "not evaluated at this sim time". None never latches a
                # failure, terminates the trial, or posts telemetry, though.
                self._live_cache[(spec.name, state.data.time)] = passed
                if passed is not None:
                    self._last_live_result[spec.name] = passed
                    if not passed and spec.name not in self._first_live_failure:
                        self._first_live_failure[spec.name] = (
                            state.data.time,
                            req_msg or "no message attached",
                        )
                    if not passed and spec.terminate_on_fail:
                        terminate_msgs.append(
                            f"requirement '{spec.name}' triggered early termination ({req_msg or 'no message attached'})"
                        )
                    if passed and spec.terminate_on_pass:
                        satisfied_msgs.append(
                            f"requirement '{spec.name}' was satisfied and ended the trial early ({req_msg or 'no message attached'})"
                        )
                    if already_latched is None and (
                        (passed and spec.latch_on_pass)
                        or (not passed and spec.latch_on_fail)
                    ):
                        self._latched[spec.name] = (
                            passed,
                            req_msg or "no message attached",
                            state.data.time,
                        )

            # post last known result on every step so the telemetry signal is continuous;
            # skip entirely if this requirement has never been evaluated yet.
            if (
                signal_manager
                and spec.post_result
                and spec.name in self._last_live_result
            ):
                signal_manager.post(
                    value=1.0 if self._last_live_result[spec.name] else 0.0,
                    category=SignalCategory.REQUIREMENTS,
                    subgroups=(spec.name,),
                    attr="result",
                )

        # a failing terminator wins over a satisfied one on the same step
        if terminate_msgs:
            combined = "; ".join(terminate_msgs)
            self._termination_reason = combined
            logger.info(combined)
            raise RequirementTerminated(combined)
        if satisfied_msgs:
            combined = "; ".join(satisfied_msgs)
            self._termination_reason = combined
            logger.info(combined)
            raise RequirementSatisfied(combined)

    def run_end_of_trial_evaluation(
        self,
        last_state: MjState,
        *,
        signal_manager: SignalManager,
        mojo_model: MojoModel,
    ) -> None:
        """Runs all requirements against the final simulation state and telemetry parquet, stores results, and writes `requirements.json` to the trial directory."""
        from mujoco_mojo.utils.dataframe import _MojoFrame

        parquet_path = signal_manager.export_path
        df = _MojoFrame.read_parquet(parquet_path) if parquet_path.exists() else None

        results: list[RequirementResult] = []
        for spec in self._requirements.values():
            # the requirement's static configuration -- shown alongside the
            # per-trial verdict so callers can tell e.g. "this failed" apart
            # from "this failed and would have kept re-checking every 10 steps"
            config = {
                "every": spec.every,
                "terminate_on_fail": spec.terminate_on_fail,
                "terminate_on_pass": spec.terminate_on_pass,
                "latch_on_fail": spec.latch_on_fail,
                "latch_on_pass": spec.latch_on_pass,
            }

            if (latched := self._latched.get(spec.name)) is not None:
                # verdict already locked in by latch_on_pass/latch_on_fail:
                # never call fn again, just report the locked-in verdict
                passed, latch_msg, latch_time = latched
                message = (
                    f"latched {'passed' if passed else 'failed'} at t={latch_time:.6f} "
                    f"({latch_msg}); evaluation skipped afterward to save compute"
                )
                results.append(
                    RequirementResult(
                        name=spec.name,
                        passed=passed,
                        message=message,
                        decided_at=latch_time,
                        **config,
                    )
                )
                continue

            try:
                passed, message = spec.fn(mojo_model, last_state, df)
            except Exception as e:
                passed = False
                message = f"requirement raised {type(e).__name__}: {e}"

            # end of trial is the last chance to decide: a check that is still
            # undetermined here never passed, so it fails
            if passed is None:
                passed = False
                message = f"undetermined at end of trial ({message})"

            # a plain end-of-trial verdict is decided at the final sim time;
            # overridden below if a live failure decided it earlier
            decided_at = last_state.data.time

            # a live requirement that failed at any point during the run is a
            # failure for the trial, even if its end-of-trial evaluation passes
            if (failure := self._first_live_failure.get(spec.name)) is not None:
                fail_time, fail_msg = failure
                # only count determinate (True/False) evaluations; undetermined
                # (None) verdicts are cached but never counted as checks or failures
                n_evals = sum(
                    1
                    for (n, _), ok in self._live_cache.items()
                    if n == spec.name and ok is not None
                )
                n_fails = sum(
                    1
                    for (n, _), ok in self._live_cache.items()
                    if n == spec.name and ok is False
                )
                message = (
                    f"failed {n_fails}/{n_evals} live checks, first at t={fail_time:.6f} ({fail_msg}); "
                    f"end-of-trial evaluation {'passed' if passed else 'failed'} ({message})"
                )
                passed = False
                decided_at = fail_time

            results.append(
                RequirementResult(
                    name=spec.name,
                    passed=passed,
                    message=message,
                    decided_at=decided_at,
                    **config,
                )
            )

        self.results = results
        trial_dir = parquet_path.parent
        (trial_dir / REQUIREMENTS_FNAME).write_text(
            json.dumps([r.model_dump() for r in results], indent=2),
            encoding="utf-8",
        )
