from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import GeomName, MeshName

__all__ = ["SensorTactile"]


class SensorTactile(SensorBase):
    """The tactile sensor returns the maximum penetration depth and the sliding velocities in the tangent frame at given points between the geom associated with the sensor and the SDF geoms in contact with it. The sensor is associated with a geom and a mesh. It is activated by the contact between its associated geom and other geoms. The vertices of the mesh, when positioned in the geom frame, are the points at which sensor values are computed, so the dimension of the output is 3 times the number of vertices in the mesh. The mesh must have 3 normal vectors per vertex, which are used to compute the tangent frame. If the penetration depth is positive (no contact), then all values are 0 for the corresponding vertex. Only contacts with geoms of type SDF contribute to the sensor output. The sensor can be visualized by enabling the visualization of contact points."""

    tag = "tactile"

    attributes = ("name", "user", "geom", "mesh")

    geom: GeomName
    """Name of the geom to associate the tactile sensor with."""

    mesh: MeshName
    """Name of the mesh to associate the tactile sensor with. The mesh will be created by the sensor."""
