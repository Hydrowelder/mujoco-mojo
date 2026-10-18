import logging
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mujoco_mojo.utils.layers.cli import cli_app

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


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


@pytest.fixture
def help_text() -> Callable[..., str]:
    """
    Returns a function that runs `mujoco-mojo <args> --help` and gives back its text without styling.

    Typer styles its help whenever `GITHUB_ACTIONS`, `FORCE_COLOR`, or `PY_COLORS` is set, and Rich highlights an option name in pieces (`-` and `-arg` separately), so a plain `"--arg" in output` check passes on a laptop and fails in CI.
    """

    def run(*args: str) -> str:
        result = CliRunner().invoke(cli_app, [*args, "--help"])
        assert result.exit_code == 0
        return _ANSI_ESCAPE.sub("", result.output)

    return run
