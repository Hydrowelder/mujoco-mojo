from __future__ import annotations

from typing import ClassVar

import mujoco

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import (
    SensorName,
    VecN,
)

__all__ = ["SensorBase"]


class SensorBase(XMLModel):
    """MuJoCo can simulate a wide variety of sensors as described in the sensor element below. User sensor types can also be defined, and are evaluated by the callback mjcb_sensor. Sensors do not affect the simulation. Instead their outputs are copied in the array mjData.sensordata and are available for user processing."""

    tag = ""

    attributes = ("name", "noise", "cutoff", "user")

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_SENSOR

    name: SensorName | None = None
    """Name of the sensor."""

    noise: float = 0
    """The standard deviation of the noise model of this sensor. In versions prior to 3.1.4, this would lead to noise being added to the sensors. In release 3.1.4 this feature was removed, see 3.1.4 changelog for a detailed justification. As of subsequent versions, this attrbute serves as a convenient location for saving standard deviation information for later use."""

    cutoff: float = 0
    """When this value is positive, it limits the absolute value of the sensor output. It is also used to normalize the sensor output in the sensor data plots in simulate.cc."""

    user: VecN | None = None
    """See User parameters."""
