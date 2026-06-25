from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

import numpy as np

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.settings import MujocoMojoSettings, VisualizationSettings
from mujoco_mojo.typing import Vec3, Vec4
from mujoco_mojo.utils.color import Color
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.visualization import LineConfig, Traceable

if TYPE_CHECKING:
    from mujoco_mojo.runtime.runtime_manager import RuntimeManager

logger = get_logger(__name__)

__all__ = ["Tracer"]


@dataclass
class Tracer:
    """
    Draws a fading trail of recent world positions behind a `Traceable` object (a `Body`, `Site`, or `Geom`).

    Typical usage inside a runtime function, within a `with runtime_manager as rm:` block::

        Tracer(target=box1, duration=2.0).register_to_rm()

    Sampled once per `RuntimeManager.step()` and drawn by any `VideoRecorder` with `show_traces=True`.
    """

    target: Traceable
    """The object whose world position is followed over time."""

    duration: float = 1.0
    """How many seconds of trailing history to keep."""

    color: Vec4 | None = None
    """RGBA color of the trail. Defaults to the user's `visualization.trace_line` setting."""

    width: float = 0.005
    """Width of the trail line."""

    fade: bool = True
    """If True, older segments are drawn more transparent than newer ones."""

    record_decimation: int = 1
    """How many steps between each recorded point. Increase for long, fine-timestep simulations to reduce the number of trail segments."""

    _history: deque[tuple[float, Vec3]] = field(default_factory=deque, init=False)
    _step_count: int = field(default=0, init=False)
    _vis: VisualizationSettings = field(
        default_factory=VisualizationSettings, init=False
    )
    _vis_loaded: bool = field(default=False, init=False)

    def register_to_rm(self, runtime_manager: RuntimeManager | None = None) -> Self:
        from mujoco_mojo.runtime.runtime_manager import RuntimeManager

        (runtime_manager or RuntimeManager.current()).add_tracer(self)
        return self

    def update(self, state: MjState) -> None:
        """Records the target's current position, then drops points older than `duration`. Call once per step."""
        self._step_count += 1
        if self._step_count % self.record_decimation != 0:
            return

        self._history.append((state.data.time, np.array(self.target.rt_pos(state))))

        cutoff = state.data.time - self.duration
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()

    def get_visuals(self, state: MjState) -> list[LineConfig]:
        """Returns one `LineConfig` per consecutive pair of recorded positions."""
        if not self._vis_loaded:
            self._vis = MujocoMojoSettings().visualization
            self._vis_loaded = True

        color = self.color
        if color is None:
            if not self._vis.trace_line:
                return []
            color = Color[self._vis.trace_line].rgba

        points = list(self._history)
        n = len(points)
        if n < 2:
            return []

        lines = []
        for i in range(n - 1):
            _, p1 = points[i]
            _, p2 = points[i + 1]

            segment_color = color
            if self.fade:
                segment_color = np.array(color, dtype=float)
                segment_color[3] *= (i + 1) / (n - 1)

            lines.append(
                LineConfig(pos1=p1, pos2=p2, color=segment_color, width=self.width)
            )

        return lines
