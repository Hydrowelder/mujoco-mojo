import shutil
from pathlib import Path

import mujoco
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.runtime.video_recorder import VideoRecorder
from mujoco_mojo.typing import CameraName
from mujoco_mojo.utils.color import Color
from mujoco_mojo.visualization import ArrowConfig, LineConfig

HAS_FFMPEG = shutil.which("ffmpeg") is not None
CAM1 = CameraName("cam1")


def _frames_visually_equal(a: np.ndarray, b: np.ndarray) -> bool:
    """
    True if two frames are equal modulo the ~1px anti-aliasing jitter that
    GPU-backed renderers (e.g. macOS's glfw/Metal backend) can introduce between
    otherwise-identical draws of the same scene. A real overlay (arrow/line/trace)
    changes far more than a handful of pixels by a few intensity levels, so this
    tolerance won't mask an actual gating bug.
    """
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return diff.max() <= 4 and int((diff.max(axis=-1) > 0).sum()) <= 4


@pytest.fixture
def cam_setup():
    """A minimal scene with a named camera, for VideoRecorder tests."""
    xml = """
    <mujoco>
        <worldbody>
            <body name="body1" pos="0 0 0">
                <geom name="geom1" type="sphere" size="0.1" rgba="1 0 0 1"/>
                <camera name="cam1" pos="0 -2 0" euler="90 0 0"/>
            </body>
        </worldbody>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


@pytest.fixture
def state(cam_setup):
    model, data = cam_setup
    return MjState(model, data)


@pytest.fixture
def recorder(tmp_path, state):
    # .gif buffers frames instead of streaming to ffmpeg, so these generic
    # logic tests don't need ffmpeg installed; the actual ffmpeg-streaming
    # path is covered separately by TestSaveEncodesRealVideo.
    rec = VideoRecorder(
        path=tmp_path / "out.gif",
        camera_name=CAM1,
        width=64,
        height=48,
        fps=10,
    ).setup(state)
    yield rec
    rec.close()


def _expected_bbox(
    text: str, position: tuple[int, int], font_size: int, padding: int, frame_shape
) -> tuple[int, int, int, int]:
    """Mirrors `VideoRecorder._draw_label`'s bbox math, so tests can sample a pixel that's inside the padded background rect but outside the tight text bbox (i.e. guaranteed to have no glyph ink)."""
    font = ImageFont.load_default(size=font_size)
    bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox(position, text, font=font)
    x0 = max(round(bbox[0]) - padding, 0)
    y0 = max(round(bbox[1]) - padding, 0)
    x1 = min(round(bbox[2]) + padding, frame_shape[1])
    y1 = min(round(bbox[3]) + padding, frame_shape[0])
    return x0, y0, x1, y1


class TestSetupValidation:
    def test_raises_on_unknown_camera(self, state):
        rec = VideoRecorder(
            path=Path("unused.mp4"),
            camera_name=CameraName("does_not_exist"),
            width=64,
            height=48,
        )
        with pytest.raises(ValueError, match="does not exist"):
            rec.setup(state)

    def test_raises_on_oversized_render(self, state):
        rec = VideoRecorder(
            path=Path("unused.mp4"), camera_name=CAM1, width=10_000, height=10_000
        )
        with pytest.raises(ValueError, match="exceeds"):
            rec.setup(state)

    def test_raises_on_out_of_range_encode_speed(self, state):
        rec = VideoRecorder(
            path=Path("unused.mp4"),
            camera_name=CAM1,
            width=64,
            height=48,
            encode_speed=9,
        )
        with pytest.raises(ValueError, match="encode_speed"):
            rec.setup(state)

    def test_raises_on_negative_quality(self, state):
        rec = VideoRecorder(
            path=Path("unused.mp4"), camera_name=CAM1, width=64, height=48, quality=-1
        )
        with pytest.raises(ValueError, match="quality"):
            rec.setup(state)

    def test_raises_when_ffmpeg_missing_for_streamed_format(self, state, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: None)
        rec = VideoRecorder(
            path=Path("unused.mp4"), camera_name=CAM1, width=64, height=48
        )
        with pytest.raises(RuntimeError, match="ffmpeg was not found"):
            rec.setup(state)

    def test_does_not_require_ffmpeg_for_gif(self, state, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: None)
        rec = VideoRecorder(
            path=tmp_path / "out.gif", camera_name=CAM1, width=64, height=48
        ).setup(state)
        rec.close()


class TestIsDueAndCaptureFrame:
    def test_is_due_true_immediately(self, recorder, state):
        assert recorder.is_due(state) is True

    def test_is_due_respects_fps_decimation(self, recorder, state):
        recorder.capture_frame(state, [], [], [])  # advances _next_record_time to 0.1
        state.data.time = 0.05
        assert recorder.is_due(state) is False

    def test_is_due_respects_recording_trigger(self, state, tmp_path):
        rec = VideoRecorder(
            path=tmp_path / "out.gif",
            camera_name=CAM1,
            width=64,
            height=48,
            recording_trigger=lambda s: False,
        ).setup(state)
        assert rec.is_due(state) is False
        rec.close()

    def test_is_due_respects_max_frames(self, recorder, state):
        recorder.max_frames = 1
        recorder.capture_frame(state, [], [], [])
        state.data.time = 10.0  # past the fps gate too, so only max_frames can block it
        assert recorder.is_due(state) is False

    def test_capture_frame_decimates_by_fps(self, recorder, state):
        for i in range(5):
            state.data.time = i * 0.01  # fps=10 -> only t=0 is due among these
            recorder.capture_frame(state, [], [], [])
        assert recorder._frame_count == 1

    def test_capture_frame_warns_once_at_max_frames(self, recorder, state, caplog):
        recorder.max_frames = 1
        recorder.capture_frame(state, [], [], [])
        with caplog.at_level("WARNING"):
            state.data.time = 1.0
            recorder.capture_frame(state, [], [], [])
            state.data.time = 2.0
            recorder.capture_frame(state, [], [], [])
        warnings = [r for r in caplog.records if "max_frames" in r.message]
        assert len(warnings) == 1
        assert recorder._frame_count == 1


class TestRenderFrameOverlayGating:
    """Each `show_*` flag should gate its matching `custom_*` overlay independently."""

    def test_arrows_only_drawn_when_show_loads(self, recorder, state):
        arrow = ArrowConfig(
            # MuJoCo scales arrow length by `force_map / meanmass`, so a unit
            # vector here would render at a sub-pixel fraction of a meter
            pos=np.zeros(3),
            vec=np.array([1000.0, 0.0, 0.0]),
            color=Color.AMBER_500.rgba,
            is_torque=False,
        )
        baseline = recorder._render_frame(state, [], [], [])
        disabled = recorder._render_frame(state, [arrow], [], [])
        assert _frames_visually_equal(baseline, disabled)

        recorder.show_loads = True
        enabled = recorder._render_frame(state, [arrow], [], [])
        assert not np.array_equal(baseline, enabled)

    def test_lines_only_drawn_when_show_proximities(self, recorder, state):
        line = LineConfig(
            pos1=np.array([-0.5, 0.0, 0.0]),
            pos2=np.array([0.5, 0.0, 0.0]),
            color=Color.WHITE.rgba,
            width=0.05,
        )
        baseline = recorder._render_frame(state, [], [], [])
        disabled = recorder._render_frame(state, [], [line], [])
        assert _frames_visually_equal(baseline, disabled)

        recorder.show_proximities = True
        enabled = recorder._render_frame(state, [], [line], [])
        assert not np.array_equal(baseline, enabled)

    def test_traces_only_drawn_when_show_traces(self, recorder, state):
        trace = LineConfig(
            pos1=np.array([-0.5, 0.0, 0.0]),
            pos2=np.array([0.5, 0.0, 0.0]),
            color=Color.VIOLET_500.rgba,
            width=0.05,
        )
        baseline = recorder._render_frame(state, [], [], [])
        disabled = recorder._render_frame(state, [], [], [trace])
        assert _frames_visually_equal(baseline, disabled)

        recorder.show_traces = True
        enabled = recorder._render_frame(state, [], [], [trace])
        assert not np.array_equal(baseline, enabled)


class TestDrawLabel:
    def test_empty_text_is_a_no_op(self, recorder):
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        result = recorder._draw_label(frame, {"text": ""})
        assert result is frame

    def test_draws_visible_text(self, recorder):
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        result = recorder._draw_label(
            frame,
            {
                "text": "A",
                "position": (5, 5),
                "color": Color.WHITE.rgba,
                "font_size": 16,
            },
        )
        assert not np.array_equal(result, frame)
        assert result.max() > 0

    def test_opaque_background_overwrites_exactly(self, recorder):
        frame = np.full((48, 64, 3), 100, dtype=np.uint8)
        position, font_size, padding = (10, 10), 14, 4
        result = recorder._draw_label(
            frame,
            {
                "text": "A",
                "position": position,
                "background_color": Color.BLUE_500.rgba,
                "font_size": font_size,
                "padding": padding,
            },
        )
        x0, y0, _, _ = _expected_bbox("A", position, font_size, padding, frame.shape)
        expected_rgb = tuple(round(c * 255) for c in Color.BLUE_500.rgba[:3])
        assert tuple(result[y0, x0]) == expected_rgb

    def test_translucent_background_blends_with_frame(self, recorder):
        frame = np.full((48, 64, 3), 100, dtype=np.uint8)
        position, font_size, padding, alpha = (10, 10), 14, 4, 0.5
        result = recorder._draw_label(
            frame,
            {
                "text": "A",
                "position": position,
                "background_color": Color.BLACK.with_alpha(alpha),
                "font_size": font_size,
                "padding": padding,
            },
        )
        x0, y0, _, _ = _expected_bbox("A", position, font_size, padding, frame.shape)
        expected = 100 * (1 - alpha) + 0 * alpha
        assert result[y0, x0, 0] == pytest.approx(expected, abs=1)

    def test_no_background_leaves_surroundings_untouched(self, recorder):
        frame = np.full((48, 64, 3), 100, dtype=np.uint8)
        result = recorder._draw_label(
            frame, {"text": "A", "position": (40, 40), "font_size": 12}
        )
        # a far corner, away from the text, should be untouched
        assert tuple(result[0, 0]) == (100, 100, 100)


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not available")
class TestSaveEncodesRealVideo:
    """Exercises the actual mediapy/ffmpeg/PIL encoding paths: the same code path that broke when numpy 2.5.0 shipped without mediapy support."""

    @pytest.mark.parametrize("suffix", [".mp4", ".webm", ".gif"])
    def test_save_writes_a_readable_video(self, tmp_path, state, suffix):
        rec = VideoRecorder(
            path=tmp_path / f"out{suffix}",
            camera_name=CAM1,
            width=64,
            height=48,
            fps=10,
            # burn the frame index into each frame so they're pixel-distinct --
            # the scene itself is static, and PIL's GIF encoder collapses
            # consecutive identical frames into a single frame
            frame_label=lambda s: {"text": f"t={s.data.time:.2f}"},
        ).setup(state)
        try:
            for i in range(3):
                state.data.time = i / rec.fps
                rec.capture_frame(state, [], [], [])
            rec.save()

            assert rec.path.exists()
            assert rec.path.stat().st_size > 0

            if suffix == ".gif":
                with Image.open(rec.path) as img:
                    assert getattr(img, "n_frames", 1) == 3
                # .gif has no incremental encoder, so frames stay buffered until save
                assert len(rec._frames) == 3
            else:
                import mediapy as media

                frames = media.read_video(str(rec.path))
                assert len(frames) == 3
                # .mp4/.webm are piped to ffmpeg as captured, never buffered
                assert len(rec._frames) == 0
        finally:
            rec.close()

    def test_save_is_a_no_op_with_no_frames(self, tmp_path, state):
        rec = VideoRecorder(
            path=tmp_path / "empty.mp4", camera_name=CAM1, width=64, height=48
        ).setup(state)
        rec.save()
        assert not rec.path.exists()
        rec.close()

    def test_close_kills_unfinished_encoder(self, tmp_path, state):
        """If `save` is never called, `close` must not leave a hung ffmpeg process behind."""
        rec = VideoRecorder(
            path=tmp_path / "out.mp4", camera_name=CAM1, width=64, height=48, fps=10
        ).setup(state)
        rec.capture_frame(state, [], [], [])
        proc = rec._encoder_proc
        assert proc is not None
        assert proc.poll() is None  # still running, waiting on stdin

        rec.close()
        assert proc.poll() is not None  # killed, not left hanging


class TestEncoderMissingFfmpeg:
    def test_missing_ffmpeg_raises_clear_error(self, tmp_path, state, monkeypatch):
        def raise_not_found(*args, **kwargs):
            raise FileNotFoundError("ffmpeg")

        # Pretend ffmpeg is on PATH so setup()'s eager check passes, letting
        # the FileNotFoundError surface from the Popen call in _open_encoder instead.
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ffmpeg")
        monkeypatch.setattr("subprocess.Popen", raise_not_found)

        rec = VideoRecorder(
            path=tmp_path / "out.mp4", camera_name=CAM1, width=64, height=48
        ).setup(state)
        try:
            with pytest.raises(RuntimeError, match="ffmpeg was not found"):
                rec.capture_frame(state, [], [], [])
        finally:
            rec.close()


class TestEncoderCodecArgs:
    """Verifies `quality`/`encode_speed` reach the ffmpeg command line, without spawning a real process."""

    @pytest.fixture
    def captured_argv(self, monkeypatch):
        calls = []

        class FakeStdin:
            def write(self, data):
                pass

        class FakeProc:
            stdin = FakeStdin()
            returncode = 0

            def poll(self):
                return 0

        def fake_popen(argv, **kwargs):
            calls.append(argv)
            return FakeProc()

        # Pretend ffmpeg is on PATH so setup()'s eager check passes regardless
        # of whether ffmpeg is actually installed in this environment.
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ffmpeg")
        monkeypatch.setattr("subprocess.Popen", fake_popen)
        return calls

    def test_mp4_uses_default_crf_and_preset(self, tmp_path, state, captured_argv):
        rec = VideoRecorder(
            path=tmp_path / "out.mp4", camera_name=CAM1, width=64, height=48
        ).setup(state)
        rec.capture_frame(state, [], [], [])
        rec.close()
        argv = captured_argv[0]
        assert "-crf" in argv and argv[argv.index("-crf") + 1] == "23"
        assert "-preset" in argv and argv[argv.index("-preset") + 1] == "fast"

    def test_mp4_quality_and_encode_speed_overrides(
        self, tmp_path, state, captured_argv
    ):
        rec = VideoRecorder(
            path=tmp_path / "out.mp4",
            camera_name=CAM1,
            width=64,
            height=48,
            quality=18,
            encode_speed=0,
        ).setup(state)
        rec.capture_frame(state, [], [], [])
        rec.close()
        argv = captured_argv[0]
        assert argv[argv.index("-crf") + 1] == "18"
        assert argv[argv.index("-preset") + 1] == "veryslow"

    def test_webm_quality_and_encode_speed_overrides(
        self, tmp_path, state, captured_argv
    ):
        rec = VideoRecorder(
            path=tmp_path / "out.webm",
            camera_name=CAM1,
            width=64,
            height=48,
            quality=15,
            encode_speed=8,
        ).setup(state)
        rec.capture_frame(state, [], [], [])
        rec.close()
        argv = captured_argv[0]
        assert argv[argv.index("-crf") + 1] == "15"
        assert argv[argv.index("-cpu-used") + 1] == "8"


class TestSnapshot:
    def test_snapshot_writes_a_single_image(self, recorder, state, tmp_path):
        snap_path = tmp_path / "snap.png"
        recorder.snapshot(state, snap_path)
        assert snap_path.exists()
        with Image.open(snap_path) as img:
            assert img.size == (64, 48)
