from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.visualization import ArrowConfig, LineConfig

__all__ = ["ConnectionInfo", "ViewerBackend"]


@dataclass(frozen=True)
class ConnectionInfo:
    """How to reach a browser based viewer, shown in the Reloaded terminal UI."""

    url: str
    """Address to open in a browser on the machine running Reloaded."""

    tunnel_command: str | None = None
    """Command to run on a local machine to forward the viewer's port, when Reloaded is on a remote host."""

    warning: str | None = None
    """Standing caution about the viewer, e.g. that it listens on every network interface without authentication."""


class ViewerBackend(Protocol):
    """
    What Reloaded needs from a viewer.

    A backend only shows state. It never owns the command loop, so the terminal UI and the unit tests can drive every backend the same way.
    """

    def start(self, state: MjState) -> None:
        """Opens the viewer on the initial model."""
        ...

    def close(self) -> None:
        """Shuts the viewer down and releases its resources."""
        ...

    def is_running(self) -> bool:
        """Whether the viewer is still alive, e.g. its window has not been closed."""
        ...

    def on_reload(self, state: MjState) -> None:
        """Shows a new or refreshed model. Called once the model is generated and again after a run finishes."""
        ...

    def sync_hook(
        self, state: MjState, arrows: list[ArrowConfig], lines: list[LineConfig]
    ) -> None:
        """Pushes the current physics state and overlays to the viewer. Called by the `RuntimeManager` after every step."""
        ...

    @property
    def viewer_lock(self) -> Callable[[], AbstractContextManager[Any]] | None:
        """Lock the `RuntimeManager` holds while mutating model and data, or `None` if the viewer works on its own copy."""
        ...

    def pump(self) -> None:
        """Keeps the viewer responsive while no run is stepping physics, i.e. while idle or paused."""
        ...

    def connection_info(self) -> ConnectionInfo | None:
        """How to reach the viewer from a browser, or `None` for a native window."""
        ...
