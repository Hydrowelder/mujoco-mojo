from __future__ import annotations

from typing import Optional, Sequence

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.asset import Asset
from mujoco_mojo.mjcf.mujoco_attr.body import WorldBody
from mujoco_mojo.mjcf.mujoco_attr.compiler import Compiler
from mujoco_mojo.mjcf.mujoco_attr.option import Option
from mujoco_mojo.mjcf.mujoco_attr.size import Size
from mujoco_mojo.mjcf.mujoco_attr.statistic import Statistic
from mujoco_mojo.typing import ModelName
from mujoco_mojo.utils import is_empty_list

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

    model: ModelName = ModelName("MuJoCo Model")
    """The name of the model. This name is shown in the title bar of simulate.cc."""

    options: Sequence[Option] = Field(default_factory=list, exclude_if=is_empty_list)
    compilers: Sequence[Compiler] = Field(
        default_factory=list, exclude_if=is_empty_list
    )
    sizes: Sequence[Size] = Field(default_factory=list, exclude_if=is_empty_list)
    statistics: Sequence[Statistic] = Field(
        default_factory=list, exclude_if=is_empty_list
    )
    assets: Sequence[Asset] = Field(default_factory=list, exclude_if=is_empty_list)
    worldbody: Optional[WorldBody] = None
    deformables: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO
    contacts: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO
    equalities: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO
    tendons: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO
    actuators: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO
    sensors: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO
    keyframes: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO
    visuals: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO
    defaults: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO
    customs: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO
    extensions: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO
