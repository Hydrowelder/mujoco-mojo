from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Annotated, Literal, Self

import numpy as np
import pint
import polars as pl
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from scipy.signal import savgol_filter
from scipy.spatial.transform import Rotation as R

__all__ = [
    "UNIT_GROUPS",
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
    "RotationFilter",
    "SavitzkyGolayFilter",
    "ScaleFilter",
    "TaringFilter",
    "UnitFilter",
    "WrapFilter",
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
    TARING = "taring"
    DEADBAND = "deadband"
    WRAP = "wrap"
    MEDIAN = "median"
    NORMALIZE = "normalize"
    SAVITZKY_GOLAY = "savitzky_golay"
    UNIT = "unit"
    ROTATION = "rotation"


class BaseFilter(ABC, BaseModel):
    """Base class for all data transformations."""

    model_config = ConfigDict(extra="forbid")

    @abstractmethod
    def apply(self, expr: pl.Expr) -> pl.Expr:
        """Applies the transformation to a Polars expression."""

    def apply_with_context(
        self, series: pl.Series, df: pl.DataFrame
    ) -> pl.Series | None:
        """
        Override for filters that need access to other columns.
        Receives the current (already-transformed) series and the original dataframe.
        Return None to fall back to apply(expr).
        """
        return None


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
    """The time step between samples in seconds. Ignored when wrt_col is set."""

    wrt_col: str | None = Field(default=None, json_schema_extra={"ui_type": "col"})
    """Optional column to differentiate with respect to instead of a fixed dt."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        # Backward difference: (x[n] - x[n-1]) / dt
        return expr.diff().fill_null(0) / self.dt

    def apply_with_context(
        self, series: pl.Series, df: pl.DataFrame
    ) -> pl.Series | None:
        if not self.wrt_col or self.wrt_col not in df.columns:
            return None
        wrt = df[self.wrt_col].cast(pl.Float64)
        # Avoid divide-by-zero at the first sample
        dx = wrt.diff().fill_null(strategy="forward").fill_null(1)
        return series.cast(pl.Float64).diff().fill_null(0) / dx


class IntegralFilter(BaseFilter):
    """
    Computes the cumulative sum of the signal multiplied by the time step.
    Useful for deriving position from velocity or calculating energy.
    """

    type: Literal[FilterType.INTEGRAL] = FilterType.INTEGRAL
    """The discriminator type for Pydantic."""

    dt: float = Field(default=0.001, gt=0)
    """The time step between samples in seconds. Ignored when wrt_col is set."""

    wrt_col: str | None = Field(default=None, json_schema_extra={"ui_type": "col"})
    """Optional column to integrate with respect to instead of a fixed dt."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        # Simple rectangular integration with fixed step
        return expr.cum_sum() * self.dt

    def apply_with_context(
        self, series: pl.Series, df: pl.DataFrame
    ) -> pl.Series | None:
        if not self.wrt_col or self.wrt_col not in df.columns:
            return None
        wrt = df[self.wrt_col].cast(pl.Float64)
        dx = wrt.diff().fill_null(0)
        return (series.cast(pl.Float64) * dx).cum_sum()


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
    def validate_range(self) -> ClipFilter:
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


class TaringFilter(BaseFilter):
    """Offsets the entire signal so that the first sample is zero."""

    type: Literal[FilterType.TARING] = FilterType.TARING
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
try:
    ureg.define("lbm = pound")
    ureg.define("lbf = force_pound")
    ureg.define("ozf = force_ounce")
except pint.errors.RedefinitionError:
    pass

# ---------------------------------------------------------------------------
# Unit groups - single source of truth for both the frontend smart dropdown
# and the SignalUnit type annotation on UnitFilter.  To add a new unit,
# add it here; SignalUnit is derived automatically.  Verify that pint can
# parse any new string via `ureg.parse_units(...)` before committing.
# ---------------------------------------------------------------------------
UNIT_GROUPS: list[tuple[str, list[str]]] = [
    # --- Kinematics ---
    ("Angle", ["rad", "deg", "mrad", "rev", "rpm"]),
    ("Angular Velocity", ["rad/s", "deg/s"]),
    ("Angular Accel.", ["rad/s^2", "deg/s^2"]),
    ("Length", ["m", "mm", "cm", "um", "km", "in", "ft", "thou"]),
    ("Velocity", ["m/s", "mm/s", "cm/s", "ft/s", "in/s", "km/h", "mph"]),
    ("Acceleration", ["m/s^2", "mm/s^2", "ft/s^2", "in/s^2"]),
    # --- Dynamics & Statics ---
    ("Mass", ["kg", "g", "mg", "lbm", "slug"]),
    ("Force", ["N", "mN", "uN", "kN", "lbf"]),
    ("Torque", ["N*m", "N*mm", "mN*m", "kN*m", "lbf*ft", "lbf*in", "ozf*in"]),
    ("Inertia", ["kg*m^2", "kg*mm^2", "lbm*in^2", "lbm*ft^2", "slug*ft^2"]),
    # --- Work & Thermodynamics ---
    ("Energy", ["J", "mJ", "kJ", "W*s", "W*h", "kW*h", "ft*lbf", "BTU"]),
    ("Power", ["W", "mW", "kW", "MW", "hp", "ft*lbf/s"]),
    ("Pressure", ["Pa", "kPa", "MPa", "psi", "bar", "atm", "torr"]),
    # --- Temporal & Electronics ---
    ("Time", ["s", "ms", "us", "ns", "min", "hr"]),
    ("Frequency", ["Hz", "kHz", "MHz"]),
    ("Voltage", ["V", "mV", "kV"]),
    ("Current", ["A", "mA"]),
    # --- Dimensionless & Ratios ---
    ("Misc.", ["dimensionless", "pct", "count", "bit"]),
]

# Derived automatically - Literal[tuple_of_strings] is equivalent to Literal["a", "b", ...]
# in Python 3.9+ because x[a, b] and x[(a, b)] make the same __getitem__ call.
_ALL_UNITS: tuple[str, ...] = tuple(u for _, us in UNIT_GROUPS for u in us)
SignalUnit = Literal[_ALL_UNITS] | str


class UnitFilter(BaseFilter):
    """
    Unit conversion using Pint.
    Ensures dimensional consistency and applies necessary scaling/offsets.
    """

    type: Literal[FilterType.UNIT] = FilterType.UNIT
    """The discriminator type for Pydantic."""

    from_unit: SignalUnit  # pyright: ignore[reportInvalidTypeForm]
    """The original unit of the telemetry data (e.g., 'rad')."""

    to_unit: SignalUnit  # pyright: ignore[reportInvalidTypeForm]
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


class RotationFilter(BaseFilter):
    """Rotates a 3D vector component into a reference frame using a quaternion column."""

    type: Literal[FilterType.ROTATION] = FilterType.ROTATION
    """The discriminator type for Pydantic."""

    quat_col: str = Field("", json_schema_extra={"ui_type": "col"})
    """Base name of the quaternion column group (e.g. 'Bodies/hand/xquat')."""

    invert: bool = True
    """If True, transforms world-to-local (invert the quaternion rotation)."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr

    def apply_with_context(
        self, series: pl.Series, df: pl.DataFrame
    ) -> pl.Series | None:
        name = series.name
        suffix = name.rsplit(":", 1)[-1] if ":" in name else ""
        if suffix not in ("x", "y", "z") or not self.quat_col:
            return None
        base = name.rsplit(":", 1)[0]
        x_col, y_col, z_col = f"{base}:x", f"{base}:y", f"{base}:z"
        if not all(c in df.columns for c in (x_col, y_col, z_col)):
            return None
        # scipy expects (x, y, z, w) column order
        q_cols = [f"{self.quat_col}:{k}" for k in ("x", "y", "z", "w")]
        if not all(c in df.columns for c in q_cols):
            return None
        transformer = R.from_quat(df.select(q_cols).to_numpy())
        if self.invert:
            transformer = transformer.inv()
        v_rot = transformer.apply(df.select([x_col, y_col, z_col]).to_numpy())
        return pl.Series(name=name, values=v_rot[:, {"x": 0, "y": 1, "z": 2}[suffix]])


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
    | TaringFilter
    | UnitFilter
    | MedianFilter
    | NormalizeFilter
    | WrapFilter
    | RotationFilter,
    Field(discriminator="type"),
]

filter_adapter = TypeAdapter(dict[str, list[AnyFilter]])
