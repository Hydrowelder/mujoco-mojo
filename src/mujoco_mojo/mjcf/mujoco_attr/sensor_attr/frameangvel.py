from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import SensorAttachableName, SensorObjectType

__all__ = ["SensorFrameangvel"]


class SensorFrameangvel(SensorBase):
    """This element creates a sensor that returns the 3D angular velocity of the spatial frame of the object, in global coordinates."""

    tag = "frameangvel"

    attributes = (*SensorBase.attributes, "objtype", "objname", "reftype", "refname")

    objtype: SensorObjectType
    """The type of object to which the sensor is attached. This must be an object type that has a spatial frame. "body" refers to the inertial frame of the body, while "xbody" refers to the regular frame of the body (usually centered at the joint with the parent body)."""

    objname: SensorAttachableName
    """The name of the object to which the sensor is attached."""

    reftype: SensorObjectType
    """The type of object to which the frame-of-reference is attached. The semantics are identical to the objtype attribute. If reftype and refname are given, the sensor values will be measured with respect to this frame. If they are not given, sensor values will be measured with respect to the global frame."""

    refname: SensorAttachableName | None = None
    """The name of the object to which the frame-of-reference is attached."""
