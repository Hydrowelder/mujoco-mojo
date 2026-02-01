from __future__ import annotations

from typing import Optional

import numpy as np

from mujoco_mojo.mjcf.mujoco_attr.equality_attr.equality_base import EqualityBase
from mujoco_mojo.typing import TendonName, Vec5

__all__ = ["EqualityTendon"]


class EqualityTendon(EqualityBase):
    """This element constrains the position or angle of one joint to be a quartic polynomial of another joint. Only scalar joint types (slide and hinge) can be used."""

    tag = "tendon"
    attributes = EqualityBase.attributes + ("tendon1", "tendon2", "polycoef")

    tendon1: TendonName
    """Name of the first tendon."""

    tendon2: Optional[TendonName] = None
    """Name of the second tendon. If this attribute is omitted, the first tendon is fixed to a constant."""

    polycoef: Vec5 = np.array((0, 1, 0, 0, 0))
    """Same as in the EqualityJoint element, but applied to tendon lengths instead of joint positions.
    """
