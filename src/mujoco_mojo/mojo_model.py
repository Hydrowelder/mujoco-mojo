from __future__ import annotations

from typing import Self

from numpydantic import NDArray
from pydantic import Field

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco import Mujoco
from mujoco_mojo.process_manager import (
    NOMINAL_TRIAL_NUM,
    Dist,
    DistributionDict,
    NamedValue,
    NamedValueDict,
)
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = ["MojoModel", "Values"]


class Values(MojoBaseModel):
    trial_num: int = NOMINAL_TRIAL_NUM
    seed: int | None = None
    dists: DistributionDict = Field(default_factory=DistributionDict)
    named: NamedValueDict[NDArray] = Field(default_factory=NamedValueDict[NDArray])

    def sample_dist(
        self,
        dist: Dist,
        size: int = 1,
        force: bool = False,
        warn: bool = True,
    ) -> NamedValue[NDArray]:
        """
        Sets the seed and trial number of the distribution, sample, registers it and the sampled value to the MuJoCo model, and returns the named value.

        If the NamedValue is already registered, the registered named value is returned.

        Args:
            dist (Dist): Distribution to sample and register.
            size (int, optional): Number of samples to take. Will be embedded in the returned NamedValue. Defaults to 1.
            force (bool, optional): Force the sampled value into the NamedValueDict if it already exists. Defaults to False.
            warn (bool, optional): Whether or not to warn if there is a conflict while forcing. Defaults to True.

        Returns:
            NamedValue[NDArray]: NamedValue containing the random draw.

        """
        dist.with_seed(self.seed).with_trial_num(self.trial_num)
        self.dists.update(dist)

        nv = dist.sample_to_named_value(size=size)

        if nv in self.named and not force:
            if warn:
                logger.warning(
                    f"NamedValue [bold cyan]{nv.name}[/bold cyan] already registered. Returning it instead of the sampled value.",
                    extra={"terminal_only": True},
                )
                logger.warning(
                    f"NamedValue {nv.name} already registered. Returning it instead of the sampled value.",
                    extra={"file_only": True},
                )
            return self.named[nv.name]
        elif nv in self.named and force:
            if warn:
                logger.warning(
                    f"NamedValue [bold cyan]{nv.name}[/bold cyan] already registered. Force setting it to the new value in the registry.",
                    extra={"terminal_only": True},
                )
                logger.warning(
                    f"NamedValue {nv.name} already registered. Force setting it to the new value in the registry.",
                    extra={"file_only": True},
                )
            self.named.force_update(nv, warn=False)
        else:
            self.named.update(nv)
        return nv

    def with_override(self, override: NamedValueDict[NDArray]) -> None:
        """
        Sets the NamedValueDict to the provided override.

        This is useful for manually setting some named values to be used.
        """
        self.named = override

    def with_seed(self, seed: int | None = None) -> None:
        self.seed = seed

    def with_trial_num(self, trial_num: int) -> None:
        self.trial_num = trial_num


class MojoModel(MojoBaseModel):
    """Mojo is the highest level watcher which manages running jobs."""

    mjcf: Mujoco = Field(default_factory=Mujoco)
    values: Values = Field(default_factory=Values)

    def sample_dist(
        self,
        dist: Dist,
        size: int = 1,
        force: bool = False,
        warn: bool = True,
    ) -> NamedValue[NDArray]:
        """
        Sets the seed and trial number of the distribution, sample, registers it and the sampled value to the MuJoCo model, and returns the named value.

        If the NamedValue is already registered, the registered named value is returned.

        Args:
            dist (Dist): Distribution to sample and register.
            size (int, optional): Number of samples to take. Will be embedded in the returned NamedValue. Defaults to 1.
            force (bool, optional): Force the sampled value into the NamedValueDict if it already exists. Defaults to False.
            warn (bool, optional): Whether or not to warn if there is a conflict while forcing. Defaults to True.

        Returns:
            NamedValue[NDArray]: NamedValue containing the random draw.

        """
        return self.values.sample_dist(dist=dist, size=size, force=force, warn=warn)

    def with_overrides(self, overrides: NamedValueDict[NDArray]) -> Self:
        """
        Sets the NamedValueDict to the provided override.

        This is useful for manually setting some named values to be used.
        """
        self.values.with_override(overrides)
        return self

    def with_seed(self, seed: int | None = None) -> Self:
        """
        Sets the seed to the provided value.

        This is useful for initializaing the model.
        """
        self.values.with_seed(seed=seed)
        return self

    def with_trial_num(self, trial_num: int) -> Self:
        """
        Sets the trial_num to the provided value.

        This is useful for initializaing the model.
        """
        self.values.with_trial_num(trial_num=trial_num)
        return self
