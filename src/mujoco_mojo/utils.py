from __future__ import annotations

from enum import StrEnum, auto

__all__ = ["Color", "SimStatus"]


class Color(StrEnum):
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[97m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    ITALIC = "\033[3m"
    NC = "\033[0m"


class SimStatus(StrEnum):
    RUNNING = auto()
    NORMAL_TERMINATION = auto()
    ERROR_TERMINATION = auto()

    @classmethod
    def prog_bar(cls, p: float, width: int = 40) -> str:
        p = min(max(0, p), 1)
        filled_length = int(width * p)
        return f"[{'█' * filled_length}{'░' * (width - filled_length)}]"
