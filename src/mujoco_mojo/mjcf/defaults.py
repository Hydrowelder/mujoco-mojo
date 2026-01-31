from __future__ import annotations

import numpy as np

from mujoco_mojo.typing import Vec2, Vec3, Vec5

__all__ = [
    "SOLIMP_DEFAULT",
    "SOLREF_DEFAULT",
    "FRICTION_DEFAULT",
]

SOLIMP_DEFAULT: Vec5 = np.array((0.9, 0.95, 0.001, 0.5, 2))
"""Default value of `solimp` parameters. The values are `d0`, `dwidth`, `width`, `midpoint`, and `power`."""

SOLREF_DEFAULT: Vec2 = np.array((0.02, 1))
"""Default value of `solimp` parameters. The two numbers are `timeconst` and `dampratio`."""

FRICTION_DEFAULT: Vec3 = np.array((1, 0.005, 0.0001))
"""Default friction definition. The values are coefficients for `sliding`, `torsion`, and `rolling`."""
