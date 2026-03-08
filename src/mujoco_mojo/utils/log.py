import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TypedDict

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

__all__ = ["get_logger", "setup_logger"]

mojo_theme = Theme(
    {
        "logging.level.debug": "bold dodger_blue1",
        "logging.level.info": "bold green",
        "logging.level.warning": "bold yellow",
        "logging.level.error": "bold red",
        "path": "dim white",
        "message": "white",
    }
)


class MojoLogExtra(TypedDict, total=False):
    file_only: bool
    terminal_only: bool


class TerminalFilter(logging.Filter):
    def filter(self, record: logging.LogRecord):
        # Block if 'file_only' is True
        return not getattr(record, "file_only", False)


class FileFilter(logging.Filter):
    def filter(self, record: logging.LogRecord):
        # Block if 'terminal_only' is True
        return not getattr(record, "terminal_only", False)


def get_logger(name: str):
    logger = logging.getLogger(name)

    if not logger.hasHandlers():
        logger.addHandler(logging.NullHandler())
    return logger


def setup_logger(
    level=logging.INFO,
    terminal: bool = True,
    log_file: Path | str | None = Path("mojo.log"),
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """Shortcut to a sensible MuJoCo Mojo logger using Rich for the terminal."""
    logger = logging.getLogger()
    logger.setLevel(level)

    # avoid double logging by preventing logs from being sent to the root logger
    logger.propagate = False

    if not terminal and log_file is None:
        return logger

    # clear existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # --- RICH HANDLER FOR TERMINAL ---
    if terminal:
        console = Console(theme=mojo_theme)
        rich_handler = RichHandler(
            console=console,
            show_time=False,
            show_path=True,
            enable_link_path=False,
            # highlighter=None,
            markup=True,  # allows color in the log message itself currently disabled in case an array is logged. Square brackets will break logging.
            rich_tracebacks=True,
        )
        rich_handler.addFilter(TerminalFilter())
        logger.addHandler(rich_handler)

    # --- PLAIN TEXT HANDLER ---
    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_format = (
            "%(asctime)s [%(levelname)s] %(pathname)s:%(lineno)d - %(message)s"
        )
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setFormatter(logging.Formatter(file_format))
        file_handler.addFilter(FileFilter())
        logger.addHandler(file_handler)

    return logger
