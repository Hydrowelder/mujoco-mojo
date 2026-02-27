from enum import StrEnum

__all__ = ["SimStatus"]


class SimStatus(StrEnum):
    RUNNING = "running"
    NORMAL_TERMINATION = "normal_termination"
    ERROR_TERMINATION = "error_termination"

    @classmethod
    def prog_bar(cls, p: float, width: int = 40) -> str:
        p = min(max(0, p), 1)
        filled_length = int(width * p)
        return f"[{'█' * filled_length}{'░' * (width - filled_length)}]"
