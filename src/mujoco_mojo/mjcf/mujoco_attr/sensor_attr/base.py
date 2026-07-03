from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any, ClassVar

import mujoco
import numpy as np
from pydantic import PrivateAttr

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.transmission_units import (
    actuator_transmission_metadata,
    joint_type_metadata,
    sensor_referenced_joint_type,
)
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import (
    SensorInterp,
    SensorName,
    SignalCategory,
    VecN,
)
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.signal_metadata import (
    Dimension,
    angular_rate_metadata,
    dim,
    dimensionless_metadata,
    merge_signal_metadata,
)

logger = get_logger(__name__)

__all__ = ["SensorBase"]

if TYPE_CHECKING:
    from mujoco_mojo.runtime.signal_manager import SignalManager

# tags with a fixed, unambiguous physical quantity regardless of what the sensor references
_TAG_METADATA: dict[str, dict[str, str]] = {
    "accelerometer": dim(Dimension.ACCELERATION),
    "velocimeter": dim(Dimension.VELOCITY),
    "gyro": angular_rate_metadata(),
    "force": dim(Dimension.FORCE),
    "torque": {**dim(Dimension.TORQUE), "quantity": "torque"},
    "framepos": dim(Dimension.LENGTH),
    "subtreecom": dim(Dimension.LENGTH),
    "framelinvel": dim(Dimension.VELOCITY),
    "subtreelinvel": dim(Dimension.VELOCITY),
    "frameangvel": angular_rate_metadata(),
    "ballangvel": angular_rate_metadata(),
    "framelinacc": dim(Dimension.ACCELERATION),
    "frameangacc": angular_rate_metadata(per="second ** 2"),
    "subtreeangmom": dim(Dimension.ANGULAR_MOMENTUM),
    "e_kinetic": dim(Dimension.ENERGY),
    "e_potential": dim(Dimension.ENERGY),
    "touch": dim(Dimension.FORCE),
    "distance": dim(Dimension.LENGTH),
    "rangefinder": dim(Dimension.LENGTH),
    "fromto": dim(Dimension.LENGTH),
    "tendonpos": dim(Dimension.LENGTH),
    "tendonvel": dim(Dimension.VELOCITY),
    "tendonlimitvel": dim(Dimension.VELOCITY),
    "tendonactuatorfrc": dim(Dimension.FORCE),
    "tendonlimitfrc": dim(Dimension.FORCE),
    "clock": dim(Dimension.TIME),
    "framexaxis": dimensionless_metadata(),
    "frameyaxis": dimensionless_metadata(),
    "framezaxis": dimensionless_metadata(),
    "normal": dimensionless_metadata(),
    "insidesite": dimensionless_metadata(),
}

# tags whose physical quantity depends on the referenced joint's type (hinge vs. slide),
# resolved at sample time via sensor_referenced_joint_type(); maps tag -> joint_type_metadata() key
_JOINT_REF_TAGS: dict[str, str] = {
    "jointpos": "pos",
    "jointlimitpos": "pos",
    "jointvel": "vel",
    "jointlimitvel": "vel",
    "jointactuatorfrc": "frc",
    "jointlimitfrc": "frc",
}

# tags whose physical quantity depends on the referenced actuator's transmission, resolved at
# sample time via actuator_transmission_metadata(); maps tag -> that function's result key
_ACTUATOR_REF_TAGS: dict[str, str] = {
    "actuatorpos": "length",
    "actuatorvel": "velocity",
    "actuatorfrc": "force",
}


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

    _metadata_resolved: bool = PrivateAttr(default=False)
    """Whether `_resolved_metadata_cache` has been computed yet (None is itself a valid resolution, so a plain `is None` check can't distinguish "unresolved" from "resolved to no metadata")."""

    _resolved_metadata_cache: dict[str, str] | None = PrivateAttr(default=None)
    """Cached built-in metadata for this sensor's tag, resolved once on first sample."""

    def _resolve_builtin_metadata(self, state: MjState) -> dict[str, str] | None:
        """Resolves and caches this sensor's built-in dimension/unit metadata, based on its tag (and, for joint-/actuator-referencing tags, the referenced object's type)."""
        if self._metadata_resolved:
            return self._resolved_metadata_cache

        if self.tag in _TAG_METADATA:
            builtin = _TAG_METADATA[self.tag]
        elif self.tag in _JOINT_REF_TAGS:
            sid = self.get_id(state.model)
            jnt_type = sensor_referenced_joint_type(state, sid)
            builtin = (
                joint_type_metadata(jnt_type)[_JOINT_REF_TAGS[self.tag]]
                if jnt_type is not None
                else None
            )
        elif self.tag in _ACTUATOR_REF_TAGS:
            sid = self.get_id(state.model)
            actuator_id = int(state.model.sensor_objid[sid])
            trans_meta = actuator_transmission_metadata(state, actuator_id)
            builtin = (
                trans_meta[_ACTUATOR_REF_TAGS[self.tag]]
                if trans_meta is not None
                else None
            )
        elif self.tag.endswith("quat"):
            builtin = dimensionless_metadata()
        else:
            builtin = None

        self._resolved_metadata_cache = builtin
        self._metadata_resolved = True
        return builtin

    def request(
        self,
        signal_manager: SignalManager | None = None,
        metadata: dict[str, dict[str, Any]] | None = None,
    ):
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

        Each signal is tagged with built-in `dimension`/`unit` metadata where the sensor's physical quantity is unambiguous (e.g. `accelerometer` is tagged as an acceleration). For `jointpos`/`jointvel`/`jointactuatorfrc`/`jointlimit*`, the metadata is resolved from the referenced joint's type (angle/length); for `actuatorpos`/`actuatorvel`/`actuatorfrc`, from the referenced actuator's transmission. No built-in default is applied for sensors whose unit is genuinely unspecified by MuJoCo (`magnetometer`, `tactile`, `user`, `plugin`, `camprojection`, `contact`) or for actuator-referencing tags on a SITE/BODY/SLIDERCRANK-transmission actuator. Supply `metadata` yourself for those if you know it.

        If `signal_manager` is omitted, the `SignalManager` of the active `RuntimeManager` `with` block is used. If that `RuntimeManager` has no `SignalManager` configured, this is a no-op.

        Args:
            signal_manager: The signal manager to register the sampler with.
            metadata: Metadata overriding or extending the built-in default for this sensor's tag.

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
            meta = merge_signal_metadata(
                self._resolve_builtin_metadata(state),
                self.tag,
                metadata,
                unit_system=state.us,
            )

            # find where this sensor's data starts and how long it is
            # (e.g., sensor_dim=3 for an accelerometer, sensor_dim=4 for a framequat sensor)
            adr = state.model.sensor_adr[sid]
            sensor_dim = state.model.sensor_dim[sid]

            # slice the flat sensordata array
            val = state.data.sensordata[adr : adr + sensor_dim]

            if sensor_dim == 1:
                signal_manager.post(
                    value=float(val[0]),
                    category=SignalCategory.SENSORS,
                    subgroups=(str(self.name),),
                    attr=self.tag,  # scalar values are considered an attr of the parent
                    metadata=meta,
                )
            elif sensor_dim == 4 and self.tag.endswith("quat"):
                for v, attr in zip(val, "wxyz", strict=True):
                    signal_manager.post(
                        value=float(v),
                        category=SignalCategory.SENSORS,
                        subgroups=(str(self.name), self.tag),
                        attr=attr,
                        metadata=meta,
                    )
            elif sensor_dim == 3 and self.tag not in ("tactile", "user"):
                full_vec = np.append(val, np.linalg.norm(val))
                for v, attr in zip(full_vec, "xyzm", strict=True):
                    signal_manager.post(
                        value=float(v),
                        category=SignalCategory.SENSORS,
                        subgroups=(str(self.name), self.tag),
                        attr=attr,
                        metadata=meta,
                    )
            else:
                for i, v in enumerate(val):
                    signal_manager.post(
                        value=float(v),
                        category=SignalCategory.SENSORS,
                        subgroups=(str(self.name), self.tag),
                        attr=str(i),
                        metadata=meta,
                    )

        signal_manager.register_sampler(sample)
