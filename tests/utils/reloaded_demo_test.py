import threading
import time

from reloaded_fakes import FakeSession
from reloaded_tui_demo import fake_runtime

import mujoco_mojo.runtime as rt


def test_the_demo_runtime_obeys_the_run_controls_like_a_real_run() -> None:
    """The demo is only worth opening if pause, step, and `run until` do something in it, which needs its runtime to step through a `RuntimeManager`."""
    session = FakeSession(behavior=fake_runtime)
    session.playback_speed = 0
    reasons: list[str | None] = []
    session.run_control.on_hold = reasons.append
    session.run_control.run_until(rt.RunTarget(rt.TargetKind.STEP, 3))
    finished = threading.Event()

    def run() -> None:
        try:
            fake_runtime(session)
        finally:
            finished.set()

    threading.Thread(target=run, daemon=True).start()
    deadline = time.monotonic() + 5
    while not session.run_control.paused:
        assert time.monotonic() < deadline
        time.sleep(0.005)
    time.sleep(0.1)

    assert session.run_control.position == (0.75, 3)
    assert reasons == ["reached step 3 (time 0.75, step 3)"]
    assert not finished.is_set()

    session.run_control.resume()
    assert finished.wait(5)
