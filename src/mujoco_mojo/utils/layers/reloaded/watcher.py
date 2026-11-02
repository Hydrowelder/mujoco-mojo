import logging
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from watchfiles import PythonFilter, watch

from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

# silence watchfiles' own "N changes detected" log; the controller reports changes itself
logging.getLogger("watchfiles").setLevel(logging.WARNING)

__all__ = ["FileWatcher", "watched_directories"]

REFRESH_SECONDS = 2.0
"""How often the directories being watched are compared with the modules that are imported now."""
DEBOUNCE_MS = 1600
"""How long watchfiles waits for a burst of saves to settle before reporting them as one batch."""
_INSTALLED_PARTS = ("site-packages", "dist-packages")
_WATCH_LIMIT_HINT = (
    "The operating system's limit on watched files was reached, which other programs such as your editor share. "
    "On Linux it can be raised with `sysctl fs.inotify.max_user_watches`."
)


def watched_directories(root: Path) -> list[Path]:
    """
    The directories to watch for a reload under `root`: `root` itself and the directory of every imported module that lives under it.

    That is the same set of modules a reload acts on, and watching only their directories keeps the number of watches small. Watching everything under `root` also watches build trees, virtual environments, and checkouts that happen to sit beneath it, which can use up the operating system's whole allowance of watches.
    """
    root = root.resolve()
    found = {root}
    for module in list(sys.modules.values()):
        file = getattr(module, "__file__", None)
        if not file:
            continue
        try:
            directory = Path(file).resolve().parent
        except (OSError, RuntimeError):
            continue
        if (
            directory.is_relative_to(root)
            and not any(part in _INSTALLED_PARTS for part in directory.parts)
            and directory.is_dir()
        ):
            found.add(directory)
    return sorted(found)


@dataclass(eq=False)
class FileWatcher:
    """Watches the code a reload would pick up for `*.py` changes on a background thread and reports how many files changed in each batch."""

    path: Path
    """The project directory. It and the directories of the project's imported modules are watched, each on its own."""
    on_change: Callable[[int], None]
    """Called from the watcher's thread with the number of files that changed."""
    on_stopped: Callable[[str], None] | None = None
    """Called from the watcher's thread with the reason, if watching ends because of a failure. It is not called when `stop` ends it."""
    _stop: threading.Event = field(
        default_factory=threading.Event, init=False, repr=False
    )
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Starts watching. Does nothing if already running."""
        if self.running:
            return
        # a fresh event per run, so a stale thread can never be revived by a later start
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            args=(self._stop,),
            daemon=True,
            name="reloaded-file-watcher",
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stops watching and waits up to `timeout` seconds for the thread to finish."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _run(self, stop: threading.Event) -> None:
        try:
            while not stop.is_set():
                # counted first, so a module imported while the directories are being worked out shows up as a change
                known_modules = len(sys.modules)
                directories = watched_directories(self.path)
                for changes in watch(
                    *directories,
                    watch_filter=PythonFilter(),
                    debounce=DEBOUNCE_MS,
                    stop_event=stop,
                    recursive=False,
                    rust_timeout=int(REFRESH_SECONDS * 1000),
                    yield_on_timeout=True,
                ):
                    if changes:
                        self.on_change(len(changes))
                    # a module imported since the last look may live somewhere that is not watched yet. looking
                    # means resolving the path of every module there is, so it is only done once the number of
                    # modules has changed
                    if len(sys.modules) != known_modules:
                        known_modules = len(sys.modules)
                        if watched_directories(self.path) != directories:
                            break
        except Exception as e:
            logger.debug(f"File watcher for {self.path} stopped", exc_info=True)
            if self.on_stopped is not None and not stop.is_set():
                reason = (
                    _WATCH_LIMIT_HINT
                    if "MaxFilesWatch" in str(e)
                    else f"{type(e).__name__}: {e}"
                )
                self.on_stopped(reason)
