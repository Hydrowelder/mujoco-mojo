from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import ActuatorName

__all__ = ["SensorActuatorvel"]


class SensorActuatorvel(SensorBase):
    """This element creates an actuator velocity sensor. This sensor can be attached to any actuator. Its output is scalar."""

    tag = "actuatorvel"

    attributes = (
        *SensorBase.attributes,
        "actuator",
    )

    actuator: ActuatorName
    """The actuator whose transmission's velocity will be sensed. The sensor output is copied from mjData.actuator_velocity."""
