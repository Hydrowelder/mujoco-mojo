from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import JointName

__all__ = ["SensorJointlimitvel"]


class SensorJointlimitvel(SensorBase):
    """This element creates a joint limit sensor for velocity."""

    tag = "jointlimitvel"

    attributes = (
        *SensorBase.attributes,
        "joint",
    )

    joint: JointName
    """The joint whose limit is sensed. The sensor output is copied from mjData.efc_vel. If the joint limit is not violated, the result is 0."""
