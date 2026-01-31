from __future__ import annotations

from typing import Sequence

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.asset_attr.hfield import HField
from mujoco_mojo.mjcf.mujoco_attr.asset_attr.material import Material
from mujoco_mojo.mjcf.mujoco_attr.asset_attr.mesh import Mesh
from mujoco_mojo.mjcf.mujoco_attr.asset_attr.model import Model
from mujoco_mojo.mjcf.mujoco_attr.asset_attr.texture import Texture
from mujoco_mojo.mjcf.mujoco_attr.body_attr.composite_attr.skin import Skin
from mujoco_mojo.utils import is_empty_list

__all__ = ["Asset"]


class Asset(XMLModel):
    """This is a grouping element for defining assets. It does not have attributes. Assets are created in the model so that they can be referenced from other model elements; recall the discussion of Assets in the Overview chapter. Assets opened from a file can be identified in two different ways: filename extensions or the content_type attribute. MuJoCo will attempt to open a file specified by the content type provided, and only defaults to the filename extension if no content_type attribute is specified. The content type is ignored if the asset isn't loaded from a file."""

    tag = "asset"

    children = ("meshes", "hfields", "skins", "textures", "materials", "models")

    meshes: Sequence[Mesh] = Field(default_factory=list, exclude_if=is_empty_list)
    hfields: Sequence[HField] = Field(default_factory=list, exclude_if=is_empty_list)
    skins: Sequence[Skin] = Field(default_factory=list, exclude_if=is_empty_list)
    textures: Sequence[Texture] = Field(default_factory=list, exclude_if=is_empty_list)
    materials: Sequence[Material] = Field(
        default_factory=list, exclude_if=is_empty_list
    )
    models: Sequence[Model] = Field(default_factory=list, exclude_if=is_empty_list)

    # TODO add validator that makes sure each material has a texture that exists (if material.texture is not None)
