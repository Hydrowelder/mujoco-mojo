from __future__ import annotations

from typing import List, Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.elements.geom import Geom

__all__ = ["Body"]


class Body(XMLModel):
    tag = "body"

    attributes = {"name", "pos"}

    children_map = {"geoms": "geom", "bodies": "body"}

    name: Optional[str] = None
    pos: Optional[str] = None
    geoms: List[Geom] = []
    bodies: List[Body] = []
