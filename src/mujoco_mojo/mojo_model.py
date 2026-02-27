from __future__ import annotations

from pathlib import Path

from process_manager.distribution import DistributionDict
from pydantic import Field

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco import Mujoco
from mujoco_mojo.process_manager import BaseList, NamedValueDict


class Values(MojoBaseModel):
    dists: DistributionDict = Field(default_factory=DistributionDict)
    named: NamedValueDict = Field(default_factory=NamedValueDict)
    runtime_assets: BaseList[Path] = Field(default_factory=BaseList[Path])
    """This list contains a list of the unique assets required by an instance of Mojo.

    This currently does nothing, but is intended to be used to copy assets to a central location to be shared by multiple instances of a runtime."""


class MojoModel(MojoBaseModel):
    """Mojo is the highest level watcher which manages running jobs."""

    mjcf: Mujoco
    values: Values = Field(default_factory=Values)
