from typing import Any, Literal, Self

import numpy as np
import pandas as pd
from pydantic import PrivateAttr, model_validator
from scipy.interpolate import interp1d

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.typing import VecN

InterpOptions = Literal[
    "linear",
    "nearest",
    "nearest-up",
    "zero",
    "slinear",
    "quadratic",
    "cubic",
    "previous",
    "next",
]


class Interpolator(MojoBaseModel):
    """Utility to handle 1D lookup tables for forcing functions."""

    x: VecN
    """Interpolation abscissa values."""

    y: VecN
    """Interpolation ordinate values"""

    kind: InterpOptions = "linear"
    """What type of interpolation should be used."""

    _func: Any = PrivateAttr()
    """Defined in _init_spline on model validation."""

    @model_validator(mode="after")
    def _init_spline(self) -> Self:
        self._func = interp1d(
            self.x,
            self.y,
            kind=self.kind,
            fill_value="extrapolate",
        )
        return self

    def lookup(self, val: float) -> float:
        return float(self._func(val))

    @classmethod
    def from_series(cls, series: pd.Series, kind: InterpOptions = "linear") -> Self:
        """Create an interpolator directly from a Pandas Series."""
        return cls(x=np.asarray(series.index), y=np.asarray(series.values), kind=kind)
