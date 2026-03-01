from __future__ import annotations

from typing import ClassVar

import mujoco

from mujoco_mojo.mjcf.dependency_path import DepPath
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import ModelName

__all__ = ["Model"]


class Model(XMLModel):
    """This element specifies other MJCF models which may be used for attachment in the current model."""

    tag = "model"

    attributes = ("name", "file", "content_type")

    name: ModelName | None = None
    """Name of the sub-model, used for referencing in attach. If unspecified, the model name is used."""

    file: DepPath
    """The file from which the sub-model will be loaded. Note that the sub-model must be a valid MJCF model."""

    content_type: str | None = None
    """The file type to be loaded into a model. Currently only text/xml is supported."""

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_MODEL
