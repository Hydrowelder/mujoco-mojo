import threading
from pathlib import Path

from filelock import FileLock
from pydantic import BaseModel

_IO_LOCK = threading.Lock()


class MojoBaseModel(BaseModel):
    """Base model for all MuJoCo Mojo classes."""

    def dump_to_path(
        self, path: Path, indent: int | None = None, encoding: str = "utf-8"
    ):
        lock_path = path.with_suffix(path.suffix + ".lock")
        with FileLock(lock_path):
            path.write_text(self.model_dump_json(indent=indent), encoding=encoding)
