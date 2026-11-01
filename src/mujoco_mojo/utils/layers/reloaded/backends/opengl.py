from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.visualization import ArrowConfig, LineConfig

from .base import ConnectionInfo

if TYPE_CHECKING:
    import mujoco.viewer

__all__ = ["OpenGLBackend"]


@dataclass(eq=False)
class OpenGLBackend:
    """
    The classic MuJoCo viewer (`mujoco.viewer.launch_passive`): a native window drawn with OpenGL.

    It needs a display, so over SSH it needs X11 forwarding. The viewer reads the model and data from its own thread, which is why the `RuntimeManager` holds `viewer_lock` while it steps physics.
    """

    xml_path: Callable[[], Path]
    """Gives the file the current model was written to, which the viewer shows in its title and reloads from."""
    _viewer: mujoco.viewer.Handle | None = field(default=None, init=False, repr=False)

    def start(self, state: MjState) -> None:
        import mujoco.viewer

        self._viewer = mujoco.viewer.launch_passive(state.model, state.data)
        self.on_reload(state)

    def close(self) -> None:
        if self._viewer is not None:
            self._viewer.close()
            self._viewer = None

    def is_running(self) -> bool:
        return self._viewer is not None and self._viewer.is_running()

    def on_reload(self, state: MjState) -> None:
        viewer = self._viewer
        assert viewer is not None
        sim = viewer._get_sim()
        if sim:
            if viewer.user_scn and state.data.time == 0.0:
                # ensure the custom visual layer is wiped on every model reload
                with viewer.lock():
                    viewer.user_scn.ngeom = 0
            sim.load(state.model, state.data, str(self.xml_path()))
            viewer.sync()

    def sync_hook(
        self, state: MjState, arrows: list[ArrowConfig], lines: list[LineConfig]
    ) -> None:
        viewer = self._viewer
        assert viewer is not None
        assert viewer.user_scn
        # the viewer's GUI thread reads user_scn while rendering, so edits
        # must happen under the viewer lock. viewer.sync() locks internally,
        # so it stays outside to avoid nesting
        with viewer.lock():
            viewer.user_scn.ngeom = 0

            for arrow in arrows:
                arrow.draw_in_scene(mj_model=state.model, scene=viewer.user_scn)

            for line in lines:
                line.draw_in_scene(scene=viewer.user_scn)

        viewer.sync()

    @property
    def viewer_lock(self) -> Callable[[], AbstractContextManager[Any]] | None:
        # the viewer's GUI thread reads model/data under this lock (e.g. the
        # sensor/profiler panels), so physics stepping must hold it too
        return None if self._viewer is None else self._viewer.lock

    def pump(self) -> None:
        # the viewer runs its own thread, so there is nothing to keep alive
        pass

    def connection_info(self) -> ConnectionInfo | None:
        return None
