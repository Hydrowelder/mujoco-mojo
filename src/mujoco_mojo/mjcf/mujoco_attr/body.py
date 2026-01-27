from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.geom import Geom

__all__ = ["Body"]


class Body(XMLModel):
    tag = "body"

    attributes = ("name", "pos")
    children = ("geoms", "bodies")

    name: Optional[str] = None
    pos: Optional[str] = None
    geoms: List[Geom] = Field(default_factory=list)
    bodies: List[Body] = Field(default_factory=list)
