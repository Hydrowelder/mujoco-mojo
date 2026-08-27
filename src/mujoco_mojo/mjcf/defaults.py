from __future__ import annotations

import numpy as np

from mujoco_mojo.typing import Angle, EulerSeq, Vec2, Vec5

__all__ = [
    "FRICTION_DEFAULT",
    "SOLIMP_DEFAULT",
    "SOLREF_DEFAULT",
]

SOLIMP_DEFAULT: Vec5 = np.array((0.9, 0.95, 0.001, 0.5, 2))
"""Default value of `solimp` parameters. The values are `d0`, `dwidth`, `width`, `midpoint`, and `power`."""

SOLREF_DEFAULT: Vec2 = np.array((0.02, 1))
"""Default value of `solimp` parameters. The two numbers are `timeconst` and `dampratio`."""

FRICTION_DEFAULT: Vec5 = np.array((1, 1, 0.005, 0.0001, 0.0001))
"""Default friction definition. The values are coefficients for `sliding`, `torsion`, and `rolling`."""

DEFAULT_ANGLE = Angle.DEGREE
"""Default angle convention."""

DEFAULT_EULERSEQ = EulerSeq.xyz
"""Default Euler angle sequence."""
