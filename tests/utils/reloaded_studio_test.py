import gc
import importlib.util
import logging
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from importlib.machinery import ModuleSpec
from pathlib import Path
from typing import Any

import mujoco
import numpy as np
import pytest
from mujoco.studio import launch_native, launch_web, messages, sim
from reloaded_fakes import make_state

import mujoco_mojo.utils.layers.reloaded.backends.studio as studio_module
from mujoco_mojo.typing import StudioGraphics
from mujoco_mojo.utils.layers.reloaded.backends import (
    StudioBackend,
    ViewerUnavailableError,
)
from mujoco_mojo.utils.layers.reloaded.backends.studio_plugins import (
    MojoOverlay,
    MojoOverlaySnapshot,
    MojoStepControl,
    mojo_speed,
    studio_speed,
)
from mujoco_mojo.visualization import ArrowConfig, LineConfig


@pytest.fixture(autouse=True)
def no_settling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Starting the browser viewer waits a moment for it to settle, which only costs time here."""
    monkeypatch.setattr(studio_module, "SETTLE_SECONDS", 0)


@pytest.fixture(autouse=True)
def display_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """The native window needs a display to open on, and these tests must not depend on the machine having one."""
    monkeypatch.setattr(studio_module, "display_problem", lambda: None)


PAUSED = sim.PauseState.NORMAL_PAUSED
RUNNING = sim.PauseState.UNPAUSED


@dataclass
class FakeControls:
    """Satisfies `ViewerControls` and remembers what the viewer's buttons asked for."""

    paused: bool = False
    speed: float = 1.0
    calls: list[tuple[str, str]] = field(default_factory=list)

    def pause(self) -> None:
        self.calls.append(("pause", ""))

    def resume(self) -> None:
        self.calls.append(("resume", ""))

    def step(self, arg: str = "") -> None:
        self.calls.append(("step", arg))

    def set_speed(self, arg: str) -> None:
        self.calls.append(("speed", arg))

    def rerun(self) -> None:
        self.calls.append(("rerun", ""))


class RecordingStepControl(MojoStepControl):
    """Keeps what it would send to the viewer instead of needing one."""

    def __init__(self, controls: FakeControls) -> None:
        super().__init__(controls)
        self.sent: list[messages.StepControlSnapshot] = []

    def _send(self, snapshot: messages.StepControlSnapshot) -> None:
        self.sent.append(snapshot)


def slider(
    paused: bool = False, percent: float = 100.0
) -> messages.StepControlSnapshot:
    """What the viewer sends when its pause button or speed slider was used."""
    return messages.StepControlSnapshot(
        pause_state=PAUSED if paused else RUNNING,
        speed=percent,
        noise_scale=0.0,
        noise_rate=0.0,
    )


def a_step() -> messages.StepEvent:
    """What the handle dispatches on every sync."""
    model = mujoco.MjModel.from_xml_string("<mujoco/>")
    return messages.StepEvent(model=model, data=mujoco.MjData(model))


@pytest.fixture
def controls() -> FakeControls:
    return FakeControls()


@pytest.fixture
def step_control(controls: FakeControls) -> RecordingStepControl:
    return RecordingStepControl(controls)


def test_speeds_are_converted_between_a_multiple_of_real_time_and_a_percentage() -> (
    None
):
    assert studio_speed(1.0) == 100.0
    assert studio_speed(0.5) == 50.0
    assert mojo_speed(50.0) == 0.5


@pytest.mark.parametrize("speed", [2.0, float("inf"), 0.0])
def test_a_speed_the_slider_cannot_show_reads_as_real_time(speed: float) -> None:
    """Faster than real time and `inf` are off its scale, and manual stepping (0) has no speed of its own."""
    assert studio_speed(speed) == 100.0


def test_a_speed_slower_than_the_slider_goes_stops_at_its_slowest() -> None:
    assert studio_speed(0.0001) == pytest.approx(0.1)


def test_the_pause_button_pauses_and_resumes_the_controller(
    step_control: RecordingStepControl, controls: FakeControls
) -> None:
    assert step_control._on_step_control(slider(paused=True)) is True
    controls.paused = True
    assert step_control._on_step_control(slider(paused=False)) is True

    assert controls.calls == [("pause", ""), ("resume", "")]


def test_the_speed_slider_sets_the_controllers_speed(
    step_control: RecordingStepControl, controls: FakeControls
) -> None:
    step_control._on_step_control(slider(percent=25.0))

    assert controls.calls == [("speed", "0.25")]


def test_a_panel_that_changed_nothing_leaves_the_controller_alone(
    step_control: RecordingStepControl, controls: FakeControls
) -> None:
    step_control._on_step_control(slider())

    assert controls.calls == []


def test_the_slider_does_not_take_a_speed_the_controller_has_that_it_cannot_show(
    step_control: RecordingStepControl, controls: FakeControls
) -> None:
    """The slider tops out at real time, so a run at 2x or `inf` shows 100. Sending that back must not change the speed to 1x."""
    for speed in (2.0, float("inf"), 0.0):
        controls.speed = speed
        step_control._on_step_control(slider(percent=100.0))

    assert controls.calls == []


def test_a_pause_that_was_refused_is_put_right_on_the_widgets_again(
    step_control: RecordingStepControl, controls: FakeControls
) -> None:
    """Pause pressed with nothing running: the controller refuses, and the next step shows the truth again."""
    step_control._on_step(a_step())
    assert len(step_control.sent) == 1

    step_control._on_step_control(slider(paused=True))
    step_control._on_step(a_step())

    assert len(step_control.sent) == 2
    assert step_control.sent[-1].pause_state == RUNNING


def test_the_widgets_follow_the_controller_but_only_when_it_changes(
    step_control: RecordingStepControl, controls: FakeControls
) -> None:
    event = a_step()

    step_control._on_step(event)
    step_control._on_step(event)
    assert [(s.pause_state, s.speed) for s in step_control.sent] == [(RUNNING, 100.0)]

    controls.paused = True
    controls.speed = 0.5
    step_control._on_step(event)
    step_control._on_step(event)
    assert [(s.pause_state, s.speed) for s in step_control.sent] == [
        (RUNNING, 100.0),
        (PAUSED, 50.0),
    ]


def test_the_control_noise_in_the_panel_is_left_as_the_user_set_it(
    step_control: RecordingStepControl,
) -> None:
    """Reloaded adds no noise, but sending zero back would snap the slider away from a hand that is dragging it."""
    step_control._on_step_control(
        messages.StepControlSnapshot(
            pause_state=PAUSED, speed=100.0, noise_scale=0.4, noise_rate=0.2
        )
    )

    step_control._on_step(a_step())

    sent = step_control.sent[-1]
    assert (sent.noise_scale, sent.noise_rate) == (
        pytest.approx(0.4),
        pytest.approx(0.2),
    )


def test_a_model_with_a_new_path_has_the_widgets_shown_again(
    step_control: RecordingStepControl,
) -> None:
    event = a_step()
    step_control._on_step(event)

    step_control._on_post_model(
        messages.PostModelEvent(model=event.model, data=event.data, path="a.xml")
    )
    step_control._on_step(event)

    assert len(step_control.sent) == 2


def test_the_single_step_button_steps_once_and_a_pause_request_pauses(
    step_control: RecordingStepControl, controls: FakeControls
) -> None:
    assert step_control._on_single_step(messages.SingleStepEvent()) is True
    assert (
        step_control._on_request_pause(messages.RequestPauseEvent(pause_state=PAUSED))
        is True
    )

    assert controls.calls == [("step", "1"), ("pause", "")]


def test_reset_and_reload_run_the_last_command_again_instead_of_touching_the_model(
    step_control: RecordingStepControl, controls: FakeControls
) -> None:
    """Both are consumed, because the built in handlers would reset or replace the model the runtime is stepping."""
    assert step_control._on_reset(messages.ResetEvent()) is True
    assert step_control._on_load_model(messages.LoadModelEvent()) is True

    assert controls.calls == [("rerun", ""), ("rerun", "")]


def test_a_dropped_model_file_is_refused_because_the_generator_builds_the_model(
    step_control: RecordingStepControl,
    controls: FakeControls,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert (
        step_control._on_load_model(messages.LoadModelEvent(path="/tmp/robot.xml"))
        is True
    )

    assert controls.calls == []
    assert "/tmp/robot.xml" in caplog.text


def an_arrow() -> ArrowConfig:
    return ArrowConfig(
        pos=np.zeros(3),
        vec=np.array([0.0, 0.0, 1.0]),
        color=np.array([1.0, 0.0, 0.0, 1.0]),
        is_torque=False,
    )


def a_line() -> LineConfig:
    return LineConfig(
        pos1=np.zeros(3),
        pos2=np.ones(3),
        color=np.array([0.0, 1.0, 0.0, 1.0]),
        width=2.0,
    )


@pytest.fixture
def model() -> mujoco.MjModel:
    return mujoco.MjModel.from_xml_string("<mujoco/>")


def test_arrows_and_lines_become_extra_geoms_in_the_viewer(
    model: mujoco.MjModel,
) -> None:
    overlay = MojoOverlay()
    extra: list[mujoco.MjvGeom] = []

    overlay._on_overlay(MojoOverlaySnapshot((an_arrow(),), (a_line(),)))
    overlay.refresh(extra, model)

    assert [g.type for g in extra] == [
        mujoco.mjtGeom.mjGEOM_ARROW,
        mujoco.mjtGeom.mjGEOM_LINE,
    ]
    assert np.allclose(extra[0].rgba, (1, 0, 0, 1))
    assert np.allclose(extra[1].rgba, (0, 1, 0, 1))


def test_an_overlay_that_has_not_changed_is_not_made_again(
    model: mujoco.MjModel,
) -> None:
    overlay = MojoOverlay()
    extra: list[mujoco.MjvGeom] = []
    overlay._on_overlay(MojoOverlaySnapshot((an_arrow(),), ()))
    overlay.refresh(extra, model)
    first = list(extra)

    overlay.refresh(extra, model)

    assert extra == first
    assert extra[0] is first[0]


def test_a_new_overlay_replaces_the_old_one_and_leaves_other_plugins_geoms(
    model: mujoco.MjModel,
) -> None:
    overlay = MojoOverlay()
    foreign = mujoco.MjvGeom()
    extra = [foreign]
    overlay._on_overlay(MojoOverlaySnapshot((an_arrow(), an_arrow()), ()))
    overlay.refresh(extra, model)
    assert len(extra) == 3

    overlay._on_overlay(MojoOverlaySnapshot((), (a_line(),)))
    overlay.refresh(extra, model)

    assert len(extra) == 2
    assert extra[0] is foreign
    assert extra[1].type == mujoco.mjtGeom.mjGEOM_LINE


def test_an_empty_overlay_clears_what_was_drawn(model: mujoco.MjModel) -> None:
    overlay = MojoOverlay()
    extra: list[mujoco.MjvGeom] = []
    overlay._on_overlay(MojoOverlaySnapshot((an_arrow(),), (a_line(),)))
    overlay.refresh(extra, model)

    overlay._on_overlay(MojoOverlaySnapshot())
    overlay.refresh(extra, model)

    assert extra == []


def test_a_new_model_makes_the_overlay_draw_again_because_the_viewer_emptied_its_geoms(
    model: mujoco.MjModel,
) -> None:
    overlay = MojoOverlay()
    extra: list[mujoco.MjvGeom] = []
    overlay._on_overlay(MojoOverlaySnapshot((an_arrow(),), ()))
    overlay.refresh(extra, model)

    extra.clear()
    overlay._on_post_model(
        messages.PostModelEvent(model=model, data=mujoco.MjData(model), path="b.xml")
    )
    overlay.refresh(extra, model)

    assert len(extra) == 1


def test_shapes_past_what_the_viewer_can_draw_drop_the_oldest_trail_segments_with_a_warning(
    model: mujoco.MjModel,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        "mujoco_mojo.utils.layers.reloaded.backends.studio_plugins.MAX_OVERLAY_GEOMS", 3
    )
    overlay = MojoOverlay()
    extra: list[mujoco.MjvGeom] = []
    oldest = LineConfig(
        pos1=np.array([0.0, 0.0, 0.0]),
        pos2=np.array([0.0, 0.0, 1.0]),
        color=np.array([0.0, 1.0, 0.0, 1.0]),
        width=2.0,
    )
    newest = LineConfig(
        pos1=np.array([0.0, 0.0, 5.0]),
        pos2=np.array([0.0, 0.0, 6.0]),
        color=np.array([0.0, 1.0, 0.0, 1.0]),
        width=2.0,
    )
    overlay._on_overlay(MojoOverlaySnapshot((an_arrow(), an_arrow()), (oldest, newest)))

    overlay.refresh(extra, model)

    assert len(extra) == 3
    # both arrows are kept, and of the two trail segments the one nearest the present
    assert [g.type for g in extra[:2]] == [mujoco.mjtGeom.mjGEOM_ARROW] * 2
    assert extra[2].type == mujoco.mjtGeom.mjGEOM_LINE
    assert extra[2].pos[2] == pytest.approx(5.0)
    assert "3 extra shapes and 4 were asked for" in caplog.text


# --- the backend, with the browser viewer for real ---


@dataclass
class ViewerSpy:
    """Wraps the handle `launch_web.launch` returns, to count syncs and keep what is sent to the viewer."""

    handle: Any = None
    syncs: int = 0
    sent: list[Any] = field(default_factory=list)

    def launch(self, real: Any) -> Any:
        def launch(*args: Any, **kwargs: Any) -> Any:
            handle = real(*args, **kwargs)
            self.handle = handle
            real_sync, real_send = handle.sync, handle.send_to_viewer

            def sync(model: Any, data: Any) -> Any:
                self.syncs += 1
                return real_sync(model, data)

            def send(message: Any) -> None:
                self.sent.append(message)
                real_send(message)

            handle.sync, handle.send_to_viewer = sync, send
            return handle

        return launch


@pytest.mark.skipif(
    not studio_module.web_client_available(),
    reason="this MuJoCo build has no Studio browser viewer (e.g. the 4.0.0 Windows wheel)",
)
# Studio's web server leaves one loopback socket open after it is closed, whatever the caller does
@pytest.mark.filterwarnings(
    "ignore::ResourceWarning",
    "ignore::pytest.PytestUnraisableExceptionWarning",
)
def test_the_browser_viewer_comes_up_stays_alive_and_goes_away_again(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controls: FakeControls,
    capfd: pytest.CaptureFixture[str],
) -> None:
    # the server's log records carry tracebacks that hold on to its connections, and this test is about the
    # lifecycle. routing the logs has a test of its own
    monkeypatch.setattr(studio_module, "route_web_server_logs", lambda: None)
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.delenv("SSH_TTY", raising=False)
    spy = ViewerSpy()
    monkeypatch.setattr(launch_web, "launch", spy.launch(launch_web.launch))
    backend = StudioBackend(
        xml_path=lambda: tmp_path / "model.xml", web=True, port=8100
    )
    backend.attach(controls)
    state = make_state()

    backend.start(state)
    try:
        info = backend.connection_info()
        assert info is not None
        port = int(info.url.rstrip("/").rsplit(":", 1)[1])
        assert port >= 8100
        assert info.tunnel_command is None
        assert info.warning is not None and "authentication" in info.warning
        assert backend.is_running()
        assert backend.failure is None
        # Studio's own box of addresses is held back, since Reloaded says where to go itself
        assert "MuJoCo Web Viewer" not in capfd.readouterr().out

        # nothing is stepping, yet the viewer is kept alive
        before = spy.syncs
        time.sleep(0.3)
        assert spy.syncs - before >= 5

        # a runtime calling the hook at a thousand steps a second is thinned out
        before = spy.syncs
        end = time.monotonic() + 0.3
        calls = 0
        while time.monotonic() < end:
            backend.sync_hook(state, [an_arrow()], [a_line()])
            calls += 1
            time.sleep(0.001)
        assert calls > 100
        assert 5 <= spy.syncs - before <= 70
        overlays = [m for m in spy.sent if isinstance(m, MojoOverlaySnapshot)]
        assert (
            overlays and len(overlays[-1].arrows) == 1 and len(overlays[-1].lines) == 1
        )

        # what the viewer's buttons send reaches the controller
        spy.handle.dispatch(slider(paused=True))
        spy.handle.dispatch(messages.SingleStepEvent())
        spy.handle.dispatch(messages.ResetEvent())
        assert controls.calls == [("pause", ""), ("step", "1"), ("rerun", "")]

        # and a change made from the terminal reaches the viewer's widgets
        controls.paused = True
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not any(
            isinstance(m, messages.StepControlSnapshot) and m.pause_state == PAUSED
            for m in spy.sent
        ):
            time.sleep(0.01)
        assert any(
            isinstance(m, messages.StepControlSnapshot) and m.pause_state == PAUSED
            for m in spy.sent
        )

        # the runtime's physics and the viewer's syncs never overlap
        lock = backend.viewer_lock
        assert lock is not None
        with lock():
            held = spy.syncs
            time.sleep(0.15)
            assert spy.syncs == held
    finally:
        backend.close()

    assert not backend.is_running()
    with socket.socket() as probe:
        probe.settimeout(0.3)
        assert probe.connect_ex(("127.0.0.1", port)) != 0
    assert not [t for t in threading.enumerate() if t.name == "studio-pump"]
    # so the leak is reported here, where it is allowed, and not at some later test
    spy.handle = None
    gc.collect()


# --- the backend, with a stand-in for the viewer ---


@dataclass
class FakeHandle:
    """Stands in for the handle `launch_*` returns, so the backend's handling of a viewer that fails can be tried without one."""

    error: Exception | None = None
    """Raised by `is_running`, as the viewer thread's exception is."""
    sync_error: Exception | None = None
    replace_model: bool = False
    models: list[tuple[Any, str, Any]] = field(default_factory=list)
    syncs: int = 0
    sent: list[Any] = field(default_factory=list)
    configs: list[Any] = field(default_factory=list)
    """What the viewer was launched with, one `ViewerConfig` per launch."""
    closed: bool = False

    def is_running(self) -> bool:
        if self.error is not None:
            raise self.error
        return not self.closed

    def close(self) -> None:
        self.closed = True

    def set_model(self, model: Any, path: str = "", data: Any = None) -> None:
        self.models.append((model, path, data))

    def sync(self, model: Any, data: Any) -> tuple[Any, Any]:
        self.syncs += 1
        if self.sync_error is not None:
            raise self.sync_error
        if self.replace_model:
            return mujoco.MjModel.from_xml_string("<mujoco/>"), data
        return model, data

    def send_to_viewer(self, message: Any) -> None:
        self.sent.append(message)


@pytest.fixture
def listener() -> Iterator[int]:
    """A port that something is listening on, which is all the backend asks of a browser viewer that has come up."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        yield int(sock.getsockname()[1])


@pytest.fixture
def fake_viewer(monkeypatch: pytest.MonkeyPatch, listener: int) -> Iterator[FakeHandle]:
    handle = FakeHandle()

    def launch(*args: Any, **kwargs: Any) -> FakeHandle:
        handle.configs.append(args[0])
        print("MuJoCo Web Viewer running at: http://localhost/")
        return handle

    monkeypatch.setattr(launch_web, "launch", launch)
    monkeypatch.setattr(launch_native, "launch", launch)
    # the fake stands in for the browser client too, so these run on MuJoCo builds that do not ship one
    monkeypatch.setattr(studio_module, "web_client_available", lambda: True)
    monkeypatch.setattr(studio_module, "find_free_port", lambda host, start: listener)
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.delenv("SSH_TTY", raising=False)
    yield handle


def started_backend(
    controls: FakeControls,
    tmp_path: Path,
    web: bool = True,
    gfx: StudioGraphics = StudioGraphics.DEFAULT,
) -> StudioBackend:
    backend = StudioBackend(xml_path=lambda: tmp_path / "model.xml", web=web, gfx=gfx)
    backend.attach(controls)
    return backend


def test_a_viewer_that_cannot_start_ends_the_start_with_its_own_reason(
    fake_viewer: FakeHandle,
    controls: FakeControls,
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    fake_viewer.error = RuntimeError(
        "Port 8095 is already in use, is another web viewer running?"
    )
    backend = started_backend(controls, tmp_path)

    with pytest.raises(ViewerUnavailableError, match="already in use"):
        backend.start(make_state())

    assert fake_viewer.closed
    assert not backend.is_running()
    assert not [t for t in threading.enumerate() if t.name == "studio-pump"]


def test_a_viewer_that_dies_mid_run_stops_the_backend_and_keeps_its_reason(
    fake_viewer: FakeHandle, controls: FakeControls, tmp_path: Path
) -> None:
    backend = started_backend(controls, tmp_path)
    state = make_state()
    backend.start(state)
    assert backend.is_running()

    fake_viewer.error = RuntimeError("the viewer thread died")

    assert not backend.is_running()
    assert backend.failure == "the viewer thread died"
    # the runtime may still be stepping, so none of this may raise
    backend.sync_hook(state, [], [])
    backend.pump()
    backend.on_reload(state)
    backend.close()


def test_a_sync_that_fails_stops_the_backend_without_raising_into_the_runtime(
    fake_viewer: FakeHandle, controls: FakeControls, tmp_path: Path
) -> None:
    backend = started_backend(controls, tmp_path)
    backend.start(make_state())
    fake_viewer.sync_error = ValueError("boom")

    backend.pump()

    assert backend.failure == "boom"
    assert not backend.is_running()
    backend.close()


def test_over_ssh_the_connection_includes_the_command_that_forwards_the_port(
    fake_viewer: FakeHandle,
    controls: FakeControls,
    tmp_path: Path,
    listener: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SSH_CONNECTION", "10.0.0.2 5000 10.0.0.1 22")
    backend = started_backend(controls, tmp_path)
    backend.start(make_state())

    info = backend.connection_info()
    backend.close()

    assert info is not None
    assert info.url == f"http://localhost:{listener}/"
    assert info.tunnel_command is not None
    assert info.tunnel_command.startswith(f"ssh -L {listener}:localhost:{listener} ")


@pytest.mark.parametrize("gfx", list(StudioGraphics))
def test_the_native_window_is_drawn_in_the_mode_asked_for(
    fake_viewer: FakeHandle, controls: FakeControls, tmp_path: Path, gfx: StudioGraphics
) -> None:
    backend = started_backend(controls, tmp_path, web=False, gfx=gfx)

    backend.start(make_state())

    # Studio reads an empty mode as its own default
    expected = "" if gfx is StudioGraphics.DEFAULT else gfx.value
    assert fake_viewer.configs[0].gfx == expected
    backend.close()


def test_the_browser_viewer_ignores_the_graphics_mode(
    fake_viewer: FakeHandle, controls: FakeControls, tmp_path: Path
) -> None:
    backend = started_backend(
        controls, tmp_path, web=True, gfx=StudioGraphics.OPENGL_SOFTWARE
    )

    backend.start(make_state())

    assert fake_viewer.configs[0].gfx == "web"
    backend.close()


def test_the_native_window_needs_no_address_and_no_port(
    fake_viewer: FakeHandle, controls: FakeControls, tmp_path: Path
) -> None:
    backend = started_backend(controls, tmp_path, web=False)

    backend.start(make_state())

    assert backend.connection_info() is None
    assert backend.is_running()
    backend.close()
    assert fake_viewer.closed


def test_a_new_model_is_published_under_the_path_of_its_file_and_the_same_one_is_synced(
    fake_viewer: FakeHandle, controls: FakeControls, tmp_path: Path
) -> None:
    backend = started_backend(controls, tmp_path)
    first = make_state()
    backend.start(first)

    backend.on_reload(first)
    second = make_state()
    backend.on_reload(second)
    backend.close()

    assert [(model, path, data) for model, path, data in fake_viewer.models] == [
        (first.model, str(tmp_path / "model.xml"), first.data),
        (second.model, str(tmp_path / "model.xml"), second.data),
    ]
    # an unchanged model is shown by syncing it, which is also what the end of a run does
    assert fake_viewer.syncs >= 1
    assert any(isinstance(m, MojoOverlaySnapshot) for m in fake_viewer.sent)


def test_the_web_servers_messages_go_through_reloadeds_logging_not_the_terminal(
    caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    """The server's own handler writes to the terminal's stdout, which scribbles over the terminal UI and is never seen."""
    import logging

    from mujoco.studio.web import web_server

    web_logger = logging.getLogger("WebServer")
    saved = (list(web_logger.handlers), web_logger.level)
    try:
        studio_module.route_web_server_logs()
        studio_module.route_web_server_logs()
        forwarders = [
            h
            for h in web_logger.handlers
            if isinstance(h, studio_module._ForwardToRoot)
        ]
        assert len(forwarders) == 1
        assert not [h for h in web_logger.handlers if type(h) is logging.StreamHandler]

        with caplog.at_level(logging.DEBUG):
            web_server.logger.info("Browser connected (1 total)")
            web_server.logger.debug("Controller slot taken; rejecting new browser")

        messages_seen = [r.getMessage() for r in caplog.records]
        assert "Browser connected (1 total)" in messages_seen
        assert "Controller slot taken; rejecting new browser" in messages_seen
        assert "Browser connected" not in capfd.readouterr().out
    finally:
        web_logger.handlers[:] = saved[0]
        web_logger.setLevel(saved[1])


def test_routing_the_web_servers_logs_leaves_its_own_logging_setup_in_place() -> None:
    """The server sets up its logger when it is first imported, and gives up if the logger already has a handler. Adding ours first used to leave it noisy: every page load logged a line, and so did harmless handshake errors."""
    code = (
        "import logging\n"
        "import mujoco_mojo.utils.layers.reloaded.backends.studio as studio\n"
        "studio.route_web_server_logs()\n"
        "print(logging.getLogger('websockets').level)\n"
        "print([type(f).__name__ for f in logging.getLogger('websockets.server').filters])\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    level, filters = result.stdout.strip().splitlines()[-2:]
    assert int(level) == logging.WARNING
    assert "_HandshakeNoiseFilter" in filters


def test_a_model_swapped_by_the_viewer_is_ignored_with_one_warning(
    fake_viewer: FakeHandle,
    controls: FakeControls,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    backend = started_backend(controls, tmp_path)
    state = make_state()
    backend.start(state)
    fake_viewer.replace_model = True

    backend.pump()
    backend.pump()
    backend.close()

    assert caplog.text.count("replaced the model it was shown") == 1


def test_the_viewer_cannot_be_started_without_the_controls_for_its_buttons(
    tmp_path: Path,
) -> None:
    backend = StudioBackend(xml_path=lambda: tmp_path / "model.xml", web=True)

    with pytest.raises(ViewerUnavailableError, match="controls"):
        backend.start(make_state())


def only_the_bindings_exist(name: str) -> ModuleSpec | None:
    """Stands in for `importlib.util.find_spec` on a MuJoCo build that has the browser viewer's bindings but no client in the package."""
    return ModuleSpec(name, None) if name == "mujoco.studio.web.state_payload" else None


def test_the_browser_client_is_found_where_the_override_points_or_in_the_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", only_the_bindings_exist)
    monkeypatch.setenv("MUJOCO_WEB_VIEWER_DIST", str(tmp_path))
    assert studio_module.web_client_available()

    monkeypatch.setenv("MUJOCO_WEB_VIEWER_DIST", str(tmp_path / "missing"))
    assert not studio_module.web_client_available()


def test_a_client_is_no_use_without_the_browser_viewers_bindings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    monkeypatch.setenv("MUJOCO_WEB_VIEWER_DIST", str(tmp_path))
    assert not studio_module.web_client_available()
