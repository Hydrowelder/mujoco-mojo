from __future__ import annotations

from typing import Any, Self

import numpy as np

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import Vec3
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = ["Pos"]


class Pos(XMLModel):
    """Defines a model for positions."""

    tag = ""

    attributes = ("pos",)

    pos: Vec3 = np.array((0, 0, 0))
    """Position (in (x, y, z))"""

    def __init__(self, pos: Vec3 = np.array((0, 0, 0)), **kwargs: Any) -> None:
        """Allows positional construction, e.g. `Pos(my_vec)` instead of `Pos(pos=my_vec)`."""
        kwargs["pos"] = pos
        super().__init__(**kwargs)

    def with_pos(self, pos: Pos | Vec3 | list | tuple) -> Self:
        """Returns a copy of this object with a new position, keeping all other fields."""
        pos_val = pos.pos if isinstance(pos, Pos) else np.asarray(pos, dtype=float)
        return self.model_copy(update={"pos": pos_val})

    def distance_to(self, other: Pos | Vec3 | list | tuple) -> float:
        """Returns the euclidian distance to another position."""
        return np.linalg.norm(self - other).astype(float)

    def lerp(self, other: Pos | Vec3 | list | tuple, t: float) -> Pos:
        """
        Linearly interpolates between this position and another.

        Args:
            other: The target position.
            t: The interpolation factor (0.0 = self, 1.0 = other).

        """
        return self * (1.0 - t) + np.asarray(other, dtype=float) * t

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Pos):
            return NotImplemented
        return np.array_equal(self.pos, other.pos)

    def __getitem__(self, key):
        return self.pos[key]

    def __len__(self) -> int:
        return 3

    def __add__(self, other: Pos | Vec3 | list | tuple) -> Pos:
        """Adds another position or vecotr to this one."""
        other_val = (
            other.pos if isinstance(other, Pos) else np.asarray(other, dtype=float)
        )
        assert isinstance(self.pos, np.ndarray)
        return Pos(self.pos + other_val)

    def __sub__(self, other: Pos | Vec3 | list | tuple) -> Pos:
        """Subtracts another position or vector from this one."""
        other_val = (
            other.pos if isinstance(other, Pos) else np.asarray(other, dtype=float)
        )
        assert isinstance(self.pos, np.ndarray)
        return Pos(self.pos - other_val)

    def __mul__(self, scalar: float) -> Pos:
        """Multiplies the position by a scalar."""
        assert isinstance(self.pos, np.ndarray)
        return Pos(self.pos * scalar)

    def __rmul__(self, scalar: float) -> Pos:
        """Handles scalar * Pos (required for the m1 * p1 logic)."""
        return self.__mul__(scalar)

    def __truediv__(self, scalar: float) -> Pos:
        """Divides the position by a scalar."""
        assert isinstance(self.pos, np.ndarray)
        return Pos(self.pos / scalar)

    def __array__(self, dtype=None, copy=None) -> np.ndarray:
        """Allows np.asarray(my_pos) to work seamlessly."""
        return np.array(self.pos, dtype=dtype, copy=copy)
