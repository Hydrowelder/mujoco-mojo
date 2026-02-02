from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import JointName

__all__ = ["SensorJointvel"]


class SensorJointvel(SensorBase):
    """This element creates a joint velocity sensor. It can be attached to scalar joints (slide or hinge). Its output is scalar."""

    tag = "jointvel"

    attributes = (
        *SensorBase.attributes,
        "joint",
    )

    joint: JointName
    """The joint whose velocity will be sensed. Only scalar joints can be referenced here. The sensor output is copied from mjData.qvel."""
