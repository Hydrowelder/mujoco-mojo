from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import BodyName

__all__ = ["SensorSubtreecom"]


class SensorSubtreecom(SensorBase):
    """This element creates sensor that returns the center of mass of the kinematic subtree rooted at a specified body, in global coordinates."""

    tag = "subtreecom"

    attributes = (
        *SensorBase.attributes,
        "body",
    )

    body: BodyName
    """Name of the body where the kinematic subtree is rooted."""
