from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base_collision import SensorCollisionBase

__all__ = ["SensorNormal"]


class SensorNormal(SensorCollisionBase):
    """
    This element creates a sensor that returns the normal direction of the smallest signed distance between the surfaces of two geoms. It is guaranteed to point from the surface of geom1 to the surface of geom2, though note that in the case of penetration, this direction is generally in the opposite direction to that of the centroids. See collision sensors for more details about sensors of this type.

    !!! note "`cutoff` attribute"
        See collision sensors for the sematics of this attribute, which is different than for other sensor categories. If no collision is detected, the normal sensor returns (0, 0, 0), otherwise it returns a normalized direction vector. For this sensor, cutoff does not lead to any clamping.
    """

    tag = "normal"

    attributes = (*SensorCollisionBase.attributes,)
