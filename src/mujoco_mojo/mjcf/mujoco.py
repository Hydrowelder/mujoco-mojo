from __future__ import annotations

from typing import List, Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.compiler import Compiler
from mujoco_mojo.mjcf.mujoco_attr.option import Option
from mujoco_mojo.mjcf.mujoco_attr.size import Size
from mujoco_mojo.mjcf.mujoco_attr.worldbody import WorldBody

__all__ = ["Mujoco"]


class Mujoco(XMLModel):
    """The unique top-level element, identifying the XML file as an MJCF model file."""

    tag = "mujoco"

    attributes = ("model",)
    children = (
        "options",
        "compilers",
        "sizes",
        "statistics",
        "assets",
        "worldbody",
        "deformables",
        "contacts",
        "equalities",
        "tendons",
        "actuators",
        "sensors",
        "keyframes",
        "visuals",
        "defaults",
        "customs",
        "extensions",
    )

    model: str = "MuJoCo Model"
    """The name of the model. This name is shown in the title bar of simulate.cc."""

    options: List[Option] = []
    compilers: List[Compiler] = []
    sizes: List[Size] = []
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
