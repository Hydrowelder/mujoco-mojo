from __future__ import annotations

import numpy as np

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import Vec3

__all__ = ["Pos"]


class Pos(XMLModel):
    """Defines a model for positions."""

    tag = ""

    pos: Vec3 = np.array((0, 0, 0))
    """Position (in (x, y, z))"""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Pos):
            return NotImplemented
        return np.array_equal(np.asarray(self.pos), np.asarray(other.pos))
