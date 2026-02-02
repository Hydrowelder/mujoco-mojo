from __future__ import annotations

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import GeomName

__all__ = ["SpatialGeom"]


class SpatialGeom(XMLModel):
    """This element specifies a geom that acts as an obstacle for the tendon path. If the minimum-length path does not touch the geom it has no effect; otherwise the path wraps around the surface of the geom. Wrapping is computed analytically, which is why we restrict the geom types allowed here to spheres and cylinders. The latter are treated as having infinite length for tendon wrapping purposes. If a sidesite is defined, and its position is inside the geom, then the tendon is constrained to pass through the geom instead of passing around it."""

    tag = "geom"

    attributes = ("geom",)

    geom: GeomName
    """The name of a geom that acts as an obstacle for the tendon path. Only sphere and cylinder geoms can be referenced here."""

    sidesite: str | None = None
    """To prevent the tendon path from snapping from one side of the geom to the other as the model configuration varies, the user can define a preferred "side" of the geom. At runtime, the wrap that is closer to the specified site is automatically selected. Specifying a side site is often needed in practice. If the side site is inside the geom, the tendon is constrained to pass through the interior of the geom."""
