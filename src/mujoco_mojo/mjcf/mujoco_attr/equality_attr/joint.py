from __future__ import annotations

from typing import Optional

import numpy as np

from mujoco_mojo.mjcf.mujoco_attr.equality_attr.equality_base import EqualityBase
from mujoco_mojo.typing import JointName, Vec5

__all__ = ["EqualityJoint"]


class EqualityJoint(EqualityBase):
    """This element constrains the position or angle of one joint to be a quartic polynomial of another joint. Only scalar joint types (slide and hinge) can be used."""

    tag = "joint"
    attributes = EqualityBase.attributes + ("joint1", "joint2", "polycoef")

    joint1: JointName
    """Name of the first joint."""

    joint2: Optional[JointName] = None
    """Name of the second joint. If this attribute is omitted, the first joint is fixed to a constant."""

    polycoef: Vec5 = np.array((0, 1, 0, 0, 0))
    """Coefficients a0...a4 of the quartic polynomial. If the joint values of joint1 and joint2 are respectively yy and xx, and their reference positions (corresponding to the joint values in the initial model configuration) are y0 and x0, the constraint is:

    > `y-y0 = a0 + a1(x-x0) + a2(x-x0)^2 + a3(x-x0)^3 + a4(x-x0)^4`

    Omitting joint2 is equivalent to setting x=x0, in which case the constraint is y=y0+a0.
    """
