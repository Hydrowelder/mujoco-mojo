from __future__ import annotations

from typing import List, Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.option import Option
from mujoco_mojo.mjcf.mujoco_attr.worldbody import WorldBody

__all__ = ["Mujoco"]


class Mujoco(XMLModel):
    tag = "mujoco"

    attributes = {"model"}
    children_map = {"worldbody": "worldbody", "options": "options"}

    model: str = "MuJoCo Model"
    options: List[Option] = []
    worldbody: Optional[WorldBody] = None
