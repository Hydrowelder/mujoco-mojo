import threading
import time
from pathlib import Path

from mujoco_mojo.utils.layers.reloaded.watcher import FileWatcher


def test_reports_python_file_changes(tmp_path: Path) -> None:
    """Saving a `.py` file under the watched directory calls back with the number of changed files."""
    seen: list[int] = []
    changed = threading.Event()

    def on_change(count: int) -> None:
        seen.append(count)
        changed.set()

    watcher = FileWatcher(tmp_path, on_change)
    watcher.start()
    try:
        assert watcher.running
        # the watcher needs a moment to arm, so keep saving until it notices
        deadline = time.monotonic() + 10
        i = 0
        while not changed.wait(0.2) and time.monotonic() < deadline:
            (tmp_path / "sim.py").write_text(f"x = {i}\n")
            i += 1
        assert changed.is_set()
        assert seen[0] >= 1
    finally:
        watcher.stop()

    assert not watcher.running


def test_start_and_stop_are_idempotent(tmp_path: Path) -> None:
    """Starting twice keeps one thread, and stopping twice (or before starting) is harmless."""
    watcher = FileWatcher(tmp_path, lambda count: None)
    watcher.stop()

    watcher.start()
    thread = watcher._thread
    watcher.start()
    assert watcher._thread is thread

    watcher.stop()
    watcher.stop()
    assert not watcher.running


def test_can_restart_after_stop(tmp_path: Path) -> None:
    """A stopped watcher can be started again."""
    watcher = FileWatcher(tmp_path, lambda count: None)
    watcher.start()
    watcher.stop()
    assert not watcher.running

    watcher.start()
    try:
        assert watcher.running
    finally:
        watcher.stop()
