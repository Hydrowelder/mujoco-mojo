from pathlib import Path

from pydantic import Field

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco import Mujoco
from mujoco_mojo.process_manager import NamedValueDict, NamedValueList


class Config(MojoBaseModel):
    """Contains metadata definitions for how jobs should be run."""

    workdir: Path
    iterations: int


class Mojo(MojoBaseModel):
    """Mojo is the highest level watcher which manages running jobs."""

    mjcf: Mujoco
    named_values: NamedValueDict | NamedValueList = Field(NamedValueDict())
    config: Config
