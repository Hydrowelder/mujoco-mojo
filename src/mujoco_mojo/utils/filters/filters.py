from __future__ import annotations

import math
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Self

import numpy as np
import pint
import polars as pl
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from pydantic.alias_generators import to_camel
from scipy.signal import savgol_filter
from scipy.spatial.transform import Rotation as R

__all__ = [
    "UNIT_GROUPS",
    "AbsoluteValueFilter",
    "AnyFilter",
    "ClipFilter",
    "ComparisonFilter",
    "DeadbandFilter",
    "DerivativeFilter",
    "ExpFilter",
    "FilterType",
    "FirstFilter",
    "HighPassFilter",
    "IntegralFilter",
    "LastFilter",
    "LogFilter",
    "LowPassFilter",
    "MaxFilter",
    "MeanFilter",
    "MedianFilter",
    "MinFilter",
    "ModeFilter",
    "NormalizeFilter",
    "PowerFilter",
    "ReverseFilter",
    "RollingMeanFilter",
    "RollingMedianFilter",
    "RotationFilter",
    "RoundFilter",
    "SavitzkyGolayFilter",
    "ScaleFilter",
    "SignFilter",
    "SortFilter",
    "StandardDeviationFilter",
    "TaringFilter",
    "TrigFilter",
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
    LOG = "log"
    EXP = "exp"
    POWER = "power"
    ROUND = "round"
    TRIG = "trig"
    SIGN = "sign"
    COMPARISON = "comparison"
    STAT_MAX = "stat_max"
    STAT_MIN = "stat_min"
    STAT_MEAN = "stat_mean"
    STAT_MEDIAN = "stat_median"
    STAT_MODE = "stat_mode"
    STAT_STANDARD_DEVIATION = "stat_standard_deviation"
    STAT_FIRST = "stat_first"
    STAT_LAST = "stat_last"
    SORT = "sort"
    REVERSE = "reverse"


class BaseFilter(ABC, BaseModel):
    """Base class for all data transformations."""

    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )
    category: ClassVar[str] = "Misc"

    enabled: bool = True
    """Whether this filter step is active."""

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

    category: ClassVar[str] = "Arithmetic"

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

    category: ClassVar[str] = "Arithmetic"

    type: Literal[FilterType.ABSOLUTE_VALUE] = FilterType.ABSOLUTE_VALUE
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.abs()


class DerivativeFilter(BaseFilter):
    """
    Computes the numerical rate of change using backward difference.
    Useful for deriving velocity from position or acceleration from velocity.
    """

    category: ClassVar[str] = "Calculus"

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

    category: ClassVar[str] = "Calculus"

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

    category: ClassVar[str] = "Smoothing"

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

    category: ClassVar[str] = "Smoothing"

    type: Literal[FilterType.HIGH_PASS] = FilterType.HIGH_PASS
    """The discriminator type for Pydantic."""

    alpha: float = Field(default=0.1, gt=0, le=1)
    """Smoothing factor used for the underlying low-pass component."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        # HighPass = Original - LowPass
        return expr - expr.ewm_mean(alpha=self.alpha)


class ClipFilter(BaseFilter):
    """Clamps the signal values within a specified range."""

    category: ClassVar[str] = "Bounding"

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

    category: ClassVar[str] = "Smoothing"

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

    category: ClassVar[str] = "Bounding"

    type: Literal[FilterType.TARING] = FilterType.TARING
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr - expr.first()


class DeadbandFilter(BaseFilter):
    """Suppresses noise around zero by forcing values below a threshold to zero."""

    category: ClassVar[str] = "Bounding"

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

    category: ClassVar[str] = "Bounding"

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


class RollingMedianFilter(BaseFilter):
    """
    Applies a sliding window median filter.
    Highly effective for removing impulse noise (spikes) without blurring edges.
    """

    category: ClassVar[str] = "Smoothing"

    type: Literal[FilterType.MEDIAN] = FilterType.MEDIAN
    """The discriminator type for Pydantic."""

    window: int = Field(default=10, gt=0)
    """Size of the sliding window in samples."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.rolling_median(window_size=self.window, center=True)


class NormalizeFilter(BaseFilter):
    """Rescales the signal to the range [0, 1]."""

    category: ClassVar[str] = "Bounding"

    type: Literal[FilterType.NORMALIZE] = FilterType.NORMALIZE
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return (expr - expr.min()) / (expr.max() - expr.min() + 1e-9)


class SavitzkyGolayFilter(BaseFilter):
    """
    Applies a Savitzky-Golay smoothing filter by fitting a polynomial to the data.
    Preserves signal features (like peaks and transients) better than a simple moving average.
    """

    category: ClassVar[str] = "Smoothing"

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


from mujoco_mojo.stochas import ureg

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
    ("Mass", ["kg", "g", "mg", "pound", "slug"]),
    ("Force", ["N", "mN", "uN", "kN", "pound_force", "ounce_force"]),
    (
        "Torque",
        [
            "N*m",
            "N*mm",
            "mN*m",
            "kN*m",
            "pound_force*ft",
            "pound_force*in",
            "ounce_force*in",
        ],
    ),
    ("Inertia", ["kg*m^2", "kg*mm^2", "pound*in^2", "pound*ft^2", "slug*ft^2"]),
    # --- Work & Thermodynamics ---
    ("Energy", ["J", "mJ", "kJ", "W*s", "W*h", "kW*h", "ft*pound_force", "BTU"]),
    ("Power", ["W", "mW", "kW", "MW", "hp", "ft*pound_force/s"]),
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

    quat_col: str = Field("", json_schema_extra={"ui_type": "quat_col"})
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


class LogFilter(BaseFilter):
    """Applies a logarithm to the signal. Defaults to natural log (base e)."""

    category: ClassVar[str] = "Arithmetic"

    type: Literal[FilterType.LOG] = FilterType.LOG
    """The discriminator type for Pydantic."""

    base: float = Field(default=math.e, gt=0)
    """Logarithm base. Use e (2.718...) for natural log, 2 for log2, 10 for log10."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.log(base=self.base)


class ExpFilter(BaseFilter):
    """Raises a base to the power of each signal sample. Defaults to e^x."""

    category: ClassVar[str] = "Arithmetic"

    type: Literal[FilterType.EXP] = FilterType.EXP
    """The discriminator type for Pydantic."""

    base: float = Field(default=math.e, gt=0)
    """The base to exponentiate. Use e (2.718...) for the natural exponential."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        if abs(self.base - math.e) < 1e-12:
            return expr.exp()
        return expr.map_batches(
            lambda s: pl.Series(np.power(self.base, s.fill_null(0).to_numpy())),
            return_dtype=pl.Float64,
        )


class PowerFilter(BaseFilter):
    """Raises each signal sample to a fixed exponent. Supports fractional exponents (e.g. 0.5 for sqrt)."""

    category: ClassVar[str] = "Arithmetic"

    type: Literal[FilterType.POWER] = FilterType.POWER
    """The discriminator type for Pydantic."""

    exponent: float = Field(default=2.0)
    """The power to raise each sample to. Use 0.5 for square root, 1/3 for cube root."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.pow(self.exponent)


class RoundFilter(BaseFilter):
    """Quantizes the signal to a fixed number of decimal places."""

    category: ClassVar[str] = "Bounding"

    type: Literal[FilterType.ROUND] = FilterType.ROUND
    """The discriminator type for Pydantic."""

    method: Literal["round", "floor", "ceil"] = Field(
        default="round",
        json_schema_extra={"ui_type": "select"},
    )
    """Rounding method: round (nearest), floor (toward -inf), or ceil (toward +inf)."""

    decimals: int = Field(default=0, ge=0)
    """Number of decimal places to round to (only used when method is 'round')."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        if self.method == "floor":
            return expr.floor()
        if self.method == "ceil":
            return expr.ceil()
        return expr.round(self.decimals)


_TRIG_FUNCS = Literal[
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "sinh",
    "cosh",
    "tanh",
    "degrees",
    "radians",
]


class TrigFilter(BaseFilter):
    """Applies a trigonometric or angle-conversion function to the signal."""

    category: ClassVar[str] = "Trigonometry"

    type: Literal[FilterType.TRIG] = FilterType.TRIG
    """The discriminator type for Pydantic."""

    func: _TRIG_FUNCS = Field(
        default="sin",
        json_schema_extra={"ui_type": "select"},
    )
    """The trig function to apply."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        match self.func:
            case "sin":
                return expr.sin()
            case "cos":
                return expr.cos()
            case "tan":
                return expr.tan()
            case "asin":
                return expr.arcsin()
            case "acos":
                return expr.arccos()
            case "atan":
                return expr.arctan()
            case "sinh":
                return expr.sinh()
            case "cosh":
                return expr.cosh()
            case "tanh":
                return expr.tanh()
            case "degrees":
                return expr * (180.0 / math.pi)
            case "radians":
                return expr * (math.pi / 180.0)
            case _:
                return expr


class SignFilter(BaseFilter):
    """Returns the sign of each sample: 1 for positive, -1 for negative, 0 for zero."""

    category: ClassVar[str] = "Comparison"

    type: Literal[FilterType.SIGN] = FilterType.SIGN
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return (
            pl.when(expr > 0)
            .then(pl.lit(1.0))
            .when(expr < 0)
            .then(pl.lit(-1.0))
            .otherwise(pl.lit(0.0))
        )


_COMPARISON_OPS = Literal["gt", "gte", "lt", "lte", "eq", "neq"]


class ComparisonFilter(BaseFilter):
    """Compares each sample against a threshold, returning 1.0 (true) or 0.0 (false)."""

    category: ClassVar[str] = "Comparison"

    type: Literal[FilterType.COMPARISON] = FilterType.COMPARISON
    """The discriminator type for Pydantic."""

    operator: _COMPARISON_OPS = Field(
        default="gt",
        json_schema_extra={"ui_type": "select"},
    )
    """Comparison operator: gt (>), gte (>=), lt (<), lte (<=), eq (==), neq (!=)."""

    threshold: float = 0.0
    """The value to compare each sample against."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        match self.operator:
            case "gt":
                cond = expr > self.threshold
            case "gte":
                cond = expr >= self.threshold
            case "lt":
                cond = expr < self.threshold
            case "lte":
                cond = expr <= self.threshold
            case "eq":
                cond = expr == self.threshold
            case "neq":
                cond = expr != self.threshold
            case _:
                return expr
        return pl.when(cond).then(pl.lit(1.0)).otherwise(pl.lit(0.0))


class MaxFilter(BaseFilter):
    """Reduces the signal to its maximum value, broadcast across every sample."""

    category: ClassVar[str] = "Statistics"

    type: Literal[FilterType.STAT_MAX] = FilterType.STAT_MAX
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.max()


class MinFilter(BaseFilter):
    """Reduces the signal to its minimum value, broadcast across every sample."""

    category: ClassVar[str] = "Statistics"

    type: Literal[FilterType.STAT_MIN] = FilterType.STAT_MIN
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.min()


class MeanFilter(BaseFilter):
    """Reduces the signal to its mean value, broadcast across every sample."""

    category: ClassVar[str] = "Statistics"

    type: Literal[FilterType.STAT_MEAN] = FilterType.STAT_MEAN
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.mean()


class MedianFilter(BaseFilter):
    """Reduces the signal to its median value, broadcast across every sample."""

    category: ClassVar[str] = "Statistics"

    type: Literal[FilterType.STAT_MEDIAN] = FilterType.STAT_MEDIAN
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.median()


class ModeFilter(BaseFilter):
    """Reduces the signal to its most frequent value, broadcast across every sample."""

    category: ClassVar[str] = "Statistics"

    type: Literal[FilterType.STAT_MODE] = FilterType.STAT_MODE
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        # mode() can return multiple values when several samples are tied for
        # the highest frequency; first() collapses it to a single broadcastable value.
        return expr.mode().first()


class StandardDeviationFilter(BaseFilter):
    """Reduces the signal to its standard deviation, broadcast across every sample."""

    category: ClassVar[str] = "Statistics"

    type: Literal[FilterType.STAT_STANDARD_DEVIATION] = (
        FilterType.STAT_STANDARD_DEVIATION
    )
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.std()


class FirstFilter(BaseFilter):
    """Reduces the signal to its first value, broadcast across every sample."""

    category: ClassVar[str] = "Statistics"

    type: Literal[FilterType.STAT_FIRST] = FilterType.STAT_FIRST
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.first()


class LastFilter(BaseFilter):
    """Reduces the signal to its last value, broadcast across every sample."""

    category: ClassVar[str] = "Statistics"

    type: Literal[FilterType.STAT_LAST] = FilterType.STAT_LAST
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.last()


class SortFilter(BaseFilter):
    """Sorts the signal's values in ascending or descending order."""

    category: ClassVar[str] = "Ordering"

    type: Literal[FilterType.SORT] = FilterType.SORT
    """The discriminator type for Pydantic."""

    descending: bool = False
    """Whether to sort in descending order."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.sort(descending=self.descending)


class ReverseFilter(BaseFilter):
    """Reverses the order of the signal's values without changing their order of occurrence in time."""

    category: ClassVar[str] = "Ordering"

    type: Literal[FilterType.REVERSE] = FilterType.REVERSE
    """The discriminator type for Pydantic."""

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.reverse()


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
    | RollingMedianFilter
    | NormalizeFilter
    | WrapFilter
    | RotationFilter
    | LogFilter
    | ExpFilter
    | PowerFilter
    | RoundFilter
    | TrigFilter
    | SignFilter
    | ComparisonFilter
    | MaxFilter
    | MinFilter
    | MeanFilter
    | MedianFilter
    | ModeFilter
    | StandardDeviationFilter
    | FirstFilter
    | LastFilter
    | SortFilter
    | ReverseFilter,
    Field(discriminator="type"),
]

filter_adapter = TypeAdapter(dict[str, list[AnyFilter]])
