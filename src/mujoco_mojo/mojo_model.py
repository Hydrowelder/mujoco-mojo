from __future__ import annotations

from numpydantic import NDArray
from process_manager.distribution import DistributionDict
from pydantic import Field

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco import Mujoco
from mujoco_mojo.process_manager import NamedValueDict

__all__ = ["MojoModel", "Values"]


class Values(MojoBaseModel):
    trial_num: int
    seed: int | None = None
    dists: DistributionDict = Field(default_factory=DistributionDict)
    named: NamedValueDict[NDArray] = Field(default_factory=NamedValueDict[NDArray])


class MojoModel(MojoBaseModel):
    """Mojo is the highest level watcher which manages running jobs."""

    mjcf: Mujoco
    values: Values
