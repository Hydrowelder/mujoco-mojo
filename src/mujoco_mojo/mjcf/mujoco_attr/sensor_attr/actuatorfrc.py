from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import ActuatorName

__all__ = ["SensorActuatorfrc"]


class SensorActuatorfrc(SensorBase):
    """This element creates an actuator force sensor. The quantity being sensed is the scalar actuator force, not the generalized force contributed by the actuator (the latter is the product of the scalar force and the vector of moment arms determined by the transmission). This sensor can be attached to any actuator. Its output is scalar."""

    tag = "actuatorfrc"

    attributes = (
        *SensorBase.attributes,
        "actuator",
    )

    actuator: ActuatorName
    """The actuator whose scalar force output will be sensed. The sensor output is copied from mjData.actuator_force."""
