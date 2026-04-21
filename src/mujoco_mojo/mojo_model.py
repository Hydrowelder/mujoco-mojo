from __future__ import annotations

from typing import Any

from pydantic import Field, PrivateAttr
from stochas import StochasBase

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco import Mujoco
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = ["MojoModel"]


class MojoModel(MojoBaseModel, StochasBase):
    """Mojo is the highest level watcher which manages running jobs."""

    mjcf: Mujoco = Field(default_factory=Mujoco)
    """MuJoCo MJCF model to be writted to XML."""

    _user_data: Any = PrivateAttr(default=None)
    """User defined data not serialized with the model. This is used for transferring information from one function to another (generator to runtime or objective function)."""
