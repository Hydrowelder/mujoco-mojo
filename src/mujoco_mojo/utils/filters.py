from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Annotated, Literal, Self

import numpy as np
import pint
import polars as pl
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from scipy.signal import savgol_filter

__all__ = [
    "AbsoluteValueFilter",
    "AnyFilter",
    "ClipFilter",
    "DeadbandFilter",
    "DerivativeFilter",
    "FilterType",
    "HighPassFilter",
    "IntegralFilter",
    "LowPassFilter",
    "MedianFilter",
    "NormalizeFilter",
    "RollingMeanFilter",
    "ScaleFilter",
    "UnitFilter",
    "WrapFilter",
    "ZeroingFilter",
    "filter_adapter",
]


class FilterType(StrEnum):
    SCALE = "scale"
    ABSOLUTE_VALUE = "absolute_value"
    DERIVATIVE = "derivative"
    INTEGRAL = "integral"
    LOW_PASS = "low_pass"
    HIGH_PASS = "high_pass"
    CLIP = "clip"
    ROLLING_MEAN = "rolling_mean"
    ZEROING = "zeroing"
    DEADBAND = "deadband"
    WRAP = "wrap"
    MEDIAN = "median"
    NORMALIZE = "normalize"
    SAVITZKY_GOLAY = "savitzky_golay"
    UNIT = "unit"


class BaseFilter(ABC, BaseModel):
    """Base class for all data transformations."""

    model_config = ConfigDict(extra="forbid")

    @abstractmethod
    def apply(self, expr: pl.Expr) -> pl.Expr:
        """Applies the transformation to a Polars expression."""


class ScaleFilter(BaseFilter):
    """Applies a linear transformation: (value * factor) + offset."""

    type: Literal[FilterType.SCALE] = FilterType.SCALE
    """The discriminator type for Pydantic."""

    factor: float = 1.0
    """Multiplicative gain applied to the signal."""

    offset: float = 0.0
    """Additive constant applied after scaling."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return (expr * self.factor) + self.offset


class AbsoluteValueFilter(BaseFilter):
    """Rectifies the signal by taking the magnitude of every sample."""

    type: Literal[FilterType.ABSOLUTE_VALUE] = FilterType.ABSOLUTE_VALUE
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.abs()


class DerivativeFilter(BaseFilter):
    """
    Computes the numerical rate of change using backward difference.
    Useful for deriving velocity from position or acceleration from velocity.
    """

    type: Literal[FilterType.DERIVATIVE] = FilterType.DERIVATIVE
    """The discriminator type for Pydantic."""

    dt: float = Field(default=0.001, gt=0)
    """The time step between samples in seconds."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        # Backward difference: (x[n] - x[n-1]) / dt
        return expr.diff().fill_null(0) / self.dt


class IntegralFilter(BaseFilter):
    """
    Computes the cumulative sum of the signal multiplied by the time step.
    Useful for deriving position from velocity or calculating energy.
    """

    type: Literal[FilterType.INTEGRAL] = FilterType.INTEGRAL
    """The discriminator type for Pydantic."""

    dt: float = Field(default=0.001, gt=0)
    """The time step between samples in seconds."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        # Simple cumulative trapezoidal or rectangular integration
        return expr.cum_sum() * self.dt


class LowPassFilter(BaseFilter):
    """
    Applies a 1st-order Exponential Moving Average (EMA) to smooth the signal.
    Effective for removing high-frequency noise while introducing slight phase lag.
    """

    type: Literal[FilterType.LOW_PASS] = FilterType.LOW_PASS
    """The discriminator type for Pydantic."""

    alpha: float = Field(default=0.1, gt=0, le=1)
    """Smoothing factor (0 < alpha <= 1). Lower values result in heavier smoothing."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.ewm_mean(alpha=self.alpha)


class HighPassFilter(BaseFilter):
    """
    Removes low-frequency drift or steady-state offsets.
    Implemented as the complement of the Exponential Moving Average.
    """

    type: Literal[FilterType.HIGH_PASS] = FilterType.HIGH_PASS
    """The discriminator type for Pydantic."""

    alpha: float = Field(default=0.1, gt=0, le=1)
    """Smoothing factor used for the underlying low-pass component."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        # HighPass = Original - LowPass
        return expr - expr.ewm_mean(alpha=self.alpha)


class ClipFilter(BaseFilter):
    """Clamps the signal values within a specified range."""

    type: Literal[FilterType.CLIP] = FilterType.CLIP
    """The discriminator type for Pydantic."""

    min: float | None = None
    """Optional lower bound; values below this will be set to min."""

    max: float | None = None
    """Optional upper bound; values above this will be set to max."""

    @model_validator(mode="after")
    def validate_range(self) -> "ClipFilter":
        if self.min is not None and self.max is not None:
            if self.min >= self.max:
                raise ValueError(
                    f"Clip min ({self.min}) must be less than max ({self.max})"
                )
        return self

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.clip(lower_bound=self.min, upper_bound=self.max)


class RollingMeanFilter(BaseFilter):
    """Applies a sliding window average to the signal."""

    type: Literal[FilterType.ROLLING_MEAN] = FilterType.ROLLING_MEAN
    """The discriminator type for Pydantic."""

    window: int = Field(default=10, gt=0)
    """Size of the sliding window in samples."""

    center: bool = True
    """If True, centers the window on the current sample to minimize phase lag."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.rolling_mean(window_size=self.window, center=self.center)


class ZeroingFilter(BaseFilter):
    """Offsets the entire signal so that the first sample is zero."""

    type: Literal[FilterType.ZEROING] = FilterType.ZEROING
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr - expr.first()


class DeadbandFilter(BaseFilter):
    """Suppresses noise around zero by forcing values below a threshold to zero."""

    type: Literal[FilterType.DEADBAND] = FilterType.DEADBAND
    """The discriminator type for Pydantic."""

    threshold: float = Field(default=0.01, ge=0)
    """Magnitude threshold; values where abs(x) <= threshold are set to 0."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return pl.when(expr.abs() > self.threshold).then(expr).otherwise(0.0)


class WrapFilter(BaseFilter):
    """
    Keeps circular data (like Euler angles or radians) within a specific range.
    Ensures continuity when a signal crosses the upper or lower boundary.
    """

    type: Literal[FilterType.WRAP] = FilterType.WRAP
    """The discriminator type for Pydantic."""

    lb: float = -np.pi
    """Lower boundary for the wrap operation."""

    ub: float = np.pi
    """Upper boundary for the wrap operation."""

    @model_validator(mode="after")
    def validate_bound(self) -> Self:
        if self.lb > self.ub:
            raise ValueError("Wrap filter lower bound must be less than upper bound")
        return self

    def apply(self, expr: pl.Expr) -> pl.Expr:
        range_val = self.ub - self.lb
        return ((expr - self.lb) % range_val) + self.lb


class MedianFilter(BaseFilter):
    """
    Applies a sliding window median filter.
    Highly effective for removing impulse noise (spikes) without blurring edges.
    """

    type: Literal[FilterType.MEDIAN] = FilterType.MEDIAN
    """The discriminator type for Pydantic."""

    window: int = Field(default=10, gt=0)
    """Size of the sliding window in samples."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.rolling_median(window_size=self.window, center=True)


class NormalizeFilter(BaseFilter):
    """Rescales the signal to the range [0, 1]."""

    type: Literal[FilterType.NORMALIZE] = FilterType.NORMALIZE
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return (expr - expr.min()) / (expr.max() - expr.min() + 1e-9)


class SavitzkyGolayFilter(BaseFilter):
    """
    Applies a Savitzky-Golay smoothing filter by fitting a polynomial to the data.
    Preserves signal features (like peaks and transients) better than a simple moving average.
    """

    type: Literal[FilterType.SAVITZKY_GOLAY] = FilterType.SAVITZKY_GOLAY
    """The discriminator type for Pydantic."""

    window: int = Field(default=11, gt=1)
    """Number of samples in the sliding window; must be an odd integer."""

    order: int = Field(default=2, ge=0)
    """The order of the polynomial used to fit the samples."""

    @model_validator(mode="after")
    def validate_params(self) -> Self:
        if self.window % 2 == 0:
            raise ValueError("Savitzky-Golay window size must be odd.")
        if self.window <= self.order:
            raise ValueError("Window size must be greater than polynomial order.")
        return self

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.map_batches(
            lambda s: pl.Series(
                savgol_filter(s.fill_null(0).to_numpy(), self.window, self.order)
            ),
            return_dtype=pl.Float64,
        )


ureg = pint.UnitRegistry()
# --- Kinematics ---
AngleUnit = Literal["rad", "deg", "rad/s", "deg/s", "rad/s^2", "deg/s^2", "rev", "rpm"]
LenUnit = Literal["m", "mm", "cm", "km", "in", "ft", "thou"]
VelUnit = Literal["m/s", "ft/s", "in/s", "km/h", "mph"]
AccUnit = Literal["m/s^2", "g", "ft/s^2", "in/s^2"]

# --- Dynamics & Statics ---
MassUnit = Literal["kg", "lbm", "slug", "g", "mg"]
ForceUnit = Literal["N", "lbf", "kN", "mN"]
TorqueUnit = Literal["N*m", "N*mm", "mN*m", "lbf*ft", "lbf*in", "ozf*in"]
InertiaUnit = Literal["kg*m^2", "lbm*in^2", "lbm*ft^2", "slug*ft^2"]

# --- Work & Thermodynamics ---
EnergyUnit = Literal["J", "kJ", "mJ", "W*s", "ft*lbf", "BTU"]
PowerUnit = Literal["W", "kW", "hp", "ft*lbf/s"]
PressureUnit = Literal["Pa", "kPa", "psi", "bar", "atm", "torr"]

# --- Temporal & Electronics ---
TimeUnit = Literal["s", "ms", "us", "ns", "min", "hr"]
FreqUnit = Literal["Hz", "kHz", "MHz", "rad/s"]

# --- Dimensionless & Ratios ---
MiscUnit = Literal["dimensionless", "pct", "count", "bit", "V", "A"]

SignalUnit = (
    AngleUnit
    | LenUnit
    | VelUnit
    | AccUnit
    | MassUnit
    | ForceUnit
    | TorqueUnit
    | InertiaUnit
    | EnergyUnit
    | PowerUnit
    | PressureUnit
    | TimeUnit
    | FreqUnit
    | MiscUnit
    | str
)

try:
    # explicitly map lbm and lbf to avoid ambiguity
    ureg.define("lbm = pound")
    ureg.define("lbf = force_pound")
except pint.errors.RedefinitionError:
    # already defined in some Pint versions
    pass


class UnitFilter(BaseFilter):
    """
    Unit conversion using Pint.
    Ensures dimensional consistency and applies necessary scaling/offsets.
    """

    type: Literal[FilterType.UNIT] = FilterType.UNIT
    """The discriminator type for Pydantic."""

    from_unit: SignalUnit
    """The original unit of the telemetry data (e.g., 'rad')."""
    to_unit: SignalUnit
    """The target unit for analysis/display (e.g., 'deg')."""

    @model_validator(mode="after")
    def validate_units(self) -> Self:
        try:
            # check if units are dimensionally compatible
            source = ureg.parse_units(self.from_unit)
            target = ureg.parse_units(self.to_unit)

            # ensure valid dimensionality (not converting meters to degrees)
            if source.dimensionality != target.dimensionality:
                raise ValueError(
                    f"Incompatible units: {self.from_unit} and {self.to_unit} ({source.dimensionality} != {target.dimensionality})"
                )
        except pint.UndefinedUnitError as e:
            raise ValueError(f"Unknown unit definition: {e}")
        return self

    def apply(self, expr: pl.Expr) -> pl.Expr:
        # applies y = mx + b
        # m (factor) is the difference between converting 1.0 and 0.0
        # b (offset) is the value of 0.0 in the target unit

        # zero-point offset (e.g., 273.15 for C -> K)
        b = ureg.Quantity(0.0, self.from_unit).to(self.to_unit).magnitude

        # the scaling factor (the slope)
        # for meters -> mm, this is (1000 - 0) = 1000
        # for Celsius -> Kelvin, this is (274.15 - 273.15) = 1.0
        val_at_one = ureg.Quantity(1.0, self.from_unit).to(self.to_unit).magnitude
        m = val_at_one - b

        return (expr * m) + b


AnyFilter = Annotated[
    ScaleFilter
    | AbsoluteValueFilter
    | DerivativeFilter
    | IntegralFilter
    | LowPassFilter
    | HighPassFilter
    | RollingMeanFilter
    | SavitzkyGolayFilter
    | ClipFilter
    | DeadbandFilter
    | ZeroingFilter
    | UnitFilter
    | MedianFilter
    | NormalizeFilter
    | WrapFilter,
    Field(discriminator="type"),
]

filter_adapter = TypeAdapter(dict[str, list[AnyFilter]])
