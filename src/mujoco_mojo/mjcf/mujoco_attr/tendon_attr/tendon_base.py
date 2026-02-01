from __future__ import annotations

from typing import Optional

import numpy as np

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.defaults import SOLIMP_DEFAULT, SOLREF_DEFAULT
from mujoco_mojo.typing import (
    Limited,
    TendonName,
    Vec2,
    Vec5,
    VecN,
)

__all__ = ["TendonBase"]


class TendonBase(XMLModel):
    """Base model to be used for Tendons."""

    tag = ""

    attributes = (
        "name",
        "class_",
        "group",
        "limited",
        "range",
        "solreflimit",
        "solimplimit",
        "solreffriction",
        "solimpfriction",
        "frictionloss",
        "margin",
        "springlength",
        "stiffness",
        "damping",
        "user",
    )

    name: Optional[TendonName] = None
    """Name of the tendon."""

    class_: Optional[str] = None
    """Defaults class for setting unspecified attributes."""

    group: int = 0
    """Integer group to which the tendon belongs. This attribute can be used for custom tags. It is also used by the visualizer to enable and disable the rendering of entire groups of tendons."""

    limited: Limited = Limited.AUTO
    """If this attribute is "true", the length limits defined by the range attribute below are imposed by the constraint solver. If this attribute is "auto", and autolimits is set in compiler, length limits will be enabled if range is defined."""

    range: Vec2 = np.array((0, 0))
    """Range of allowed tendon lengths. Setting this attribute without specifying limited is an error, unless autolimits is set in compiler."""

    solreflimit: Vec2 = SOLREF_DEFAULT
    """Constraint solver parameters for simulating tendon limits. See Solver parameters."""

    solimplimit: Vec5 = SOLIMP_DEFAULT
    """Constraint solver parameters for simulating tendon limits. See Solver parameters."""

    solreffriction: Vec2 = SOLREF_DEFAULT
    """Constraint solver parameters for simulating dry friction in the tendon. See Solver parameters."""

    solimpfriction: Vec5 = SOLIMP_DEFAULT
    """Constraint solver parameters for simulating dry friction in the tendon. See Solver parameters."""

    margin: float = 0
    """The limit constraint becomes active when the absolute value of the difference between the tendon length and either limit of the specified range falls below this margin. Similar to contacts, the margin parameter is subtracted from the difference between the range limit and the tendon length. The resulting constraint distance is always negative when the constraint is active. This quantity is used to compute constraint impedance as a function of distance, as explained in Solver parameters."""

    frictionloss: float = 0
    """Friction loss caused by dry friction. To enable friction loss, set this attribute to a positive value."""

    springlength: Vec2 = np.array((-1, -1))
    """Spring resting position, can take either one or two values. If one value is given, it corresponds to the length of the tendon at rest. If it is -1, the tendon resting length is determined from the model reference configuration in mjModel.qpos0.

    Note that the default value of -1, which invokes the automatic length computation, was designed with spatial tendons in mind, which can only have nonegative length. In order to set the springlength of a fixed tendon to -1, use a nearby value like -0.99999.

    If two non-decreasing values are given, they define a dead-band range. If the tendon length is between the two values, the force is 0. If it is outside this range, the force behaves like a regular spring, with the rest-point corresponding to the nearest springlength value. A deadband can be used to define tendons whose limits are enforced by springs rather than constraints."""

    stiffness: float = 0
    """Stiffness coefficient. A positive value generates a spring force (linear in position) acting along the tendon."""

    damping: float = 0
    """Damping coefficient. A positive value generates a damping force (linear in velocity) acting along the tendon. Unlike joint damping which is integrated implicitly by the Euler method, tendon damping is not integrated implicitly, thus joint damping should be used if possible."""

    user: Optional[VecN] = None
    """See User parameters."""
