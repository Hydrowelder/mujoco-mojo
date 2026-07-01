from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, SerializeAsAny
from stochas import StochasBase

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco import Mujoco
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.unit_system import UnitSystem

logger = get_logger(__name__)

__all__ = ["MojoModel", "UserData"]


class UserData(MojoBaseModel):
    """Base class for all user-defined simulation data."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")


T = TypeVar("T", bound=UserData)


class MojoModel(MojoBaseModel, StochasBase):
    """Mojo is the highest level watcher which manages model definitions."""

    mjcf: Mujoco = Field(default_factory=Mujoco)
    """MuJoCo MJCF model to be written to XML."""

    user_data: SerializeAsAny[UserData] | None = None
    """User defined data for the model. This is used for transferring information from one function to another (generator to runtime or objective function)."""

    u: UnitSystem | None = None
    """Physical unit system for this model. Set to `UnitSystem.si()` or similar so that values in the generator can be expressed in any unit (e.g. `pos * u.inch` converts inches to meters) and telemetry channels report concrete units instead of abstract Pint dimensions."""

    _trial_dir: Path | None = PrivateAttr(default=None)

    @property
    def trial_dir(self) -> Path:
        """
        Absolute path to this trial's workspace directory.

        Set automatically after the generator runs. Available in runtime and objective functions. Raises `RuntimeError` if accessed inside the generator, where the directory has not yet been created.
        """
        if self._trial_dir is None:
            raise RuntimeError(
                "trial_dir is not available inside the generator. "
                "It is set after generation completes and the workspace is created."
            )
        return self._trial_dir

    def get_user_data(self, cls: type[T]) -> T:
        """Returns the user_data re-validated into the requested class."""
        if self.user_data is None:
            msg = "Unable to get user_data since it is None."
            logger.error(msg)
            raise ValueError(msg)

        if not isinstance(self.user_data, cls):
            data = self.user_data
            if isinstance(data, BaseModel):
                data = data.model_dump()

            self.user_data = cls.model_validate(data)

        return self.user_data

    def clear_unpickleable_data(self) -> None:
        """
        Clear unpickleable objects from the model tree before serialization.

        This walks through all geoms in the MJCF tree and clears cached collision managers and proximity queries that contain Cython objects which cannot be pickled for multiprocessing.
        """
        from mujoco_mojo.utils.proximity_mixin import ProximityMixin

        if self.mjcf.worldbody is None:
            return

        bodies = self.mjcf.worldbody.walk_bodies(include_self=True)
        for body in bodies:
            for geom in body.geoms:
                if isinstance(geom, ProximityMixin):
                    geom.clear_unpickleable()
