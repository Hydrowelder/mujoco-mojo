from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

import mujoco
import numpy as np
from pydantic import PrivateAttr

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.transmission_units import (
    actuator_transmission_metadata,
)
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import (
    ActuatorControlLimited,
    ActuatorForceLimited,
    ActuatorName,
    JointName,
    SensorInterp,
    SignalCategory,
    SiteName,
    TendonName,
    Vec2,
    Vec3,
    Vec6,
    VecN,
)
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.signal_metadata import merge_signal_metadata

if TYPE_CHECKING:
    from mujoco_mojo.runtime.signal_manager import SignalManager

logger = get_logger(__name__)

__all__ = ["ActuatorBase"]


class ActuatorBase(XMLModel, ABC):
    """This element creates a base class for actuators, this is not intended for use in the SDK apart from inheritance."""

    tag = ""

    attributes = (
        "name",
        "class_",
        "group",
        "nsample",
        "interp",
        "delay",
        "ctrllimited",
        "forcelimited",
        "ctrlrange",
        "forcerange",
        "lengthrange",
        "gear",
        "cranklength",
        "damping",
        "armature",
        "joint",
        "jointinparent",
        "tendon",
        "cranksite",
        "slidersite",
        "site",
        "refsite",
        "user",
    )

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_ACTUATOR

    name: ActuatorName | None = None
    """Element name. See Naming elements."""

    class_: str | None = None
    """Active defaults class. See Default settings."""

    group: int = 0
    """Integer group to which the actuator belongs. This attribute can be used for custom tags. It is also used by the visualizer to enable and disable the rendering of entire groups of actuators."""

    nsample: int = 0
    """If greater than 0, creates a time-indexed ring buffer with nsample samples of this actuator's `ctrl` history. During state advancement, the current control input is appended to the buffer with timestamp `time`, and the oldest sample is removed. Values in the history buffer can be read via mj_readCtrl.

    A positive nsample is required for delay."""

    interp: SensorInterp = SensorInterp.ZOH
    """The interpolation method used when reading from the history buffer. Corresponds to the interp argument in mj_readCtrl.

    - zoh: Zero-order hold (piecewise constant).
    - linear: Piecewise linear interpolation.
    - cubic: Cubic spline interpolation (Catmull-Rom)."""

    delay: float = 0
    """If greater than 0, then during the forward dynamics, instead of reading the control input to the actuator from `mjData.ctrl`, the control input is read from the history buffer using mj_readCtrl. Requires a history buffer (nsample > 0).

    In the most common case, `delay = nsample * timestep`."""

    ctrllimited: ActuatorControlLimited = ActuatorControlLimited.AUTO
    """If true, the control input to this actuator is automatically clamped to ctrlrange at runtime. If false, control input clamping is disabled. If "auto" and autolimits is set in compiler, control clamping will automatically be set to true if ctrlrange is defined without explicitly setting this attribute to "true". Note that control input clamping can also be globally disabled with the clampctrl attribute of option/flag."""

    forcelimited: ActuatorForceLimited = ActuatorForceLimited.AUTO
    """If true, the force output of this actuator is automatically clamped to forcerange at runtime. If false, force clamping is disabled. If "auto" and autolimits is set in compiler, force clamping will automatically be set to true if forcerange is defined without explicitly setting this attribute to "true"."""

    ctrlrange: Vec2 = np.array((0, 0))
    """Range for clamping the control input. The first value must be smaller than the second value.

    Setting this attribute without specifying ctrllimited is an error if autolimits is "false" in compiler."""

    forcerange: Vec2 = np.array((0, 0))
    """Range for clamping the force output. The first value must be no greater than the second value.

    Setting this attribute without specifying forcelimited is an error if autolimits is "false" in compiler."""

    lengthrange: Vec2 = np.array((0, 0))
    """Range of feasible lengths of the actuator's transmission. See Length Range."""

    gear: Vec6 = np.array((1, 0, 0, 0, 0, 0))
    """This attribute scales the length (and consequently moment arms, velocity and force) of the actuator, for all transmission types. It is different from the gain in the force generation mechanism, because the gain only scales the force output and does not affect the length, moment arms and velocity. For actuators with scalar transmission, only the first element of this vector is used. The remaining elements are needed for joint, jointinparent and site transmissions where this attribute is used to specify 3D force and torque axes."""

    damping: Vec3 = np.array((0, 0, 0))
    """Viscous damping coefficients, contributed by the actuator to its transmission target (joint or tendon only). The damping value is scaled by gear squared, because the gear ratio scales both forces and velocities, leading to reflected damping (analogous to reflected inertia). Like joint damping, coefficients correspond to linear, quadratic and cubic velocity. See Polynomial forces for details.

    Several actuator shortcuts have a kv attribute which maps to -biasprm[2] and has similar semantics to damping: (e.g., position/kv). The differences between these attributes are:
    - damping is applied at the transmission target, and therefore includes the gear^2 factor. This factor is not required for kv as it is already applied in actuator space (so the units are identical).
    - Implicit integration works for damping when using the Euler integrator but not for kv. To get implicit integration for kv, implicit or implicitfast is required, see Integrators.
    - damping allows for polynomial damping, while kv is only linear.
    - Damping forces generated by kv are subject to forcerange clamping, but forces generated by damping are not.

    Finally, note that while it is permitted for nonzero damping and armature to be specified for multiple actuators acting on the same transmission target, it is more performant to specify them for only one actuator. Since these values are summed anyway, it is recommended to place all damping and armature for one transmission target in a single actuator definition."""

    armature: float = 0
    """Armature inertia (or mass for slider joints) contributed by the actuator to its transmission target (joint or tendon only). This is the actual inertia of the spinning element inside the actuator (e.g., a rotor). The contributed value is scaled by gear squared, because the gear ratio scales both forces and velocities, leading to reflected inertia. See joint and tendon armature for more details.

    See also the note in damping regarding multiple actuators acting on the same transmission target."""

    cranklength: float = 0
    """Used only for the slider-crank transmission type. Specifies the length of the connecting rod. The compiler expects this value to be positive when a slider-crank transmission is present."""

    joint: JointName | None = None
    """`joint`, `jointinparent`, `site`, and `body` (if applicable) determine the type of actuator transmission. All of them are optional, and exactly one of them must be specified. If this attribute is specified, the actuator acts on the given joint.

    For `hinge` and `slide` joints, the actuator length equals the joint position/angle times the first element of gear.

    For `ball` joints, the first three elements of gear define a 3d rotation axis in the child frame around which the actuator produces torque.

    The actuator length is defined as the dot-product between this gear axis and the angle-axis representation of the joint quaternion, and is in units of radian if gear is normalized (generally scaled by by the norm of gear). Note that after total rotation of more than `PI()`, the length will wrap to `-PI()`, and vice-versa. Therefore `position` servos for ball joints should generally use tighter limits which prevent this wrapping.

    For `free` joints, gear defines a 3d translation axis in the world frame followed by a 3d rotation axis in the child frame. The actuator generates force and torque relative to the specified axes. The actuator length for free joints is defined as zero (so it should not be used with position servos)."""

    jointinparent: JointName | None = None
    """Identical to joint, except that for ball and free joints, the 3d rotation axis given by gear is defined in the parent frame (which is the world frame for free joints) rather than the child frame."""

    site: SiteName | None = None
    """This transmission can apply force and torque at a site. The gear vector defines a 3d translation axis followed by a 3d rotation axis. Both are defined in the site's frame. This can be used to model jets and propellers. The effect is similar to actuating a free joint, and the actuator length is defined as zero unless a refsite is defined (see below). One difference from the joint and jointinparent transmissions above is that here the actuator operates on a site rather than a joint, but this difference disappears when the site is defined at the frame origin of the free-floating body. The other difference is that for site transmissions both the translation and rotation axes are defined in local coordinates. In contrast, translation is global and rotation is local for joint, and both translation and rotation are global for jointinparent."""

    refsite: SiteName | None = None
    """When using a site transmission, measure the translation and rotation w.r.t the frame of the refsite. In this case the actuator does have length and position actuators can be used to directly control an end effector, see refsite.xml example model. As above, the length is the dot product of the gear vector and the frame difference. So gear="0 1 0 0 0 0" means "Y-offset of site in the refsite frame", while gear="0 0 0 0 0 1" means rotation "Z-rotation of site in the refsite frame". It is recommended to use a normalized gear vector with nonzeros in only the first 3 or the last 3 elements of gear, so the actuator length will be in either length units or radians, respectively. As with ball joints (see joint above), for rotations which exceed a total angle of ππ will wrap around, so tighter limits are recommended."""

    tendon: TendonName | None = None
    """If specified, the actuator acts on the given tendon. The actuator length equals the tendon length times the gear ratio. Both spatial and fixed tendons can be used."""

    cranksite: SiteName | None = None
    """If specified, the actuator acts on a slider-crank mechanism which is implicitly determined by the actuator (i.e., it is not a separate model element). The specified site corresponds to the pin joining the crank and the connecting rod. The actuator length equals the position of the slider-crank mechanism times the gear ratio."""

    slidersite: SiteName | None = None
    """Used only for the slider-crank transmission type (required). The specified site is the pin joining the slider and the connecting rod. The slider moves along the z-axis of the slidersite frame. Therefore the site should be oriented as needed when it is defined in the kinematic tree; its orientation cannot be changed in the actuator definition."""

    user: VecN | None = None
    """See User parameters."""

    _act_dims_cache: tuple[int, int] | None = PrivateAttr(default=None)
    """Cached (actadr, actnum) for this actuator's internal activation state, resolved against the compiled MuJoCo model."""

    _ctrl_dims_cache: tuple[int, int] | None = PrivateAttr(default=None)
    """Cached (ctrladr, ctrlnum) for this actuator's control block, resolved against the compiled MuJoCo model."""

    _out_dims_cache: tuple[int, int] | None = PrivateAttr(default=None)
    """Cached (outadr, outnum) for this actuator's force-output block, resolved against the compiled MuJoCo model."""

    def _act_dims(self, state: MjState) -> tuple[int, int]:
        """Returns (actadr, actnum) for this actuator's internal activation state. actnum is 0 for actuators without internal dynamics (dyntype=none), e.g. motor, velocity, damper, adhesion."""
        if self._act_dims_cache is not None:
            return self._act_dims_cache

        aid = self.get_id(state.model)
        actnum = int(state.model.actuator_actnum[aid])
        actadr = int(state.model.actuator_actadr[aid]) if actnum > 0 else -1

        self._act_dims_cache = (actadr, actnum)
        return self._act_dims_cache

    def _ctrl_dims(self, state: MjState) -> tuple[int, int]:
        """Returns (ctrladr, ctrlnum) for this actuator's slice of mjData.ctrl (sized nu = sum(ctrlnum) across all actuators, not nactuator). ctrlnum is 1 for every native actuator except MIMO actuators (e.g. orientation with a quaternion input has ctrlnum 4)."""
        if self._ctrl_dims_cache is not None:
            return self._ctrl_dims_cache

        aid = self.get_id(state.model)
        ctrladr = int(state.model.actuator_ctrladr[aid])
        ctrlnum = int(state.model.actuator_ctrlnum[aid])

        self._ctrl_dims_cache = (ctrladr, ctrlnum)
        return self._ctrl_dims_cache

    def _out_dims(self, state: MjState) -> tuple[int, int]:
        """Returns (outadr, outnum) for this actuator's slice of mjData.actuator_length/velocity/force (sized nout = sum(outnum) across all actuators, not nactuator). outnum is 1 for every native actuator except MIMO actuators (e.g. orientation, which always has outnum 3 regardless of its input chart)."""
        if self._out_dims_cache is not None:
            return self._out_dims_cache

        aid = self.get_id(state.model)
        outadr = int(state.model.actuator_outadr[aid])
        outnum = int(state.model.actuator_outnum[aid])

        self._out_dims_cache = (outadr, outnum)
        return self._out_dims_cache

    def rt_ctrl(self, state: MjState) -> float | VecN:
        """Control input to the actuator during runtime (mjData.ctrl). Returns a scalar for single-input actuators, or a vector of length ctrlnum for MIMO actuators (e.g. orientation, pid)."""
        ctrladr, ctrlnum = self._ctrl_dims(state)
        vals = state.data.ctrl[ctrladr : ctrladr + ctrlnum]
        return float(vals[0]) if ctrlnum == 1 else vals

    def rt_length(self, state: MjState) -> float | VecN:
        """Length of the actuator's transmission during runtime (mjData.actuator_length). Returns a scalar for single-output actuators, or a vector of length outnum for MIMO actuators (e.g. orientation)."""
        outadr, outnum = self._out_dims(state)
        vals = state.data.actuator_length[outadr : outadr + outnum]
        return float(vals[0]) if outnum == 1 else vals

    def rt_velocity(self, state: MjState) -> float | VecN:
        """Velocity of the actuator's transmission during runtime (mjData.actuator_velocity). Returns a scalar for single-output actuators, or a vector of length outnum for MIMO actuators (e.g. orientation)."""
        outadr, outnum = self._out_dims(state)
        vals = state.data.actuator_velocity[outadr : outadr + outnum]
        return float(vals[0]) if outnum == 1 else vals

    def rt_force(self, state: MjState) -> float | VecN:
        """Force output of the actuator during runtime (mjData.actuator_force). Returns a scalar for single-output actuators, or a vector of length outnum for MIMO actuators (e.g. orientation, which always reports 3 force outputs)."""
        outadr, outnum = self._out_dims(state)
        vals = state.data.actuator_force[outadr : outadr + outnum]
        return float(vals[0]) if outnum == 1 else vals

    def rt_act(self, state: MjState) -> VecN:
        """Internal activation state(s) of the actuator during runtime (mjData.act slice for this actuator). Empty for actuators with no internal dynamics (dyntype=none), e.g. motor, velocity, damper, adhesion. Native activation dynamics (filter, filterexact, integrator, muscle, dcmotor) have exactly one element; only user-defined dynamics can have more."""
        actadr, actnum = self._act_dims(state)
        if actnum == 0:
            return np.empty(0)
        return state.data.act[actadr : actadr + actnum]

    def rt_act_dot(self, state: MjState) -> VecN:
        """Time derivative of the actuator's internal activation state(s) during runtime (mjData.act_dot slice for this actuator). Empty for actuators with no internal dynamics."""
        actadr, actnum = self._act_dims(state)
        if actnum == 0:
            return np.empty(0)
        return state.data.act_dot[actadr : actadr + actnum]

    _metadata_resolved: bool = PrivateAttr(default=False)
    """Whether `_transmission_metadata_cache` has been computed yet (None is itself a valid resolution for SITE/BODY/SLIDERCRANK transmission, so a plain `is None` check can't distinguish "unresolved" from "resolved to no metadata")."""

    _transmission_metadata_cache: dict[str, dict[str, str]] | None = PrivateAttr(
        default=None
    )
    """Cached `{"length": ..., "velocity": ..., "force": ...}` metadata for this actuator's transmission, resolved once on first sample."""

    def _resolve_transmission_metadata(
        self, state: MjState
    ) -> dict[str, dict[str, str]] | None:
        """Resolves and caches this actuator's transmission-based metadata for `length`/`velocity`/`force`."""
        if not self._metadata_resolved:
            actuator_id = self.get_id(state.model)
            self._transmission_metadata_cache = actuator_transmission_metadata(
                state, actuator_id
            )
            self._metadata_resolved = True
        return self._transmission_metadata_cache

    def request(
        self,
        signal_manager: SignalManager | None = None,
        channels: list[Literal["ctrl", "length", "velocity", "force", "act", "act_dot"]]
        | dict[
            Literal["ctrl", "length", "velocity", "force", "act", "act_dot"],
            dict[str, Any] | None,
        ] = [
            "ctrl",
            "length",
            "velocity",
            "force",
            "act",
            "act_dot",
        ],
    ):
        """
        Registers specific channels for logging.

        | Channel    | Description                                            | Type            |
        |:-----------|:--------------------------------------------------------|:----------------|
        | `ctrl`     | control input to the actuator                           | scalar / vector |
        | `length`   | length of the actuator's transmission                   | scalar / vector |
        | `velocity` | velocity of the actuator's transmission                 | scalar / vector |
        | `force`    | actuator force output                                   | scalar / vector |
        | `act`      | internal activation state(s), for stateful actuators    | scalar / vector |
        | `act_dot`  | time derivative of the internal activation state(s)     | scalar / vector |

        `ctrl` is a vector only for MIMO actuators whose input signature has more than one control (`ctrlnum` > 1, e.g. `orientation` with a quaternion input); `length`/`velocity`/`force` are vectors only for MIMO actuators with more than one force output (`outnum` > 1, e.g. `orientation`, which always has 3). Every other native actuator has `ctrlnum` = `outnum` = 1, so these remain scalars as before.

        `act` and `act_dot` only apply to actuators with internal dynamics (dyntype != none, e.g. position with timeconst, intvelocity, cylinder, muscle, dcmotor, pid); for actuators without internal state these channels are silently skipped. Whenever any of these six channels is a vector for a given actuator, each element is posted under `subgroups=(actuator_name, channel)` with `attr` set to `0`-`N`; otherwise the single value is posted as a scalar with `attr=channel` under `subgroups=(actuator_name,)`.

        `length`/`velocity`/`force` are tagged with built-in `dimension`/`units` metadata resolved from the actuator's transmission target when it's a single joint or a tendon (e.g. a hinge-driving actuator's `force` is tagged as torque). For SITE/BODY/SLIDERCRANK transmission, and for `ctrl`/`act`/`act_dot` on any actuator (control-signal abstractions reinterpreted by `gear`/`dyntype`, not direct physical readouts), no built-in default is applied. Supply `channels` as a dict with the desired metadata yourself if you know it.

        If `signal_manager` is omitted, the `SignalManager` of the active `RuntimeManager` `with` block is used. If that `RuntimeManager` has no `SignalManager` configured, this is a no-op.

        Args:
            signal_manager: The signal manager to register the sampler with.
            channels: The actuator data channels to log. Pass a list to select channels, or a dict mapping channel name to metadata overrides (or `None`) to select channels and attach per-channel metadata in one step.

        Raises:
            ValueError: If the actuator has no name.

        """
        from mujoco_mojo.runtime.signal_manager import resolve_signal_manager

        signal_manager = resolve_signal_manager(signal_manager)
        if signal_manager is None:
            return

        if self.name is None:
            msg = f"Cannot request telemetry for an unnamed {self.tag}."
            logger.error(msg)
            raise ValueError(msg)

        if isinstance(channels, dict):
            _meta = cast("dict[str, dict[str, Any] | None]", channels)
            channels = list(channels.keys())
        else:
            _meta = {}

        def sample(state: MjState):
            transmission_meta = self._resolve_transmission_metadata(state)

            for channel in channels:
                builtin = (
                    transmission_meta.get(channel)
                    if transmission_meta is not None
                    else None
                )
                meta = merge_signal_metadata(
                    builtin, channel, _meta, unit_system=state.us
                )

                match channel:
                    case "ctrl":
                        val = self.rt_ctrl(state)
                    case "length":
                        val = self.rt_length(state)
                    case "velocity":
                        val = self.rt_velocity(state)
                    case "force":
                        val = self.rt_force(state)
                    case "act":
                        val = self.rt_act(state)
                    case "act_dot":
                        val = self.rt_act_dot(state)
                    case _:
                        continue

                if isinstance(val, np.ndarray):
                    if val.size == 0:
                        continue
                    if val.size == 1:
                        signal_manager.post(
                            value=float(val[0]),
                            category=SignalCategory.ACTUATORS,
                            subgroups=(f"{self.name}",),
                            attr=channel,
                            metadata=meta,
                        )
                    else:
                        for i in range(val.size):
                            signal_manager.post(
                                value=float(val[i]),
                                category=SignalCategory.ACTUATORS,
                                subgroups=(f"{self.name}", channel),
                                attr=str(i),
                                metadata=meta,
                            )
                    continue

                signal_manager.post(
                    value=val,
                    category=SignalCategory.ACTUATORS,
                    subgroups=(f"{self.name}",),
                    attr=channel,
                    metadata=meta,
                )

        signal_manager.register_sampler(sample)
