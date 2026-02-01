from __future__ import annotations

from mujoco_mojo.base import XMLModel

__all__ = ["FlexEdge"]


class FlexEdge(XMLModel):
    """This element adjusts the passive or constraint properties of all edges of the flex. A flex edge can have a damping passive force and an equality constraint associated with it, resulting in edge constraint forces. In the latter case, passive forces are usually unnecessary. For a 1D flex, an edge can also have a passive stiffness, while Solid or Membrane first-party plugins can be used for the 2D and 3D case, respectively. which would generally make edge constraints unnecessary. However these are modeling choices left to the user. MuJoCo allows all these mechanisms to be combined as desired."""

    tag = "edge"

    attributes = ("stiffness", "damping")

    stiffness: float = 0
    """Stiffness of all edges. Only for 1D flex. For 2D and 3D, plugins must be used."""

    damping: float = 0
    """Damping of all edges."""
