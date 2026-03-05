from enum import StrEnum

import numpy as np

from mujoco_mojo.typing import Vec4
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = ["Color"]

rng = np.random.default_rng(seed=42)


class Color(StrEnum):
    """
    Contains color aliases and converters to go between the various color formats.

    MuJoCo uses a normalized rgba (all color channels clamped between 0 and 1). This enum defines with hex values, but they can be easily transformed with the provided methods (for example: `Color.WHITE.rgba`).
    """

    WHITE = "#FFFFFF"
    BLACK = "#000000"
    RED = "#FF0000"
    GREEN = "#00FF00"
    BLUE = "#0000FF"
    YELLOW = "#FFFF00"
    CYAN = "#00FFFF"
    MAGENTA = "#FF00FF"
    PURPLE = "#8A2BE2"

    @classmethod
    def random_rgba(cls) -> Vec4:
        return np.append((rng.random(3)), 1)

    @property
    def rgba(self) -> Vec4:
        """Returns the normalized RGBA array for MuJoCo."""
        return Color.hex_to_rgba(self.value)

    def with_alpha(self, alpha: float) -> Vec4:
        """Returns the color with a custom transparency level."""
        return Color.hex_to_rgba(self.value, alpha=alpha)

    @classmethod
    def hex_to_rgba(cls, hex_str: str, alpha: float = 1.0) -> Vec4:
        """Converts '#RRGGBB' or 'RRGGBB' to normalized [0, 1] RGBA."""
        hex_str = hex_str.lstrip("#")
        # Convert hex to integers using bit-shifting
        lv = len(hex_str)
        if lv == 6:
            rgb = tuple(int(hex_str[i : i + 2], 16) for i in (0, 2, 4))
        else:
            raise ValueError(f"Invalid hex color: {hex_str}. Expected 6 characters.")

        return np.array([*(np.array(rgb) / 255.0), alpha])

    @classmethod
    def rgba255_to_rgba(cls, rgba255: Vec4) -> Vec4:
        """Converts [0-255, 0-255, 0-255, 0-1] to normalized [0, 1] RGBA."""
        res = np.array(rgba255, dtype=float)
        res[:3] /= 255.0
        return res

    @classmethod
    def rgba_to_hex(cls, rgba: Vec4) -> str:
        """Converts normalized RGBA to '#RRGGBB' (alpha is discarded)."""
        rgba = np.asarray(rgba)
        rgb255 = (rgba[:3] * 255).astype(int)
        return "#{:02x}{:02x}{:02x}".format(*rgb255)

    @classmethod
    def rgba_to_rgba255(cls, rgba: Vec4) -> Vec4:
        """Converts normalized RGBA to [0-255, 0-255, 0-255, 0-1]."""
        res = np.array(rgba, dtype=float)
        res[:3] *= 255.0
        return res
