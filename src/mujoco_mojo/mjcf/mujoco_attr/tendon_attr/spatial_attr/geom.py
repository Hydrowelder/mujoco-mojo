from __future__ import annotations

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import GeomName

__all__ = ["SpatialGeom"]


class SpatialGeom(XMLModel):
    """This element specifies a geom that acts as an obstacle for the tendon path. If the minimum-length path does not touch the geom it has no effect; otherwise the path wraps around the surface of the geom. Wrapping is computed analytically, which is why we restrict the geom types allowed here to spheres and cylinders. The latter are treated as having infinite length for tendon wrapping purposes. If a sidesite is defined, and its position is inside the geom, then the tendon is constrained to pass through the geom instead of passing around it."""

    tag = "geom"

    attributes = ("geom", "sidesite")

    geom: GeomName
    """The name of a geom that acts as an obstacle for the tendon path. Only sphere and cylinder geoms can be referenced here."""

    sidesite: str | None = None
    """To prevent the tendon path from snapping from one side of the geom to the other as the model configuration varies, the user can define a preferred "side" of the geom. The tendon then goes around the geom the same way as the path from the first endpoint `p_1`, through the side site `s` (projected onto the surface of the geom), to the second endpoint `p_2`. If the straight segment between the endpoints already passes the geom that way, the tendon does not wrap. Formally, the tendon is the shortest path from `p_1` to `p_2` that is homotopic to the polyline `p_1 -> s -> p_2` in the wrapping plane with the geom removed, i.e., that has the same winding angle around the geom center.

    The tendon snaps off the geom when an endpoint crosses the ray opposite the side site, so side sites should be placed such that the endpoints do not cross this ray over the range of motion, typically near the middle of the wrapped arc. Specifying a side site is often needed in practice. If the side site is inside the geom, the tendon is constrained to pass through the interior of the geom."""
