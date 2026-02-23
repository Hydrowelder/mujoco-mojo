from pathlib import Path

from pydantic import BaseModel, Field

from mujoco_mojo.mjcf.mujoco import Mujoco
from mujoco_mojo.process_manager import NamedValueDict, NamedValueList


class MojoBaseModel(BaseModel):
    """Base model for all MuJoCo Mojo classes."""


class Config(MojoBaseModel):
    """Contains metadata definitions for how jobs should be run."""

    workdir: Path
    iterations: int


class Mojo(MojoBaseModel):
    """Mojo is the highest level watcher which manages running jobs."""

    mjcf: Mujoco  # contains Var which reference to named_value
    named_values: NamedValueDict | NamedValueList = Field(
        NamedValueDict()
    )  # contains named values
    config: Config
