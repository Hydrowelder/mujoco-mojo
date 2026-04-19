import threading
from pathlib import Path

from pydantic import BaseModel

_IO_LOCK = threading.Lock()


class MojoBaseModel(BaseModel):
    """Base model for all MuJoCo Mojo classes."""

    def dump_to_path(
        self, path: Path, indent: int | None = None, encoding: str = "utf-8"
    ):
        with _IO_LOCK:
            path.write_text(self.model_dump_json(indent=indent), encoding=encoding)
