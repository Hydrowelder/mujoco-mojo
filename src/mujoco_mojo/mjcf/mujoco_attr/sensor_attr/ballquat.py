from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import JointName

__all__ = ["SensorBallquat"]


class SensorBallquat(SensorBase):
    """This element creates a quaternion sensor for a ball joints. It outputs 4 numbers corresponding to a unit quaternion."""

    tag = "ballquat"

    attributes = (
        *SensorBase.attributes,
        "joint",
    )

    joint: JointName
    """The ball joint whose quaternion is sensed. The sensor output is copied from mjData.qpos."""
