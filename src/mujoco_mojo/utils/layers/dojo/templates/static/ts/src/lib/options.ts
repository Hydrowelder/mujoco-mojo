// ---------------------------------------------------------------------------
// Option arrays - single source of truth for every select/dropdown in the UI.
// Each array is `as const` so element types narrow to their literal values.
//
// Named types (DashStyle, GridMode, …) are generated from plot_config.py
// and imported from plot-config.generated.ts to avoid duplication.
// ---------------------------------------------------------------------------

import {
  DASH_STYLE_VALUES,
  GRID_MODE_VALUES,
  LEGEND_POS_VALUES,
  MARKER_SYMBOL_VALUES,
  SCALE_TYPE_VALUES,
} from "./plot-config.generated";
import type {
  DashStyle,
  GridMode,
  HoverMode,
  InterpMode,
  LegendPos,
  LineMode,
  MarkerSymbol,
  ScaleType,
} from "./plot-config.generated";

export type {
  DashStyle,
  GridMode,
  HoverMode,
  InterpMode,
  LegendPos,
  LineMode,
  MarkerSymbol,
  ScaleType,
};

// Bare-value option arrays are derived from the generated *_VALUES constants
// (sourced from the Pydantic StrEnums in plot_config.py) so new enum members
// show up in the UI automatically without editing this file.
export const DASH_OPTIONS: DashStyle[] = DASH_STYLE_VALUES;

export const MARKER_OPTIONS: MarkerSymbol[] = MARKER_SYMBOL_VALUES;

export const GRID_OPTIONS: GridMode[] = GRID_MODE_VALUES;

export const LINE_MODE_OPTIONS = [
  { label: "Lines", value: "lines" as LineMode },
  { label: "Markers", value: "markers" as LineMode },
  { label: "Both", value: "lines+markers" as LineMode },
] as const;

export const INTERP_OPTIONS = [
  { label: "Linear", value: "linear" as InterpMode },
  { label: "Spline", value: "spline" as InterpMode },
  { label: "Step (HV)", value: "hv" as InterpMode },
  { label: "Step (VH)", value: "vh" as InterpMode },
  { label: "Step (HVH)", value: "hvh" as InterpMode },
  { label: "Step (VHV)", value: "vhv" as InterpMode },
] as const;

export const HOVER_OPTIONS = [
  { label: "Unified X", value: "x unified" as HoverMode },
  { label: "Unified Y", value: "y unified" as HoverMode },
  { label: "Closest", value: "closest" as HoverMode },
  { label: "X Axis", value: "x" as HoverMode },
  { label: "Y Axis", value: "y" as HoverMode },
  { label: "Off", value: "none" as HoverMode },
] as const;

export const LEGEND_POS_OPTIONS: LegendPos[] = LEGEND_POS_VALUES;

export const SCALE_OPTIONS: ScaleType[] = SCALE_TYPE_VALUES;

// ---------------------------------------------------------------------------
// Label-lookup helpers - derive the display string for a current config value.
// ---------------------------------------------------------------------------

function labelOf<T extends { label: string; value: string }>(
  options: readonly T[],
  value: string,
): string {
  return options.find((o) => o.value === value)?.label ?? value;
}

// ---------------------------------------------------------------------------
// The OPTIONS object is exposed on the Alpine component as `opts`.
// Templates use `opts.lineMode`, `opts.lineModeLabel(config.linemode)`, etc.
// ---------------------------------------------------------------------------

export const OPTIONS = {
  dash: DASH_OPTIONS,
  marker: MARKER_OPTIONS,
  grid: GRID_OPTIONS,
  lineMode: LINE_MODE_OPTIONS,
  interp: INTERP_OPTIONS,
  hover: HOVER_OPTIONS,
  legendPos: LEGEND_POS_OPTIONS,
  scale: SCALE_OPTIONS,

  lineModeLabel: (v: string) => labelOf(LINE_MODE_OPTIONS, v),
  interpLabel: (v: string) => labelOf(INTERP_OPTIONS, v),
  hoverLabel: (v: string) => labelOf(HOVER_OPTIONS, v),
} as const;

export type Options = typeof OPTIONS;
