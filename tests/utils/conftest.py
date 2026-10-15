import logging
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def isolated_logging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """
    Runs a CLI command in a temporary directory and puts the logging state back afterwards.

    Every command calls `setup_logger`, which replaces the root logger's handlers and opens `mojo.log` in the current directory. Left alone, that writes a log into the repository and leaves the file handle open for pytest to complain about.
    """
    monkeypatch.chdir(tmp_path)
    root = logging.getLogger()
    handlers, level, propagate = list(root.handlers), root.level, root.propagate
    yield
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)
    root.propagate = propagate
