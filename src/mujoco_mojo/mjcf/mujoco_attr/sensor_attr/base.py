from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, ClassVar

import mujoco
import numpy as np

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import (
    SensorInterp,
    SensorName,
    SignalCategory,
    VecN,
)
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from mujoco_mojo.runtime.signal_manager import SignalManager

logger = get_logger(__name__)

__all__ = ["SensorBase"]


class SensorBase(XMLModel, ABC):
    """MuJoCo can simulate a wide variety of sensors as described in the sensor element below. User sensor types can also be defined, and are evaluated by the callback mjcb_sensor. Sensors do not affect the simulation. Instead their outputs are copied in the array mjData.sensordata and are available for user processing."""

    tag = ""

    attributes = (
        "name",
        "noise",
        "cutoff",
        "nsample",
        "interp",
        "delay",
        "interval",
        "user",
    )

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_SENSOR

    name: SensorName | None = None
    """Name of the sensor."""

    noise: float = 0
    """The standard deviation of the noise model of this sensor. In versions prior to 3.1.4, this would lead to noise being added to the sensors. In release 3.1.4 this feature was removed, see 3.1.4 changelog for a detailed justification. As of subsequent versions, this attrbute serves as a convenient location for saving standard deviation information for later use."""

    cutoff: float = 0
    """When this value is positive, it limits the absolute value of the sensor output. It is also used to normalize the sensor output in the sensor data plots in simulate.cc."""

    nsample: int = 0
    """If nsample is greater than 0, creates a time-indexed ring buffer with nsample slots of sensor data. During state advancement, the current sensor data is appended to the buffer with timestamp time, and the oldest sample is removed. Values in the history buffer can be read via mj_readSensor. A positive nsample is required for both delay and interval features.

    See Delays for details."""

    interp: SensorInterp = SensorInterp.ZOH
    """The interpolation method used when reading from the history buffer. Corresponds to the interp argument in mj_readSensor.

    - zoh: Zero-order hold (piecewise constant).
    - linear: Piecewise linear interpolation.
    - cubic: Cubic spline interpolation (Catmull-Rom).

    The interp value is for advanced use-cases, see Delays for details."""

    delay: float = 0
    """If greater than 0, sensor values in `mjData.sensordata` are read from the history buffer at `time - delay` rather than computed directly. Requires positive nsample, cannot be negative.

    In the most common case, `delay = nsample * timestep`, see Delays for details."""

    interval: tuple[float, float] = (0, 0)
    """This attribute controls how often sensor values are recomputed. It is useful for modeling sensors that have a larger sampling period than the simulation timestep. Requires a history buffer (nsample > 0).

    This attribute is defined by two real-valued numbers, both in units of time, called interval = "period phase". It is possible to only specify the period, in which case the phase is assumed to be 0.

    The period specifies the interval period between recomputations. The default value of 0 has the special meaning "every simulation timestep". Note that the period is not required to be an integer multiple of the timestep. For example, if the simulation timestep is 1.0, and period is 2.5, the sensor will be computed at times 0.0, 3.0, 5.0, 8.0, 10.0, 13.0, ... with the actual interval alternating between 2 and 3 timesteps. period cannot be negative. Note that only period > timestep values make sense; values smaller than or equal to the timestep will not lead to an error but merely cause the sensor to be recomputed at every timestep.

    The phase only takes effect during history buffer initialization in mj_resetData. It specifies the last time that the sensor was computed "before the simulation started" in continuous time (i.e., disregarding the quantization of timesteps). It is useful for precisely controlling the relative phase of sensor computation and simulation time, when interval is used. The default value of 0 has the special meaning "-period", i.e. specifying that the sensor should be computed at the first timestep of the simulation. Continuing our example from earlier, if the timestep is 1.0 and interval is "2.5 -1.5", the sensor will be computed at times 1.0, 4.0, 6.0, 9.0, 11.0, 14.0, etc. phase must be in the range (-period,0]."""

    user: VecN | None = None
    """See User parameters."""

    def request(self, signal_manager: SignalManager | None = None):
        """
        Registers the sensor's output for logging.

        | Dim                       | Description                                                          | Type    |
        |:--------------------------|:---------------------------------------------------------------------|:--------|
        | 1                         | scalar sensors, e.g. touch, rangefinder, jointpos, jointvel          | scalar  |
        | 3                         | cartesian vector sensors, e.g. accelerometer, gyro, force, framepos  | xyzm    |
        | 4, `tag` ends with `quat` | orientation quaternion sensor, e.g. framequat, ballquat              | quat    |
        | other                     | any other sensor, e.g. tactile, user, geomfromto                     | indexed |

        `tactile` and `user` sensors are always `indexed`, even when `dim` is 3 or 4, since their outputs are not cartesian or quaternion by convention.

        * A `scalar` is posted as a single value under `subgroups=(sensor_name,)` with `attr=tag`.
        * An `xyzm` is a cartesian vector, posted as 4 values (`x`, `y`, `z`, and its magnitude `m`) under `subgroups=(sensor_name, tag)`.
        * A `quat` is an orientation quaternion, posted as 4 values (`w`, `x`, `y`, `z`) under `subgroups=(sensor_name, tag)`.
        * An `indexed` output posts `dim` values under `subgroups=(sensor_name, tag)` with `attr` set to `0`-`dim - 1`.

        If `signal_manager` is omitted, the `SignalManager` of the active `RuntimeManager` `with` block is used. If that `RuntimeManager` has no `SignalManager` configured, this is a no-op.
        """
        from mujoco_mojo.runtime.signal_manager import resolve_signal_manager

        signal_manager = resolve_signal_manager(signal_manager)
        if signal_manager is None:
            return

        if self.name is None:
            msg = f"Cannot request telemetry for an unnamed {self.tag}."
            logger.error(msg)
            raise ValueError(msg)

        def sample(state: MjState):
            sid = self.get_id(state.model)

            # find where this sensor's data starts and how long it is
            # (e.g., dim=3 for an accelerometer, dim=4 for a framequat sensor)
            adr = state.model.sensor_adr[sid]
            dim = state.model.sensor_dim[sid]

            # slice the flat sensordata array
            val = state.data.sensordata[adr : adr + dim]

            if dim == 1:
                signal_manager.post(
                    value=float(val[0]),
                    category=SignalCategory.SENSORS,
                    subgroups=(str(self.name),),
                    attr=self.tag,  # scalar values are considered an attr of the parent
                )
            elif dim == 4 and self.tag.endswith("quat"):
                for v, attr in zip(val, "wxyz", strict=True):
                    signal_manager.post(
                        value=float(v),
                        category=SignalCategory.SENSORS,
                        subgroups=(str(self.name), self.tag),
                        attr=attr,
                    )
            elif dim == 3 and self.tag not in ("tactile", "user"):
                full_vec = np.append(val, np.linalg.norm(val))
                for v, attr in zip(full_vec, "xyzm", strict=True):
                    signal_manager.post(
                        value=float(v),
                        category=SignalCategory.SENSORS,
                        subgroups=(str(self.name), self.tag),
                        attr=attr,
                    )
            else:
                for i, v in enumerate(val):
                    signal_manager.post(
                        value=float(v),
                        category=SignalCategory.SENSORS,
                        subgroups=(str(self.name), self.tag),
                        attr=str(i),
                    )

        signal_manager.register_sampler(sample)
