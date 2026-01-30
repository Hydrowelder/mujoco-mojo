from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from mujoco_mojo.base import XMLModel

__all__ = ["Asset"]


class Asset(XMLModel):
    """This is a grouping element for defining assets. It does not have attributes. Assets are created in the model so that they can be referenced from other model elements; recall the discussion of Assets in the Overview chapter. Assets opened from a file can be identified in two different ways: filename extensions or the content_type attribute. MuJoCo will attempt to open a file specified by the content type provided, and only defaults to the filename extension if no content_type attribute is specified. The content type is ignored if the asset isn't loaded from a file."""

    tag = "asset"

    children = ("meshes", "hfields", "skins", "textures", "materials", "models")

    meshes: Optional[List] = Field(default_factory=list)
    hfields: Optional[List] = Field(default_factory=list)
    skins: Optional[List] = Field(default_factory=list)
    textures: Optional[List] = Field(default_factory=list)
    materials: Optional[List] = Field(default_factory=list)
    models: Optional[List] = Field(default_factory=list)

    # TODO add validator that makes sure each material has a texture that exists (if material.texture is not None)
