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

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# ---------------------------------------------------------------------------
# String-enum types  (generate named TypeScript union types)
# ---------------------------------------------------------------------------

camel_case_dict = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    serialize_by_alias=True,
)

camel_case_dict_extra = camel_case_dict.copy()
camel_case_dict_extra["extra"] = "allow"


class DashStyle(StrEnum):
    SOLID = "solid"
    DASH = "dash"
    DOT = "dot"
    DASHDOT = "dashdot"


class MarkerSymbol(StrEnum):
    NONE = "none"
    CIRCLE = "circle"
    SQUARE = "square"
    DIAMOND = "diamond"
    CROSS = "cross"


class GridMode(StrEnum):
    NONE = "none"
    MAJOR = "major"
    ALL = "all"


class LineMode(StrEnum):
    LINES = "lines"
    MARKERS = "markers"
    LINES_AND_MARKERS = "lines+markers"


class InterpMode(StrEnum):
    LINEAR = "linear"
    SPLINE = "spline"
    HV = "hv"
    VH = "vh"
    HVH = "hvh"
    VHV = "vhv"


class HoverMode(StrEnum):
    X_UNIFIED = "x unified"
    Y_UNIFIED = "y unified"
    CLOSEST = "closest"
    X = "x"
    Y = "y"
    NONE = "none"


class LegendPos(StrEnum):
    BOTTOM = "bottom"
    RIGHT = "right"
    HIDDEN = "hidden"


class ScaleType(StrEnum):
    LINEAR = "linear"
    LOG = "log"


class ShapeType(StrEnum):
    VLINE = "vline"
    HLINE = "hline"
    RECT = "rect"


class PlotType(StrEnum):
    CARTESIAN = "cartesian"
    POLAR = "polar"


# ---------------------------------------------------------------------------
# Composite models
# ---------------------------------------------------------------------------


class FilterEntry(BaseModel):
    """A single filter step applied to a signal.  Extra keys are preserved."""

    model_config = camel_case_dict_extra

    type: str
    enabled: bool = True


class XAxisConfig(BaseModel):
    model_config = camel_case_dict

    col: str = "time"
    filters: list[FilterEntry] = []


class YAxisConfig(BaseModel):
    model_config = camel_case_dict

    label: str
    color: str
    width: float
    opacity: float
    filters: list[FilterEntry]
    dash: DashStyle
    marker: MarkerSymbol


class Annotation(BaseModel):
    model_config = camel_case_dict

    x: float
    y: float
    text: str


class Shape(BaseModel):
    model_config = camel_case_dict

    type: ShapeType
    x0: float
    x1: float | None = None
    y0: float | None = None
    y1: float | None = None
    color: str
    dash: DashStyle | None = None
    label: str


class PlotConfig(BaseModel):
    """Complete serialisable state of a trial-viewer plot."""

    model_config = camel_case_dict

    x_axis: XAxisConfig = Field(default_factory=XAxisConfig)
    y_axes: dict[str, YAxisConfig]
    ref_frame: str | None
    grid: GridMode
    line_mode: LineMode
    interp: InterpMode
    hover: HoverMode
    title: str
    x_axis_title: str
    y_axis_title: str
    show_spike: bool
    legend_pos: LegendPos
    range_x: Annotated[tuple[float, float], Field()] | None
    range_y: Annotated[tuple[float, float], Field()] | None
    x_scale: ScaleType
    y_scale: ScaleType
    x_log_base: float | None = None
    y_log_base: float | None = None
    plot_type: PlotType = PlotType.CARTESIAN
    vs_enabled: bool
    vs_range: Annotated[tuple[float, float], Field()]
    annotations: list[Annotation]
    shapes: list[Shape]
