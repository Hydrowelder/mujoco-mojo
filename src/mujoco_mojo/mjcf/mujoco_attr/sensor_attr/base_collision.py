from __future__ import annotations

from pydantic import model_validator

from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import (
    BodyName,
    GeomName,
)
from mujoco_mojo.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["SensorCollisionBase"]


class SensorCollisionBase(SensorBase):
    """
    This is a base class for collision sensors.

    MuJoCo can simulate a wide variety of sensors as described in the sensor element below. User sensor types can also be defined, and are evaluated by the callback mjcb_sensor. Sensors do not affect the simulation. Instead their outputs are copied in the array mjData.sensordata and are available for user processing.
    """

    tag = ""

    attributes = (*SensorBase.attributes, "geom1", "geom2", "body1", "body2")

    cutoff: float = 0  # included again for the change in docstring
    """For most sensors, the cutoff attribute simply defines a clipping operation on sensor values. For collision sensors, it defines the maximum distance at which collisions will be detected, corresponding to the dismax argument of mj_geomDistance. For example, at the default value of 0, only negative distances (corresponding to geom-geom penetration) will be reported by sensor/distance. In order to determine collision properties of non-penetrating geom pairs, a positive cutoff is required.

    !!! warning "different (correct) behavior under `nativeccd`"
        As explained in Collision Detection, distances are inaccurate when using the legacy CCD pipeline, and its use is discouraged.
    """

    geom1: GeomName | None = None
    """For all 3 collision sensor types, the two colliding geoms can be specified explicitly using the geom1 and geom2 attributes or implicitly, using body1, body2. In the latter case the sensor will iterate over all geoms of the specified body or bodies (mixed specification like geom1, body2 are allowed), and select the collision with the smallest signed distance."""

    geom2: GeomName | None = None
    """For all 3 collision sensor types, the two colliding geoms can be specified explicitly using the geom1 and geom2 attributes or implicitly, using body1, body2. In the latter case the sensor will iterate over all geoms of the specified body or bodies (mixed specification like geom1, body2 are allowed), and select the collision with the smallest signed distance."""

    body1: BodyName | None = None
    """For all 3 collision sensor types, the two colliding geoms can be specified explicitly using the geom1 and geom2 attributes or implicitly, using body1, body2. In the latter case the sensor will iterate over all geoms of the specified body or bodies (mixed specification like geom1, body2 are allowed), and select the collision with the smallest signed distance."""

    body2: BodyName | None = None
    """For all 3 collision sensor types, the two colliding geoms can be specified explicitly using the geom1 and geom2 attributes or implicitly, using body1, body2. In the latter case the sensor will iterate over all geoms of the specified body or bodies (mixed specification like geom1, body2 are allowed), and select the collision with the smallest signed distance."""

    @model_validator(mode="after")
    def validate_targets(self):
        if (self.geom1 is None) == (self.body1 is None):
            msg = "Exactly one of geom1 or body1 must be specified"
            logger.error(msg)
            raise ValueError(msg)

        if (self.geom2 is None) == (self.body2 is None):
            msg = "Exactly one of geom2 or body2 must be specified"
            logger.error(msg)
            raise ValueError(msg)

        return self
