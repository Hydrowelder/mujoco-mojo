from __future__ import annotations

from pydantic import Field

from mujoco_mojo.mjcf.mujoco_attr.asset import Asset
from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.flex import Flex
from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.skin import DeformableSkin
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.utils.utils import is_empty_list

__all__ = ["Deformable"]


class Deformable(XMLModel):
    """This is a grouping element and does not have any attributes. It groups elements that specify deformable objects, namely flexes and skins."""

    tag = "deformable"

    children = ("flexes", "skins")

    flexes: list[Flex] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Flexes defined in the deformable."""

    skins: list[DeformableSkin] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Skins defined in the deformable."""


# asset's skins are deformable skins, which asset.py can't import itself (see the note there)
Asset.model_rebuild(_types_namespace={"DeformableSkin": DeformableSkin})
