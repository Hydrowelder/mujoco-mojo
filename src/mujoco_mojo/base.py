from pathlib import Path

from pydantic import BaseModel


class MojoBaseModel(BaseModel):
    """Base model for all MuJoCo Mojo classes."""

    def dump_to_path(self, path: Path, indent: int = 4, encoding: str = "utf-8"):
        path.write_text(self.model_dump_json(indent=indent), encoding=encoding)
