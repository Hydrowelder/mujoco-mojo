from __future__ import annotations

from abc import ABC
from typing import ClassVar

import mujoco
import numpy as np

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import (
    ActuatorControlLimited,
    ActuatorForceLimited,
    ActuatorName,
    JointName,
    SiteName,
    TendonName,
    Vec2,
    Vec3,
    Vec6,
    VecN,
)

__all__ = ["ActuatorBase"]


class ActuatorBase(XMLModel, ABC):
    """This element creates a base class for actuators, this is not intended for use in the SDK apart from inheritance."""

    tag = ""

    attributes = (
        "name",
        "class_",
        "group",
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
