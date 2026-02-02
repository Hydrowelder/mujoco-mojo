from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.defaults import SOLIMP_DEFAULT, SOLREF_DEFAULT
from mujoco_mojo.typing import EqualityName, Vec2, Vec5


class EqualityBase(XMLModel):
    tag = ""

    attributes = ("name", "class_", "active", "solref", "solimp")

    name: EqualityName | None = None
    """Name of the equality constraint."""

    class_: str | None = None
    """Defaults class for setting unspecified attributes."""

    active: bool = True
    """If this attribute is set to "true", the constraint is active and the constraint solver will try to enforce it. The field mjModel.eq_active0 corresponds to this value, and is used to initialize mjData.eq_active, which is user-settable at runtime."""

    solref: Vec2 = SOLREF_DEFAULT
    """Constraint solver parameters for equality constraint simulation. See Solver parameters."""

    solimp: Vec5 = SOLIMP_DEFAULT
    """Constraint solver parameters for equality constraint simulation. See Solver parameters."""
