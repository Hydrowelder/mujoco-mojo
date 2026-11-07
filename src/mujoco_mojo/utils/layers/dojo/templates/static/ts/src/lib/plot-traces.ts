// the plotly traces of a trial viewer plot, moved out of trial-viewer.ts so
// they can be tested without an alpine component: the line style and hover
// text of each signal, how integer-coded (enum) signals are drawn, and the
// faint traces of the versus (comparison) trials.

import {
  enumAxisIds,
  enumLabels,
  enumMapOf,
  planEnumAxes,
  type EnumPlan,
} from "./enum-axes";

// the resolved look of one signal (color, width, dash, marker, ...)
export interface YProps {
  name: string;
  label: string;
  color: string;
  width: number;
  opacity: number;
  dash: string;
  marker: string;
}

// one signal on the y-axis: its look, and its unit once filters are applied
export interface Series {
  key: string;
  props: YProps;
  unit: string | null;
}

export interface TraceColors {
  tooltipBg: string;
  tooltipFont: string;
  tooltipBorder: string;
}

// which signals are enum-coded, and what that does to the plot's axes
export interface EnumContext {
  plan: EnumPlan;
  // the signals that are not enum-coded
  numericKeys: string[];
  // true when only enum signals are drawn, so the first enum axis takes the
  // primary y slot instead of leaving an empty axis on the left
  enumPromoted: boolean;
  hasEnumAxes: boolean;
}

export interface TraceContext {
  isPolar: boolean;
  interp: string;
  lineMode: string;
  enum: EnumContext;
}

// integer-coded columns (those with an enumeration_map) sit on right-hand axes
// whose ticks are the enum names, one axis per distinct map (see enum-axes.ts).
export function enumContext(
  yKeys: string[],
  data: Record<string, number[]>,
  columnMetadata: Record<string, { enumeration_map?: unknown } | undefined>,
  isPolar: boolean,
): EnumContext {
  const plan = planEnumAxes(
    yKeys.filter((k) => data[k]),
    columnMetadata,
  );
  const numericKeys = yKeys.filter((k) => enumMapOf(columnMetadata[k]) === null);
  // with nothing numeric to draw, the first enum axis takes the primary slot so
  // the plot is not left with an empty axis on the left
  const enumPromoted =
    !isPolar && plan.groups.length > 0 && !numericKeys.some((k) => data[k]);
  const hasEnumAxes = !isPolar && plan.groups.length > 0;
  return { plan, numericKeys, enumPromoted, hasEnumAxes };
}

// a marker symbol of "none" hides per-point markers regardless of lineMode
export function traceMode(marker: string, lineMode: string): string {
  if (marker !== "none") return lineMode;
  if (lineMode === "lines+markers") return "lines";
  if (lineMode === "markers") return "none";
  return lineMode;
}

// a step line for an enum signal, since interpolating between two codes would
// draw values that never happened
export function lineShape(key: string, ctx: TraceContext): string {
  return !ctx.enum.plan.groupOf.has(key)
    ? ctx.interp
    : ctx.isPolar
      ? "linear"
      : "hv";
}

// the tooltip shows an enum point as its label (customdata) instead of the raw number
export function yHover(key: string, ref: "y" | "r", ctx: TraceContext): string {
  return ctx.enum.plan.groupOf.has(key) ? "%{customdata}" : `%{${ref}:.4f}`;
}

// per-trace extras for an enum column: the label of each point and, outside
// polar mode, which right-hand axis the trace belongs to
export function enumTrace(
  key: string,
  values: number[],
  ctx: TraceContext,
): object {
  const gi = ctx.enum.plan.groupOf.get(key);
  if (gi === undefined) return {};
  const traceRef = ctx.isPolar
    ? "y"
    : enumAxisIds(gi, ctx.enum.enumPromoted).traceRef;
  return {
    customdata: enumLabels(values, ctx.enum.plan.groups[gi]!),
    ...(traceRef !== "y" ? { yaxis: traceRef } : {}),
  };
}

// one trace per signal that has data, in signal order
export function primaryTraces(
  series: Series[],
  data: Record<string, number[]>,
  xCol: string,
  ctx: TraceContext,
  colors: TraceColors,
): object[] {
  return series
    .map(({ key, props: p, unit }) => {
      if (!data[p.name]) {
        return null;
      }
      const traceLabel =
        p.label + (unit ? ` (${unit.replace(/\s+/g, "")})` : "");
      const lineStyle = {
        width: p.width,
        color: p.color,
        shape: lineShape(key, ctx),
        dash: p.dash,
      };
      if (ctx.isPolar) {
        return {
          r: data[p.name]!,
          theta: data[xCol],
          name: traceLabel,
          mode: traceMode(p.marker, ctx.lineMode),
          type: "scatterpolar",
          line: lineStyle,
          marker: { size: 6, symbol: p.marker },
          opacity: p.opacity,
          hoverlabel: {
            namelength: -1,
            bgcolor: colors.tooltipBg,
            bordercolor: colors.tooltipBorder,
            font: { family: "monospace", size: 12, color: colors.tooltipFont },
          },
          hovertemplate: `<b>${key}</b><br>θ: %{theta:.4f}<br>r: ${yHover(key, "r", ctx)}<extra></extra>`,
          ...enumTrace(key, data[p.name]!, ctx),
        };
      }
      return {
        x: data[xCol],
        y: data[p.name]!,
        name: traceLabel,
        mode: traceMode(p.marker, ctx.lineMode),
        type: "scatter",
        line: lineStyle,
        marker: { size: 6, symbol: p.marker },
        opacity: p.opacity,
        hoverlabel: {
          namelength: -1,
          bgcolor: colors.tooltipBg,
          bordercolor: colors.tooltipBorder,
          font: { family: "monospace", size: 12, color: colors.tooltipFont },
        },
        hovertemplate: `<b>${key}</b><br>%{x}: ${yHover(key, "y", ctx)}<extra></extra>`,
        ...enumTrace(key, data[p.name]!, ctx),
      };
    })
    .filter((t): t is NonNullable<typeof t> => t !== null);
}

// the trial number at the end of a trial id like `run_12`
function trialNumber(id: string, fallback: string): number {
  return parseInt(id.split("_").pop() ?? fallback);
}

// the versus traces: for each comparison trial inside the range (or pinned),
// in trial-number order, a faint dotted line per signal it has data for. A
// signal's legend entry appears once, on the first trial that has it.
export function vsTraces(
  series: Series[],
  datasets: Record<string, Record<string, number[]>>,
  vs: { range: [number, number]; pinned?: number[] },
  trialId: string,
  xCol: string,
  ctx: TraceContext,
): object[] {
  const [start, end] = vs.range;
  const pinnedSet = new Set(vs.pinned ?? []);
  const legendTracker = new Set<string>();
  const sortedVsIds = Object.keys(datasets).sort(
    (a, b) => trialNumber(a, "0") - trialNumber(b, "0"),
  );
  let traces: object[] = [];
  sortedVsIds.forEach((vsId) => {
    const n = trialNumber(vsId, "");
    if (
      !((n >= start && n <= end) || pinnedSet.has(n)) ||
      vsId === trialId
    )
      return;
    const dataset = datasets[vsId];
    if (!dataset) return;
    const perTrial = series
      .map(({ key, props: p }) => {
        if (!dataset[p.name]) return null;
        const isFirst = !legendTracker.has(key);
        const lineStyle = {
          width: 1,
          color: p.color,
          shape: lineShape(key, ctx),
          dash: "dot",
        };
        const t = ctx.isPolar
          ? {
              r: dataset[p.name]!,
              theta: dataset[xCol],
              name: `${p.label} (<i>vs.</i>)`,
              legendgroup: `group_${key}`,
              showlegend: isFirst,
              mode: traceMode(p.marker, ctx.lineMode),
              type: "scatterpolar",
              line: lineStyle,
              opacity: 0.35,
              marker: { size: 4, symbol: p.marker },
              hoverlabel: { namelength: -1 },
              hovertemplate: `<b>${key}</b> (#${n})<br>θ: %{theta:.4f}<br>r: ${yHover(key, "r", ctx)}<extra></extra>`,
              ...enumTrace(key, dataset[p.name]!, ctx),
            }
          : {
              x: dataset[xCol],
              y: dataset[p.name]!,
              name: `${p.label} (<i>vs.</i>)`,
              legendgroup: `group_${key}`,
              showlegend: isFirst,
              mode: traceMode(p.marker, ctx.lineMode),
              type: "scatter",
              line: lineStyle,
              opacity: 0.35,
              marker: { size: 4, symbol: p.marker },
              hoverlabel: { namelength: -1 },
              hovertemplate: `<b>${key}</b> (#${n})<br>%{x}: ${yHover(key, "y", ctx)}<extra></extra>`,
              ...enumTrace(key, dataset[p.name]!, ctx),
            };
        legendTracker.add(key);
        return t;
      })
      .filter((t): t is NonNullable<typeof t> => t !== null);
    traces = [...traces, ...perTrial];
  });
  return traces;
}
