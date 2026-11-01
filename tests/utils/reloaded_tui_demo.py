"""
Opens the Reloaded terminal UI against a fake session, to try the layout and keys. This is not a test.

    python tests/utils/reloaded_tui_demo.py          # native window style, no connection panel
    python tests/utils/reloaded_tui_demo.py --web    # also shows the browser viewer connection panel
    python tests/utils/reloaded_tui_demo.py --dev    # live reload while you work on the UI

With `--dev`, saving `tui.tcss` restyles the running app at once, and saving any Python file under `mujoco_mojo` or this folder restarts it. Quitting the app (Ctrl+Q) also ends the dev session.

F2 generates, F3 runs a fake runtime that takes a few seconds and logs a line per step, and Escape stops it. It steps a real `RuntimeManager`, so the run can also be controlled the way a real one is: `pause` or F12, `step`, `speed 4`, `run` to carry on a paused run, and `run until step 3` or `run until time 2` to have it pause by itself. The right end of the command line says what the command you are typing will do (F8 turns that off), and `explain seed 42` or `seed 42?` prints it to the log.
"""

import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

from reloaded_fakes import FakeBackend, FakeSession

import mujoco

import mujoco_mojo
import mujoco_mojo.runtime as rt
from mujoco_mojo.mj_state import MjState
from mujoco_mojo.utils.layers.reloaded.backends.base import ConnectionInfo
from mujoco_mojo.utils.layers.reloaded.controller import ReloadedController
from mujoco_mojo.utils.layers.reloaded.tui import ReloadedApp
from mujoco_mojo.utils.log import setup_logger

demo_logger = logging.getLogger("demo")

_CHILD_FLAG = "RELOADED_DEMO_CHILD"


def fake_runtime(session: FakeSession) -> None:
    """Takes twenty steps of a real `RuntimeManager` over an empty model. Each step is a quarter of a second of simulation time, so at speed 1 it runs in real time and takes five seconds."""
    model = mujoco.MjModel.from_xml_string('<mujoco><option timestep="0.25"/></mujoco>')
    state = MjState(model, mujoco.MjData(model))
    manager = rt.RuntimeManager(
        playback_speed=session.playback_speed,
        _run_control=session.run_control,
        _stop_event=session.stop_event,
    )
    for step in range(20):
        manager.step(state)
        demo_logger.info(f"step {step + 1} of 20, time {state.data.time:g}")
    print("runtime finished (this line came from print)")


def run_app(dev: bool) -> None:
    setup_logger(log_file=None)
    session = FakeSession(workdir=Path("mojo-models"), behavior=fake_runtime)

    info = None
    if "--web" in sys.argv:
        info = ConnectionInfo(
            url="http://localhost:8000/",
            tunnel_command="ssh -L 8000:localhost:8000 you@this-host",
            warning="This viewer has no authentication and listens on every network interface. Use the tunnel above.",
        )
    backend = FakeBackend(info)

    controller = ReloadedController(session, backend)
    ReloadedApp(controller, backend, subtitle="demo | mojo-models", watch_css=dev).run()


def run_with_restart() -> None:
    """Runs the demo in a child process and starts it again whenever a Python file changes."""
    from watchfiles import PythonFilter, watch

    watched = [
        Path(mujoco_mojo.__file__).resolve().parent,
        Path(__file__).resolve().parent,
    ]
    command = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    env = {**os.environ, _CHILD_FLAG: "1"}

    def stop(child: subprocess.Popen[bytes]) -> None:
        # a signal rather than a kill, so Textual gets to put the terminal back before the next copy starts
        if child.poll() is None:
            child.send_signal(signal.SIGINT)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()

    child = subprocess.Popen(command, env=env)
    try:
        for changes in watch(
            *watched,
            watch_filter=PythonFilter(),
            debounce=300,
            rust_timeout=250,
            yield_on_timeout=True,
        ):
            if child.poll() is not None:
                break
            if changes:
                stop(child)
                child = subprocess.Popen(command, env=env)
    except KeyboardInterrupt:
        pass
    finally:
        stop(child)


def main() -> None:
    dev = "--dev" in sys.argv
    if dev and _CHILD_FLAG not in os.environ:
        run_with_restart()
    else:
        run_app(dev)


if __name__ == "__main__":
    main()
