from pathlib import Path
from typing import Any

from pydantic import GetCoreSchemaHandler

__all__ = ["DepPath"]


class DepPath(Path):
    """Filesystem path to a dependency. MuJoCo Mojo will copy this file."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler):
        return handler.generate_schema(Path)
