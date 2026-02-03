from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.keyframe_attr.key import Key
from mujoco_mojo.utils import is_empty_list

__all__ = ["Keyframe"]


class Keyframe(XMLModel):
    """This is a grouping element for keyframe definitions. It does not have attributes. Keyframes can be used to create a library of states that are of interest to the user, and to initialize the simulation state to one of the states in the library. They are not needed by any MuJoCo computations. The number of keyframes allocated in mjModel is the larger of the nkey attribute of size, and the number of elements defined here. If fewer than nkey elements are defined here, the undefined keyframes have all their data set to 0, except for the qpos attribute which is set to mjModel.qpos0. The user can also set keyframe data in mjModel at runtime; this data will then appear in the saved MJCF model. Note that in simulate.cc the simulation state can be copied into a selected keyframe and vice versa."""

    tag = "keyframe"

    children = ("keys",)

    keys: Sequence[Key] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Key grouping."""
