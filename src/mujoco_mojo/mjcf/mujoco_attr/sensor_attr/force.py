from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import SiteName

__all__ = ["SensorForce"]


class SensorForce(SensorBase):
    """
    This element creates a 3-axis force sensor. The sensor outputs three numbers, which are the interaction force between a child and a parent body, expressed in the site frame defining the sensor. The convention is that the site is attached to the child body, and the force points from the child towards the parent. The computation here takes into account all forces acting on the system, including contacts as well as external perturbations. Using this sensor often requires creating a dummy body welded to its parent (i.e., having no joint elements).

    The presence of this sensor in a model triggers a call to mj_rnePostConstraint during sensor computation.
    """

    tag = "force"

    attributes = (
        *SensorBase.attributes,
        "site",
    )

    site: SiteName
    """Site where the sensor is mounted. The measured interaction force is between the body where the site is defined and its parent body, and points from the child towards the parent. The physical sensor being modeled could of course be attached to the parent body, in which case the sensor data would have the opposite sign. Note that each body has a unique parent but can have multiple children, which is why we define this sensor through the child rather than the parent body in the pair."""
