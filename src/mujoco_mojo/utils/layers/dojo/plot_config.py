"""
Pydantic models for the Dojo trial-viewer PlotConfig.

These are the single source of truth for both server-side validation
(profile save/load) and the generated TypeScript types in
``lib/plot-config.generated.ts``.

To regenerate TypeScript types after changing this file:

    python scripts/gen_ts_models.py
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from mujoco_mojo.utils.filters.filters import AnyFilter

# ---------------------------------------------------------------------------
# String-enum types  (generate named TypeScript union types)
# ---------------------------------------------------------------------------

camel_case_dict = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    serialize_by_alias=True,
)


class DashStyle(StrEnum):
    """Dash pattern applied to a plot line."""

    SOLID = "solid"
    """Unbroken line."""

    DASH = "dash"
    """Evenly spaced dashes."""

    DOT = "dot"
    """Evenly spaced dots."""

    DASHDOT = "dashdot"
    """Alternating dash and dot."""


class MarkerSymbol(StrEnum):
    """Shape used to mark individual data points."""

    NONE = "none"
    """No marker."""

    CIRCLE = "circle"
    """Circular marker."""

    SQUARE = "square"
    """Square marker."""

    DIAMOND = "diamond"
    """Diamond marker."""

    CROSS = "cross"
    """Cross (+) marker."""


class GridMode(StrEnum):
    """Which grid lines are drawn on the plot."""

    NONE = "none"
    """No grid lines."""

    MAJOR = "major"
    """Major tick grid lines only."""

    ALL = "all"
    """Major and minor tick grid lines."""


class LineMode(StrEnum):
    """Controls whether traces are drawn as lines, markers, or both."""

    LINES = "lines"
    """Connected line only."""

    MARKERS = "markers"
    """Individual point markers only."""

    LINES_AND_MARKERS = "lines+markers"
    """Connected line with point markers."""


class InterpMode(StrEnum):
    """Line interpolation method between data points."""

    LINEAR = "linear"
    """Straight segments between points."""

    SPLINE = "spline"
    """Smooth cubic spline."""

    HV = "hv"
    """Horizontal then vertical step."""

    VH = "vh"
    """Vertical then horizontal step."""

    HVH = "hvh"
    """Horizontal-vertical-horizontal step."""

    VHV = "vhv"
    """Vertical-horizontal-vertical step."""


class HoverMode(StrEnum):
    """Tooltip behavior when hovering over the plot."""

    X_UNIFIED = "x unified"
    """Single tooltip showing all series at the hovered x value."""

    Y_UNIFIED = "y unified"
    """Single tooltip showing all series at the hovered y value."""

    CLOSEST = "closest"
    """Tooltip for the nearest individual data point."""

    X = "x"
    """Per-series tooltips triggered by x proximity."""

    Y = "y"
    """Per-series tooltips triggered by y proximity."""

    NONE = "none"
    """Tooltips disabled."""


class LegendPos(StrEnum):
    """Position of the plot legend."""

    BOTTOM = "bottom"
    """Legend below the plot area."""

    RIGHT = "right"
    """Legend to the right of the plot area."""

    HIDDEN = "hidden"
    """Legend not shown."""


class ScaleType(StrEnum):
    """Numeric scale type for an axis."""

    LINEAR = "linear"
    """Uniform linear scale."""

    LOG = "log"
    """Logarithmic scale."""


class ShapeType(StrEnum):
    """Geometric shape drawn as an annotation on the plot."""

    VLINE = "vline"
    """Vertical line at a fixed x value."""

    HLINE = "hline"
    """Horizontal line at a fixed y value."""

    RECT = "rect"
    """Filled rectangle defined by x0, x1, y0, y1."""


class PlotType(StrEnum):
    """Coordinate system used to render the plot."""

    CARTESIAN = "cartesian"
    """Standard x/y Cartesian axes."""

    POLAR = "polar"
    """Polar coordinates (r/theta)."""


# ---------------------------------------------------------------------------
# Composite models
# ---------------------------------------------------------------------------


class XAxisConfig(BaseModel):
    """Configuration for the x-axis signal and its filter chain."""

    model_config = camel_case_dict

    col: str = "time"
    """Column name used as the x-axis source."""

    filters: list[AnyFilter] = []
    """Ordered list of filters applied to the x-axis signal."""


class YAxisConfig(BaseModel):
    """Visual and filter configuration for a single y-axis signal."""

    model_config = camel_case_dict

    label: str
    """Display label shown in the legend and tooltip."""

    color: str
    """Line color as a CSS color string."""

    width: float = Field(gt=0)
    """Line stroke width in pixels."""

    opacity: float = Field(ge=0, le=1)
    """Line opacity from 0 (transparent) to 1 (opaque)."""

    filters: list[AnyFilter]
    """Ordered list of filters applied to this signal."""

    dash: DashStyle
    """Dash pattern for the line."""

    marker: MarkerSymbol
    """Marker symbol drawn at each data point."""


class Annotation(BaseModel):
    """A text label pinned to a specific data coordinate."""

    model_config = camel_case_dict

    x: float
    """x-axis coordinate of the annotation anchor."""

    y: float
    """y-axis coordinate of the annotation anchor."""

    text: str
    """Annotation text content."""


class Shape(BaseModel):
    """A geometric shape drawn over the plot as a reference marker."""

    model_config = camel_case_dict

    type: ShapeType
    """Shape variant (vertical line, horizontal line, or rectangle)."""

    x0: float
    """Left x coordinate. For `vline` this is the line position."""

    x1: float | None = None
    """Right x coordinate. Required for `rect`."""

    y0: float | None = None
    """Bottom y coordinate. Required for `rect` and `hline`."""

    y1: float | None = None
    """Top y coordinate. Required for `rect`."""

    color: str
    """Fill/stroke color as a CSS color string."""

    dash: DashStyle | None = None
    """Dash pattern for the shape border. `None` uses a solid stroke."""

    label: str
    """Short label displayed alongside the shape."""

    @model_validator(mode="after")
    def validate_coords(self) -> Shape:
        if self.type == ShapeType.HLINE:
            if self.y0 is None:
                raise ValueError("hline requires y0")
        if self.type == ShapeType.RECT:
            if self.x1 is None or self.y0 is None or self.y1 is None:
                raise ValueError("rect requires x1, y0, and y1")
            if self.x0 >= self.x1:
                raise ValueError("rect requires x0 < x1")
            if self.y0 >= self.y1:
                raise ValueError("rect requires y0 < y1")
        return self


class PlotConfig(BaseModel):
    """Complete serialisable state of a trial-viewer plot."""

    model_config = camel_case_dict

    x_axis: XAxisConfig = Field(default_factory=XAxisConfig)
    """X-axis signal selection and filter chain."""

    y_axes: dict[str, YAxisConfig]
    """Mapping of signal key to y-axis configuration."""

    ref_frame: str | None
    """Reference frame used to transform signal coordinates. `None` for world frame."""

    grid: GridMode
    """Grid line visibility."""

    line_mode: LineMode
    """Whether traces render as lines, markers, or both."""

    interp: InterpMode
    """Interpolation method drawn between data points."""

    hover: HoverMode
    """Tooltip behavior on hover."""

    title: str
    """Plot title displayed above the chart."""

    x_axis_title: str
    """Label shown along the x-axis."""

    y_axis_title: str
    """Label shown along the y-axis."""

    show_spike: bool
    """Whether to draw spike lines from the hovered point to each axis."""

    legend_pos: LegendPos
    """Legend placement relative to the plot area."""

    range_x: Annotated[tuple[float, float], Field()] | None
    """Fixed x-axis range as `(min, max)`. `None` enables auto-range."""

    range_y: Annotated[tuple[float, float], Field()] | None
    """Fixed y-axis range as `(min, max)`. `None` enables auto-range."""

    x_scale: ScaleType
    """Scale type for the x-axis."""

    y_scale: ScaleType
    """Scale type for the y-axis."""

    x_log_base: float | None = Field(default=None, gt=1)
    """Logarithm base for the x-axis. Only used when `x_scale` is `log`."""

    y_log_base: float | None = Field(default=None, gt=1)
    """Logarithm base for the y-axis. Only used when `y_scale` is `log`."""

    plot_type: PlotType = PlotType.CARTESIAN
    """Coordinate system used to render the plot."""

    vs_enabled: bool
    """Whether comparison traces from other trials are shown."""

    vs_range: Annotated[tuple[float, float], Field()]
    """Trial number range for comparison traces as `(first, last)`."""

    annotations: list[Annotation]
    """Text annotations pinned to data coordinates."""

    shapes: list[Shape]
    """Geometric reference shapes drawn over the plot."""

    @model_validator(mode="after")
    def validate_ranges(self) -> PlotConfig:
        if self.range_x is not None and self.range_x[0] >= self.range_x[1]:
            raise ValueError("range_x min must be less than max")
        if self.range_y is not None and self.range_y[0] >= self.range_y[1]:
            raise ValueError("range_y min must be less than max")
        if self.vs_range[0] > self.vs_range[1]:
            raise ValueError("vs_range first must be <= last")
        if self.x_scale == ScaleType.LOG and self.x_log_base is None:
            raise ValueError("x_log_base is required when x_scale is log")
        if self.y_scale == ScaleType.LOG and self.y_log_base is None:
            raise ValueError("y_log_base is required when y_scale is log")
        return self
