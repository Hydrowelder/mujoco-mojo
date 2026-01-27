from __future__ import annotations

from typing import List, Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.option import Option
from mujoco_mojo.mjcf.mujoco_attr.worldbody import WorldBody

__all__ = ["Mujoco"]


class Mujoco(XMLModel):
    """The unique top-level element, identifying the XML file as an MJCF model file."""

    tag = "mujoco"

    attributes = {"model"}
    children_map = {
        "options": "options",
        "compilers": "compilers",
        "sizes": "sizes",
        "statistics": "statistics",
        "assets": "assets",
        "worldbody": "worldbody",
        "deformables": "deformables",
        "contacts": "contacts",
        "equalities": "equalities",
        "tendons": "tendons",
        "actuators": "actuators",
        "sensors": "sensors",
        "keyframes": "keyframes",
        "visuals": "visuals",
        "defaults": "defaults",
        "customs": "customs",
        "extensions": "extensions",
    }

    model: str = "MuJoCo Model"
    """The name of the model. This name is shown in the title bar of simulate.cc."""

    options: List[Option] = []
    compilers: List = []
    sizes: List = []
    statistics: List = []
    assets: List = []
    worldbody: Optional[WorldBody] = None
    deformables: List = []
    contacts: List = []
    equalities: List = []
    tendons: List = []
    actuators: List = []
    sensors: List = []
    keyframes: List = []
    visuals: List = []
    defaults: List = []
    customs: List = []
    extensions: List = []
