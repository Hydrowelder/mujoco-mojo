from __future__ import annotations

from typing import Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.elements.worldbody import WorldBody

__all__ = ["Mujoco"]


class Mujoco(XMLModel):
    tag = "mujoco"

    children_map = {"worldbody": "worldbody"}

    worldbody: Optional[WorldBody] = None
