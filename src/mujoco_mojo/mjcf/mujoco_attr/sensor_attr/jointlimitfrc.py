from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import JointName

__all__ = ["SensorJointlimitfrc"]


class SensorJointlimitfrc(SensorBase):
    """This element creates a joint limit sensor for constraint force."""

    tag = "jointlimitfrc"

    attributes = (
        *SensorBase.attributes,
        "joint",
    )

    joint: JointName
    """The joint whose limit is sensed. The sensor output is copied from mjData.efc_force. If the joint limit is not violated, the result is 0."""
