from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import SiteName

__all__ = ["SensorTorque"]


class SensorTorque(SensorBase):
    """
    This element creates a 3-axis torque sensor. This is similar to the force sensor above, but measures torque rather than force.

    The presence of this sensor in a model triggers a call to mj_rnePostConstraint during sensor computation.
    """

    tag = "torque"

    attributes = (
        *SensorBase.attributes,
        "site",
    )

    site: SiteName
    """Site where the sensor is mounted. The measured interaction torque is between the body where the site is defined and its parent body."""
