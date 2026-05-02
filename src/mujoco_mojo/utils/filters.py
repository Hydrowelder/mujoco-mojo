from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Annotated, Literal, Self

import numpy as np
import polars as pl
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

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


class BaseFilter(ABC, BaseModel):
    """Base class for all data transformations."""

    model_config = ConfigDict(extra="forbid")

    @abstractmethod
    def apply(self, expr: pl.Expr) -> pl.Expr:
        pass


class ScaleFilter(BaseFilter):
    type: Literal[FilterType.SCALE] = FilterType.SCALE
    factor: float = 1.0
    offset: float = 0.0

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return (expr * self.factor) + self.offset


class AbsoluteValueFilter(BaseFilter):
    type: Literal[FilterType.ABSOLUTE_VALUE] = FilterType.ABSOLUTE_VALUE

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.abs()


class DerivativeFilter(BaseFilter):
    type: Literal[FilterType.DERIVATIVE] = FilterType.DERIVATIVE
    dt: float = Field(default=0.001, gt=0)

    def apply(self, expr: pl.Expr) -> pl.Expr:
        # Backward difference: (x[n] - x[n-1]) / dt
        return expr.diff().fill_null(0) / self.dt


class IntegralFilter(BaseFilter):
    type: Literal[FilterType.INTEGRAL] = FilterType.INTEGRAL
    dt: float = Field(default=0.001, gt=0)

    def apply(self, expr: pl.Expr) -> pl.Expr:
        # Simple cumulative trapezoidal or rectangular integration
        return expr.cum_sum() * self.dt


class LowPassFilter(BaseFilter):
    """Exponential Moving Average (EMA) as a simple 1st-order Low-pass."""

    type: Literal[FilterType.LOW_PASS] = FilterType.LOW_PASS
    alpha: float = Field(default=0.1, gt=0, le=1)  # Smoothing factor (0 < alpha <= 1)

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.ewm_mean(alpha=self.alpha)


class HighPassFilter(BaseFilter):
    """
    Simple 1st-order High-pass using the complement of a Low-pass.
    Removes low-frequency drift/offsets.
    """

    type: Literal[FilterType.HIGH_PASS] = FilterType.HIGH_PASS
    alpha: float = Field(default=0.1, gt=0, le=1)

    def apply(self, expr: pl.Expr) -> pl.Expr:
        # HighPass = Original - LowPass
        return expr - expr.ewm_mean(alpha=self.alpha)


class ClipFilter(BaseFilter):
    type: Literal[FilterType.CLIP] = FilterType.CLIP
    min: float | None = None
    max: float | None = None

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
    type: Literal[FilterType.ROLLING_MEAN] = FilterType.ROLLING_MEAN
    window: int = Field(default=10, gt=0)
    center: bool = True

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.rolling_mean(window_size=self.window, center=self.center)


class ZeroingFilter(BaseFilter):
    type: Literal[FilterType.ZEROING] = FilterType.ZEROING

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr - expr.first()


class DeadbandFilter(BaseFilter):
    type: Literal[FilterType.DEADBAND] = FilterType.DEADBAND
    threshold: float = Field(default=0.01, ge=0)

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return pl.when(expr.abs() > self.threshold).then(expr).otherwise(0.0)


class WrapFilter(BaseFilter):
    type: Literal[FilterType.WRAP] = FilterType.WRAP
    lb: float = -np.pi
    ub: float = np.pi

    @model_validator(mode="after")
    def validate_bound(self) -> Self:
        if self.lb > self.ub:
            raise ValueError("Wrap filter lower bound must be less than upper bound")
        return self

    def apply(self, expr: pl.Expr) -> pl.Expr:
        range_val = self.ub - self.lb
        return ((expr - self.lb) % range_val) + self.lb


class MedianFilter(BaseFilter):
    type: Literal[FilterType.MEDIAN] = FilterType.MEDIAN
    window: int = Field(default=10, gt=0)

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return expr.rolling_median(window_size=self.window, center=True)


class NormalizeFilter(BaseFilter):
    type: Literal[FilterType.NORMALIZE] = FilterType.NORMALIZE

    def apply(self, expr: pl.Expr) -> pl.Expr:
        return (expr - expr.min()) / (expr.max() - expr.min() + 1e-9)


AnyFilter = Annotated[
    ScaleFilter
    | AbsoluteValueFilter
    | DerivativeFilter
    | IntegralFilter
    | LowPassFilter
    | HighPassFilter
    | RollingMeanFilter
    | ClipFilter
    | DeadbandFilter
    | ZeroingFilter
    | MedianFilter
    | NormalizeFilter
    | WrapFilter,
    Field(discriminator="type"),
]

filter_adapter = TypeAdapter(dict[str, list[AnyFilter]])
