// ---------------------------------------------------------------------------
// Option arrays — single source of truth for every select/dropdown in the UI.
// Each array is `as const` so element types narrow to their literal values.
// ---------------------------------------------------------------------------

export const DASH_OPTIONS = ['solid', 'dash', 'dot', 'dashdot'] as const;
export type DashStyle = (typeof DASH_OPTIONS)[number];

export const MARKER_OPTIONS = ['none', 'circle', 'square', 'diamond', 'cross'] as const;
export type MarkerSymbol = (typeof MARKER_OPTIONS)[number];

export const GRID_OPTIONS = ['none', 'major', 'all'] as const;
export type GridMode = (typeof GRID_OPTIONS)[number];

export const LINE_MODE_OPTIONS = [
  { label: 'Lines', value: 'lines' },
  { label: 'Markers', value: 'markers' },
  { label: 'Both', value: 'lines+markers' },
] as const;
export type LineMode = (typeof LINE_MODE_OPTIONS)[number]['value'];

export const INTERP_OPTIONS = [
  { label: 'Linear', value: 'linear' },
  { label: 'Spline', value: 'spline' },
  { label: 'Step (HV)', value: 'hv' },
  { label: 'Step (VH)', value: 'vh' },
  { label: 'Step (HVH)', value: 'hvh' },
  { label: 'Step (VHV)', value: 'vhv' },
] as const;
export type InterpMode = (typeof INTERP_OPTIONS)[number]['value'];

export const HOVER_OPTIONS = [
  { label: 'Unified X', value: 'x unified' },
  { label: 'Unified Y', value: 'y unified' },
  { label: 'Closest', value: 'closest' },
  { label: 'X Axis', value: 'x' },
  { label: 'Y Axis', value: 'y' },
  { label: 'Off', value: 'none' },
] as const;
export type HoverMode = (typeof HOVER_OPTIONS)[number]['value'];

export const LEGEND_POS_OPTIONS = ['bottom', 'right', 'hidden'] as const;
export type LegendPos = (typeof LEGEND_POS_OPTIONS)[number];

export const SCALE_OPTIONS = ['linear', 'log'] as const;
export type ScaleType = (typeof SCALE_OPTIONS)[number];

// ---------------------------------------------------------------------------
// Label-lookup helpers — derive the display string for a current config value.
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
