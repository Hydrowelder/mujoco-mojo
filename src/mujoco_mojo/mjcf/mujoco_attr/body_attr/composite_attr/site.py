"""
Defines the site type for composites.

!!! note
    I was pretty lazy when I did this, I just decided to have this type inherit from the SiteBase class. That is not a super clean way to do it because it means this object may have attributes that MuJoCo will just ignore. The XML attributes defined here are restricted to the subset that only the composite site has.

    Sorry...
"""

from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import SiteBase
from mujoco_mojo.typing import Vec3


class CompositeSite(SiteBase):
    """This sub-element adjusts the attributes of the sites in the composite object. Otherwise it is the same as geom above."""

    attributes = ("group", "size", "material", "rgba")

    # inherited from SiteBase but not part of the composite site's restricted schema
    non_xml_fields = ("name", "class_", "pose", "user")

    size: Vec3 | None = None
    """Sizes of the geometric shape representing the site. What shape it is I do not know."""
