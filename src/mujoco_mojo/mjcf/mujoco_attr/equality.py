from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.equality_attr.connect import EqualityConnect
from mujoco_mojo.mjcf.mujoco_attr.equality_attr.flex import EqualityFlex
from mujoco_mojo.mjcf.mujoco_attr.equality_attr.joint import EqualityJoint
from mujoco_mojo.mjcf.mujoco_attr.equality_attr.tendon import EqualityTendon
from mujoco_mojo.mjcf.mujoco_attr.equality_attr.weld import EqualityWeld
from mujoco_mojo.utils import is_empty_list

__all__ = ["Equality"]


class Equality(XMLModel):
    """This is a grouping element for equality constraints. It does not have attributes. See the Equality section of the Computation chapter for a detailed description of equality constraints. Several attributes are common to all equality constraint types, thus we document them only once, under the connect element."""

    tag = "equality"

    children = ("connects", "welds", "joints", "tendons", "flexes")

    connects: Sequence[EqualityConnect] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Connect elements assigned to Equality."""

    welds: Sequence[EqualityWeld] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Weld elements assigned to Equality."""

    joints: Sequence[EqualityJoint] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Joint elements assigned to Equality."""

    tendons: Sequence[EqualityTendon] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Tendon elements assigned to Equality."""

    flexes: Sequence[EqualityFlex] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Flex elements assigned to Equality."""
