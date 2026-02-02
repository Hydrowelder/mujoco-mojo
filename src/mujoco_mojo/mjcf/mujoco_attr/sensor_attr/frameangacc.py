from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import SensorAttachableName, SensorObjectType

__all__ = ["SensorFrameangacc"]


class SensorFrameangacc(SensorBase):
    """
    This element creates a sensor that returns the 3D angular acceleration of the spatial frame of the object, in global coordinates.

    The presence of this sensor in a model triggers a call to mj_rnePostConstraint during sensor computation.
    """

    tag = "frameangacc"

    attributes = (*SensorBase.attributes, "objtype", "objname")

    objtype: SensorObjectType
    """The type of object to which the sensor is attached. This must be an object type that has a spatial frame. "body" refers to the inertial frame of the body, while "xbody" refers to the regular frame of the body (usually centered at the joint with the parent body)."""

    objname: SensorAttachableName
    """The name of the object to which the sensor is attached."""
