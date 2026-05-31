from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Self

import mujoco

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.typing import CameraName
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.visualization import ArrowConfig, LineConfig

if TYPE_CHECKING:
    from mujoco_mojo.runtime.runtime_manager import RuntimeManager

logger = get_logger(__name__)


@dataclass
class VideoRecorder:
    """
    Records a MuJoCo simulation to a video file.

    Frames are captured at a fixed rate (`fps`) relative to simulation time, not wall-clock time, so the output plays back at the exact rate specified regardless of how fast the simulation runs. The recorder skips `capture_frame` calls that fall between the interval boundaries, which prevents duplicate frames when the physics step is finer than 1/fps.

    Typical usage inside a runtime function::

        recorder = VideoRecorder(
            path=model.trial_dir / "camera.mp4",
            camera_name="top_view",
            fps=30,
            width=1280,
            height=720,
        ).setup(mj_model).register_to_rm(runtime_manager)

    `register_to_rm` wires the recorder into the `RuntimeManager` so that `capture_frame` is called automatically on every physics step and `save` is called when the simulation finishes.

    Supported output formats (determined by the `path` extension):

    - `.mp4`: H.264 via mediapy/ffmpeg; widest browser and player compatibility.
    - `.webm`: VP9 via ffmpeg; smaller files, fully seekable in the Dojo viewer. Requires ffmpeg with libvpx-vp9 support.
    - `.gif`: via PIL; no audio, loops automatically; large file size, not seekable.

    Visual overlays (contact forces, net forces, custom arrows/lines) are controlled by the `show_*` flags and the `show_loads` flag passed to `capture_frame`.
    """

    path: Path
    """Output file path. The extension determines the container and codec."""

    camera_name: CameraName
    """Name of the MuJoCo camera to render from (must exist in the model)."""

    show_loads: bool = False
    """Whether to render custom arrow overlays (passed via `custom_arrows` in `capture_frame`)."""

    show_net_force: bool = False
    """Whether to render net force visualizations (`mjVIS_PERTFORCE`)."""

    show_contacts: bool = False
    """Whether to render contact force visualizations (`mjVIS_CONTACTFORCE`)."""

    show_proximities: bool = False
    """Whether to render custom line overlays (passed via `custom_lines` in `capture_frame`)."""

    fps: int = 30
    """Target frame rate of the output video. Frames are sampled every `1/fps` seconds of simulation time."""

    width: int = 640
    """Render width in pixels."""

    height: int = 480
    """Render height in pixels."""

    _frames: list = field(default_factory=list)
    _renderer: mujoco.Renderer = field(init=False)
    _vopt: mujoco.MjvOption = field(default_factory=mujoco.MjvOption, init=False)
    _next_record_time: float = field(default=0.0, init=False)

    def setup(self, state: MjState) -> Self:
        """Initializes the MuJoCo renderer for this model. Must be called before the simulation loop."""
        try:
            self._renderer = mujoco.Renderer(
                model=state.model, height=self.height, width=self.width
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
        state: MjState,
        custom_arrows: list[ArrowConfig],
        custom_lines: list[LineConfig],
    ):
        """Captures the current state as a video frame."""
        if state.data.time < self._next_record_time:
            return

        # update standard mujoco objects in scene
        self._renderer.update_scene(
            data=state.data,
            camera=self.camera_name,
            scene_option=self._vopt,
        )

        if custom_arrows and self.show_loads:
            for arrow in custom_arrows:
                arrow.draw_in_scene(state.model, self._renderer.scene)

        if custom_lines and self.show_proximities:
            for line in custom_lines:
                line.draw_in_scene(self._renderer.scene)

        # capture and increment the clock for the next frame
        self._frames.append(self._renderer.render())
        self._next_record_time += 1 / self.fps

    def save(self):
        """
        Writes the captured frames to a video file.

        Supported formats:
        - `.mp4` — H.264 via mediapy/ffmpeg; universally compatible.
        - `.webm` — VP9 via mediapy/ffmpeg; smaller files and fully seekable.
        - `.gif` — via PIL; no audio, loops automatically, large file size, not seekable.

        The output format is determined by the extension of `path`.
        """
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
        elif self.path.suffix.lower() == ".webm":
            self._save_webm()
        else:
            media.write_video(path=self.path, images=self._frames, fps=self.fps)
        logger.info(f"Video saved to {self.path}")

    def _save_webm(self) -> None:
        """Encodes frames to VP9 WebM by piping raw RGB directly to ffmpeg (no intermediate file)."""
        import subprocess

        h_raw, w_raw = self._frames[0].shape[:2]
        # yuv420p requires even dimensions
        w = w_raw - (w_raw % 2)
        h = h_raw - (h_raw % 2)

        proc = subprocess.Popen(
            [
                "ffmpeg",
                "-y",
                "-f",
                "rawvideo",
                "-vcodec",
                "rawvideo",
                "-s",
                f"{w}x{h}",
                "-pix_fmt",
                "rgb24",
                "-r",
                str(self.fps),
                "-i",
                "pipe:0",
                "-c:v",
                "libvpx-vp9",
                "-b:v",
                "0",
                "-crf",
                "33",
                "-cpu-used",
                "2",  # 0=slowest/best ... 8=fastest/worst; 4 is a good balance
                "-row-mt",
                "1",  # row-based multithreading
                "-threads",
                "0",  # use all available cores
                "-an",
                "-pix_fmt",
                "yuv420p",
                str(self.path),
            ],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        try:
            assert proc.stdin is not None
            for frame in self._frames:
                proc.stdin.write(frame[:h, :w].tobytes())
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError(
                    f"ffmpeg exited with a non-zero status while encoding {self.path}"
                )
        except Exception:
            proc.kill()
            raise

    def register_to_rm(self, runtime_manager: "RuntimeManager") -> Self:
        runtime_manager.add_video_recorder(self)
        return self
