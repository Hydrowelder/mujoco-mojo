from __future__ import annotations

from mujoco_mojo.base import XMLModel
from mujoco_mojo.types import Vec3

__all__ = ["Pos"]


class Pos(XMLModel):
    """Defines a model for positions."""

    tag = ""

    pos: Vec3
    """Position (in (x, y, y))"""
