from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import SiteName

__all__ = ["SensorVelocimeter"]


class SensorVelocimeter(SensorBase):
    """This element creates a 3-axis velocimeter. The sensor is mounted at a site, and has the same position and orientation as the site frame. This sensor outputs three numbers, which are the linear velocity of the site in local coordinates."""

    tag = "velocimeter"

    attributes = (
        *SensorBase.attributes,
        "site",
    )

    site: SiteName
    """Site where the sensor is mounted. The velocimeter is centered and aligned with the site local frame."""
