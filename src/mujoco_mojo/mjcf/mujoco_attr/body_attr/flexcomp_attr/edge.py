from __future__ import annotations

from copy import deepcopy

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.defaults import SOLIMP_DEFAULT, SOLREF_DEFAULT
from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.flex_attr.edge import FlexEdge
from mujoco_mojo.typing import Vec2, Vec5

__all__ = ["FlexCompEdge"]


class FlexCompEdge(XMLModel):
    """Each flex element has one edge in 1D (coinciding with the capsule element), three edges in 2D, and six edges in 3D. The edges are generated automatically when the flex element is compiled, and the user cannot specify them directly. This element is used to adjust the properties of all edges in the flex."""

    tag = "edge"

    attributes = (
        "equality",
        "solref",
        "solimp",
        "stiffness",
        "damping",
    )

    equality: bool = False
    """When enabled, an equality constraint of type flex is added to the model, referencing the automatically-generated flex by name."""

    solref: Vec2 = SOLREF_DEFAULT
    """The standard constraint parameters, passed through to the automatically generated equality constraint."""

    solimp: Vec5 = SOLIMP_DEFAULT
    """The standard constraint parameters, passed through to the automatically generated equality constraint."""

    stiffness: float = Field(
        default_factory=lambda: deepcopy(FlexEdge.model_fields["stiffness"].default)
    )
    """Edge stiffness, passed through to the automatically generated flex."""

    damping: float = Field(
        default_factory=lambda: deepcopy(FlexEdge.model_fields["damping"].default)
    )
    """Edge damping, passed through to the automatically generated flex."""
