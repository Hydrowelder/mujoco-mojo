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

# ---------------------------------------------------------------------------
# String-enum types  (generate named TypeScript union types)
# ---------------------------------------------------------------------------


class DashStyle(StrEnum):
    solid = "solid"
    dash = "dash"
    dot = "dot"
    dashdot = "dashdot"


class MarkerSymbol(StrEnum):
    none = "none"
    circle = "circle"
    square = "square"
    diamond = "diamond"
    cross = "cross"


class GridMode(StrEnum):
    none = "none"
    major = "major"
    all = "all"


class LineMode(StrEnum):
    lines = "lines"
    markers = "markers"
    lines_and_markers = "lines+markers"


class InterpMode(StrEnum):
    linear = "linear"
    spline = "spline"
    hv = "hv"
    vh = "vh"
    hvh = "hvh"
    vhv = "vhv"


class HoverMode(StrEnum):
    x_unified = "x unified"
    y_unified = "y unified"
    closest = "closest"
    x = "x"
    y = "y"
    none = "none"


class LegendPos(StrEnum):
    bottom = "bottom"
    right = "right"
    hidden = "hidden"


class ScaleType(StrEnum):
    linear = "linear"
    log = "log"


class ShapeType(StrEnum):
    vline = "vline"
    hline = "hline"
    rect = "rect"


class PlotType(StrEnum):
    cartesian = "cartesian"
    polar = "polar"


# ---------------------------------------------------------------------------
# Composite models
# ---------------------------------------------------------------------------


class FilterEntry(BaseModel):
    """A single filter step applied to a signal.  Extra keys are preserved."""

    model_config = ConfigDict(extra="allow")

    type: str
    enabled: bool = True


class YAxisConfig(BaseModel):
    label: str
    color: str
    width: float
    opacity: float
    filters: list[FilterEntry]
    dash: DashStyle
    marker: MarkerSymbol


class Annotation(BaseModel):
    x: float
    y: float
    text: str


class Shape(BaseModel):
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

    xAxis: str
    yAxes: dict[str, YAxisConfig]
    refFrame: str | None
    grid: GridMode
    linemode: LineMode
    interp: InterpMode
    hover: HoverMode
    title: str
    xAxisTitle: str
    yAxisTitle: str
    showSpike: bool
    legendPos: LegendPos
    rangeX: Annotated[tuple[float, float], Field()] | None
    rangeY: Annotated[tuple[float, float], Field()] | None
    xScale: ScaleType
    yScale: ScaleType
    xLogBase: float | None = None
    yLogBase: float | None = None
    plotType: PlotType = PlotType.cartesian
    vsEnabled: bool
    vsRange: Annotated[tuple[float, float], Field()]
    annotations: list[Annotation]
    shapes: list[Shape]
