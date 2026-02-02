from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import BodyName

__all__ = ["SensorSubtreelinvel"]


class SensorSubtreelinvel(SensorBase):
    """
    This element creates sensor that returns the linear velocity of the center of mass of the kinematic subtree rooted at a specified body, in global coordinates.

    The presence of this sensor in a model triggers a call to mj_subtreeVel during sensor computation.
    """

    tag = "subtreelinvel"

    attributes = (
        *SensorBase.attributes,
        "body",
    )

    body: BodyName
    """Name of the body where the kinematic subtree is rooted."""
