import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from watchfiles import PythonFilter, watch

from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

# silence watchfiles' own "N changes detected" log; the controller reports changes itself
logging.getLogger("watchfiles").setLevel(logging.WARNING)

__all__ = ["FileWatcher"]


@dataclass(eq=False)
class FileWatcher:
    """Watches a directory tree for `*.py` changes on a background thread and reports how many files changed in each batch."""

    path: Path
    """The directory to watch, including everything under it."""
    on_change: Callable[[int], None]
    """Called from the watcher's thread with the number of files that changed."""
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
            for changes in watch(
                self.path, watch_filter=PythonFilter(), stop_event=stop
            ):
                self.on_change(len(changes))
        except Exception:
            logger.exception(f"File watcher for {self.path} stopped unexpectedly")
