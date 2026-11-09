// the plot config a fresh trial viewer starts from, and what the Plot Editor
// does with it: showing a field's default in its help, and resetting a field

import type { PlotConfig } from "../models";
import { formatDefaultValue } from "./format";

export const DEFAULT_CONFIG: PlotConfig = {
  xAxis: { col: "time", filters: [] },
  yAxes: {},
  refFrame: [null, null],
  grid: "all",
  lineMode: "lines+markers",
  interp: "linear",
  hover: "closest",
  title: "",
  xAxisTitle: "",
  yAxisTitle: "",
  showSpike: true,
  legendPos: "bottom",
  rangeX: null,
  rangeY: null,
  xScale: "linear",
  yScale: "linear",
  xLogBase: null,
  yLogBase: null,
  plotType: "cartesian",
  annotations: [],
  shapes: [],
  displayUnitSystem: null,
  maxPoints: null,
};

const defaults = DEFAULT_CONFIG as unknown as Record<string, unknown>;

// whether `key` is a config field with a default
export function hasPlotDefault(key: string): boolean {
  return key in DEFAULT_CONFIG;
}

// `description` with a "Default: `X`." line added, unless the schema's own text
// already has one or the field has no default here
export function withDefaultNote(description: string, key: string): string {
  if (!description || description.includes("\n\nDefault:")) return description;
  if (!hasPlotDefault(key)) return description;
  return `${description}\n\nDefault: \`${formatDefaultValue(defaults[key])}\`.`;
}

// Whether config[key] currently matches DEFAULT_CONFIG[key] - drives
// the per-field reset icon's x-show (_macros.html's field_reset_icon),
// the same "only show a reset affordance once there's something to
// reset" behavior the Dojo settings panel's own per-field reset icon
// uses. JSON.stringify rather than === since a couple of these
// (rangeX/rangeY) are small arrays, not primitives - reference
// equality would never match even when the values are identical.
export function isPlotFieldDefault(config: PlotConfig, key: string): boolean {
  if (!hasPlotDefault(key)) return true;
  const current = (config as unknown as Record<string, unknown>)[key];
  return JSON.stringify(current) === JSON.stringify(defaults[key]);
}

// a copy of the field's default to assign when resetting it. deep-clones any
// object/array default (rangeX/rangeY are the only such fields among the Plot
// Editor's own, but this stays correct if a future field needs it too) so
// resetting two fields back to back can never have one's reset mutate
// DEFAULT_CONFIG's own array/object and silently change the other's "default"
// out from under it.
export function plotDefaultCopy(key: string): unknown {
  const value = defaults[key];
  return typeof value === "object" && value !== null ? (JSON.parse(JSON.stringify(value)) as unknown) : value;
}

// Maps a shape's own "type" discriminator (ShapeType's values: "vline"/
// "hline"/"rect") to its $defs name, for plotDefFieldHelp calls in the
// Shape editor whose defName has to follow shapeDraft.type rather than
// being fixed per call site (fields like x0/y0/dash/color are shared
// across more than one shape type, each with its own description).
export function shapeDefName(type: string): string {
  if (type === "vline") return "VlineShape";
  if (type === "hline") return "HlineShape";
  return "RectShape";
}
