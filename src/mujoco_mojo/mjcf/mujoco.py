from __future__ import annotations

from pathlib import Path

from pydantic import Field

import mujoco_mojo.utils as utils
from mujoco_mojo.mjcf.extension import Extension
from mujoco_mojo.mjcf.mujoco_attr.actuator import Actuator
from mujoco_mojo.mjcf.mujoco_attr.asset import Asset
from mujoco_mojo.mjcf.mujoco_attr.body import WorldBody
from mujoco_mojo.mjcf.mujoco_attr.compiler import Compiler
from mujoco_mojo.mjcf.mujoco_attr.contact import Contact
from mujoco_mojo.mjcf.mujoco_attr.deformable import Deformable
from mujoco_mojo.mjcf.mujoco_attr.equality import Equality
from mujoco_mojo.mjcf.mujoco_attr.keyframe import Keyframe
from mujoco_mojo.mjcf.mujoco_attr.option import Option
from mujoco_mojo.mjcf.mujoco_attr.sensor import Sensor
from mujoco_mojo.mjcf.mujoco_attr.size import Size
from mujoco_mojo.mjcf.mujoco_attr.statistic import Statistic
from mujoco_mojo.mjcf.mujoco_attr.tendon import Tendon
from mujoco_mojo.mjcf.mujoco_attr.visual import Visual
from mujoco_mojo.mjcf.xml_model import XMLModel
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
        # "defaults",
        # "customs",
        "extensions",
    )

    model: ModelName = ModelName("MuJoCo Model")
    """The name of the model. This name is shown in the title bar of simulate.cc."""

    worldbody: WorldBody | None = None
    """World body of the model. There can be only one."""

    options: list[Option] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Simulation options."""

    compilers: list[Compiler] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Compiler options."""

    sizes: list[Size] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Size parameter options."""

    statistics: list[Statistic] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Model statistic overrides."""

    assets: list[Asset] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Assets definitions in the model."""

    deformables: list[Deformable] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Deformables elements definitions in the model."""

    contacts: list[Contact] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Contact elements definitions in the model."""

    equalities: list[Equality] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Equality constraint definition grouping."""

    tendons: list[Tendon] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Tendon definition grouping."""

    actuators: list[Actuator] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Actuator definition grouping."""

    sensors: list[Sensor] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Sensor definition grouping."""

    keyframes: list[Keyframe] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Keyframe definition grouping."""

    visuals: list[Visual] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Visual definition grouping."""

    # the following two are not planned for implementation
    # defaults: list[Default] = Field(
    #     default_factory=list,
    #     exclude_if=is_empty_list,
    # )
    # """Default definition grouping."""

    # customs: list[Custom] = Field(
    #     default_factory=list,
    #     exclude_if=is_empty_list,
    # )
    # """Custom definitions grouping."""

    extensions: list[Extension] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Extension definitions grouping."""

    def write_xml(self, file: Path, exclude_default: bool = True) -> None:
        """
        Writes the MuJoCo model to an XML file.

        Args:
            file (Path): Filepath to save XML.
            exclude_default (bool, optional): Wheter or not to include default values. Values equal to None are always ignored. Attributes which are literals (such as Geom.type) are always included. Defaults to True.

        """
        xml = utils.to_pretty_xml(self.to_xml(exclude_default=exclude_default))
        file.write_text(xml)
