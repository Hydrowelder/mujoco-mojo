from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import SiteName

__all__ = ["SensorRangefinder"]


class SensorRangefinder(SensorBase):
    """This element creates a rangefinder. It measures the distance to the nearest geom surface, along the ray defined by the positive Z-axis of the sensor site. If the ray does not intersect any geom surface, the sensor output is -1. If the origin of the ray is inside a geom, the surface is still sensed (but not the inner volume). Geoms attached to the same body as the sensor site are excluded. Invisible geoms, defined as geoms whose rgba (or whose material rgba) has alpha=0, are also excluded. Note however that geoms made invisible in the visualizer by disabling their geom group are not excluded; this is because sensor calculations are independent of the visualizer."""

    tag = "rangefinder"

    attributes = (
        *SensorBase.attributes,
        "site",
    )

    site: SiteName
    """The site where the sensor is attached."""
