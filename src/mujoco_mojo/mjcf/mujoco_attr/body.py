from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.geom import Geom

__all__ = ["Body", "WorldBody"]

_body_attr = ("name", "pos")
_body_children = ("geoms", "bodies", "inertial", "joints")


class Body(XMLModel):
    tag = "body"

    attributes = _body_attr
    children = _body_children

    name: Optional[str] = None
    pos: Optional[str] = None
    geoms: List[Geom] = Field(default_factory=list)
    bodies: List[Body] = Field(default_factory=list)
    inertial: Optional[Geom] = None  # TODO
    joints: List[Body] = Field(default_factory=list)  # TODO


_temp_list = list(_body_children)
for not_in in ("inertial", "joints"):
    _temp_list.remove(not_in)
_world_body_children = tuple(_temp_list)


class WorldBody(Body):
    tag = "worldbody"

    attributes = ()
    children = _world_body_children
