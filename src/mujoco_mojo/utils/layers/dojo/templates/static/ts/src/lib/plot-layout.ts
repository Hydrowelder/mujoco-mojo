// the plotly layout of a trial viewer plot, moved out of trial-viewer.ts so it
// can be tested without an alpine component: axis titles and ranges, the
// right-hand axes of enum signals, the polar layout, legend and margins.

import { enumAxisIds, enumAxisLayout, enumRange } from "./enum-axes";
import type { PlotConfig } from "./plot-config.generated";
import type { EnumContext } from "./plot-traces";
import { refFrameActive, refFrameLabel, type RefFrame } from "./ref-frame";

// the theme colors a layout uses, resolved by the caller
export interface LayoutColors {
  text: string;
  majorGrid: string;
  minorGrid: string;
  tooltipBg: string;
  tooltipFont: string;
  tooltipBorder: string;
  spike: string;
  title: string;
}

// whether hovering is on, and which spike lines (across the plot, at the
// hovered point) each axis shows
export function hoverFlags(
  hover: string,
  showSpike: boolean,
): { isHoverDisabled: boolean; showX: boolean; showY: boolean } {
  const isHoverDisabled = hover === "none";
  const showX =
    showSpike &&
    !isHoverDisabled &&
    (hover.includes("x") || hover === "closest");
  const showY =
    showSpike &&
    !isHoverDisabled &&
    (hover.includes("y") || hover === "closest");
  return { isHoverDisabled, showX, showY };
}

// the x-axis title: the one set in the config, else "column (unit)"
export function xAxisText(
  xAxisTitle: string,
  xCol: string,
  xUnit: string | null,
): string {
  return (
    xAxisTitle || (xUnit ? `${xCol} (${xUnit.replace(/\s+/g, "")})` : xCol)
  );
}

// same "column (unit)" fallback the x-axis title has, extended for the fact
// that the y-axis can have several signals: with exactly one, mirror the
// x-axis exactly; with several, fall back to just the shared unit (e.g.
// "N·m") if they all agree on one, since concatenating every column name
// doesn't read as a title. No fallback (blank) if units disagree. Enum
// columns have axes of their own, so they take no part in the primary axis.
export function yAxisText(
  yAxisTitle: string,
  yCols: string[],
  yUnitList: Array<string | null>,
): string {
  const yUnitsShared =
    yUnitList.length > 0 && yUnitList.every((u) => u && u === yUnitList[0])
      ? yUnitList[0]
      : null;
  const yAxisFallback =
    yCols.length === 1
      ? yUnitsShared
        ? `${yCols[0]} (${yUnitsShared.replace(/\s+/g, "")})`
        : yCols[0]!
      : (yUnitsShared ?? "");
  return yAxisTitle || yAxisFallback;
}

// the note under the y-axis title naming the reference frame, when one is set
export function frameLabel(refFrame: RefFrame, textColor: string): string {
  return refFrameActive(refFrame)
    ? `<br><span style="color: ${textColor}; font-size: 14px; opacity: 0.6;">[Frame: ${refFrameLabel(refFrame)}]</span>`
    : "";
}

export interface AxisInput {
  scale: string | null | undefined;
  logBase: number | null | undefined;
  // the range to fix the axis to, or null to let plotly pick one
  resolvedRange: [number, number] | null;
  grid: string;
  title: string;
  showSpikes: boolean;
  colors: LayoutColors;
}

// a numeric axis. a log axis takes its range as exponents, with anything at or
// below 1e-6 raised to it first since a log of zero or less does not exist
export function cartesianAxis(a: AxisInput): object {
  return {
    type: a.scale ?? "linear",
    ...(a.resolvedRange
      ? {
          autorange: false as const,
          range:
            a.scale === "log"
              ? [
                  Math.log10(Math.max(1e-6, a.resolvedRange[0])),
                  Math.log10(Math.max(1e-6, a.resolvedRange[1])),
                ]
              : a.resolvedRange,
        }
      : { autorange: true as const }),
    dtick:
      a.scale === "log" && a.logBase ? Math.log10(a.logBase) : undefined,
    gridcolor: a.colors.majorGrid,
    showgrid: a.grid !== "none",
    minor: { showgrid: a.grid === "all", gridcolor: a.colors.minorGrid },
    zeroline: false,
    tickfont: { color: a.colors.text, size: 14 },
    title: {
      text: a.title,
      font: { size: 14, color: a.colors.text, family: "monospace" },
    },
    showspikes: a.showSpikes,
    spikemode: "across",
    spikelinecolor: a.colors.spike,
    spikethickness: -2,
  };
}

// one right-hand axis per distinct enum map; when promoted the first one is
// keyed `yaxis` and so replaces the (empty) primary axis.
export function enumAxesLayout(
  enumCtx: EnumContext,
  yAxisTitle: string,
  labelOf: (col: string) => string,
  data: Record<string, number[]>,
  colors: LayoutColors,
  grid: string,
): Record<string, unknown> {
  const enumLayout: Record<string, unknown> = {};
  enumCtx.plan.groups.forEach((group, gi) => {
    const ids = enumAxisIds(gi, enumCtx.enumPromoted);
    const primary = ids.layoutKey === "yaxis";
    // a lone signal names the axis; a shared axis just counts its signals. the
    // text uses the same color as the other axes, since the legend carries the trace colors
    const only = group.columns.length === 1 ? group.columns[0]! : null;
    const label = only ? labelOf(only) : null;
    const title =
      primary && yAxisTitle
        ? yAxisTitle
        : label !== null
          ? label
          : `${group.columns.length} signals`;
    enumLayout[ids.layoutKey] = enumAxisLayout(group, {
      title,
      range: enumRange(
        group,
        group.columns.map((c) => data[c]!),
      ),
      color: colors.text,
      primary,
      grid: { color: colors.majorGrid, show: grid !== "none" },
    });
  });
  return enumLayout;
}

export function polarLayout(
  colors: LayoutColors,
  yText: string,
  xText: string,
): object {
  return {
    polar: {
      bgcolor: "rgba(0,0,0,0)",
      radialaxis: {
        color: colors.text,
        gridcolor: colors.majorGrid,
        tickfont: { color: colors.text, size: 14, family: "monospace" },
        title: {
          text: yText || "r",
          font: { size: 14, color: colors.text, family: "monospace" },
        },
      },
      angularaxis: {
        color: colors.text,
        gridcolor: colors.majorGrid,
        tickfont: { color: colors.text, size: 14, family: "monospace" },
        title: {
          text: xText,
          font: { size: 14, color: colors.text, family: "monospace" },
        },
      },
    },
  };
}

export function legendLayout(
  legendPos: string,
  hasEnumAxes: boolean,
  textColor: string,
): object {
  return legendPos === "right"
    ? {
        orientation: "v",
        // hanging off the plot edge would sit on the enum axes, so with
        // them the legend anchors to the container edge and Plotly widens the margin
        ...(hasEnumAxes
          ? { xref: "container", x: 1, xanchor: "right" }
          : { x: 1.02 }),
        y: 1,
        font: { family: "monospace", size: 14, color: textColor },
        groupclick: "togglegroup",
      }
    : {
        orientation: "h",
        y: -0.2,
        x: 0.5,
        xanchor: "center",
        font: { family: "monospace", size: 14, color: textColor },
        groupclick: "togglegroup",
      };
}

// beside enum axes the margins are Plotly's to grow (the axes use automargin),
// so the fixed legend gutter and the empty left axis are dropped.
export function plotMargins(
  title: string,
  legendPos: string,
  hasEnumAxes: boolean,
  enumPromoted: boolean,
  yText: string,
): { t: number; r: number; b: number; l: number } {
  return {
    t: title ? 60 : 30,
    r: legendPos === "right" && !hasEnumAxes ? 150 : 30,
    b: legendPos === "bottom" ? 80 : 50,
    l: enumPromoted ? 30 : yText ? 80 : 60,
  };
}

export interface LayoutInput {
  trialId: string;
  config: PlotConfig;
  isPolar: boolean;
  enum: EnumContext;
  // the fixed ranges (null for automatic), resolved by the caller from the
  // config and the data
  resolvedRangeX: [number, number] | null;
  resolvedRangeY: [number, number] | null;
  xUnit: string | null;
  // the unit of each numeric (not enum) signal
  yUnitList: Array<string | null>;
  labelOf: (col: string) => string;
  data: Record<string, number[]>;
  colors: LayoutColors;
  // the plotly annotations and shapes (see overlays.ts)
  overlays: { annotations: object[]; shapes: object[] };
}

// the whole plotly layout of a plot
export function buildLayout(input: LayoutInput): object {
  const { config, isPolar, colors } = input;
  const flags = hoverFlags(config.hover, config.showSpike);
  const xCol = config.xAxis!.col!;
  const xText = xAxisText(config.xAxisTitle, xCol, input.xUnit);
  const yText = yAxisText(
    config.yAxisTitle,
    input.enum.numericKeys,
    input.yUnitList,
  );

  const xAxisObj = cartesianAxis({
    scale: config.xScale,
    logBase: config.xLogBase,
    resolvedRange: input.resolvedRangeX,
    grid: config.grid,
    title: xText,
    showSpikes: flags.showX,
    colors,
  });
  const yAxisObj = cartesianAxis({
    scale: config.yScale,
    logBase: config.yLogBase,
    resolvedRange: input.resolvedRangeY,
    grid: config.grid,
    title: yText + frameLabel(config.refFrame, colors.text),
    showSpikes: flags.showY,
    colors,
  });

  const enumLayout = isPolar
    ? {}
    : enumAxesLayout(
        input.enum,
        config.yAxisTitle,
        input.labelOf,
        input.data,
        colors,
        config.grid,
      );

  const polar = isPolar
    ? polarLayout(colors, yText, xText)
    : { xaxis: xAxisObj, yaxis: yAxisObj, ...enumLayout };

  return {
    uirevision: `${input.trialId}_${xCol}_${Object.keys(config.yAxes).join("_")}_${config.plotType}`,
    title: config.title
      ? {
          text: config.title,
          font: {
            family: "monospace",
            size: 16,
            color: colors.title,
            weight: "bold",
          },
          x: 0,
          xanchor: "left",
        }
      : null,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: plotMargins(
      config.title,
      config.legendPos,
      input.enum.hasEnumAxes,
      input.enum.enumPromoted,
      yText,
    ),
    hovermode: flags.isHoverDisabled ? false : config.hover,
    hoverlabel: {
      bgcolor: colors.tooltipBg,
      bordercolor: colors.tooltipBorder,
      font: { family: "monospace", size: 12, color: colors.tooltipFont },
      align: "left",
    },
    showlegend: config.legendPos !== "hidden",
    legend: legendLayout(
      config.legendPos,
      input.enum.hasEnumAxes,
      colors.text,
    ),
    ...polar,
    annotations: input.overlays.annotations,
    shapes: input.overlays.shapes,
  };
}
