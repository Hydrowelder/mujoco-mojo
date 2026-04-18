from __future__ import annotations

from pydantic import model_validator

from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import CameraName, RangefinderData, SiteName

__all__ = ["SensorRangefinder"]


class SensorRangefinder(SensorBase):
    """
    This element creates a rangefinder.

    * If associated with a site, it measures the distance to the nearest geom surface, along the ray defined by the positive Z-axis of the site.
    * If associated with a camera, it outputs one distance measurement for each pixel in the camera image. Note that cameras face the negative Z-axis of their frame. The number of measurements in this case is equal to product of the camera's width and height resolutions.

    If a ray does not intersect any geom surface, the sensor output is -1. If the origin of the ray is inside a geom, the surface is still detected. Geoms attached to the same body as the sensor site/camera are excluded. Invisible geoms, defined as geoms whose rgba (or whose material rgba) has alpha=0, are also excluded. Note however that geoms made invisible in the visualizer by disabling their geom group are not excluded; this is because sensor calculations are independent of the visualizer.

    """

    tag = "rangefinder"

    attributes = (
        *SensorBase.attributes,
        "data",
        "site",
        "camera",
    )

    __exclusive_groups__ = (("site", "camera"),)

    data: tuple[RangefinderData, ...] = (RangefinderData.DIST,)
    """By default, the rangefinder outputs a distance measurement, as described above. However, it is also possible to specify a set of output data fields. The data attribute can contain multiple sequential data types, as long as the relative order—as listed above—is maintained. For example, data = "dist point normal" will return 7 numbers per ray, while data = "point origin" is an error because origin must come before point.

    * dist real(1): The distance from the ray origin to the nearest geom surface, -1 if no surface was hit. If this data type is included, rays will be visualized as lines.
    * dir real(3): Normalized direction of the ray, or (0, 0, 0) if no surface was hit.
    * origin real(3): The point from which the ray emanates (global frame). For sites and perspective cameras, this is the site/camera xpos. However for orthographic cameras, ray origins are spatially distributed along the image plane.
    * point real(3): The point where the ray intersects the nearest geom surface in the global frame, or (0, 0, 0) if no surface was hit. If this data type is included, intersection points will be visualized as spheres.
    * normal real(3): The geom surface normal at the point where the ray intersects it, in the global frame, or (0, 0, 0) if no surface was hit. Note that normals always point towards the outside of the geom surface, regardless of the ray origin. If this data type is included along with either dist or point, normals will be visualized as arrows at the intersection points.
    * depth real(1): The distance of the hit point from the camera plane, -1 if no surface was hit. Note that this depth semantic corresponds to depth images in the computer graphics sense."""

    site: SiteName | None = None
    """The site where the sensor is attached."""

    camera: CameraName | None = None
    """The camera where the sensor is attached."""

    @model_validator(mode="after")
    def coerce_and_validate_data(self) -> SensorRangefinder:
        """
        Silently deduplicates and reorders the data sequence to match the required MuJoCo spec: dist -> dir -> origin -> point -> normal -> depth.
        """
        if not self.data:
            self.data = (RangefinderData.DIST,)
            return self

        _DATA_RANK: dict[RangefinderData, int] = {
            RangefinderData.DIST: 0,
            RangefinderData.DIR: 1,
            RangefinderData.ORIGIN: 2,
            RangefinderData.POINT: 3,
            RangefinderData.NORMAL: 4,
            RangefinderData.DEPTH: 5,
        }

        # Deduplicate and sort based on the defined rank
        unique_fields = set(self.data)
        sorted_fields = sorted(unique_fields, key=lambda x: _DATA_RANK.get(x, 99))

        # Update the field with the correctly ordered tuple
        self.data = tuple(sorted_fields)
        return self
