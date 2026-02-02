from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import SensorAttachableName, SensorObjectType, SiteName

__all__ = ["SensorInsidesite"]


class SensorInsidesite(SensorBase):
    """This element creates a sensor that returns 1 if the given object is inside a site, 0 otherwise. It is useful for triggering events in surrounding environment logic. See example model."""

    tag = "insidesite"

    attributes = (*SensorBase.attributes,)

    objtype: SensorObjectType
    """The type of the object whose position will be queried. See framepos."""

    objname: SensorAttachableName
    """The name of the object whose position will be queried. See framepos."""

    site: SiteName
    """The site defining the volume used for the inside check."""
