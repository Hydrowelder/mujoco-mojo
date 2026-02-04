from __future__ import annotations

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.tendon_attr.fixed import Fixed
from mujoco_mojo.mjcf.mujoco_attr.tendon_attr.spatial import Spatial
from mujoco_mojo.utils import is_empty_list

__all__ = ["Tendon"]


class Tendon(XMLModel):
    """Grouping element for tendon definitions. The attributes of fixed tendons are a subset of the attributes of spatial tendons, thus we document them only once under spatial tendons. Tendons can be used to impose length limits, simulate spring, damping and dry friction forces, as well as attach actuators to them. When used in equality constraints, tendons can also represent different forms of mechanical coupling."""

    tag = "tendon"

    children = ("spatials", "fixeds")

    spatials: list[Spatial] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Spatial tendon elements."""

    fixeds: list[Fixed] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Fixed tendon elements."""
