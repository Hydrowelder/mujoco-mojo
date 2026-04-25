from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny
from stochas import StochasBase

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco import Mujoco
from mujoco_mojo.utils.log import get_logger

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
