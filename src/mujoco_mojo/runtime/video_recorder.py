from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Self

import mujoco

from mujoco_mojo.typing import CameraName
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from mujoco_mojo.runtime.runtime_manager import RuntimeManager

logger = get_logger(__name__)


@dataclass
class VideoRecorder:
    path: Path
    camera_name: CameraName
    fps: int = 30
    width: int = 640
    height: int = 480

    _frames: list = field(default_factory=list)
    _renderer: mujoco.Renderer = field(init=False)
    _next_record_time: float = field(default=0.0, init=False)

    def setup(self, mj_model: mujoco.MjModel) -> Self:
        # Ensure directory exists and connect
        try:
            self._renderer = mujoco.Renderer(
                model=mj_model, height=self.height, width=self.width
            )
        except Exception as e:
            msg = "Failed to initialize the MuJoCo Renderer. If on a server, try setting 'export MUJOCO_GL=egl' in your terminal."
            logger.error(msg)
            raise RuntimeError(msg) from e
        return self

    def capture_frame(self, mj_data):
        """Captures the current state as a video frame."""
        if mj_data.time >= self._next_record_time:
            self._renderer.update_scene(data=mj_data, camera=self.camera_name)
            self._frames.append(self._renderer.render())

            # increment the clock for the next frame
            self._next_record_time += 1 / self.fps

    def save(self):
        """Writes the captured frames to a video file."""
        if not self._frames:
            return
        import mediapy as media

        media.write_video(path=self.path, images=self._frames, fps=self.fps)
        logger.info(f"Video saved to {self.path}")

    def register_to_rm(self, runtime_manager: "RuntimeManager") -> Self:
        runtime_manager.add_video_recorder(self)
        return self
