from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base_collision import SensorCollisionBase

__all__ = ["SensorDistance"]


class SensorDistance(SensorCollisionBase):
    """
    This element creates a sensor that returns the smallest signed distance between the surfaces of two geoms. See collision sensors for more details about sensors of this type.

    !!! note "`cutoff` attribute"
        See collision sensors for the sematics of this attribute, which is different than for other sensor categories. If no collision is detected, the distance sensor returns the cutoff value, so in this case cutoff acts as a maximum clipping value, in addition to the special semantics.
    """

    tag = "distance"

    attributes = (*SensorCollisionBase.attributes,)
