from __future__ import annotations

from typing import ClassVar

import mujoco

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import BodyName, ContactExcludeName

__all__ = ["Exclude"]


class Exclude(XMLModel):
    """This element is used to exclude a pair of bodies from collision checking. Unlike all other contact-related elements which refer to geoms, this element refers to bodies. Experience has shown that exclusion is more useful on the level of bodies. Collisions between any geom defined in the first body and any geom defined in the second body are excluded."""

    tag = "exclude"

    attributes = (
        "name",
        "body1",
        "body2",
    )

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_EXCLUDE

    name: ContactExcludeName | None = None
    """Name of this contact pair."""

    body1: BodyName
    """The name of the first body in the pair."""

    body2: BodyName
    """The name of the second body in the pair."""
