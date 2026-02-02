from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import JointName

__all__ = ["SensorJointlimitpos"]


class SensorJointlimitpos(SensorBase):
    """This element creates a joint limit sensor for position."""

    tag = "jointlimitpos"

    attributes = (
        *SensorBase.attributes,
        "joint",
    )

    joint: JointName
    """The joint whose limit is sensed. The sensor output equals mjData.efc_pos - mjData.efc_margin for the corresponding limit constraint. Note that the result is negative if the limit is violated, regardless of which side of the limit is violated. If both sides of the limit are violated simultaneously, only the first component is returned. If there is no violation, the result is 0."""
