from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import TendonName

__all__ = ["SensorTendonactuatorfrc"]


class SensorTendonactuatorfrc(SensorBase):
    """This element creates an actuator force sensor, measured at a tendon. The quantity being sensed is the total force contributed by all actuators to a single tendon. This type of sensor is important when multiple actuators act on a single tendon. See Force limits for details."""

    tag = "tendonactuatorfrc"

    attributes = (
        *SensorBase.attributes,
        "tendon",
    )

    tendon: TendonName
    """The tendon where actuator forces will be sensed."""
