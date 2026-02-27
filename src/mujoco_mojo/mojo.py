from __future__ import annotations

from pathlib import Path

from process_manager.distribution import DistributionDict
from pydantic import Field

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco import Mujoco
from mujoco_mojo.process_manager import NamedValueDict


class Config(MojoBaseModel):
    """Contains metadata definitions for how jobs should be run."""

    workdir: Path
    iterations: int


class Values(MojoBaseModel):
    dists: DistributionDict = Field(default_factory=DistributionDict)
    named: NamedValueDict = Field(default_factory=NamedValueDict)


class Mojo(MojoBaseModel):
    """Mojo is the highest level watcher which manages running jobs."""

    mjcf: Mujoco
    values: Values = Field(default_factory=Values)
    config: Config
