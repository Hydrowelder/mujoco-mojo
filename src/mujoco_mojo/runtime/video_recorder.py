from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, NotRequired, Self, TypedDict

import mujoco
import numpy as np

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.typing import CameraName, Vec3, Vec4
from mujoco_mojo.utils.color import Color
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.visualization import ArrowConfig, LineConfig

if TYPE_CHECKING:
    import subprocess

    from mujoco_mojo.runtime.runtime_manager import RuntimeManager

logger = get_logger(__name__)

__all__ = ["LabelConfig", "VideoRecorder"]


STREAMED_VIDEO_FORMAT = {".mp4", ".webm"}
"""Formats encoded incrementally by piping frames to ffmpeg as they're captured, instead of buffering them in memory."""

_X264_PRESETS = (
    "veryslow",
    "slower",
    "slow",
    "medium",
    "fast",
    "faster",
    "veryfast",
    "superfast",
    "ultrafast",
)
"""x264 `-preset` names indexed by `VideoRecorder.encode_speed` (0=slowest/best, 8=fastest/worst), mirroring libvpx-vp9's `-cpu-used` scale so `.mp4`/`.webm` share one knob."""


class LabelConfig(TypedDict):
    """Describes one frame label, returned fresh per-frame by `VideoRecorder.frame_label`."""

    text: str
    """The label text to burn into the frame."""

    position: NotRequired[tuple[int, int]]
    """Top-left pixel coordinate to draw at. Defaults to `(10, 10)`."""

    color: NotRequired[Vec3 | Vec4]
    """Text color, normalized `[0, 1]` RGB(A) (e.g. `Color.WHITE.rgba`). Defaults to opaque white."""

    background_color: NotRequired[Vec3 | Vec4 | None]
    """Optional fill behind the text, normalized `[0, 1]` RGB(A). An RGBA alpha `< 1` is true-blended with the frame beneath it. Defaults to no background."""

    border_color: NotRequired[Vec3 | Vec4 | None]
    """Optional 1px outline around the padded label box, normalized `[0, 1]` RGB(A). Defaults to no border."""

    font_size: NotRequired[int]
    """Font size in pixels. Defaults to `14`."""

    font_path: NotRequired[str | Path | None]
    """Path to a TrueType/OpenType font file, for custom styles/weights. Defaults to PIL's built-in font."""

    padding: NotRequired[int]
    """Padding in pixels around the text when drawing `background_color`. Defaults to `4`."""


def _color_to_rgb255_alpha(color: Vec3 | Vec4) -> tuple[tuple[int, int, int], float]:
    """Splits a normalized `[0, 1]` RGB(A) color into a `0-255` RGB tuple (for PIL) and a separate `[0, 1]` alpha (for manual blending). RGB-only input is treated as fully opaque."""
    arr = np.asarray(color, dtype=float)
    alpha = float(arr[3]) if arr.shape[0] == 4 else 1.0
    r, g, b = (round(c * 255) for c in arr[:3])
    return (r, g, b), alpha


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

    - `.mp4`: H.264 via ffmpeg; widest browser and player compatibility.
    - `.webm`: VP9 via ffmpeg; smaller files, fully seekable in the Dojo viewer. Requires ffmpeg with libvpx-vp9 support.
    - `.gif`: via PIL; no audio, loops automatically; large file size, not seekable.

    `.mp4` and `.webm` frames are piped to ffmpeg as they're captured rather than buffered in memory, so recording length isn't limited by available RAM. `.gif` (and any other extension, which falls back to mediapy) still buffers every frame until `save` is called. `quality` and `encode_speed` tune the ffmpeg encoder for `.mp4`/`.webm`; both have no effect on `.gif`.

    Visual overlays (contact forces, net forces, custom arrows/lines) are controlled by the `show_*` flags and the `show_loads` flag passed to `capture_frame`.

    `playback_speed` scales the frame rate of the saved video relative to `fps`: 0.5 plays back in slow motion, 1 is real time, and 2 plays back at double speed. It does not change how many frames are captured per second of simulation time, only how quickly they are played back.

    `recording_trigger` is a function of the current `MjState` that gates whether a due frame is actually captured, e.g. `lambda state: 5.0 <= state.data.time <= 10.0` to only record a window of the simulation.

    `frame_label`, if set, is called with the current `MjState` and the returned `LabelConfig` is burned into the frame - text, position, color, an optional (alpha-blended) background, and font are all configurable per-frame.

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

    fps: float = 30
    """Target frame rate of the output video. Frames are sampled every `1/fps` seconds of simulation time."""

    playback_speed: float = 1.0
    """Target for playback speed. If using 0.5 the video will record in "slow motion", 2 will record as occurring twice as fast."""

    width: int = 640
    """Render width in pixels."""

    height: int = 480
    """Render height in pixels."""

    recording_trigger: Callable[[MjState], bool] = lambda state: True
    """Function evaluated against the current `MjState` on every step. Frames are only captured while it returns `True`."""

    frame_label: Callable[[MjState], LabelConfig] | None = None
    """Optional function returning a `LabelConfig` to burn into each captured frame, e.g. `lambda state: {"text": f"t={state.data.time:.2f}s"}`."""

    max_frames: int | None = None
    """Optional cap on the number of frames captured. Once reached, further `capture_frame` calls are ignored. For `.gif` and other buffered formats this also bounds memory use; `.mp4`/`.webm` are streamed to disk as they're captured, so it only bounds recording length for those."""

    quality: int | None = None
    """Override for ffmpeg's `-crf` (constant rate factor) on `.mp4`/`.webm`: lower means higher quality and a larger file. Defaults to a codec-specific value (`23` for `.mp4`/libx264, `33` for `.webm`/libvpx-vp9) when unset. Useful range is roughly `18`-`32`; has no effect on `.gif`."""

    encode_speed: int | None = None
    """Override for the `.mp4`/`.webm` encoder's speed-vs-compression trade-off, on a `0`-`8` scale where `0` is slowest/best compression and `8` is fastest/worst (passed straight through as `-cpu-used` for `.webm`; mapped to an x264 `-preset` name for `.mp4`). Defaults to a codec-specific value (`4` for `.mp4`, `2` for `.webm`) when unset. Has no effect on `.gif`."""

    _frames: list = field(default_factory=list)
    """Buffered frames awaiting encoding. Only populated for formats outside `STREAMED_VIDEO_FORMAT` (e.g. `.gif`), since those formats can't be written incrementally."""
    _renderer: mujoco.Renderer = field(init=False)
    _vopt: mujoco.MjvOption = field(default_factory=mujoco.MjvOption, init=False)
    _next_record_time: float = field(default=0.0, init=False)
    _max_frames_warned: bool = field(default=False, init=False)
    _frame_count: int = field(default=0, init=False)
    _encoder_proc: subprocess.Popen | None = field(default=None, init=False)
    _encode_size: tuple[int, int] = field(default=(0, 0), init=False)
    """Even-rounded `(width, height)` fed to ffmpeg; set once the encoder opens."""

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

        if self.encode_speed is not None and not (0 <= self.encode_speed <= 8):
            msg = f"encode_speed must be between 0 and 8 (got {self.encode_speed})."
            logger.error(msg)
            raise ValueError(msg)

        if self.quality is not None and self.quality < 0:
            msg = f"quality must be non-negative (got {self.quality})."
            logger.error(msg)
            raise ValueError(msg)

        if self.path.suffix.lower() in STREAMED_VIDEO_FORMAT and not shutil.which(
            "ffmpeg"
        ):
            msg = (
                "ffmpeg was not found on PATH. Install ffmpeg to record "
                f"{self.path.name}, or use a .gif path instead."
            )
            logger.error(msg)
            raise RuntimeError(msg)

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
        try:
            self._renderer.update_scene(
                data=state.data,
                camera=self.camera_name,
                scene_option=self._vopt,
            )
        except AttributeError as e:
            msg = f"Failed to record frame due to an attribute error. This is likely because this video recorder was not prepared for simulation. Try using the '.setup(state)' method before simulating: {e}"
            logger.error(msg)
            raise AttributeError(msg)

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

    def _draw_label(self, frame: np.ndarray, label: LabelConfig) -> np.ndarray:
        """Burns `label`'s text into `frame`, with an optional alpha-blended background rectangle behind it."""
        text = label.get("text", "")
        if not text:
            return frame

        from PIL import Image, ImageDraw, ImageFont

        position = label.get("position", (10, 10))
        font_path = label.get("font_path")
        font_size = label.get("font_size", 14)
        font = (
            ImageFont.truetype(str(font_path), font_size)
            if font_path is not None
            else ImageFont.load_default(size=font_size)
        )

        # measure on a throwaway image before touching the real frame, so the
        # background rectangle's extent is known up front
        bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox(
            position, text, font=font
        )

        background_color = label.get("background_color")
        border_color = label.get("border_color")
        box = None
        if background_color is not None or border_color is not None:
            padding = label.get("padding", 4)
            box = (
                max(bbox[0] - padding, 0),
                max(bbox[1] - padding, 0),
                min(bbox[2] + padding, frame.shape[1]),
                min(bbox[3] + padding, frame.shape[0]),
            )

        if background_color is not None:
            assert box is not None
            x0, y0, x1, y1 = box
            frame = frame.copy()
            rgb255, alpha = _color_to_rgb255_alpha(background_color)
            if alpha >= 1.0:
                frame[y0:y1, x0:x1] = rgb255
            else:
                region = frame[y0:y1, x0:x1].astype(np.float32)
                blended = (
                    region * (1 - alpha) + np.array(rgb255, dtype=np.float32) * alpha
                )
                frame[y0:y1, x0:x1] = blended.astype(np.uint8)

        text_rgb255, _ = _color_to_rgb255_alpha(label.get("color", Color.WHITE.rgba))
        image = Image.fromarray(frame)
        draw = ImageDraw.Draw(image)
        if border_color is not None:
            assert box is not None
            x0, y0, x1, y1 = box
            border_rgb255, _ = _color_to_rgb255_alpha(border_color)
            draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=border_rgb255, width=1)
        draw.text(position, text, font=font, fill=text_rgb255)
        return np.asarray(image)

    def is_due(self, state: MjState) -> bool:
        """Returns whether `capture_frame` would actually capture a frame for `state` right now, without any side effects. Lets callers skip expensive work (e.g. building `custom_traces`) that would otherwise go unused on the steps between frames."""
        if state.data.time < self._next_record_time:
            return False
        if not self.recording_trigger(state):
            return False
        if self.max_frames is not None and self._frame_count >= self.max_frames:
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

        if self.max_frames is not None and self._frame_count >= self.max_frames:
            if not self._max_frames_warned:
                logger.warning(
                    f"VideoRecorder for {self.path} reached max_frames={self.max_frames}; "
                    "no further frames will be captured."
                )
                self._max_frames_warned = True
            return

        frame = self._render_frame(state, custom_arrows, custom_lines, custom_traces)

        if self.path.suffix.lower() in STREAMED_VIDEO_FORMAT:
            if self._encoder_proc is None:
                self._open_encoder()
            w, h = self._encode_size
            assert (
                self._encoder_proc is not None and self._encoder_proc.stdin is not None
            )
            self._encoder_proc.stdin.write(frame[:h, :w].tobytes())
        else:
            self._frames.append(frame)

        # increment the clock for the next frame
        self._frame_count += 1
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
        Finishes writing the video file.

        Supported formats:
        - `.mp4`: H.264 via ffmpeg; universally compatible.
        - `.webm`: VP9 via ffmpeg; smaller files and fully seekable.
        - `.gif`: via PIL; no audio, loops automatically, large file size, not seekable.

        `.mp4` and `.webm` are encoded incrementally: each frame is piped to ffmpeg as it's captured, so `save` only needs to close that pipe and wait for ffmpeg to finish. `.gif` (and any other format) buffers every frame in memory and is only encoded here.

        The output format is determined by the extension of `path`.
        """
        if self._frame_count == 0:
            return

        if self._encoder_proc is not None:
            self._finish_encoding()
        elif self.path.suffix.lower() == ".gif":
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
        else:
            import mediapy as media

            media.write_video(path=self.path, images=self._frames, fps=self._output_fps)
        logger.info(f"Video saved to {self.path}")

    def _open_encoder(self) -> None:
        """Spawns the ffmpeg subprocess that frames are piped to as they're captured. Called once, from `capture_frame`, on the first frame, so a recorder that's set up but never used never spawns a process."""
        import subprocess

        w = self.width - (self.width % 2)  # yuv420p requires even dimensions
        h = self.height - (self.height % 2)
        self._encode_size = (w, h)

        if self.path.suffix.lower() == ".mp4":
            crf = self.quality if self.quality is not None else 23
            speed = self.encode_speed if self.encode_speed is not None else 4
            codec_args = [
                "-c:v",
                "libx264",
                "-preset",
                _X264_PRESETS[speed],
                "-crf",
                str(crf),
                "-movflags",
                "+faststart",
            ]
        else:
            crf = self.quality if self.quality is not None else 33
            speed = self.encode_speed if self.encode_speed is not None else 2
            codec_args = [
                "-c:v",
                "libvpx-vp9",
                "-b:v",
                "0",
                "-crf",
                str(crf),
                "-cpu-used",
                str(speed),  # 0=slowest/best ... 8=fastest/worst
                "-row-mt",
                "1",  # row-based multithreading
                "-threads",
                "0",  # use all available cores
            ]

        try:
            self._encoder_proc = subprocess.Popen(
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
                    *codec_args,
                    "-an",
                    "-pix_fmt",
                    "yuv420p",
                    str(self.path),
                ],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as e:
            msg = (
                "ffmpeg was not found on PATH. Install ffmpeg to record "
                f"{self.path.name}, or use a .gif path instead."
            )
            logger.error(msg)
            raise RuntimeError(msg) from e

    def _finish_encoding(self) -> None:
        """Closes the ffmpeg stdin pipe opened by `_open_encoder` and waits for it to finish writing `self.path`."""
        assert self._encoder_proc is not None
        proc = self._encoder_proc
        try:
            assert proc.stdin is not None
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError(
                    f"ffmpeg exited with a non-zero status while encoding {self.path}"
                )
        except Exception:
            proc.kill()
            raise

    def close(self) -> None:
        """Releases the GL context held by the underlying MuJoCo renderer, and kills the ffmpeg encoder if `save` was never called. Call once recording is finished and `save` has been called."""
        if self._encoder_proc is not None and self._encoder_proc.poll() is None:
            proc = self._encoder_proc
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
            except BrokenPipeError:
                pass
            proc.kill()
            proc.wait()
        self._renderer.close()

    def register_to_rm(self, runtime_manager: RuntimeManager | None = None) -> Self:
        from mujoco_mojo.runtime.runtime_manager import RuntimeManager

        (runtime_manager or RuntimeManager.current()).add_video_recorder(self)
        return self
