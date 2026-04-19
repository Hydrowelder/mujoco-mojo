from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Self

from numpydantic import NDArray
from pydantic import Field, PrivateAttr, SerializeAsAny

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco import Mujoco
from mujoco_mojo.stochas import (
    NOMINAL_TRIAL_NUM,
    Dist,
    DistributionDict,
    NamedValue,
    NamedValueDict,
    ValueName,
)
from mujoco_mojo.stochas.design import (
    AnyDesignValue,
    DesignCategorical,
    DesignFloat,
    DesignValueDict,
)
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = ["MojoModel"]


class MojoModel(MojoBaseModel):
    """Mojo is the highest level watcher which manages running jobs."""

    mjcf: Mujoco = Field(default_factory=Mujoco)
    """MuJoCo MJCF model to be writted to XML."""

    trial_num: int = NOMINAL_TRIAL_NUM
    """Trial number identified for this instance of the MuJoCo Mojo model."""

    seed: int | None = None
    """Campaign seed for calculating random numbers."""

    design: DesignValueDict = Field(default_factory=DesignValueDict)
    """Registry of parameters for hyperparameter tuning."""

    dists: DistributionDict = Field(default_factory=DistributionDict)
    """Random distributions used to generate the MojoModel."""

    named: SerializeAsAny[NamedValueDict[NDArray]] = Field(
        default_factory=NamedValueDict[NDArray]
    )
    """Final 'baked' values from a random draw, global override, or design study."""

    _user_data: Any = PrivateAttr(default=None)
    """User defined data not serialized with the model. This is used for transferring information from one function to another (generator to runtime or objective function)."""

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
            # defined with global override
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
            # defined with global override but forced to update
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
            # standard random draw
            self.named.update(nv)
        return nv

    def design_float(
        self,
        name: str | ValueName,
        default: float,
        low: float,
        high: float,
        log: bool = False,
        step: float | None = None,
    ) -> float:
        """
        Registers a continuous or stepped floating point parameter.

        Returns the optimizer's guess if present, otherwise the default.
        """
        dv = DesignFloat(
            name=ValueName(name),
            low=low,
            high=high,
            log=log,
            step=step,
            stored_value=default,
        )

        return float(self._register_design_value(dv))

    def design_categorical[T](
        self,
        name: str | ValueName,
        default: T,
        choices: Sequence[T],
    ) -> T:
        """Registers a categorical (discrete choice) parameter."""
        dv = DesignCategorical(
            name=ValueName(name),
            choices=choices,
            stored_value=default,
        )
        return self._register_design_value(dv)

    def _register_design_value(self, dv: AnyDesignValue) -> Any:
        self.design[dv.name] = dv

        # the value has already been set and should use the fixed
        if dv.name in self.named:
            val = self.named[dv.name].value
            return val.item() if hasattr(val, "item") else val

        self.named.update(dv)
        return dv.value

    def with_overrides(self, overrides: NamedValueDict[NDArray]) -> Self:
        """
        Sets the NamedValueDict to the provided override.

        This is useful for manually setting some named values to be used.
        """
        self.named = overrides
        return self

    def with_seed(self, seed: int | None = None) -> Self:
        """
        Sets the seed to the provided value.

        This is useful for initializaing the model.
        """
        self.seed = seed
        for _, dist in self.dists.items():
            dist.with_seed(seed)
        return self

    def with_trial_num(self, trial_num: int) -> Self:
        """
        Sets the trial_num to the provided value.

        This is useful for initializaing the model.
        """
        self.trial_num = trial_num
        for _, dist in self.dists.items():
            dist.with_trial_num(trial_num)
        return self

    def with_override(self, override: NamedValueDict[NDArray]) -> Self:
        """
        Sets the NamedValueDict to the provided override.

        This is useful for manually setting some named values to be used.
        """
        self.named = override
        return self

    @property
    def is_nominal(self) -> bool:
        return self.trial_num == NOMINAL_TRIAL_NUM
