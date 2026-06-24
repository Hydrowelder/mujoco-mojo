from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Self

import mujoco
import numpy as np

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

    Typical usage inside a runtime function, within a `with runtime_manager as rm:` block::

        recorder = VideoRecorder(
            path=model.trial_dir / "camera.mp4",
            camera_name="top_view",
            fps=30,
            width=1280,
            height=720,
        ).setup(mj_model).register_to_rm()

    `register_to_rm` wires the recorder into the `RuntimeManager` so that `capture_frame` is called automatically on every physics step and `save` is called when the simulation finishes. If no `runtime_manager` is passed, it registers to the `RuntimeManager` of the active `with` block.

    Supported output formats (determined by the `path` extension):

    - `.mp4`: H.264 via mediapy/ffmpeg; widest browser and player compatibility.
    - `.webm`: VP9 via ffmpeg; smaller files, fully seekable in the Dojo viewer. Requires ffmpeg with libvpx-vp9 support.
    - `.gif`: via PIL; no audio, loops automatically; large file size, not seekable.

    Visual overlays (contact forces, net forces, custom arrows/lines) are controlled by the `show_*` flags and the `show_loads` flag passed to `capture_frame`.

    `playback_speed` scales the frame rate of the saved video relative to `fps`: 0.5 plays back in slow motion, 1 is real time, and 2 plays back at double speed. It does not change how many frames are captured per second of simulation time, only how quickly they are played back.

    `recording_trigger` is a function of the current `MjState` that gates whether a due frame is actually captured, e.g. `lambda state: 5.0 <= state.data.time <= 10.0` to only record a window of the simulation.

    `frame_label`, if set, is called with the current `MjState` and the returned string is burned into the top-left corner of each captured frame.

    `max_frames` caps the number of frames held in memory; once reached, further `capture_frame` calls are silently ignored (with a one-time warning).

    Call `close` once `save` has finished to release the renderer's GL context.
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

    show_traces: bool = False
    """Whether to render `Tracer` trails (passed via `custom_traces` in `capture_frame`)."""

    fps: int = 30
    """Target frame rate of the output video. Frames are sampled every `1/fps` seconds of simulation time."""

    playback_speed: float = 1.0
    """Target for playback speed. If using 0.5 the video will record in "slow motion", 2 will record as occurring twice as fast."""

    width: int = 640
    """Render width in pixels."""

    height: int = 480
    """Render height in pixels."""

    recording_trigger: Callable[[MjState], bool] = lambda state: True
    """Function evaluated against the current `MjState` on every step. Frames are only captured while it returns `True`."""

    frame_label: Callable[[MjState], str] | None = None
    """Optional function returning a text label to burn into the top-left corner of each captured frame, e.g. `lambda state: f"t={state.data.time:.2f}s"`."""

    max_frames: int | None = None
    """Optional cap on the number of frames held in memory. Once reached, further `capture_frame` calls are ignored."""

    _frames: list = field(default_factory=list)
    _renderer: mujoco.Renderer = field(init=False)
    _vopt: mujoco.MjvOption = field(default_factory=mujoco.MjvOption, init=False)
    _next_record_time: float = field(default=0.0, init=False)
    _max_frames_warned: bool = field(default=False, init=False)

    @property
    def _output_fps(self) -> float:
        """Frame rate of the saved video, after applying `playback_speed` to `fps`."""
        return self.fps * self.playback_speed

    def _validate(self, state: MjState) -> None:
        """Checks settings against the model before allocating any GL resources, so failures are raised here rather than as a confusing error deep in the simulation loop."""
        offwidth = state.model.vis.global_.offwidth
        offheight = state.model.vis.global_.offheight
        if self.width > offwidth or self.height > offheight:
            msg = (
                f"Requested render size ({self.width}w x {self.height}h) exceeds the model's offscreen "
                f"buffer size ({offwidth}w x {offheight}h). Increase offwidth/offheight in the model's "
                f"`mojo.Visual(global_=mojo.VisualGlobal(offwidth={self.width}, offheight={self.height}))` element, or reduce the recorder's width/height."
            )
            logger.error(msg)
            raise ValueError(msg)

        if (
            mujoco.mj_name2id(
                state.model, mujoco.mjtObj.mjOBJ_CAMERA.value, self.camera_name
            )
            == -1
        ):
            msg = f'Camera "{self.camera_name}" does not exist in the model.'
            logger.error(msg)
            raise ValueError(msg)

    def setup(self, state: MjState) -> Self:
        """Initializes the MuJoCo renderer for this model. Must be called before the simulation loop."""
        self._validate(state)

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

    def _render_frame(
        self,
        state: MjState,
        custom_arrows: list[ArrowConfig],
        custom_lines: list[LineConfig],
        custom_traces: list[LineConfig],
    ):
        """Updates the scene for the current state and renders it to an image array."""
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

        if custom_traces and self.show_traces:
            for line in custom_traces:
                line.draw_in_scene(self._renderer.scene)

        frame = self._renderer.render()

        if self.frame_label is not None:
            frame = self._draw_label(frame, self.frame_label(state))

        return frame

    def _draw_label(self, frame: np.ndarray, label: str) -> np.ndarray:
        """Burns `label` into the top-left corner of `frame`."""
        from PIL import Image, ImageDraw

        image = Image.fromarray(frame)
        ImageDraw.Draw(image).text((10, 10), label, fill=(255, 255, 255))
        return np.asarray(image)

    def is_due(self, state: MjState) -> bool:
        """Returns whether `capture_frame` would actually capture a frame for `state` right now, without any side effects. Lets callers skip expensive work (e.g. building `custom_traces`) that would otherwise go unused on the steps between frames."""
        if state.data.time < self._next_record_time:
            return False
        if not self.recording_trigger(state):
            return False
        if self.max_frames is not None and len(self._frames) >= self.max_frames:
            return False
        return True

    def capture_frame(
        self,
        state: MjState,
        custom_arrows: list[ArrowConfig],
        custom_lines: list[LineConfig],
        custom_traces: list[LineConfig],
    ):
        """Captures the current state as a video frame."""
        if state.data.time < self._next_record_time:
            return

        if not self.recording_trigger(state):
            return

        if self.max_frames is not None and len(self._frames) >= self.max_frames:
            if not self._max_frames_warned:
                logger.warning(
                    f"VideoRecorder for {self.path} reached max_frames={self.max_frames}; "
                    "no further frames will be captured."
                )
                self._max_frames_warned = True
            return

        # capture and increment the clock for the next frame
        self._frames.append(
            self._render_frame(state, custom_arrows, custom_lines, custom_traces)
        )
        self._next_record_time += 1 / self.fps

    def snapshot(
        self,
        state: MjState,
        path: Path,
        custom_arrows: list[ArrowConfig] | None = None,
        custom_lines: list[LineConfig] | None = None,
        custom_traces: list[LineConfig] | None = None,
    ):
        """Renders the current state and saves it as a single image to `path`, regardless of `recording_trigger` or `fps` timing."""
        from PIL import Image

        frame = self._render_frame(
            state, custom_arrows or [], custom_lines or [], custom_traces or []
        )
        Image.fromarray(frame).save(path)
        logger.info(f"Snapshot saved to {path}")

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
                duration=int(1000 / self._output_fps),  # ms per frame
                loop=0,  # loop forever
            )
        elif self.path.suffix.lower() == ".webm":
            self._save_webm()
        else:
            media.write_video(path=self.path, images=self._frames, fps=self._output_fps)
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
                str(self._output_fps),
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

    def close(self) -> None:
        """Releases the GL context held by the underlying MuJoCo renderer. Call once recording is finished and `save` has been called."""
        self._renderer.close()

    def register_to_rm(self, runtime_manager: RuntimeManager | None = None) -> Self:
        from mujoco_mojo.runtime.runtime_manager import RuntimeManager

        (runtime_manager or RuntimeManager.current()).add_video_recorder(self)
        return self
