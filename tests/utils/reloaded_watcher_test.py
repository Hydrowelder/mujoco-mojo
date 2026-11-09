import importlib
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

import mujoco_mojo.utils.layers.reloaded.watcher as watcher_module
from mujoco_mojo.utils.layers.reloaded.watcher import FileWatcher, watched_directories


@pytest.fixture(autouse=True)
def quick_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    """A saved file is normally held back for a moment in case more saves follow, which is only wasted time here."""
    monkeypatch.setattr(watcher_module, "DEBOUNCE_MS", 50)


Importer = Callable[[str, str], None]
"""Imports a module with the given name from the given directory under the temporary folder."""


@pytest.fixture
def imported_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Importer]:
    """Imports modules from directories under `tmp_path`, and forgets them afterwards."""
    imported: list[str] = []
    monkeypatch.syspath_prepend(str(tmp_path))

    def importer(directory: str, name: str) -> None:
        folder = tmp_path / directory
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.py").write_text("x = 1\n")
        monkeypatch.syspath_prepend(str(folder))
        importlib.invalidate_caches()
        importlib.import_module(name)
        imported.append(name)

    yield importer
    for name in imported:
        sys.modules.pop(name, None)


def wait_for(condition: Callable[[], bool], timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


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


def test_the_folder_and_the_directories_of_imported_modules_are_watched_and_nothing_else(
    tmp_path: Path, imported_from: Importer
) -> None:
    imported_from("robot", "watched_robot_module")
    (tmp_path / "builds" / "deep" / "deeper").mkdir(parents=True)
    (tmp_path / "builds" / "deep" / "deeper" / "never_imported.py").write_text(
        "x = 1\n"
    )

    directories = watched_directories(tmp_path)

    assert directories == sorted([tmp_path.resolve(), (tmp_path / "robot").resolve()])


def test_installed_packages_under_the_folder_are_not_watched(
    tmp_path: Path, imported_from: Importer
) -> None:
    imported_from("env/lib/python3/site-packages", "watched_installed_module")

    assert watched_directories(tmp_path) == [tmp_path.resolve()]


def test_a_module_imported_after_the_watcher_started_is_picked_up(
    tmp_path: Path, imported_from: Importer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(watcher_module, "REFRESH_SECONDS", 0.2)
    changed = threading.Event()
    watcher = FileWatcher(tmp_path, lambda count: changed.set())
    watcher.start()
    try:
        imported_from("late", "watched_late_module")
        # the watcher notices the new directory on its next look, so keep saving until a change gets through
        i = 0
        while not changed.wait(0.3) and i < 40:
            (tmp_path / "late" / "watched_late_module.py").write_text(f"x = {i}\n")
            i += 1
        assert changed.is_set()
    finally:
        watcher.stop()


def test_the_directories_are_only_looked_for_again_after_a_module_is_imported(
    tmp_path: Path, imported_from: Importer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Looking resolves the path of every imported module, which is too much work to repeat every couple of seconds for nothing."""
    monkeypatch.setattr(watcher_module, "REFRESH_SECONDS", 0.05)
    looks: list[int] = []
    real = watcher_module.watched_directories

    def counting(root: Path) -> list[Path]:
        looks.append(1)
        return real(root)

    monkeypatch.setattr(watcher_module, "watched_directories", counting)
    watcher = FileWatcher(tmp_path, lambda count: None)
    watcher.start()
    try:
        assert wait_for(lambda: bool(looks))
        # many periods go by with nothing imported (the odd import by some other thread may cost one more look)
        time.sleep(0.5)
        assert len(looks) <= 3

        before = len(looks)
        imported_from("quiet", "watched_quiet_module")
        assert wait_for(lambda: len(looks) > before)
    finally:
        watcher.stop()


def test_a_watcher_that_fails_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_watch(
        *args: object, **kwargs: object
    ) -> Iterator[set[tuple[int, str]]]:
        raise OSError("OS file watch limit reached (kind: MaxFilesWatch)")

    monkeypatch.setattr(watcher_module, "watch", failing_watch)
    reasons: list[str] = []
    watcher = FileWatcher(tmp_path, lambda count: None, on_stopped=reasons.append)

    watcher.start()

    assert wait_for(lambda: bool(reasons))
    assert "limit on watched files" in reasons[0]
    assert wait_for(lambda: not watcher.running)


def test_stopping_a_watcher_on_purpose_is_not_reported_as_a_failure(
    tmp_path: Path,
) -> None:
    reasons: list[str] = []
    watcher = FileWatcher(tmp_path, lambda count: None, on_stopped=reasons.append)

    watcher.start()
    watcher.stop()

    assert reasons == []
