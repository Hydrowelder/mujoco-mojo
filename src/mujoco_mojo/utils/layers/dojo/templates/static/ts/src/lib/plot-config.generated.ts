// ============================================================
// AUTO-GENERATED - do not edit manually.
// Source: src/mujoco_mojo/utils/layers/dojo/plot_config.py
// Regenerate: python scripts/gen_ts_models.py
// ============================================================

export interface AbsoluteValueFilter {
  enabled?: boolean;
  type?: string;
}

export interface Annotation {
  x: number;
  y: number;
  text: string;
}

export interface ClipFilter {
  enabled?: boolean;
  type?: string;
  min?: number | null;
  max?: number | null;
}

export interface ComparisonFilter {
  enabled?: boolean;
  type?: string;
  operator?: "gt" | "gte" | "lt" | "lte" | "eq" | "neq";
  threshold?: number;
}

export type DashStyle = "solid" | "dash" | "dot" | "dashdot";

export interface DeadbandFilter {
  enabled?: boolean;
  type?: string;
  threshold?: number;
}

export interface DerivativeFilter {
  enabled?: boolean;
  type?: string;
  dt?: number;
  wrtCol?: string | null;
}

export interface ExpFilter {
  enabled?: boolean;
  type?: string;
  base?: number;
}

export type GridMode = "none" | "major" | "all";

export interface HighPassFilter {
  enabled?: boolean;
  type?: string;
  alpha?: number;
}

export type HoverMode = "x unified" | "y unified" | "closest" | "x" | "y" | "none";

export interface IntegralFilter {
  enabled?: boolean;
  type?: string;
  dt?: number;
  wrtCol?: string | null;
}

export type InterpMode = "linear" | "spline" | "hv" | "vh" | "hvh" | "vhv";

export type LegendPos = "bottom" | "right" | "hidden";

export type LineMode = "lines" | "markers" | "lines+markers";

export interface LogFilter {
  enabled?: boolean;
  type?: string;
  base?: number;
}

export interface LowPassFilter {
  enabled?: boolean;
  type?: string;
  alpha?: number;
}

export type MarkerSymbol = "none" | "circle" | "square" | "diamond" | "cross";

export interface MedianFilter {
  enabled?: boolean;
  type?: string;
  window?: number;
}

export interface NormalizeFilter {
  enabled?: boolean;
  type?: string;
}

export type PlotType = "cartesian" | "polar";

export interface PowerFilter {
  enabled?: boolean;
  type?: string;
  exponent?: number;
}

export interface RollingMeanFilter {
  enabled?: boolean;
  type?: string;
  window?: number;
  center?: boolean;
}

export interface RotationFilter {
  enabled?: boolean;
  type?: string;
  quatCol?: string;
  invert?: boolean;
}

export interface RoundFilter {
  enabled?: boolean;
  type?: string;
  method?: "round" | "floor" | "ceil";
  decimals?: number;
}

export interface SavitzkyGolayFilter {
  enabled?: boolean;
  type?: string;
  window?: number;
  order?: number;
}

export interface ScaleFilter {
  enabled?: boolean;
  type?: string;
  factor?: number;
  offset?: number;
}

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

export interface SignFilter {
  enabled?: boolean;
  type?: string;
}

export interface TaringFilter {
  enabled?: boolean;
  type?: string;
}

export interface TrigFilter {
  enabled?: boolean;
  type?: string;
  func?: "sin" | "cos" | "tan" | "asin" | "acos" | "atan" | "sinh" | "cosh" | "tanh" | "degrees" | "radians";
}

export interface UnitFilter {
  enabled?: boolean;
  type?: string;
  fromUnit: "rad" | "deg" | "mrad" | "rev" | "rpm" | "rad/s" | "deg/s" | "rad/s^2" | "deg/s^2" | "m" | "mm" | "cm" | "um" | "km" | "in" | "ft" | "thou" | "m/s" | "mm/s" | "cm/s" | "ft/s" | "in/s" | "km/h" | "mph" | "m/s^2" | "mm/s^2" | "ft/s^2" | "in/s^2" | "kg" | "g" | "mg" | "lbm" | "slug" | "N" | "mN" | "uN" | "kN" | "lbf" | "N*m" | "N*mm" | "mN*m" | "kN*m" | "lbf*ft" | "lbf*in" | "ozf*in" | "kg*m^2" | "kg*mm^2" | "lbm*in^2" | "lbm*ft^2" | "slug*ft^2" | "J" | "mJ" | "kJ" | "W*s" | "W*h" | "kW*h" | "ft*lbf" | "BTU" | "W" | "mW" | "kW" | "MW" | "hp" | "ft*lbf/s" | "Pa" | "kPa" | "MPa" | "psi" | "bar" | "atm" | "torr" | "s" | "ms" | "us" | "ns" | "min" | "hr" | "Hz" | "kHz" | "MHz" | "V" | "mV" | "kV" | "A" | "mA" | "dimensionless" | "pct" | "count" | "bit" | string;
  toUnit: "rad" | "deg" | "mrad" | "rev" | "rpm" | "rad/s" | "deg/s" | "rad/s^2" | "deg/s^2" | "m" | "mm" | "cm" | "um" | "km" | "in" | "ft" | "thou" | "m/s" | "mm/s" | "cm/s" | "ft/s" | "in/s" | "km/h" | "mph" | "m/s^2" | "mm/s^2" | "ft/s^2" | "in/s^2" | "kg" | "g" | "mg" | "lbm" | "slug" | "N" | "mN" | "uN" | "kN" | "lbf" | "N*m" | "N*mm" | "mN*m" | "kN*m" | "lbf*ft" | "lbf*in" | "ozf*in" | "kg*m^2" | "kg*mm^2" | "lbm*in^2" | "lbm*ft^2" | "slug*ft^2" | "J" | "mJ" | "kJ" | "W*s" | "W*h" | "kW*h" | "ft*lbf" | "BTU" | "W" | "mW" | "kW" | "MW" | "hp" | "ft*lbf/s" | "Pa" | "kPa" | "MPa" | "psi" | "bar" | "atm" | "torr" | "s" | "ms" | "us" | "ns" | "min" | "hr" | "Hz" | "kHz" | "MHz" | "V" | "mV" | "kV" | "A" | "mA" | "dimensionless" | "pct" | "count" | "bit" | string;
}

export interface WrapFilter {
  enabled?: boolean;
  type?: string;
  lb?: number;
  ub?: number;
}

export interface XAxisConfig {
  col?: string;
  filters?: unknown[];
}

export interface YAxisConfig {
  label: string;
  color: string;
  width: number;
  opacity: number;
  filters: unknown[];
  dash: DashStyle;
  marker: MarkerSymbol;
}

/** Complete serialisable state of a trial-viewer plot. */
export interface PlotConfig {
  xAxis?: XAxisConfig;
  yAxes: Record<string, YAxisConfig>;
  refFrame: string | null;
  grid: GridMode;
  lineMode: LineMode;
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
