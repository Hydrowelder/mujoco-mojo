from __future__ import annotations

from typing import Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.types import Vec3

__all__ = ["Geom"]


class Geom(XMLModel):
    tag = "geom"

    attributes = {"name", "type", "size", "rgba", "pos"}

    name: Optional[str] = None
    type: Optional[str] = None
    size: Optional[str] = None
    rgba: Optional[str] = None
    pos: Optional[Vec3] = None
