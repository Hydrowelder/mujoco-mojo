// ============================================================
// AUTO-GENERATED - do not edit manually.
// Source: src/mujoco_mojo/utils/layers/dojo/plot_config.py
// Regenerate: python scripts/gen_ts_models.py
// ============================================================

export interface Annotation {
  x: number;
  y: number;
  text: string;
}

export type DashStyle = "solid" | "dash" | "dot" | "dashdot";

export interface FilterEntry {
  type: string;
  enabled?: boolean;
  [key: string]: unknown;
}

export type GridMode = "none" | "major" | "all";

export type HoverMode = "x unified" | "y unified" | "closest" | "x" | "y" | "none";

export type InterpMode = "linear" | "spline" | "hv" | "vh" | "hvh" | "vhv";

export type LegendPos = "bottom" | "right" | "hidden";

export type LineMode = "lines" | "markers" | "lines+markers";

export type MarkerSymbol = "none" | "circle" | "square" | "diamond" | "cross";

export type PlotType = "cartesian" | "polar";

export type ScaleType = "linear" | "log";

export interface Shape {
  type: ShapeType;
  x0: number;
  x1?: number | null;
  y0?: number | null;
  y1?: number | null;
  color: string;
  dash?: DashStyle | null;
  label: string;
}

export type ShapeType = "vline" | "hline" | "rect";

export interface YAxisConfig {
  label: string;
  color: string;
  width: number;
  opacity: number;
  filters: FilterEntry[];
  dash: DashStyle;
  marker: MarkerSymbol;
}

/** Complete serialisable state of a trial-viewer plot. */
export interface PlotConfig {
  xAxis: string;
  yAxes: Record<string, YAxisConfig>;
  refFrame: string | null;
  grid: GridMode;
  linemode: LineMode;
  interp: InterpMode;
  hover: HoverMode;
  title: string;
  xAxisTitle: string;
  yAxisTitle: string;
  showSpike: boolean;
  legendPos: LegendPos;
  rangeX: [number, number] | null;
  rangeY: [number, number] | null;
  xScale: ScaleType;
  yScale: ScaleType;
  xLogBase?: number | null;
  yLogBase?: number | null;
  plotType?: PlotType;
  vsEnabled: boolean;
  vsRange: [number, number];
  annotations: Annotation[];
  shapes: Shape[];
}
