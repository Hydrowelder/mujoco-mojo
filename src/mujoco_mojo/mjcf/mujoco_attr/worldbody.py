from __future__ import annotations

from typing import List

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.body import Body
from mujoco_mojo.mjcf.mujoco_attr.geom import Geom

__all__ = ["WorldBody"]


class WorldBody(XMLModel):
    tag = "worldbody"

    children = ("bodies", "geoms")

    bodies: List[Body] = Field(default_factory=list)
    geoms: List[Geom] = Field(default_factory=list)
