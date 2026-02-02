from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base_collision import SensorCollisionBase

__all__ = ["SensorFromto"]


class SensorFromto(SensorCollisionBase):
    """
    This element creates a sensor that returns the segment defining the smallest signed distance between the surfaces of two geoms. The segment is defined by 6 numbers (x1, y1, z1, x2, y2, z2) corresponding to two points in the world frame. (x1, y1, z1) is on the surface of geom1, (x2, y2, z2) is on the surface of geom2. When this sensor is present and the mjVIS_RANGEFINDER visualization flag is set, segments will be visualized as rangefinder rays. See collision sensors for more details about sensors of this type.

    !!! note "`cutoff` attribute"
        See collision sensors for the sematics of this attribute, which is different than for other sensor categories. If no collision is detected, the fromto sensor returns 6 zeros. For this sensor, cutoff does not lead to any clamping.
    """

    tag = "fromto"

    attributes = (*SensorCollisionBase.attributes,)
