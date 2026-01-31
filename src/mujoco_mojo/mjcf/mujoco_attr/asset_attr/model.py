from __future__ import annotations

from pathlib import Path
from typing import Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import ModelName

__all__ = ["Model"]


class Model(XMLModel):
    """This element specifies other MJCF models which may be used for attachment in the current model."""

    tag = "model"

    attributes = ("name", "file", "content_type")

    name: Optional[ModelName] = None
    """Name of the sub-model, used for referencing in attach. If unspecified, the model name is used."""

    file: Path
    """The file from which the sub-model will be loaded. Note that the sub-model must be a valid MJCF model."""

    content_type: Optional[str] = None
    """The file type to be loaded into a model. Currently only text/xml is supported."""
