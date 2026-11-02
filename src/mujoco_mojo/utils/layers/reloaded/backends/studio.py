from __future__ import annotations

import contextlib
import getpass
import importlib
import importlib.util
import io
import logging
import os
import socket
import threading
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import mujoco

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.typing import UserInterface
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.utils import find_free_port, is_ssh_session
from mujoco_mojo.visualization import ArrowConfig, LineConfig

from .base import ConnectionInfo, ViewerControls

if TYPE_CHECKING:
    from mujoco.studio import viewer_handle

__all__ = [
    "StudioBackend",
    "ViewerUnavailableError",
    "check_studio_available",
    "route_web_server_logs",
    "studio_available",
    "web_client_available",
]

logger = get_logger(__name__)

SYNC_PERIOD = 1 / 100
"""The shortest time between two syncs from the runtime. Physics may step thousands of times a second, and the viewer cannot show them all."""
PUMP_PERIOD = 1 / 60
"""How often the viewer is synced while the runtime is not doing it, i.e. when idle, paused, or stepping slowly."""
START_TIMEOUT = 5.0
"""How long to wait for the browser viewer to come up before giving up."""
SETTLE_SECONDS = 0.5
"""How long the browser viewer is given, after the first model is published, before anything can connect to it. Studio's own code crashes, intermittently and without a Python error, if a page's UI connection arrives within the first few tenths of a second."""
WEB_WARNING = "The browser viewer has no authentication or encryption: anyone who can reach this port can see and control it."


class ViewerUnavailableError(RuntimeError):
    """The chosen viewer cannot run here. The message says why and what to use instead."""


def studio_available() -> bool:
    """Whether the installed MuJoCo includes Studio. Released builds do not yet, so this is only true for a build made from the MuJoCo source."""
    try:
        importlib.import_module("mujoco.studio._studio")
    except ImportError:
        return False
    return True


def web_client_available() -> bool:
    """Whether the browser viewer has a client to serve: the one built into the MuJoCo package, or the one `MUJOCO_WEB_VIEWER_DIST` points at."""
    override = os.environ.get("MUJOCO_WEB_VIEWER_DIST")
    if override and Path(override).is_dir():
        return True
    spec = importlib.util.find_spec("mujoco.studio.web")
    if spec is None:
        return False
    return any(
        (Path(location) / "dist").is_dir()
        for location in spec.submodule_search_locations or []
    )


def check_studio_available(ui: UserInterface) -> None:
    """Raises `ViewerUnavailableError` if the Studio viewer chosen by `ui` cannot run with the installed MuJoCo."""
    if not studio_available():
        raise ViewerUnavailableError(
            f"The `{ui.value}` viewer needs MuJoCo Studio, which MuJoCo {mujoco.__version__} does not include. Use `-ui opengl` for now."
        )
    if ui is UserInterface.WEB and not web_client_available():
        raise ViewerUnavailableError(
            "The `web` viewer needs the Studio browser client, and this MuJoCo build does not have it. Use `-ui studio` or `-ui opengl`, or set MUJOCO_WEB_VIEWER_DIST to a directory with a built client."
        )


class _ForwardToRoot(logging.Handler):
    """Hands a record to the root logger, so it goes wherever the rest of Reloaded's logging goes."""

    def emit(self, record: logging.LogRecord) -> None:
        logging.getLogger().handle(record)


def route_web_server_logs() -> None:
    """
    Has the browser viewer's server log through Reloaded's own logging, once the viewer is up.

    The server reports each browser that connects or leaves, and why one is turned away, but it does so with a handler fixed to the terminal's stdout. Under the terminal UI that writes over the screen, and the messages are never seen. This swaps it for one that forwards to the root logger, and turns the server's debug messages on, since those say why a page is refused or is still waiting for the UI. They are few: one or two per page.

    The server module is imported first. It sets up its logger the moment it is first imported, and gives up if the logger already has a handler, which would leave its quiet log level and its filter for harmless handshake errors unset.
    """
    importlib.import_module("mujoco.studio.web.web_server")
    web_logger = logging.getLogger("WebServer")
    for handler in list(web_logger.handlers):
        if type(handler) is logging.StreamHandler:
            web_logger.removeHandler(handler)
    if not any(isinstance(h, _ForwardToRoot) for h in web_logger.handlers):
        web_logger.addHandler(_ForwardToRoot())
    web_logger.setLevel(logging.DEBUG)
    # the forwarder hands records to the root logger itself, so they must not also travel there on their own
    web_logger.propagate = False


def _listening(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) == 0


@dataclass(eq=False)
class StudioBackend:
    """
    MuJoCo Studio, in a native window or in a browser.

    Studio keeps its own copy of the model and data and shows what `sync` hands it, so unlike the classic viewer it never reads Mojo's data on its own. Mojo's runtime steps the physics, and this backend calls `sync` after steps and, when the runtime is not doing so, from a thread of its own, which keeps the viewer's buttons and camera alive. The viewer writes some things back into the data during `sync` (the Inspector's edits, dragging a body), so every `sync` and every step of the physics happens under one lock.
    """

    xml_path: Callable[[], Path]
    """Gives the file the current model was written to, which Studio shows in its title and keeps its camera by."""
    web: bool
    """Whether to show Studio in a browser instead of a native window."""
    port: int = 8080
    """The first port to try for the browser viewer."""
    title: str = "MuJoCo Mojo Reloaded"

    _controls: ViewerControls | None = field(default=None, init=False, repr=False)
    _handle: viewer_handle.ViewerHandle | None = field(
        default=None, init=False, repr=False
    )
    _lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )
    _state: MjState | None = field(default=None, init=False, repr=False)
    _shown_model: mujoco.MjModel | None = field(default=None, init=False, repr=False)
    _last_sync: float = field(default=0.0, init=False, repr=False)
    _stopping: threading.Event = field(
        default_factory=threading.Event, init=False, repr=False
    )
    _pump_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _chosen_port: int | None = field(default=None, init=False, repr=False)
    _failure: str | None = field(default=None, init=False, repr=False)
    _warned_swap: bool = field(default=False, init=False, repr=False)

    def attach(self, controls: ViewerControls) -> None:
        self._controls = controls

    @property
    def failure(self) -> str | None:
        return self._failure

    def start(self, state: MjState) -> None:
        if self._controls is None:
            raise ViewerUnavailableError(
                "The Studio viewer was started before it was given the controls it passes its buttons on to."
            )
        check_studio_available(UserInterface.WEB if self.web else UserInterface.STUDIO)
        from mujoco.studio import app as studio_app
        from mujoco.studio import launch_native, launch_web, viewer_protocol

        from .studio_plugins import MojoOverlay, MojoStepControl

        plugins = [studio_app.App(), MojoStepControl(self._controls), MojoOverlay()]
        banner = io.StringIO()
        # the web viewer prints its own box of addresses from its thread a moment after it starts, and
        # Reloaded shows the address itself, so what it prints is held back here and dropped
        with contextlib.redirect_stdout(banner):
            if self.web:
                try:
                    self._chosen_port = find_free_port("0.0.0.0", self.port)
                except RuntimeError as e:
                    raise ViewerUnavailableError(str(e)) from e
                config = viewer_protocol.ViewerConfig(
                    title=self.title, gfx="web", http_port=self._chosen_port
                )
                self._handle = launch_web.launch(config, plugins=plugins)
                self._wait_for_web_viewer(banner)
                route_web_server_logs()
            else:
                config = viewer_protocol.ViewerConfig(title=self.title)
                self._handle = launch_native.launch(config, plugins=plugins)

        self.on_reload(state)
        if self.web:
            time.sleep(SETTLE_SECONDS)
        self._pump_thread = threading.Thread(
            target=self._pump_loop, daemon=True, name="studio-pump"
        )
        self._pump_thread.start()

    def _wait_for_web_viewer(self, banner: io.StringIO) -> None:
        """Returns once the browser viewer accepts connections and has printed its box, or raises if it could not start. A port that is taken after all does not fail the launch, it fails the viewer's thread, which `is_running` reports."""
        assert self._handle is not None and self._chosen_port is not None
        deadline = time.monotonic() + START_TIMEOUT
        up = False
        while time.monotonic() < deadline:
            if not self.is_running():
                self._raise_failed_start()
            up = up or _listening(self._chosen_port)
            if up and banner.getvalue().strip():
                return
            time.sleep(0.02)
        if not up:
            self._raise_failed_start()

    def _raise_failed_start(self) -> None:
        reason = self._failure or "it did not start in time"
        self.close()
        raise ViewerUnavailableError(f"The Studio viewer could not start: {reason}")

    def close(self) -> None:
        self._stopping.set()
        thread, self._pump_thread = self._pump_thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
        handle, self._handle = self._handle, None
        if handle is not None:
            try:
                handle.close()
            except Exception as e:
                self._fail(e)

    def is_running(self) -> bool:
        handle = self._handle
        if handle is None or self._failure is not None:
            return False
        try:
            return handle.is_running()
        except Exception as e:
            # the viewer's own thread died, and this is where its exception comes out
            self._fail(e)
            return False

    def _fail(self, error: Exception) -> None:
        if self._failure is None:
            self._failure = str(error) or type(error).__name__
        logger.debug("The Studio viewer failed", exc_info=error)

    def on_reload(self, state: MjState) -> None:
        handle = self._handle
        if handle is None or self._failure is not None:
            return
        with self._lock:
            self._state = state
            if state.model is self._shown_model:
                self._sync(state)
                return
            from .studio_plugins import MojoOverlaySnapshot

            # the same path every time keeps Studio's camera and panels across reloads of the same trial
            handle.set_model(state.model, path=str(self.xml_path()), data=state.data)
            handle.send_to_viewer(MojoOverlaySnapshot())
            self._shown_model = state.model

    def sync_hook(
        self, state: MjState, arrows: list[ArrowConfig], lines: list[LineConfig]
    ) -> None:
        handle = self._handle
        if (
            handle is None
            or self._failure is not None
            or time.monotonic() - self._last_sync < SYNC_PERIOD
        ):
            return
        from .studio_plugins import MojoOverlaySnapshot

        with self._lock:
            try:
                handle.send_to_viewer(MojoOverlaySnapshot(tuple(arrows), tuple(lines)))
            except Exception as e:
                self._fail(e)
                return
            self._sync(state)

    def _sync(self, state: MjState) -> None:
        handle = self._handle
        if handle is None or self._failure is not None:
            return
        with self._lock:
            try:
                model, data = handle.sync(state.model, state.data)
            except Exception as e:
                self._fail(e)
                return
            self._last_sync = time.monotonic()
        if (
            model is not state.model or data is not state.data
        ) and not self._warned_swap:
            # the runtime holds on to the model and data it was given, so a new pair could not be used
            self._warned_swap = True
            logger.warning(
                "Studio replaced the model it was shown, which Reloaded cannot follow, so it is ignored."
            )

    def pump(self) -> None:
        state = self._state
        if state is not None:
            self._sync(state)

    def _pump_loop(self) -> None:
        while not self._stopping.wait(PUMP_PERIOD):
            state = self._state
            if state is None or self._failure is not None:
                continue
            if time.monotonic() - self._last_sync >= PUMP_PERIOD:
                self._sync(state)

    def _hold(self) -> AbstractContextManager[Any]:
        return self._lock

    @property
    def viewer_lock(self) -> Callable[[], AbstractContextManager[Any]] | None:
        # what the viewer writes back into the data happens during a sync, so a step of the physics must
        # not overlap one
        return self._hold

    def connection_info(self) -> ConnectionInfo | None:
        if not self.web or self._chosen_port is None:
            return None
        port = self._chosen_port
        tunnel: str | None = None
        if is_ssh_session():
            try:
                user = getpass.getuser()
            except Exception:
                user = "user"
            tunnel = f"ssh -L {port}:localhost:{port} {user}@{socket.gethostname()}"
        return ConnectionInfo(
            url=f"http://localhost:{port}/", tunnel_command=tunnel, warning=WEB_WARNING
        )
