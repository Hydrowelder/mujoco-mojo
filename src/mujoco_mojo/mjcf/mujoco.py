from __future__ import annotations

from typing import List, Optional

from pydantic import Field

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

    options: List[Option] = Field(default_factory=list)
    compilers: List[Compiler] = Field(default_factory=list)
    sizes: List[Size] = Field(default_factory=list)
    statistics: List = Field(default_factory=list)
    assets: List = Field(default_factory=list)
    worldbody: Optional[WorldBody] = None
    deformables: List = Field(default_factory=list)
    contacts: List = Field(default_factory=list)
    equalities: List = Field(default_factory=list)
    tendons: List = Field(default_factory=list)
    actuators: List = Field(default_factory=list)
    sensors: List = Field(default_factory=list)
    keyframes: List = Field(default_factory=list)
    visuals: List = Field(default_factory=list)
    defaults: List = Field(default_factory=list)
    customs: List = Field(default_factory=list)
    extensions: List = Field(default_factory=list)
