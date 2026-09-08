// ============================================================
// AUTO-GENERATED - do not edit manually.
// Source: src/mujoco_mojo/utils/layers/dojo/plot_config.py
// Regenerate: python scripts/gen_ts_models.py
// ============================================================

/** a single filter in a filter stack — type-discriminated, open-ended properties. */
export type FilterEntry = { type: string; enabled?: boolean; [key: string]: unknown };

export interface AbsoluteValueFilter {
  enabled?: boolean;
  type?: "absolute_value";
}

export interface Annotation {
  x: number;
  y: number;
  text: string;
}

export interface ClipFilter {
  enabled?: boolean;
  type?: "clip";
  min?: number | null;
  max?: number | null;
}

export interface ComparisonFilter {
  enabled?: boolean;
  type?: "comparison";
  operator?: "gt" | "gte" | "lt" | "lte" | "eq" | "neq";
  threshold?: number;
}

export type DashStyle = "solid" | "dash" | "dot" | "dashdot" | "longdash" | "longdashdot";
export const DASH_STYLE_VALUES: DashStyle[] = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"];

export interface DeadbandFilter {
  enabled?: boolean;
  type?: "deadband";
  threshold?: number;
}

export interface DerivativeFilter {
  enabled?: boolean;
  type?: "derivative";
  dt?: number;
  wrtCol?: string | null;
}

export type DisplayUnitSystem = "si" | "cgs" | "fps" | "ips" | "fff";
export const DISPLAY_UNIT_SYSTEM_VALUES: DisplayUnitSystem[] = ["si", "cgs", "fps", "ips", "fff"];

export interface ExpFilter {
  enabled?: boolean;
  type?: "exp";
  base?: number;
}

export interface FirstFilter {
  enabled?: boolean;
  type?: "stat_first";
}

export type GridMode = "none" | "major" | "all";
export const GRID_MODE_VALUES: GridMode[] = ["none", "major", "all"];

export interface HighPassFilter {
  enabled?: boolean;
  type?: "high_pass";
  alpha?: number;
}

export interface HlineShape {
  type?: "hline";
  y0: number;
  color: string;
  dash?: DashStyle | null;
  label?: string;
}

export type HoverMode = "x unified" | "y unified" | "closest" | "x" | "y" | "none";
export const HOVER_MODE_VALUES: HoverMode[] = ["x unified", "y unified", "closest", "x", "y", "none"];

export interface IntegralFilter {
  enabled?: boolean;
  type?: "integral";
  dt?: number;
  wrtCol?: string | null;
}

export type InterpMode = "linear" | "spline" | "hv" | "vh" | "hvh" | "vhv";
export const INTERP_MODE_VALUES: InterpMode[] = ["linear", "spline", "hv", "vh", "hvh", "vhv"];

export interface LastFilter {
  enabled?: boolean;
  type?: "stat_last";
}

export type LegendPos = "bottom" | "right" | "hidden";
export const LEGEND_POS_VALUES: LegendPos[] = ["bottom", "right", "hidden"];

export type LineMode = "lines" | "markers" | "lines+markers";
export const LINE_MODE_VALUES: LineMode[] = ["lines", "markers", "lines+markers"];

export interface LogFilter {
  enabled?: boolean;
  type?: "log";
  base?: number;
}

export interface LowPassFilter {
  enabled?: boolean;
  type?: "low_pass";
  alpha?: number;
}

export type MarkerSymbol = "none" | "circle" | "square" | "diamond" | "cross" | "x" | "triangle-up" | "triangle-down" | "triangle-left" | "triangle-right" | "triangle-ne" | "triangle-se" | "triangle-sw" | "triangle-nw" | "pentagon" | "hexagon" | "hexagon2" | "octagon" | "star" | "hexagram" | "starsquare" | "diamond-cross" | "diamond-x" | "hourglass" | "bowtie" | "asterisk" | "hash" | "y-up" | "y-down" | "y-left" | "y-right" | "line-ew" | "line-ns" | "line-ne" | "line-nw" | "arrow-up" | "arrow-down" | "arrow-left" | "arrow-right";
export const MARKER_SYMBOL_VALUES: MarkerSymbol[] = ["none", "circle", "square", "diamond", "cross", "x", "triangle-up", "triangle-down", "triangle-left", "triangle-right", "triangle-ne", "triangle-se", "triangle-sw", "triangle-nw", "pentagon", "hexagon", "hexagon2", "octagon", "star", "hexagram", "starsquare", "diamond-cross", "diamond-x", "hourglass", "bowtie", "asterisk", "hash", "y-up", "y-down", "y-left", "y-right", "line-ew", "line-ns", "line-ne", "line-nw", "arrow-up", "arrow-down", "arrow-left", "arrow-right"];

export interface MaxFilter {
  enabled?: boolean;
  type?: "stat_max";
}

export interface MeanFilter {
  enabled?: boolean;
  type?: "stat_mean";
}

export interface MedianFilter {
  enabled?: boolean;
  type?: "stat_median";
}

export interface MinFilter {
  enabled?: boolean;
  type?: "stat_min";
}

export interface ModeFilter {
  enabled?: boolean;
  type?: "stat_mode";
}

export interface NormalizeFilter {
  enabled?: boolean;
  type?: "normalize";
}

export type PlotType = "cartesian" | "polar";
export const PLOT_TYPE_VALUES: PlotType[] = ["cartesian", "polar"];

export interface PowerFilter {
  enabled?: boolean;
  type?: "power";
  exponent?: number;
}

export interface RectShape {
  type?: "rect";
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  color: string;
  dash?: DashStyle | null;
  label?: string;
}

export interface ReverseFilter {
  enabled?: boolean;
  type?: "reverse";
}

export interface RollingMeanFilter {
  enabled?: boolean;
  type?: "rolling_mean";
  window?: number;
  center?: boolean;
}

export interface RollingMedianFilter {
  enabled?: boolean;
  type?: "median";
  window?: number;
}

export interface RotationFilter {
  enabled?: boolean;
  type?: "rotation";
  quatCol?: string;
  invert?: boolean;
}

export interface RoundFilter {
  enabled?: boolean;
  type?: "round";
  method?: "round" | "floor" | "ceil";
  decimals?: number;
}

export interface SavitzkyGolayFilter {
  enabled?: boolean;
  type?: "savitzky_golay";
  window?: number;
  order?: number;
}

export interface ScaleFilter {
  enabled?: boolean;
  type?: "scale";
  factor?: number;
  offset?: number;
}

export type ScaleType = "linear" | "log";
export const SCALE_TYPE_VALUES: ScaleType[] = ["linear", "log"];

export interface SignFilter {
  enabled?: boolean;
  type?: "sign";
}

export interface SortFilter {
  enabled?: boolean;
  type?: "sort";
  descending?: boolean;
}

export interface StandardDeviationFilter {
  enabled?: boolean;
  type?: "stat_standard_deviation";
}

export interface TaringFilter {
  enabled?: boolean;
  type?: "taring";
}

export interface TrigFilter {
  enabled?: boolean;
  type?: "trig";
  func?: "sin" | "cos" | "tan" | "asin" | "acos" | "atan" | "sinh" | "cosh" | "tanh" | "degrees" | "radians";
}

export interface UnitFilter {
  enabled?: boolean;
  type?: "unit";
  fromUnit: "rad" | "deg" | "mrad" | "rev" | "rpm" | "rad/s" | "deg/s" | "rad/s^2" | "deg/s^2" | "m" | "mm" | "cm" | "um" | "km" | "in" | "ft" | "thou" | "m/s" | "mm/s" | "cm/s" | "ft/s" | "in/s" | "km/h" | "mph" | "m/s^2" | "mm/s^2" | "ft/s^2" | "in/s^2" | "kg" | "g" | "mg" | "pound" | "slug" | "N" | "mN" | "uN" | "kN" | "pound_force" | "ounce_force" | "N*m" | "N*mm" | "mN*m" | "kN*m" | "pound_force*ft" | "pound_force*in" | "ounce_force*in" | "kg*m^2" | "kg*mm^2" | "pound*in^2" | "pound*ft^2" | "slug*ft^2" | "J" | "mJ" | "kJ" | "W*s" | "W*h" | "kW*h" | "ft*pound_force" | "BTU" | "W" | "mW" | "kW" | "MW" | "hp" | "ft*pound_force/s" | "Pa" | "kPa" | "MPa" | "psi" | "bar" | "atm" | "torr" | "s" | "ms" | "us" | "ns" | "min" | "hr" | "Hz" | "kHz" | "MHz" | "V" | "mV" | "kV" | "A" | "mA" | "dimensionless" | "pct" | "count" | "bit" | string;
  toUnit: "rad" | "deg" | "mrad" | "rev" | "rpm" | "rad/s" | "deg/s" | "rad/s^2" | "deg/s^2" | "m" | "mm" | "cm" | "um" | "km" | "in" | "ft" | "thou" | "m/s" | "mm/s" | "cm/s" | "ft/s" | "in/s" | "km/h" | "mph" | "m/s^2" | "mm/s^2" | "ft/s^2" | "in/s^2" | "kg" | "g" | "mg" | "pound" | "slug" | "N" | "mN" | "uN" | "kN" | "pound_force" | "ounce_force" | "N*m" | "N*mm" | "mN*m" | "kN*m" | "pound_force*ft" | "pound_force*in" | "ounce_force*in" | "kg*m^2" | "kg*mm^2" | "pound*in^2" | "pound*ft^2" | "slug*ft^2" | "J" | "mJ" | "kJ" | "W*s" | "W*h" | "kW*h" | "ft*pound_force" | "BTU" | "W" | "mW" | "kW" | "MW" | "hp" | "ft*pound_force/s" | "Pa" | "kPa" | "MPa" | "psi" | "bar" | "atm" | "torr" | "s" | "ms" | "us" | "ns" | "min" | "hr" | "Hz" | "kHz" | "MHz" | "V" | "mV" | "kV" | "A" | "mA" | "dimensionless" | "pct" | "count" | "bit" | string;
}

export interface VlineShape {
  type?: "vline";
  x0: number;
  color: string;
  dash?: DashStyle | null;
  label?: string;
}

export interface WrapFilter {
  enabled?: boolean;
  type?: "wrap";
  lb?: number;
  ub?: number;
}

export interface XAxisConfig {
  col?: string;
  filters?: FilterEntry[];
}

export interface YAxisConfig {
  label?: string;
  color: string;
  width?: number;
  opacity?: number;
  filters?: FilterEntry[];
  dash?: DashStyle;
  marker?: MarkerSymbol;
}

/** Complete serialisable state of a trial-viewer plot. */
export interface PlotConfig {
  xAxis: XAxisConfig;
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
  rangeX: [number | null, number | null] | null;
  rangeY: [number | null, number | null] | null;
  xScale: ScaleType;
  yScale: ScaleType;
  xLogBase: number | null;
  yLogBase: number | null;
  plotType: PlotType;
  vsEnabled: boolean;
  vsRange: [number, number];
  annotations: Annotation[];
  shapes: Shape[];
  displayUnitSystem: DisplayUnitSystem | null;
  maxPoints: number | null;
  vsPinned: number[];
}

export type Shape = VlineShape | HlineShape | RectShape;
