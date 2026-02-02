from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import ActuatorName

__all__ = ["SensorActuatorpos"]


class SensorActuatorpos(SensorBase):
    """This element creates an actuator length sensor. Recall that each actuator has a transmission which has length. This sensor can be attached to any actuator. Its output is scalar."""

    tag = "actuatorpos"

    attributes = (
        *SensorBase.attributes,
        "actuator",
    )

    actuator: ActuatorName
    """The actuator whose transmission's length will be sensed. The sensor output is copied from mjData.actuator_length."""
