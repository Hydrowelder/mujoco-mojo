from typing import ClassVar

import mujoco

from mujoco_mojo.mjcf.defaults import SOLIMP_DEFAULT, SOLREF_DEFAULT
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import EqualityName, Vec2, Vec5


class EqualityBase(XMLModel):
    tag = ""

    attributes = ("name", "class_", "active", "solref", "solimp")

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_EQUALITY

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

    def set_active(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData, state: bool
    ) -> None:
        """
        Sets the runtime activation state of the equality constraint.

        Args:
            mj_model: The MuJoCo model instance.
            mj_data: The MuJoCo data instance containing the current state.
            state: True to enable the constraint, False to disable it.

        """
        eq_id = self.get_id(mj_model)
        mj_data.eq_active[eq_id] = 1 if state else 0

    def enable(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> None:
        """Convenience method to enable the constraint at runtime."""
        self.set_active(mj_model, mj_data, True)

    def disable(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> None:
        """Convenience method to disable the constraint at runtime."""
        self.set_active(mj_model, mj_data, False)

    def is_active(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> bool:
        """Returns the current runtime activation state."""
        eq_id = self.get_id(mj_model)
        return bool(mj_data.eq_active[eq_id])
