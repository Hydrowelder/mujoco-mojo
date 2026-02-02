from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from pydantic import Field

from mujoco_mojo.mjcf.mujoco_attr.tendon_attr.spatial_attr.geom import SpatialGeom
from mujoco_mojo.mjcf.mujoco_attr.tendon_attr.spatial_attr.pulley import SpatialPulley
from mujoco_mojo.mjcf.mujoco_attr.tendon_attr.spatial_attr.site import SpatialSite
from mujoco_mojo.mjcf.mujoco_attr.tendon_attr.tendon_base import TendonBase
from mujoco_mojo.typing import (
    ActuatorForceLimited,
    MaterialName,
    Vec2,
    Vec4,
)
from mujoco_mojo.utils import is_empty_list

__all__ = ["Spatial"]


class Spatial(TendonBase):
    """
    This element creates a spatial tendon, which is a minimum-length path passing through specified via-points and wrapping around specified obstacle geoms. The objects along the path are defined with the sub-elements site and geom below. One can also define pulleys which split the path in multiple branches. Each branch of the tendon path must start and end with a site, and if it has multiple obstacle geoms they must be separated by sites - so as to avoid the need for an iterative solver at the tendon level.

    A second form of wrapping is where the tendon is constrained to pass through a geom rather than wrap around it. This is enabled automatically when a sidesite is specified and its position is inside the volume of the obstacle geom.
    """

    tag = "spatial"

    attributes = (
        *TendonBase.attributes,
        "actuatorfrclimited",
        "actuatorfrcrange",
        "width",
        "material",
        "armature",
        "rgba",
    )

    children = ("sites", "geoms", "pulleys")

    actuatorfrclimited: ActuatorForceLimited = ActuatorForceLimited.AUTO
    """This attribute specifies whether actuator forces acting on the tendon should be clamped. See Force limits for details. This attribute interacts with the actuatorfrcrange attribute. If this attribute is "false", actuator force clamping is disabled. If it is "true", actuator force clamping is enabled. If this attribute is "auto", and autolimits is set in compiler, actuator force clamping will be enabled if actuatorfrcrange is defined."""

    actuatorfrcrange: Vec2 = np.array((0, 0))
    """Range for clamping total actuator forces acting on this tendon. See Force limits for details. The compiler expects the lower bound to be nonpositive and the upper bound to be nonnegative. Setting this attribute without specifying actuatorfrclimited is an error if compiler-autolimits is "false"."""

    width: float = 0.003
    """Radius of the cross-section area of the spatial tendon, used for rendering. Parts of the tendon that wrap around geom obstacles are rendered with reduced width."""

    material: MaterialName | None = None
    """Material used to set the appearance of the tendon."""

    rgba: Vec4 = np.array((0.5, 0.5, 0.5, 1))
    """Color and transparency of the tendon. When this value is different from the internal default, it overrides the corresponding material properties. If a material is unspecified and rgba has the default value, limited tendons whose length exceeds the limit are recolored using the value of the constraint impedance dd to mix the default color and rgba/constraint."""

    armature: float = 0
    """Inertia associated with changes in tendon length. Setting this attribute to a positive value mm adds a kinetic energy term 12mv221mv2, where vv is the tendon velocity. Tendon inertia is most valuable when modeling the armature inertia in a linear actuator which contains a spinning element or the inertial motion of a fluid in a linear hydraulic actuator. In the illustration, we compare (left) a 3-dof system with a "tendon" implemented with a rotational joint and a slider joint with armature, attached to the world with a connect constraint and (right) an equivalent 1-dof model with an armature-bearing tendon. Like joint armature, this added inertia is only associated with changes in tendon length, and would not affect the dynamics of a moving fixed-length tendon. Because the tendon Jacobian JJ is position-dependent, tendon armature leads to an additional bias-force term c=mJJ˙Tq˙c=mJJ˙Tq˙."""

    sites: Sequence[SpatialSite] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Pair elements assigned to Contact."""

    geoms: Sequence[SpatialGeom] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Exclude elements assigned to Contact."""

    pulleys: Sequence[SpatialPulley] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Exclude elements assigned to Contact."""
