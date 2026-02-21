from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from mujoco_mojo.base import MojoBaseModel


class RandomType(StrEnum):
    NORMAL = "normal"
    UNIFORM = "uniform"


class RandomBase(MojoBaseModel, ABC):
    nominal: int | float | str
    """Defines a nominal value that will always be called on the first run."""

    @abstractmethod
    def draw(self):
        pass


class Normal(RandomBase):
    """Defines a random normal (gaussian) value."""

    type: Literal[RandomType.NORMAL] = RandomType.NORMAL

    mu: float
    sigma: float


class Uniform(RandomBase):
    type: Literal[RandomType.UNIFORM] = RandomType.UNIFORM

    min: float
    max: float


Random = Annotated[Normal | Uniform, Field(discriminator="type")]
