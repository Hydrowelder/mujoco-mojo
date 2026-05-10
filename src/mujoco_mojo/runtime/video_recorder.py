from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Self

import mujoco

from mujoco_mojo.typing import CameraName
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.visualization import ArrowConfig, LineConfig

if TYPE_CHECKING:
    from mujoco_mojo.runtime.runtime_manager import RuntimeManager

logger = get_logger(__name__)


@dataclass
class VideoRecorder:
    path: Path
    camera_name: CameraName
    show_loads: bool = False
    show_net_force: bool = False
    show_contacts: bool = False
    show_proximities: bool = False
    fps: int = 30
    width: int = 640
    height: int = 480

    _frames: list = field(default_factory=list)
    _renderer: mujoco.Renderer = field(init=False)
    _vopt: mujoco.MjvOption = field(default_factory=mujoco.MjvOption, init=False)
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

        # initialize the vopt with defaults
        mujoco.mjv_defaultOption(self._vopt)

        # whether or not to show debug graphics
        self._vopt.flags[mujoco.mjtVisFlag.mjVIS_PERTFORCE] = int(self.show_net_force)
        self._vopt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTFORCE] = int(self.show_contacts)
        return self

    def capture_frame(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        custom_arrows: list[ArrowConfig],
        custom_lines: list[LineConfig],
    ):
        """Captures the current state as a video frame."""
        if mj_data.time < self._next_record_time:
            return

        # update standard mujoco objects in scene
        self._renderer.update_scene(
            data=mj_data,
            camera=self.camera_name,
            scene_option=self._vopt,
        )

        if custom_arrows and self.show_loads:
            for arrow in custom_arrows:
                arrow.draw_in_scene(mj_model, self._renderer.scene)

        if custom_lines and self.show_proximities:
            for line in custom_lines:
                line.draw_in_scene(self._renderer.scene)

        # capture and increment the clock for the next frame
        self._frames.append(self._renderer.render())
        self._next_record_time += 1 / self.fps

    def save(self):
        """Writes the captured frames to a video file."""
        if not self._frames:
            return
        import mediapy as media

        if self.path.suffix.lower() == ".gif":
            from PIL import Image

            # convert arrays to PIL images
            pil_images = [Image.fromarray(frame) for frame in self._frames]

            # save gif
            pil_images[0].save(
                self.path,
                save_all=True,
                append_images=pil_images[1:],
                duration=int(1000 / self.fps),  # ms per frame
                loop=0,  # loop forever
            )
        else:
            media.write_video(path=self.path, images=self._frames, fps=self.fps)
        logger.info(f"Video saved to {self.path}")

    def register_to_rm(self, runtime_manager: "RuntimeManager") -> Self:
        runtime_manager.add_video_recorder(self)
        return self
