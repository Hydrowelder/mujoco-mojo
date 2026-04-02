from __future__ import annotations

from typing import ClassVar

import mujoco

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.runtime.results_manager import ResultsManager
from mujoco_mojo.typing import (
    SensorName,
    VecN,
)
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

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

    def request(self, results_manager: ResultsManager):
        """Registers the sensor's output for logging."""
        if self.name is None:
            msg = f"Cannot request telemetry for an unnamed {self.tag}."
            logger.error(msg)
            raise ValueError(msg)

        def harvest(mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
            sid = self.get_id(mj_model)

            # find where this sensor's data starts and how long it is
            # (e.g., dim=3 for an accelerometer, dim=6 for a force/torque sensor)
            adr = mj_model.sensor_adr[sid]
            dim = mj_model.sensor_dim[sid]

            # slice the flat sensordata array
            val = mj_data.sensordata[adr : adr + dim]

            # post to telemetry
            if dim == 1:
                # scalar sensors (like a touch sensor)
                results_manager.post(str(self.name), val[0])
            else:
                # vector sensors (like IMUs or Force sensors)
                # use numerical suffixes since SensorBase doesn't know the component names
                for i in range(dim):
                    results_manager.post(f"{self.name}_{i}", val[i])

        results_manager.schedule_harvest_task(harvest)
