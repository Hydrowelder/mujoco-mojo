import re
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mujoco
import mujoco.viewer
import numpy as np
import pytest
import typer
from reloaded_fakes import FakeBackend, make_state
from typer.testing import CliRunner

import mujoco_mojo.utils.layers.reloaded.backends.studio as studio_module
import mujoco_mojo.utils.layers.reloaded.session as session_module
from mujoco_mojo.runtime import RunTarget, TargetKind
from mujoco_mojo.settings import ReloadedKeySettings, ReloadedSettings
from mujoco_mojo.typing import UserInterface
from mujoco_mojo.utils.layers.cli import cli_app
from mujoco_mojo.utils.layers.reloaded import MojoReloaded
from mujoco_mojo.utils.layers.reloaded.backends import (
    OpenGLBackend,
    ViewerUnavailableError,
)
from mujoco_mojo.visualization import ArrowConfig, LineConfig

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def make_session(tmp_path: Path, ui: UserInterface) -> MojoReloaded:
    return MojoReloaded(
        generator="pkg.module:generate",
        runtime=None,
        workdir=tmp_path / "work",
        ui=ui,
        overrides_path=None,
        config_path=None,
        trial_num=0,
        seed=None,
        model_config_name=None,
        xml_name="model.xml",
        args=[],
        kwargs={},
        host="127.0.0.1",
        port=8080,
    )


@pytest.fixture(autouse=True)
def studio_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Released MuJoCo has no Studio, but a build from source does, and these tests must not depend on which one is installed."""
    monkeypatch.setattr(studio_module, "studio_available", lambda: False)


def test_the_viewers_to_choose_from_are_opengl_studio_and_web() -> None:
    assert {ui.value for ui in UserInterface} == {"opengl", "studio", "web"}


@pytest.mark.parametrize("removed", ["viser", "mjviser", "VISER", "MjViser"])
def test_a_settings_file_naming_a_removed_viewer_now_means_web(removed: str) -> None:
    with pytest.warns(UserWarning, match="was removed"):
        settings = ReloadedSettings.model_validate({"ui": removed})

    assert settings.ui is UserInterface.WEB


@pytest.mark.parametrize("ui", list(UserInterface))
def test_a_current_viewer_in_settings_is_accepted_without_a_warning(
    ui: UserInterface,
) -> None:
    assert ReloadedSettings.model_validate({"ui": ui.value}).ui is ui


def test_an_unknown_viewer_in_settings_is_still_an_error() -> None:
    with pytest.raises(ValueError):
        ReloadedSettings.model_validate({"ui": "hologram"})


@pytest.mark.parametrize("removed", ["viser", "mjviser"])
def test_the_command_line_rejects_a_removed_viewer(removed: str) -> None:
    result = CliRunner().invoke(cli_app, ["reloaded", "-ui", removed])

    assert result.exit_code == 2
    output = _ANSI_ESCAPE.sub("", result.output)
    for choice in ("opengl", "studio", "web"):
        assert choice in output


def test_opengl_is_shown_in_the_classic_viewer(tmp_path: Path) -> None:
    backend = make_session(tmp_path, UserInterface.OPENGL)._create_backend()

    assert isinstance(backend, OpenGLBackend)


@pytest.mark.parametrize("ui", [UserInterface.STUDIO, UserInterface.WEB])
def test_studio_viewers_explain_that_they_need_studio(
    tmp_path: Path, ui: UserInterface
) -> None:
    session = make_session(tmp_path, ui)

    with pytest.raises(ViewerUnavailableError) as raised:
        session._create_backend()

    message = str(raised.value)
    assert f"`{ui.value}`" in message
    assert mujoco.__version__ in message
    assert "-ui opengl" in message


def test_a_viewer_that_cannot_run_stops_before_the_model_is_generated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = make_session(tmp_path, UserInterface.WEB)
    generated: list[bool] = []
    monkeypatch.setattr(
        session, "generate_construct", lambda **_: generated.append(True)
    )

    with pytest.raises(typer.Exit) as raised:
        session.run()

    assert raised.value.exit_code == 1
    assert generated == []


@dataclass
class LockedBackend(FakeBackend):
    """A backend that, like the classic viewer, makes the runtime hold a lock while it steps."""

    @property
    def viewer_lock(self) -> Callable[[], AbstractContextManager[Any]] | None:
        return nullcontext


@dataclass
class AppProbe:
    """Stands in for `ReloadedApp` in the session module. It notes what the session looked like while the app was running, since that is when the viewer must be wired up."""

    session: MojoReloaded
    backend: FakeBackend | None = None
    keys: ReloadedKeySettings | None = None
    subtitle: str = ""
    fail_with: Exception | None = None
    seen: dict[str, object] = field(default_factory=dict)

    def __call__(
        self,
        controller: object,
        backend: FakeBackend,
        keys: ReloadedKeySettings | None = None,
        subtitle: str = "",
    ) -> "AppProbe":
        self.backend = backend
        self.keys = keys
        self.subtitle = subtitle
        return self

    def run(self) -> None:
        assert self.backend is not None
        self.seen = {
            "started": self.backend.started,
            "closed": self.backend.closed,
            "sync_hook": self.session._sync_hook,
            "viewer_lock": self.session._viewer_lock,
            "pump": self.session.run_control.pump,
        }
        if self.fail_with is not None:
            raise self.fail_with


@pytest.fixture
def probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppProbe:
    probe = AppProbe(make_session(tmp_path, UserInterface.OPENGL))
    monkeypatch.setattr(session_module, "ReloadedApp", probe)
    return probe


def test_the_viewer_is_open_and_wired_to_the_runtime_while_the_app_runs(
    probe: AppProbe,
) -> None:
    backend = LockedBackend()

    probe.session._run_tui(backend, make_state())

    assert probe.seen["started"] is True
    assert probe.seen["closed"] is False
    assert probe.seen["sync_hook"] == backend.sync_hook
    assert probe.seen["viewer_lock"] is nullcontext
    assert probe.subtitle == f"opengl | {probe.session.workdir}"


def test_the_keys_from_settings_reach_the_app(probe: AppProbe) -> None:
    probe.session.keys = ReloadedKeySettings(generate=["f11"])

    probe.session._run_tui(LockedBackend(), make_state())

    assert probe.keys is probe.session.keys


def test_the_viewer_is_closed_and_unwired_once_the_app_returns(probe: AppProbe) -> None:
    backend = LockedBackend()

    probe.session._run_tui(backend, make_state())

    assert backend.closed
    assert probe.session._sync_hook is None
    assert probe.session._viewer_lock is None


def test_the_viewer_is_closed_even_when_the_app_crashes(probe: AppProbe) -> None:
    probe.fail_with = RuntimeError("terminal gone")
    backend = LockedBackend()

    with pytest.raises(RuntimeError, match="terminal gone"):
        probe.session._run_tui(backend, make_state())

    assert backend.closed
    assert probe.session._sync_hook is None
    assert probe.session._viewer_lock is None


@dataclass
class FakeSim:
    """The part of the classic viewer that loads a model into the simulation."""

    loads: list[tuple[mujoco.MjModel, mujoco.MjData, str]] = field(default_factory=list)

    def load(self, model: mujoco.MjModel, data: mujoco.MjData, path: str) -> None:
        self.loads.append((model, data, path))


@dataclass
class FakeHandle:
    """The classic viewer's handle, backed by a real scene so overlays are really drawn."""

    user_scn: mujoco.MjvScene
    sim: FakeSim = field(default_factory=FakeSim)
    running: bool = True
    syncs: int = 0

    def lock(self) -> AbstractContextManager[Any]:
        return nullcontext()

    def sync(self) -> None:
        self.syncs += 1

    def is_running(self) -> bool:
        return self.running

    def close(self) -> None:
        self.running = False

    def _get_sim(self) -> FakeSim:
        return self.sim


@pytest.fixture
def handle(monkeypatch: pytest.MonkeyPatch) -> FakeHandle:
    state = make_state()
    handle = FakeHandle(user_scn=mujoco.MjvScene(state.model, maxgeom=20))
    monkeypatch.setattr(
        mujoco.viewer, "launch_passive", lambda model, data, **_: handle
    )
    return handle


@pytest.fixture
def backend(tmp_path: Path) -> OpenGLBackend:
    return OpenGLBackend(xml_path=lambda: tmp_path / "trial_000" / "model.xml")


def an_arrow() -> ArrowConfig:
    return ArrowConfig(
        pos=np.zeros(3),
        vec=np.array([1.0, 0.0, 0.0]),
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


def test_starting_opens_the_viewer_on_the_model_and_the_file_it_came_from(
    backend: OpenGLBackend, handle: FakeHandle, tmp_path: Path
) -> None:
    state = make_state()

    backend.start(state)

    assert backend.is_running()
    assert handle.sim.loads == [
        (state.model, state.data, str(tmp_path / "trial_000" / "model.xml"))
    ]
    assert handle.syncs == 1
    assert backend.viewer_lock == handle.lock


def test_a_reload_shows_the_new_model_and_wipes_the_old_overlays(
    backend: OpenGLBackend, handle: FakeHandle
) -> None:
    backend.start(make_state())
    handle.user_scn.ngeom = 5
    reloaded = make_state()

    backend.on_reload(reloaded)

    assert handle.user_scn.ngeom == 0
    assert handle.sim.loads[-1][:2] == (reloaded.model, reloaded.data)
    assert handle.syncs == 2


def test_arrows_and_lines_are_drawn_in_the_viewer_scene_and_replaced_each_step(
    backend: OpenGLBackend, handle: FakeHandle
) -> None:
    state = make_state()
    backend.start(state)

    backend.sync_hook(state, [an_arrow()], [a_line()])
    drawn = handle.user_scn.ngeom
    backend.sync_hook(state, [an_arrow()], [a_line()])

    assert drawn == 2
    assert handle.user_scn.ngeom == drawn
    assert handle.syncs == 3

    backend.sync_hook(state, [], [])
    assert handle.user_scn.ngeom == 0


def test_the_backend_follows_the_viewer_window(
    backend: OpenGLBackend, handle: FakeHandle
) -> None:
    backend.start(make_state())

    handle.running = False

    assert not backend.is_running()


def test_closing_closes_the_viewer_and_lets_go_of_it(
    backend: OpenGLBackend, handle: FakeHandle
) -> None:
    backend.start(make_state())

    backend.close()

    assert not handle.running
    assert not backend.is_running()
    assert backend.viewer_lock is None
    backend.close()


def test_a_backend_that_was_never_started_is_idle(backend: OpenGLBackend) -> None:
    assert not backend.is_running()
    assert backend.viewer_lock is None
    assert backend.connection_info() is None
    backend.pump()
    backend.close()


def test_the_backend_pump_is_wired_for_the_run_control_while_the_app_runs(
    probe: AppProbe,
) -> None:
    backend = LockedBackend()

    probe.session._run_tui(backend, make_state())

    assert probe.seen["pump"] == backend.pump
    assert probe.session.run_control.pump is None


@pytest.fixture
def stepping_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A user module whose runtime takes a thousand `step`s, counting them in `progress`."""
    (tmp_path / "pause_sim.py").write_text(
        "progress = {'steps': 0}\n\n"
        "def generate(mojo_model, overrides):\n"
        "    return mojo_model\n\n"
        "def runtime(mojo_model, rm, state):\n"
        "    for _ in range(1000):\n"
        "        rm.step(state)\n"
        "        progress['steps'] += 1\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    yield "pause_sim"
    sys.modules.pop("pause_sim", None)


def steps_taken(module: str) -> int:
    return int(sys.modules[module].progress["steps"])


def test_a_real_run_is_held_and_released_by_the_sessions_run_control(
    tmp_path: Path, stepping_module: str
) -> None:
    """The whole path: the session's `RunControl` reaches the `RuntimeManager` it creates, whose `step` is where the user's loop is held."""
    session = make_session(tmp_path, UserInterface.OPENGL)
    session.generator = f"{stepping_module}.generate"
    session.runtime = f"{stepping_module}.runtime"
    session.playback_speed = 0
    session.run_control.pause()
    run = threading.Thread(
        target=session.generate_construct,
        kwargs={"use_runtime": True, "on_reload_callback": None},
        daemon=True,
    )
    run.start()

    time.sleep(0.3)
    assert steps_taken(stepping_module) == 0

    session.run_control.step(5)
    deadline = time.monotonic() + 5
    while steps_taken(stepping_module) < 5:
        assert time.monotonic() < deadline
        time.sleep(0.005)
    time.sleep(0.2)
    assert steps_taken(stepping_module) == 5

    session.run_control.resume()
    run.join(30)
    assert not run.is_alive()
    assert steps_taken(stepping_module) == 1000


def test_a_real_run_pauses_itself_at_its_target_and_the_controller_is_told(
    tmp_path: Path, stepping_module: str
) -> None:
    session = make_session(tmp_path, UserInterface.OPENGL)
    session.generator = f"{stepping_module}.generate"
    session.runtime = f"{stepping_module}.runtime"
    session.playback_speed = 0
    reasons: list[str | None] = []
    session.run_control.on_hold = reasons.append
    session.run_control.run_until(RunTarget(TargetKind.STEP, 20))
    run = threading.Thread(
        target=session.generate_construct,
        kwargs={"use_runtime": True, "on_reload_callback": None},
        daemon=True,
    )
    run.start()

    deadline = time.monotonic() + 5
    while not session.run_control.paused:
        assert time.monotonic() < deadline
        time.sleep(0.005)
    time.sleep(0.2)

    assert steps_taken(stepping_module) == 20
    assert len(reasons) == 1
    reason = reasons[0]
    assert reason is not None
    assert reason.startswith("reached step 20 (time ")
    session.run_control.resume()
    run.join(30)
    assert not run.is_alive()
    assert steps_taken(stepping_module) == 1000
