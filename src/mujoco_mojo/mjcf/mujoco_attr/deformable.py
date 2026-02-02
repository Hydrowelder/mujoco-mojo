from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.flex import Flex
from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.skin import DeformableSkin
from mujoco_mojo.utils import is_empty_list

__all__ = ["Deformable"]


class Deformable(XMLModel):
    """This is a grouping element and does not have any attributes. It groups elements that specify deformable objects, namely flexes and skins."""

    tag = "deformable"

    children = ("flexes", "skins")

    flexes: Sequence[Flex] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Flexes defined in the deformable."""

    skins: Sequence[DeformableSkin] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Skins defined in the deformable."""
