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
    _segments: deque[LineConfig] = field(default_factory=deque, init=False)
    """One `LineConfig` per consecutive pair of points in `_history`, built once in `update()` and reused by every `get_visuals()` call until its older endpoint ages out."""
    _step_count: int = field(default=0, init=False)
    _vis: VisualizationSettings = field(
        default_factory=VisualizationSettings, init=False
    )
    _vis_loaded: bool = field(default=False, init=False)
    _resolved_color: Vec4 | None = field(default=None, init=False)
    _color_resolved: bool = field(default=False, init=False)

    def _resolve_color(self) -> Vec4 | None:
        """Resolves and caches the trail's RGBA color, since it can't change over a Tracer's lifetime."""
        if self._color_resolved:
            return self._resolved_color

        if not self._vis_loaded:
            self._vis = MujocoMojoSettings().visualization
            self._vis_loaded = True

        color = self.color
        if color is None and self._vis.trace_line:
            color = Color[self._vis.trace_line].rgba

        self._resolved_color = color
        self._color_resolved = True
        return color

    def register_to_rm(self, runtime_manager: RuntimeManager | None = None) -> Self:
        from mujoco_mojo.runtime.runtime_manager import RuntimeManager

        (runtime_manager or RuntimeManager.current()).add_tracer(self)
        return self

    def update(self, state: MjState) -> None:
        """Records the target's current position, then drops points older than `duration`. Call once per step."""
        self._step_count += 1
        if self._step_count % self.record_decimation != 0:
            return

        t = state.data.time
        pos = np.array(self.target.rt_pos(state))

        color = self._resolve_color()
        if color is not None and self._history:
            _, prev_pos = self._history[-1]
            self._segments.append(
                LineConfig(
                    pos1=prev_pos,
                    pos2=pos,
                    color=np.array(color, dtype=float),
                    width=self.width,
                )
            )
        self._history.append((t, pos))

        cutoff = t - self.duration
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()
            if self._segments:
                self._segments.popleft()

    def get_visuals(self, state: MjState) -> list[LineConfig]:
        """
        Returns the trail's cached `LineConfig` segments, one per consecutive pair of recorded positions.

        Segments are built once, in `update()`, as new points are recorded, and reused across every call here - only the fade alpha is refreshed in place, since a segment's position within the trailing window (and therefore its fade level) shifts every step even though its endpoints never change.
        """
        color = self._resolve_color()
        if color is None or not self._segments:
            return []

        if self.fade:
            base_alpha = color[3]
            n = len(self._segments)
            for i, segment in enumerate(self._segments):
                segment.color[3] = base_alpha * (i + 1) / n

        return list(self._segments)
