from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import SiteName

__all__ = ["SensorAccelerometer"]


class SensorAccelerometer(SensorBase):
    """
    This element creates a 3-axis accelerometer. The sensor is mounted at a site, and has the same position and orientation as the site frame. This sensor outputs three numbers, which are the linear acceleration of the site (including gravity) in local coordinates.

    The presence of this sensor in a model triggers a call to mj_rnePostConstraint during sensor computation.
    """

    tag = "accelerometer"

    attributes = (
        *SensorBase.attributes,
        "site",
    )

    site: SiteName
    """Site defining the active sensor zone."""
