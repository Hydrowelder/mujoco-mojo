from __future__ import annotations

from pathlib import Path
from typing import Self

from process_manager.distribution import DistributionDict
from pydantic import Field, model_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco import Mujoco
from mujoco_mojo.process_manager import NamedValueDict, ValueName


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

    @model_validator(mode="after")
    def validate_reported_named_values(self) -> Self:
        unreported = self.unreported_named_values()
        if unreported:
            raise ValueError(
                f"Not all named values in the MJCF were reported to Mojo. Offending values ({', '.join(unreported)})"
            )
        return self

    def unreported_named_values(self) -> list[ValueName]:
        """
        Recursively searches the NamedValue references in the MJCF and compares to the NamedValue reported to Mojo.

        Returns:
            list[ValueName]: All ValueNames in the MJCF that were not found in the reported NamedValueDict.

        """
        in_mjcf = set([v.ref for v in self.mjcf.vals])
        reported = set(self.values.named.keys())

        unreported = []
        for m in in_mjcf:
            if m not in reported:
                unreported.append(m)
        return unreported
