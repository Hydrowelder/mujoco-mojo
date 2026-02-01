from __future__ import annotations

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import SiteName

__all__ = ["SpatialSite"]


class SpatialSite(XMLModel):
    """This attribute specifies a site that the tendon path has to pass through. Recall that sites are rigidly attached to bodies."""

    tag = "site"

    attributes = ("site",)

    site: SiteName
    """The name of the site that the tendon must pass through."""
