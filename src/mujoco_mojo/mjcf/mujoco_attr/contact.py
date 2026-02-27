from __future__ import annotations

from pydantic import Field

from mujoco_mojo.mjcf.mujoco_attr.contact_attr.exclude import Exclude
from mujoco_mojo.mjcf.mujoco_attr.contact_attr.pair import Pair
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.utils.utils import is_empty_list

__all__ = ["Contact"]


class Contact(XMLModel):
    """This is a grouping element and does not have any attributes. It groups elements that are used to adjust the generation of candidate contact pairs for collision checking. Collision detection was described in detail in the Computation chapter, thus the description here is brief."""

    tag = "contact"

    children = ("pairs", "excludes")

    pairs: list[Pair] = Field(default_factory=list, exclude_if=is_empty_list)
    """Pair elements assigned to Contact."""

    excludes: list[Exclude] = Field(default_factory=list, exclude_if=is_empty_list)
    """Exclude elements assigned to Contact."""
