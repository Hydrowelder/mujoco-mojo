from __future__ import annotations

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import VecN

__all__ = ["FlexCompPin"]


class FlexCompPin(XMLModel):
    """Each point is either pinned or not pinned. The effect of pinning was explained earlier. This element is used to specify which points are pinned. Note that each attribute below can be used to specify multiple pins, and in addition to that, the pin element itself can be repeated for user convenience. The effects are cumulative; pinning the same point multiple times is allowed."""

    tag = "pin"

    attributes = (
        "id",
        "range",
        "grid",
        "gridrange",
    )

    id: VecN
    """Zero-based ids of points to pin. When the points are automatically-generaged, the user needs to understand their layout in order to decide which points to pin. This can be done by first creating a flexcomp without any pins, loading it in the simulator, and showing the body labels."""

    range: VecN
    """Ranges of points to pin. Each range is specified by two integers."""

    grid: VecN
    """Grid coordinates of points to pin. This can only be used with type grid."""

    gridrange: VecN
    """Ranges of grid coordinates of points to pin. Each range is specified by (dim) integers for the minimum of the range followed by (dim) integers for the maximum of the range. This can only be used with type grid."""
