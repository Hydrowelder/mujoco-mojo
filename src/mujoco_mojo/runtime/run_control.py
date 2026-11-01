import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = ["RunControl", "RunTarget", "TargetKind"]

HOLD_POLL_SECONDS: float = 1 / 60
"""How often a held run wakes to check for a stop request and to call `RunControl.pump`."""


class TargetKind(StrEnum):
    """What a `RunTarget` is measured in."""

    TIME = "time"
    """The simulation clock, in whatever unit the model's `data.time` is."""
    STEP = "step"
    """The number of `RuntimeManager.step` calls the run has made."""


@dataclass(frozen=True)
class RunTarget:
    """Where a run should pause by itself. Both kinds are readings since the run began, not distances from now."""

    kind: TargetKind
    value: float

    def reached(self, sim_time: float, steps: int) -> bool:
        """Whether a run at `sim_time` that has made `steps` steps is at or past the target."""
        reading = sim_time if self.kind is TargetKind.TIME else steps
        return reading >= self.value

    @property
    def label(self) -> str:
        """The target as typed, such as `time 2.5` or `step 500`."""
        return f"{self.kind.value} {self.value:g}"


@dataclass(eq=False)
class RunControl:
    """
    What a user interface asks of a run in progress: hold it, let it carry on, advance it a few steps at a time, or change its speed.

    A speed of 0 is manual stepping: the run is held at every step and each `step` request lets one through. That meaning belongs to this class, so a `RuntimeManager` used without one still treats a `playback_speed` of 0 as unpaced.

    The interface calls the request methods from its own thread. The `RuntimeManager` calls `wait_while_paused` and `take_speed` at the top of every `step`, which is the only place a run written as a loop of `step` calls can be held without any help from the runtime function.
    """

    pump: Callable[[], None] | None = None
    """Called repeatedly while the run is held, so a viewer that needs regular attention to stay responsive gets it."""
    on_hold: Callable[[str | None], None] | None = None
    """Called from the run's own thread each time the run is about to be held. The reason is given when the run held itself on reaching its target, and is `None` when the interface asked for the hold or the run is stepping manually."""

    _condition: threading.Condition = field(
        default_factory=threading.Condition, init=False, repr=False
    )
    _paused: bool = field(default=False, init=False, repr=False)
    _manual: bool = field(default=False, init=False, repr=False)
    _steps: int = field(default=0, init=False, repr=False)
    _speed: float | None = field(default=None, init=False, repr=False)
    _target: RunTarget | None = field(default=None, init=False, repr=False)
    _position: tuple[float, int] = field(default=(0.0, 0), init=False, repr=False)

    @property
    def paused(self) -> bool:
        with self._condition:
            return self._paused

    @property
    def manual(self) -> bool:
        """Whether the run is stepping manually, held at every step until one is let through."""
        with self._condition:
            return self._manual

    def pause(self) -> None:
        """Holds the run at its next step."""
        with self._condition:
            self._paused = True
            self._condition.notify_all()

    def resume(self) -> None:
        """Lets a held run carry on, and forgets any steps still owed."""
        with self._condition:
            self._paused = False
            self._steps = 0
            self._condition.notify_all()

    def step(self, count: int = 1) -> None:
        """Lets the run take `count` more steps and then holds it again. A run that is not held yet is held after those steps."""
        with self._condition:
            self._paused = True
            self._steps += count
            self._condition.notify_all()

    def set_speed(self, speed: float) -> None:
        """Asks for a new playback speed, which the run picks up at its next step. A speed of 0 is manual stepping. Leaving manual stepping leaves the run paused, so changing the speed never starts a run by itself."""
        with self._condition:
            self._speed = speed
            was_manual = self._manual
            self._manual = speed == 0
            if was_manual and not self._manual:
                self._paused = True
                self._steps = 0
            self._condition.notify_all()

    def take_speed(self) -> float | None:
        """The speed asked for since the last call, or `None` if there is no new one."""
        with self._condition:
            speed, self._speed = self._speed, None
            return speed

    def run_until(self, target: RunTarget | None) -> None:
        """Pauses the run once it reaches `target`, in place of any earlier target. `None` clears it. A target that is reached pauses the run once and is then forgotten."""
        with self._condition:
            self._target = target

    @property
    def target(self) -> RunTarget | None:
        """Where the run will pause by itself, if anywhere."""
        with self._condition:
            return self._target

    @property
    def position(self) -> tuple[float, int]:
        """The simulation time and step count the run was at when it last asked whether to go on."""
        with self._condition:
            return self._position

    def reset(self, speed: float | None = None) -> None:
        """Clears every request, so the next run starts running. `speed` is the speed that run was given, which only matters because 0 means it starts out stepping manually."""
        with self._condition:
            self._paused = False
            self._manual = speed == 0
            self._steps = 0
            self._speed = None
            self._target = None
            self._position = (0.0, 0)
            self._condition.notify_all()

    def wait_while_paused(
        self,
        stop: threading.Event | None = None,
        sim_time: float = 0.0,
        steps: int = 0,
    ) -> float:
        """
        Blocks the calling thread while the run is held, and returns how many seconds it was held for.

        It returns at once when the run is not held, when a step is owed, or when `stop` is set. Calling it from the thread that steps the run is what holds the run. `sim_time` and `steps` say where the run is, which is how a target gets noticed: reaching it holds the run, and `on_hold` hears why.
        """
        reason: str | None = None
        with self._condition:
            self._position = (sim_time, steps)
            if self._target is not None and self._target.reached(sim_time, steps):
                reason = (
                    f"reached {self._target.label} (time {sim_time:g}, step {steps})"
                )
                self._target = None
                self._paused = True
                self._steps = 0

        began: float | None = None
        while True:
            with self._condition:
                if not (self._paused or self._manual) or (
                    stop is not None and stop.is_set()
                ):
                    break
                if self._steps > 0:
                    self._steps -= 1
                    break
                first = began is None
                if first:
                    began = time.time()
            if first and self.on_hold is not None:
                self.on_hold(reason)
            with self._condition:
                self._condition.wait(timeout=HOLD_POLL_SECONDS)
            if self.pump is not None:
                self.pump()
        return 0.0 if began is None else time.time() - began
