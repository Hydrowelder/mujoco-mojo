from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import JointName

__all__ = ["SensorBallangvel"]


class SensorBallangvel(SensorBase):
    """This element creates a ball joint angular velocity sensor. It outputs 3 numbers corresponding to the angular velocity of the joint. The norm of that vector is the rotation speed in rad/s and the direction is the axis around which the rotation takes place."""

    tag = "ballangvel"

    attributes = (
        *SensorBase.attributes,
        "joint",
    )

    joint: JointName
    """The ball joint whose angular velocity is sensed. The sensor output is copied from mjData.qvel."""
