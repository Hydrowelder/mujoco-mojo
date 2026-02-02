from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import SiteName

__all__ = ["SensorMagnetometer"]


class SensorMagnetometer(SensorBase):
    """This element creates a magnetometer. It measures the magnetic flux at the sensor site position, expressed in the sensor site frame. The output is a 3D vector."""

    tag = "magnetometer"

    attributes = (
        *SensorBase.attributes,
        "site",
    )

    site: SiteName
    """The site where the sensor is attached."""
