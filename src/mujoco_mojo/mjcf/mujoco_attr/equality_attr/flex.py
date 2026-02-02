from __future__ import annotations

from mujoco_mojo.mjcf.mujoco_attr.equality_attr.equality_base import EqualityBase
from mujoco_mojo.typing import FlexName

__all__ = ["EqualityFlex"]


class EqualityFlex(EqualityBase):
    """This element constrains the lengths of all edges of a specified flex to their respective lengths in the initial model configuration. In this way the edges are used to maintain the shape of the deformable entity. Note that all other equality constraint types add a fixed number of scalar constraints, while this element adds as many scalar constraints as there are edges in the specified flex."""

    tag = "flex"
    attributes = (
        *EqualityBase.attributes,
        "flex",
    )

    flex: FlexName
    """Name of the flex whose edges are being constrained."""
