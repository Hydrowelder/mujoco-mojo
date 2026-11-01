"""Stand-ins for the session and viewer, so the Reloaded controller and terminal UI can be driven without a model, a physics run, or a window."""

import threading
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mujoco

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.utils.layers.reloaded.backends.base import ConnectionInfo
from mujoco_mojo.utils.layers.reloaded.controller import (
    ControllerEvent,
    LogEvent,
    ReloadedController,
    RunState,
)
from mujoco_mojo.utils.layers.reloaded.session import OnReloadCallback
from mujoco_mojo.visualization import ArrowConfig, LineConfig


def make_state() -> MjState:
    model = mujoco.MjModel.from_xml_string("<mujoco/>")
    return MjState(model=model, data=mujoco.MjData(model))


@dataclass
class FakeSession:
    """Satisfies `ReloadedSession`. `generation_behavior` runs inside `generate_construct` once the model is published, and `behavior` stands in for the runtime, which like the real session only runs when asked for and a runtime exists."""

    runtime: str | None = "sim.runtime"
    workdir: Path = Path("workdir")
    seed: int | None = None
    trial_num: int = 0
    watch: bool = False
    record: bool = False
    playback_speed: float = 1.0
    stop_event: threading.Event = field(default_factory=threading.Event)
    output_sink: Callable[[str], None] | None = None

    generation_behavior: Callable[["FakeSession"], object] | None = None
    behavior: Callable[["FakeSession"], object] | None = None
    calls: list[bool] = field(default_factory=list)
    """The `use_runtime` flag of every call, in order."""
    started: threading.Event = field(default_factory=threading.Event)
    """Set each time a call has published its model."""

    def generate_construct(
        self, use_runtime: bool, on_reload_callback: OnReloadCallback | None
    ) -> MjState:
        self.calls.append(use_runtime)
        state = make_state()
        if on_reload_callback is not None:
            on_reload_callback(state)
        self.started.set()
        if self.generation_behavior is not None:
            self.generation_behavior(self)
        if use_runtime and self.runtime and self.behavior is not None:
            self.behavior(self)
        return state


@dataclass
class FakeBackend:
    """Satisfies `ViewerBackend` and records what it was asked to show."""

    info: ConnectionInfo | None = None
    reloads: list[MjState] = field(default_factory=list)
    started: bool = False
    closed: bool = False

    def start(self, state: MjState) -> None:
        self.started = True
        self.reloads.append(state)

    def close(self) -> None:
        self.closed = True

    def is_running(self) -> bool:
        return not self.closed

    def on_reload(self, state: MjState) -> None:
        self.reloads.append(state)

    def sync_hook(
        self, state: MjState, arrows: list[ArrowConfig], lines: list[LineConfig]
    ) -> None:
        pass

    @property
    def viewer_lock(self) -> Callable[[], AbstractContextManager[Any]] | None:
        return None

    def pump(self) -> None:
        pass

    def connection_info(self) -> ConnectionInfo | None:
        return self.info


@dataclass
class EventLog:
    """Thread safe sink that remembers every controller event and lets a test wait for one."""

    events: list[ControllerEvent] = field(default_factory=list)
    _condition: threading.Condition = field(
        default_factory=threading.Condition, init=False, repr=False
    )

    def __call__(self, event: ControllerEvent) -> None:
        with self._condition:
            self.events.append(event)
            self._condition.notify_all()

    def wait_for(
        self,
        predicate: Callable[[list[ControllerEvent]], bool],
        timeout: float = 5.0,
    ) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: predicate(self.events), timeout=timeout
            )

    def messages(self) -> list[str]:
        with self._condition:
            return [e.message for e in self.events if isinstance(e, LogEvent)]


def wait_idle(controller: ReloadedController, timeout: float = 5.0) -> None:
    """Blocks until the controller has no job running, failing if it takes longer than `timeout`."""
    deadline = time.monotonic() + timeout
    while controller.status().state is not RunState.IDLE:
        if time.monotonic() > deadline:
            raise TimeoutError("controller did not return to idle")
        time.sleep(0.01)
