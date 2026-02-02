from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import JointName

__all__ = ["SensorJointactuatorfrc"]


class SensorJointactuatorfrc(SensorBase):
    """This element creates an actuator force sensor, measured at a joint. The quantity being sensed is the generalized force contributed by all actuators to a single scalar joint (hinge or slider). If the joint's actuatorgravcomp attribute is "true", this sensor will also measure contributions by gravity compensation forces (which are added directly to the joint and would not register in the actuatorfrc) sensor. This type of sensor is important when multiple actuators act on a single joint or when a single actuator acts on multiple joints. See Force limits for details."""

    tag = "jointactuatorfrc"

    attributes = (
        *SensorBase.attributes,
        "joint",
    )

    joint: JointName
    """The joint where actuator forces will be sensed. The sensor output is copied from mjData.qfrc_actuator."""
