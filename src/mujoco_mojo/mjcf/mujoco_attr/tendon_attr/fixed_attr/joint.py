from __future__ import annotations

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import JointName

__all__ = ["TendonJoint"]


class TendonJoint(XMLModel):
    """This element adds a joint to the computation of the fixed tendon length. The position or angle of each included joint is multiplied by the corresponding coef value, and added up to obtain the tendon length."""

    tag = "joint"

    attributes = ("joint", "coef")

    joint: JointName
    """Name of the joint to be added to the fixed tendon. Only scalar joints (slide and hinge) can be referenced here."""

    coef: float
    """Scalar coefficient multiplying the position or angle of the specified joint."""
