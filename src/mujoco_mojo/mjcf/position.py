from __future__ import annotations

import numpy as np

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import Vec3

__all__ = ["Pos"]


class Pos(XMLModel):
    """Defines a model for positions."""

    tag = ""

    pos: Vec3 = np.array((0, 0, 0))
    """Position (in (x, y, z))"""

    def distance_to(self, other: Pos | Vec3 | list | tuple) -> float:
        """Returns the euclidian distance to another position."""
        return np.linalg.norm(self - other).astype(float)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Pos):
            return NotImplemented
        return np.array_equal(np.asarray(self.pos), np.asarray(other.pos))

    def __getitem__(self, key):
        return np.asarray(self.pos)[key]

    def __len__(self) -> int:
        return 3

    def __add__(self, other: Pos | Vec3 | list | tuple) -> Pos:
        """Adds another position or vecotr to this one."""
        other_val = (
            np.asarray(other.pos) if isinstance(other, Pos) else np.asarray(other)
        )
        return Pos(pos=np.asarray(self.pos) + other_val)

    def __sub__(self, other: Pos | Vec3 | list | tuple) -> Pos:
        """Subtracts another position or vector from this one."""
        other_val = (
            np.asarray(other.pos) if isinstance(other, Pos) else np.asarray(other)
        )
        return Pos(pos=np.asarray(self.pos) - other_val)

    def __mul__(self, scalar: float) -> Pos:
        """Multiplies the position by a scalar."""
        return Pos(pos=np.asarray(self.pos) * scalar)

    def __rmul__(self, scalar: float) -> Pos:
        """Handles scalar * Pos (required for the m1 * p1 logic)."""
        return self.__mul__(scalar)

    def __truediv__(self, scalar: float) -> Pos:
        """Divides the position by a scalar."""
        return Pos(pos=np.asarray(self.pos) / scalar)

    def __array__(self, dtype=None, copy=None) -> np.ndarray:
        """Allows np.asarray(my_pos) to work seamlessly."""
        return np.array(self.pos, dtype=dtype, copy=copy)
