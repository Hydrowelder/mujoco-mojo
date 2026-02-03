from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from mujoco_mojo.base import XMLModel
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

    worldbody: WorldBody | None = None
    """World body of the model. There can be only one."""

    options: Sequence[Option] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Simulation options."""

    compilers: Sequence[Compiler] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Compiler options."""

    sizes: Sequence[Size] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Size parameter options."""

    statistics: Sequence[Statistic] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Model statistic overrides."""

    assets: Sequence[Asset] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Assets definitions in the model."""

    deformables: Sequence[Deformable] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Deformables elements definitions in the model."""

    contacts: Sequence[Contact] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Contact elements definitions in the model."""

    equalities: Sequence[Equality] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Equality constraint definition grouping."""

    tendons: Sequence[Tendon] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Tendon definition grouping."""

    actuators: Sequence[Actuator] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Actuator definition grouping."""

    sensors: Sequence[Sensor] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Sensor definition grouping."""

    keyframes: Sequence[Keyframe] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Keyframe definition grouping."""

    visuals: Sequence[Visual] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Visual definition grouping."""

    # the following two are not planned for implementation
    # defaults: Sequence[float] = Field(
    #     default_factory=list,
    #     exclude_if=is_empty_list,
    # )
    # """Default definition grouping."""

    # customs: Sequence[float] = Field(
    #     default_factory=list,
    #     exclude_if=is_empty_list,
    # )
    # """Custom definitions grouping."""

    extensions: Sequence[Extension] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )  # TODO
    """Extension definitions grouping."""
