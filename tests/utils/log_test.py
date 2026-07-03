import logging
from pathlib import Path

from mujoco_mojo.utils.log import get_trial_log_handler


def _log_one_line(handler: logging.FileHandler, message: str) -> None:
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    try:
        root_logger.warning(message)
    finally:
        root_logger.removeHandler(handler)
        handler.close()


def test_get_trial_log_handler_defaults_to_append(tmp_path: Path) -> None:
    """The default mode preserves MojoRunner's existing append-on-rerun behavior."""
    log_file = tmp_path / "mojo.log"

    _log_one_line(get_trial_log_handler(log_file), "first")
    _log_one_line(get_trial_log_handler(log_file), "second")

    lines = log_file.read_text().splitlines()
    assert len(lines) == 2
    assert "first" in lines[0]
    assert "second" in lines[1]


def test_get_trial_log_handler_mode_w_overwrites(tmp_path: Path) -> None:
    """mode='w' truncates the file on each new handler, matching reloaded's rerun behavior."""
    log_file = tmp_path / "mojo.log"

    _log_one_line(get_trial_log_handler(log_file, mode="w"), "first")
    _log_one_line(get_trial_log_handler(log_file, mode="w"), "second")

    lines = log_file.read_text().splitlines()
    assert len(lines) == 1
    assert "second" in lines[0]
    assert "first" not in lines[0]
