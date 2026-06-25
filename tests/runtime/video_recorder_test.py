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
    rec = VideoRecorder(
        path=tmp_path / "out.mp4",
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


class TestIsDueAndCaptureFrame:
    def test_is_due_true_immediately(self, recorder, state):
        assert recorder.is_due(state) is True

    def test_is_due_respects_fps_decimation(self, recorder, state):
        recorder.capture_frame(state, [], [], [])  # advances _next_record_time to 0.1
        state.data.time = 0.05
        assert recorder.is_due(state) is False

    def test_is_due_respects_recording_trigger(self, state, tmp_path):
        rec = VideoRecorder(
            path=tmp_path / "out.mp4",
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
        assert len(recorder._frames) == 1

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
        assert len(recorder._frames) == 1


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
        assert np.array_equal(baseline, disabled)

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
        assert np.array_equal(baseline, disabled)

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
        assert np.array_equal(baseline, disabled)

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
    """Exercises the actual mediapy/ffmpeg/PIL encoding paths -- the same code path that broke when numpy 2.5.0 shipped without mediapy support."""

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
            else:
                import mediapy as media

                frames = media.read_video(str(rec.path))
                assert len(frames) == 3
        finally:
            rec.close()

    def test_save_is_a_no_op_with_no_frames(self, tmp_path, state):
        rec = VideoRecorder(
            path=tmp_path / "empty.mp4", camera_name=CAM1, width=64, height=48
        ).setup(state)
        rec.save()
        assert not rec.path.exists()
        rec.close()


class TestSnapshot:
    def test_snapshot_writes_a_single_image(self, recorder, state, tmp_path):
        snap_path = tmp_path / "snap.png"
        recorder.snapshot(state, snap_path)
        assert snap_path.exists()
        with Image.open(snap_path) as img:
            assert img.size == (64, 48)
