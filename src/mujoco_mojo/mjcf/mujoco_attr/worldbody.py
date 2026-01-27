from __future__ import annotations

from typing import List

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.body import Body
from mujoco_mojo.mjcf.mujoco_attr.geom import Geom

__all__ = ["WorldBody"]


class WorldBody(XMLModel):
    tag = "worldbody"

    children_map = {"bodies": "body", "geoms": "geom"}

    bodies: List[Body] = []
    geoms: List[Geom] = []
