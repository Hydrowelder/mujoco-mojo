// ============================================================
// AUTO-GENERATED - do not edit manually.
// Source: src/mujoco_mojo/utils/layers/dojo/plot_config.py
// Regenerate: python scripts/gen_ts_models.py
// ============================================================

import type { JsonSchemaNode } from "./schema-validate";

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
  label: string;
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

export type MarkerSymbol = "none" | "circle" | "square" | "diamond" | "cross" | "x" | "triangle-up" | "triangle-down" | "triangle-left" | "triangle-right" | "triangle-ne" | "triangle-se" | "triangle-sw" | "triangle-nw" | "pentagon" | "hexagon" | "hexagon2" | "octagon" | "star" | "hexagram" | "starsquare" | "diamond-cross" | "diamond-x" | "hourglass" | "bowtie" | "asterisk" | "hash" | "y-up" | "y-down" | "y-left" | "y-right" | "line-ew" | "line-ns" | "line-ne" | "line-nw" | "arrow-up" | "arrow-down" | "arrow-left" | "arrow-right ";
export const MARKER_SYMBOL_VALUES: MarkerSymbol[] = ["none", "circle", "square", "diamond", "cross", "x", "triangle-up", "triangle-down", "triangle-left", "triangle-right", "triangle-ne", "triangle-se", "triangle-sw", "triangle-nw", "pentagon", "hexagon", "hexagon2", "octagon", "star", "hexagram", "starsquare", "diamond-cross", "diamond-x", "hourglass", "bowtie", "asterisk", "hash", "y-up", "y-down", "y-left", "y-right", "line-ew", "line-ns", "line-ne", "line-nw", "arrow-up", "arrow-down", "arrow-left", "arrow-right "];

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
  label: string;
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
  fromUnit: "rad" | "deg" | "mrad" | "rev" | "rpm" | "rad/s" | "deg/s" | "rad/s^2" | "deg/s^2" | "m" | "mm" | "cm" | "um" | "km" | "in" | "ft" | "thou" | "m/s" | "mm/s" | "cm/s" | "ft/s" | "in/s" | "km/h" | "mph" | "m/s^2" | "mm/s^2" | "ft/s^2" | "in/s^2" | "kg" | "g" | "mg" | "lbm" | "slug" | "N" | "mN" | "uN" | "kN" | "lbf" | "N*m" | "N*mm" | "mN*m" | "kN*m" | "lbf*ft" | "lbf*in" | "ozf*in" | "kg*m^2" | "kg*mm^2" | "lbm*in^2" | "lbm*ft^2" | "slug*ft^2" | "J" | "mJ" | "kJ" | "W*s" | "W*h" | "kW*h" | "ft*lbf" | "BTU" | "W" | "mW" | "kW" | "MW" | "hp" | "ft*lbf/s" | "Pa" | "kPa" | "MPa" | "psi" | "bar" | "atm" | "torr" | "s" | "ms" | "us" | "ns" | "min" | "hr" | "Hz" | "kHz" | "MHz" | "V" | "mV" | "kV" | "A" | "mA" | "dimensionless" | "pct" | "count" | "bit" | string;
  toUnit: "rad" | "deg" | "mrad" | "rev" | "rpm" | "rad/s" | "deg/s" | "rad/s^2" | "deg/s^2" | "m" | "mm" | "cm" | "um" | "km" | "in" | "ft" | "thou" | "m/s" | "mm/s" | "cm/s" | "ft/s" | "in/s" | "km/h" | "mph" | "m/s^2" | "mm/s^2" | "ft/s^2" | "in/s^2" | "kg" | "g" | "mg" | "lbm" | "slug" | "N" | "mN" | "uN" | "kN" | "lbf" | "N*m" | "N*mm" | "mN*m" | "kN*m" | "lbf*ft" | "lbf*in" | "ozf*in" | "kg*m^2" | "kg*mm^2" | "lbm*in^2" | "lbm*ft^2" | "slug*ft^2" | "J" | "mJ" | "kJ" | "W*s" | "W*h" | "kW*h" | "ft*lbf" | "BTU" | "W" | "mW" | "kW" | "MW" | "hp" | "ft*lbf/s" | "Pa" | "kPa" | "MPa" | "psi" | "bar" | "atm" | "torr" | "s" | "ms" | "us" | "ns" | "min" | "hr" | "Hz" | "kHz" | "MHz" | "V" | "mV" | "kV" | "A" | "mA" | "dimensionless" | "pct" | "count" | "bit" | string;
}

export interface VlineShape {
  type?: "vline";
  x0: number;
  color: string;
  dash?: DashStyle | null;
  label: string;
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
  rangeX: [number | null, number | null] | null;
  rangeY: [number | null, number | null] | null;
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

export type Shape = VlineShape | HlineShape | RectShape;

/** Full JSON Schema for PlotConfig - used for additive client-side validation. */
export const PLOT_CONFIG_SCHEMA: JsonSchemaNode = {
  "$defs": {
    "AbsoluteValueFilter": {
      "additionalProperties": false,
      "description": "Rectifies the signal by taking the magnitude of every sample.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "absolute_value",
          "default": "absolute_value",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "AbsoluteValueFilter",
      "type": "object"
    },
    "Annotation": {
      "description": "A text label pinned to a specific data coordinate.",
      "properties": {
        "x": {
          "title": "X",
          "type": "number"
        },
        "y": {
          "title": "Y",
          "type": "number"
        },
        "text": {
          "title": "Text",
          "type": "string"
        }
      },
      "required": [
        "x",
        "y",
        "text"
      ],
      "title": "Annotation",
      "type": "object"
    },
    "ClipFilter": {
      "additionalProperties": false,
      "description": "Clamps the signal values within a specified range.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "clip",
          "default": "clip",
          "title": "Type",
          "type": "string"
        },
        "min": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Min"
        },
        "max": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Max"
        }
      },
      "title": "ClipFilter",
      "type": "object"
    },
    "ComparisonFilter": {
      "additionalProperties": false,
      "description": "Compares each sample against a threshold, returning 1.0 (true) or 0.0 (false).",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "comparison",
          "default": "comparison",
          "title": "Type",
          "type": "string"
        },
        "operator": {
          "default": "gt",
          "enum": [
            "gt",
            "gte",
            "lt",
            "lte",
            "eq",
            "neq"
          ],
          "title": "Operator",
          "type": "string",
          "ui_type": "select"
        },
        "threshold": {
          "default": 0.0,
          "title": "Threshold",
          "type": "number"
        }
      },
      "title": "ComparisonFilter",
      "type": "object"
    },
    "DashStyle": {
      "description": "Dash pattern applied to a plot line.",
      "enum": [
        "solid",
        "dash",
        "dot",
        "dashdot",
        "longdash",
        "longdashdot"
      ],
      "title": "DashStyle",
      "type": "string"
    },
    "DeadbandFilter": {
      "additionalProperties": false,
      "description": "Suppresses noise around zero by forcing values below a threshold to zero.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "deadband",
          "default": "deadband",
          "title": "Type",
          "type": "string"
        },
        "threshold": {
          "default": 0.01,
          "minimum": 0,
          "title": "Threshold",
          "type": "number"
        }
      },
      "title": "DeadbandFilter",
      "type": "object"
    },
    "DerivativeFilter": {
      "additionalProperties": false,
      "description": "Computes the numerical rate of change using backward difference.\nUseful for deriving velocity from position or acceleration from velocity.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "derivative",
          "default": "derivative",
          "title": "Type",
          "type": "string"
        },
        "dt": {
          "default": 0.001,
          "exclusiveMinimum": 0,
          "title": "Dt",
          "type": "number"
        },
        "wrtCol": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Wrtcol",
          "ui_type": "col"
        }
      },
      "title": "DerivativeFilter",
      "type": "object"
    },
    "ExpFilter": {
      "additionalProperties": false,
      "description": "Raises a base to the power of each signal sample. Defaults to e^x.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "exp",
          "default": "exp",
          "title": "Type",
          "type": "string"
        },
        "base": {
          "default": 2.718281828459045,
          "exclusiveMinimum": 0,
          "title": "Base",
          "type": "number"
        }
      },
      "title": "ExpFilter",
      "type": "object"
    },
    "FirstFilter": {
      "additionalProperties": false,
      "description": "Reduces the signal to its first value, broadcast across every sample.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "stat_first",
          "default": "stat_first",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "FirstFilter",
      "type": "object"
    },
    "GridMode": {
      "description": "Which grid lines are drawn on the plot.",
      "enum": [
        "none",
        "major",
        "all"
      ],
      "title": "GridMode",
      "type": "string"
    },
    "HighPassFilter": {
      "additionalProperties": false,
      "description": "Removes low-frequency drift or steady-state offsets.\nImplemented as the complement of the Exponential Moving Average.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "high_pass",
          "default": "high_pass",
          "title": "Type",
          "type": "string"
        },
        "alpha": {
          "default": 0.1,
          "exclusiveMinimum": 0,
          "maximum": 1,
          "title": "Alpha",
          "type": "number"
        }
      },
      "title": "HighPassFilter",
      "type": "object"
    },
    "HlineShape": {
      "description": "A horizontal reference line at a fixed y value.",
      "properties": {
        "type": {
          "const": "hline",
          "default": "hline",
          "title": "Type",
          "type": "string"
        },
        "y0": {
          "title": "Y0",
          "type": "number"
        },
        "color": {
          "title": "Color",
          "type": "string"
        },
        "dash": {
          "anyOf": [
            {
              "$ref": "#/$defs/DashStyle"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "label": {
          "title": "Label",
          "type": "string"
        }
      },
      "required": [
        "y0",
        "color",
        "label"
      ],
      "title": "HlineShape",
      "type": "object"
    },
    "HoverMode": {
      "description": "Tooltip behavior when hovering over the plot.",
      "enum": [
        "x unified",
        "y unified",
        "closest",
        "x",
        "y",
        "none"
      ],
      "title": "HoverMode",
      "type": "string"
    },
    "IntegralFilter": {
      "additionalProperties": false,
      "description": "Computes the cumulative sum of the signal multiplied by the time step.\nUseful for deriving position from velocity or calculating energy.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "integral",
          "default": "integral",
          "title": "Type",
          "type": "string"
        },
        "dt": {
          "default": 0.001,
          "exclusiveMinimum": 0,
          "title": "Dt",
          "type": "number"
        },
        "wrtCol": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Wrtcol",
          "ui_type": "col"
        }
      },
      "title": "IntegralFilter",
      "type": "object"
    },
    "InterpMode": {
      "description": "Line interpolation method between data points.",
      "enum": [
        "linear",
        "spline",
        "hv",
        "vh",
        "hvh",
        "vhv"
      ],
      "title": "InterpMode",
      "type": "string"
    },
    "LastFilter": {
      "additionalProperties": false,
      "description": "Reduces the signal to its last value, broadcast across every sample.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "stat_last",
          "default": "stat_last",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "LastFilter",
      "type": "object"
    },
    "LegendPos": {
      "description": "Position of the plot legend.",
      "enum": [
        "bottom",
        "right",
        "hidden"
      ],
      "title": "LegendPos",
      "type": "string"
    },
    "LineMode": {
      "description": "Controls whether traces are drawn as lines, markers, or both.",
      "enum": [
        "lines",
        "markers",
        "lines+markers"
      ],
      "title": "LineMode",
      "type": "string"
    },
    "LogFilter": {
      "additionalProperties": false,
      "description": "Applies a logarithm to the signal. Defaults to natural log (base e).",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "log",
          "default": "log",
          "title": "Type",
          "type": "string"
        },
        "base": {
          "default": 2.718281828459045,
          "exclusiveMinimum": 0,
          "title": "Base",
          "type": "number"
        }
      },
      "title": "LogFilter",
      "type": "object"
    },
    "LowPassFilter": {
      "additionalProperties": false,
      "description": "Applies a 1st-order Exponential Moving Average (EMA) to smooth the signal.\nEffective for removing high-frequency noise while introducing slight phase lag.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "low_pass",
          "default": "low_pass",
          "title": "Type",
          "type": "string"
        },
        "alpha": {
          "default": 0.1,
          "exclusiveMinimum": 0,
          "maximum": 1,
          "title": "Alpha",
          "type": "number"
        }
      },
      "title": "LowPassFilter",
      "type": "object"
    },
    "MarkerSymbol": {
      "description": "Shape used to mark individual data points.",
      "enum": [
        "none",
        "circle",
        "square",
        "diamond",
        "cross",
        "x",
        "triangle-up",
        "triangle-down",
        "triangle-left",
        "triangle-right",
        "triangle-ne",
        "triangle-se",
        "triangle-sw",
        "triangle-nw",
        "pentagon",
        "hexagon",
        "hexagon2",
        "octagon",
        "star",
        "hexagram",
        "starsquare",
        "diamond-cross",
        "diamond-x",
        "hourglass",
        "bowtie",
        "asterisk",
        "hash",
        "y-up",
        "y-down",
        "y-left",
        "y-right",
        "line-ew",
        "line-ns",
        "line-ne",
        "line-nw",
        "arrow-up",
        "arrow-down",
        "arrow-left",
        "arrow-right "
      ],
      "title": "MarkerSymbol",
      "type": "string"
    },
    "MaxFilter": {
      "additionalProperties": false,
      "description": "Reduces the signal to its maximum value, broadcast across every sample.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "stat_max",
          "default": "stat_max",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "MaxFilter",
      "type": "object"
    },
    "MeanFilter": {
      "additionalProperties": false,
      "description": "Reduces the signal to its mean value, broadcast across every sample.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "stat_mean",
          "default": "stat_mean",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "MeanFilter",
      "type": "object"
    },
    "MedianFilter": {
      "additionalProperties": false,
      "description": "Reduces the signal to its median value, broadcast across every sample.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "stat_median",
          "default": "stat_median",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "MedianFilter",
      "type": "object"
    },
    "MinFilter": {
      "additionalProperties": false,
      "description": "Reduces the signal to its minimum value, broadcast across every sample.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "stat_min",
          "default": "stat_min",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "MinFilter",
      "type": "object"
    },
    "ModeFilter": {
      "additionalProperties": false,
      "description": "Reduces the signal to its most frequent value, broadcast across every sample.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "stat_mode",
          "default": "stat_mode",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "ModeFilter",
      "type": "object"
    },
    "NormalizeFilter": {
      "additionalProperties": false,
      "description": "Rescales the signal to the range [0, 1].",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "normalize",
          "default": "normalize",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "NormalizeFilter",
      "type": "object"
    },
    "PlotType": {
      "description": "Coordinate system used to render the plot.",
      "enum": [
        "cartesian",
        "polar"
      ],
      "title": "PlotType",
      "type": "string"
    },
    "PowerFilter": {
      "additionalProperties": false,
      "description": "Raises each signal sample to a fixed exponent. Supports fractional exponents (e.g. 0.5 for sqrt).",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "power",
          "default": "power",
          "title": "Type",
          "type": "string"
        },
        "exponent": {
          "default": 2.0,
          "title": "Exponent",
          "type": "number"
        }
      },
      "title": "PowerFilter",
      "type": "object"
    },
    "RectShape": {
      "description": "A filled rectangle drawn as a reference region.",
      "properties": {
        "type": {
          "const": "rect",
          "default": "rect",
          "title": "Type",
          "type": "string"
        },
        "x0": {
          "title": "X0",
          "type": "number"
        },
        "x1": {
          "title": "X1",
          "type": "number"
        },
        "y0": {
          "title": "Y0",
          "type": "number"
        },
        "y1": {
          "title": "Y1",
          "type": "number"
        },
        "color": {
          "title": "Color",
          "type": "string"
        },
        "dash": {
          "anyOf": [
            {
              "$ref": "#/$defs/DashStyle"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "label": {
          "title": "Label",
          "type": "string"
        }
      },
      "required": [
        "x0",
        "x1",
        "y0",
        "y1",
        "color",
        "label"
      ],
      "title": "RectShape",
      "type": "object"
    },
    "ReverseFilter": {
      "additionalProperties": false,
      "description": "Reverses the order of the signal's values without changing their order of occurrence in time.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "reverse",
          "default": "reverse",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "ReverseFilter",
      "type": "object"
    },
    "RollingMeanFilter": {
      "additionalProperties": false,
      "description": "Applies a sliding window average to the signal.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "rolling_mean",
          "default": "rolling_mean",
          "title": "Type",
          "type": "string"
        },
        "window": {
          "default": 10,
          "exclusiveMinimum": 0,
          "title": "Window",
          "type": "integer"
        },
        "center": {
          "default": true,
          "title": "Center",
          "type": "boolean"
        }
      },
      "title": "RollingMeanFilter",
      "type": "object"
    },
    "RollingMedianFilter": {
      "additionalProperties": false,
      "description": "Applies a sliding window median filter.\nHighly effective for removing impulse noise (spikes) without blurring edges.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "median",
          "default": "median",
          "title": "Type",
          "type": "string"
        },
        "window": {
          "default": 10,
          "exclusiveMinimum": 0,
          "title": "Window",
          "type": "integer"
        }
      },
      "title": "RollingMedianFilter",
      "type": "object"
    },
    "RotationFilter": {
      "additionalProperties": false,
      "description": "Rotates a 3D vector component into a reference frame using a quaternion column.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "rotation",
          "default": "rotation",
          "title": "Type",
          "type": "string"
        },
        "quatCol": {
          "default": "",
          "title": "Quatcol",
          "type": "string",
          "ui_type": "quat_col"
        },
        "invert": {
          "default": true,
          "title": "Invert",
          "type": "boolean"
        }
      },
      "title": "RotationFilter",
      "type": "object"
    },
    "RoundFilter": {
      "additionalProperties": false,
      "description": "Quantizes the signal to a fixed number of decimal places.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "round",
          "default": "round",
          "title": "Type",
          "type": "string"
        },
        "method": {
          "default": "round",
          "enum": [
            "round",
            "floor",
            "ceil"
          ],
          "title": "Method",
          "type": "string",
          "ui_type": "select"
        },
        "decimals": {
          "default": 0,
          "minimum": 0,
          "title": "Decimals",
          "type": "integer"
        }
      },
      "title": "RoundFilter",
      "type": "object"
    },
    "SavitzkyGolayFilter": {
      "additionalProperties": false,
      "description": "Applies a Savitzky-Golay smoothing filter by fitting a polynomial to the data.\nPreserves signal features (like peaks and transients) better than a simple moving average.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "savitzky_golay",
          "default": "savitzky_golay",
          "title": "Type",
          "type": "string"
        },
        "window": {
          "default": 11,
          "exclusiveMinimum": 1,
          "title": "Window",
          "type": "integer"
        },
        "order": {
          "default": 2,
          "minimum": 0,
          "title": "Order",
          "type": "integer"
        }
      },
      "title": "SavitzkyGolayFilter",
      "type": "object"
    },
    "ScaleFilter": {
      "additionalProperties": false,
      "description": "Applies a linear transformation: (value * factor) + offset.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "scale",
          "default": "scale",
          "title": "Type",
          "type": "string"
        },
        "factor": {
          "default": 1.0,
          "title": "Factor",
          "type": "number"
        },
        "offset": {
          "default": 0.0,
          "title": "Offset",
          "type": "number"
        }
      },
      "title": "ScaleFilter",
      "type": "object"
    },
    "ScaleType": {
      "description": "Numeric scale type for an axis.",
      "enum": [
        "linear",
        "log"
      ],
      "title": "ScaleType",
      "type": "string"
    },
    "SignFilter": {
      "additionalProperties": false,
      "description": "Returns the sign of each sample: 1 for positive, -1 for negative, 0 for zero.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "sign",
          "default": "sign",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "SignFilter",
      "type": "object"
    },
    "SortFilter": {
      "additionalProperties": false,
      "description": "Sorts the signal's values in ascending or descending order.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "sort",
          "default": "sort",
          "title": "Type",
          "type": "string"
        },
        "descending": {
          "default": false,
          "title": "Descending",
          "type": "boolean"
        }
      },
      "title": "SortFilter",
      "type": "object"
    },
    "StandardDeviationFilter": {
      "additionalProperties": false,
      "description": "Reduces the signal to its standard deviation, broadcast across every sample.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "stat_standard_deviation",
          "default": "stat_standard_deviation",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "StandardDeviationFilter",
      "type": "object"
    },
    "TaringFilter": {
      "additionalProperties": false,
      "description": "Offsets the entire signal so that the first sample is zero.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "taring",
          "default": "taring",
          "title": "Type",
          "type": "string"
        }
      },
      "title": "TaringFilter",
      "type": "object"
    },
    "TrigFilter": {
      "additionalProperties": false,
      "description": "Applies a trigonometric or angle-conversion function to the signal.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "trig",
          "default": "trig",
          "title": "Type",
          "type": "string"
        },
        "func": {
          "default": "sin",
          "enum": [
            "sin",
            "cos",
            "tan",
            "asin",
            "acos",
            "atan",
            "sinh",
            "cosh",
            "tanh",
            "degrees",
            "radians"
          ],
          "title": "Func",
          "type": "string",
          "ui_type": "select"
        }
      },
      "title": "TrigFilter",
      "type": "object"
    },
    "UnitFilter": {
      "additionalProperties": false,
      "description": "Unit conversion using Pint.\nEnsures dimensional consistency and applies necessary scaling/offsets.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "unit",
          "default": "unit",
          "title": "Type",
          "type": "string"
        },
        "fromUnit": {
          "anyOf": [
            {
              "enum": [
                "rad",
                "deg",
                "mrad",
                "rev",
                "rpm",
                "rad/s",
                "deg/s",
                "rad/s^2",
                "deg/s^2",
                "m",
                "mm",
                "cm",
                "um",
                "km",
                "in",
                "ft",
                "thou",
                "m/s",
                "mm/s",
                "cm/s",
                "ft/s",
                "in/s",
                "km/h",
                "mph",
                "m/s^2",
                "mm/s^2",
                "ft/s^2",
                "in/s^2",
                "kg",
                "g",
                "mg",
                "lbm",
                "slug",
                "N",
                "mN",
                "uN",
                "kN",
                "lbf",
                "N*m",
                "N*mm",
                "mN*m",
                "kN*m",
                "lbf*ft",
                "lbf*in",
                "ozf*in",
                "kg*m^2",
                "kg*mm^2",
                "lbm*in^2",
                "lbm*ft^2",
                "slug*ft^2",
                "J",
                "mJ",
                "kJ",
                "W*s",
                "W*h",
                "kW*h",
                "ft*lbf",
                "BTU",
                "W",
                "mW",
                "kW",
                "MW",
                "hp",
                "ft*lbf/s",
                "Pa",
                "kPa",
                "MPa",
                "psi",
                "bar",
                "atm",
                "torr",
                "s",
                "ms",
                "us",
                "ns",
                "min",
                "hr",
                "Hz",
                "kHz",
                "MHz",
                "V",
                "mV",
                "kV",
                "A",
                "mA",
                "dimensionless",
                "pct",
                "count",
                "bit"
              ],
              "type": "string"
            },
            {
              "type": "string"
            }
          ],
          "title": "Fromunit"
        },
        "toUnit": {
          "anyOf": [
            {
              "enum": [
                "rad",
                "deg",
                "mrad",
                "rev",
                "rpm",
                "rad/s",
                "deg/s",
                "rad/s^2",
                "deg/s^2",
                "m",
                "mm",
                "cm",
                "um",
                "km",
                "in",
                "ft",
                "thou",
                "m/s",
                "mm/s",
                "cm/s",
                "ft/s",
                "in/s",
                "km/h",
                "mph",
                "m/s^2",
                "mm/s^2",
                "ft/s^2",
                "in/s^2",
                "kg",
                "g",
                "mg",
                "lbm",
                "slug",
                "N",
                "mN",
                "uN",
                "kN",
                "lbf",
                "N*m",
                "N*mm",
                "mN*m",
                "kN*m",
                "lbf*ft",
                "lbf*in",
                "ozf*in",
                "kg*m^2",
                "kg*mm^2",
                "lbm*in^2",
                "lbm*ft^2",
                "slug*ft^2",
                "J",
                "mJ",
                "kJ",
                "W*s",
                "W*h",
                "kW*h",
                "ft*lbf",
                "BTU",
                "W",
                "mW",
                "kW",
                "MW",
                "hp",
                "ft*lbf/s",
                "Pa",
                "kPa",
                "MPa",
                "psi",
                "bar",
                "atm",
                "torr",
                "s",
                "ms",
                "us",
                "ns",
                "min",
                "hr",
                "Hz",
                "kHz",
                "MHz",
                "V",
                "mV",
                "kV",
                "A",
                "mA",
                "dimensionless",
                "pct",
                "count",
                "bit"
              ],
              "type": "string"
            },
            {
              "type": "string"
            }
          ],
          "title": "Tounit"
        }
      },
      "required": [
        "fromUnit",
        "toUnit"
      ],
      "title": "UnitFilter",
      "type": "object"
    },
    "VlineShape": {
      "description": "A vertical reference line at a fixed x value.",
      "properties": {
        "type": {
          "const": "vline",
          "default": "vline",
          "title": "Type",
          "type": "string"
        },
        "x0": {
          "title": "X0",
          "type": "number"
        },
        "color": {
          "title": "Color",
          "type": "string"
        },
        "dash": {
          "anyOf": [
            {
              "$ref": "#/$defs/DashStyle"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "label": {
          "title": "Label",
          "type": "string"
        }
      },
      "required": [
        "x0",
        "color",
        "label"
      ],
      "title": "VlineShape",
      "type": "object"
    },
    "WrapFilter": {
      "additionalProperties": false,
      "description": "Keeps circular data (like Euler angles or radians) within a specific range.\nEnsures continuity when a signal crosses the upper or lower boundary.",
      "properties": {
        "enabled": {
          "default": true,
          "title": "Enabled",
          "type": "boolean"
        },
        "type": {
          "const": "wrap",
          "default": "wrap",
          "title": "Type",
          "type": "string"
        },
        "lb": {
          "default": -3.141592653589793,
          "title": "Lb",
          "type": "number"
        },
        "ub": {
          "default": 3.141592653589793,
          "title": "Ub",
          "type": "number"
        }
      },
      "title": "WrapFilter",
      "type": "object"
    },
    "XAxisConfig": {
      "description": "Configuration for the x-axis signal and its filter chain.",
      "properties": {
        "col": {
          "default": "time",
          "title": "Col",
          "type": "string"
        },
        "filters": {
          "default": [],
          "items": {
            "discriminator": {
              "mapping": {
                "absolute_value": "#/$defs/AbsoluteValueFilter",
                "clip": "#/$defs/ClipFilter",
                "comparison": "#/$defs/ComparisonFilter",
                "deadband": "#/$defs/DeadbandFilter",
                "derivative": "#/$defs/DerivativeFilter",
                "exp": "#/$defs/ExpFilter",
                "high_pass": "#/$defs/HighPassFilter",
                "integral": "#/$defs/IntegralFilter",
                "log": "#/$defs/LogFilter",
                "low_pass": "#/$defs/LowPassFilter",
                "median": "#/$defs/RollingMedianFilter",
                "normalize": "#/$defs/NormalizeFilter",
                "power": "#/$defs/PowerFilter",
                "reverse": "#/$defs/ReverseFilter",
                "rolling_mean": "#/$defs/RollingMeanFilter",
                "rotation": "#/$defs/RotationFilter",
                "round": "#/$defs/RoundFilter",
                "savitzky_golay": "#/$defs/SavitzkyGolayFilter",
                "scale": "#/$defs/ScaleFilter",
                "sign": "#/$defs/SignFilter",
                "sort": "#/$defs/SortFilter",
                "stat_first": "#/$defs/FirstFilter",
                "stat_last": "#/$defs/LastFilter",
                "stat_max": "#/$defs/MaxFilter",
                "stat_mean": "#/$defs/MeanFilter",
                "stat_median": "#/$defs/MedianFilter",
                "stat_min": "#/$defs/MinFilter",
                "stat_mode": "#/$defs/ModeFilter",
                "stat_standard_deviation": "#/$defs/StandardDeviationFilter",
                "taring": "#/$defs/TaringFilter",
                "trig": "#/$defs/TrigFilter",
                "unit": "#/$defs/UnitFilter",
                "wrap": "#/$defs/WrapFilter"
              },
              "propertyName": "type"
            },
            "oneOf": [
              {
                "$ref": "#/$defs/ScaleFilter"
              },
              {
                "$ref": "#/$defs/AbsoluteValueFilter"
              },
              {
                "$ref": "#/$defs/DerivativeFilter"
              },
              {
                "$ref": "#/$defs/IntegralFilter"
              },
              {
                "$ref": "#/$defs/LowPassFilter"
              },
              {
                "$ref": "#/$defs/HighPassFilter"
              },
              {
                "$ref": "#/$defs/RollingMeanFilter"
              },
              {
                "$ref": "#/$defs/SavitzkyGolayFilter"
              },
              {
                "$ref": "#/$defs/ClipFilter"
              },
              {
                "$ref": "#/$defs/DeadbandFilter"
              },
              {
                "$ref": "#/$defs/TaringFilter"
              },
              {
                "$ref": "#/$defs/UnitFilter"
              },
              {
                "$ref": "#/$defs/RollingMedianFilter"
              },
              {
                "$ref": "#/$defs/NormalizeFilter"
              },
              {
                "$ref": "#/$defs/WrapFilter"
              },
              {
                "$ref": "#/$defs/RotationFilter"
              },
              {
                "$ref": "#/$defs/LogFilter"
              },
              {
                "$ref": "#/$defs/ExpFilter"
              },
              {
                "$ref": "#/$defs/PowerFilter"
              },
              {
                "$ref": "#/$defs/RoundFilter"
              },
              {
                "$ref": "#/$defs/TrigFilter"
              },
              {
                "$ref": "#/$defs/SignFilter"
              },
              {
                "$ref": "#/$defs/ComparisonFilter"
              },
              {
                "$ref": "#/$defs/MaxFilter"
              },
              {
                "$ref": "#/$defs/MinFilter"
              },
              {
                "$ref": "#/$defs/MeanFilter"
              },
              {
                "$ref": "#/$defs/MedianFilter"
              },
              {
                "$ref": "#/$defs/ModeFilter"
              },
              {
                "$ref": "#/$defs/StandardDeviationFilter"
              },
              {
                "$ref": "#/$defs/FirstFilter"
              },
              {
                "$ref": "#/$defs/LastFilter"
              },
              {
                "$ref": "#/$defs/SortFilter"
              },
              {
                "$ref": "#/$defs/ReverseFilter"
              }
            ]
          },
          "title": "Filters",
          "type": "array"
        }
      },
      "title": "XAxisConfig",
      "type": "object"
    },
    "YAxisConfig": {
      "description": "Visual and filter configuration for a single y-axis signal.",
      "properties": {
        "label": {
          "title": "Label",
          "type": "string"
        },
        "color": {
          "title": "Color",
          "type": "string"
        },
        "width": {
          "exclusiveMinimum": 0,
          "title": "Width",
          "type": "number"
        },
        "opacity": {
          "maximum": 1,
          "minimum": 0,
          "title": "Opacity",
          "type": "number"
        },
        "filters": {
          "items": {
            "discriminator": {
              "mapping": {
                "absolute_value": "#/$defs/AbsoluteValueFilter",
                "clip": "#/$defs/ClipFilter",
                "comparison": "#/$defs/ComparisonFilter",
                "deadband": "#/$defs/DeadbandFilter",
                "derivative": "#/$defs/DerivativeFilter",
                "exp": "#/$defs/ExpFilter",
                "high_pass": "#/$defs/HighPassFilter",
                "integral": "#/$defs/IntegralFilter",
                "log": "#/$defs/LogFilter",
                "low_pass": "#/$defs/LowPassFilter",
                "median": "#/$defs/RollingMedianFilter",
                "normalize": "#/$defs/NormalizeFilter",
                "power": "#/$defs/PowerFilter",
                "reverse": "#/$defs/ReverseFilter",
                "rolling_mean": "#/$defs/RollingMeanFilter",
                "rotation": "#/$defs/RotationFilter",
                "round": "#/$defs/RoundFilter",
                "savitzky_golay": "#/$defs/SavitzkyGolayFilter",
                "scale": "#/$defs/ScaleFilter",
                "sign": "#/$defs/SignFilter",
                "sort": "#/$defs/SortFilter",
                "stat_first": "#/$defs/FirstFilter",
                "stat_last": "#/$defs/LastFilter",
                "stat_max": "#/$defs/MaxFilter",
                "stat_mean": "#/$defs/MeanFilter",
                "stat_median": "#/$defs/MedianFilter",
                "stat_min": "#/$defs/MinFilter",
                "stat_mode": "#/$defs/ModeFilter",
                "stat_standard_deviation": "#/$defs/StandardDeviationFilter",
                "taring": "#/$defs/TaringFilter",
                "trig": "#/$defs/TrigFilter",
                "unit": "#/$defs/UnitFilter",
                "wrap": "#/$defs/WrapFilter"
              },
              "propertyName": "type"
            },
            "oneOf": [
              {
                "$ref": "#/$defs/ScaleFilter"
              },
              {
                "$ref": "#/$defs/AbsoluteValueFilter"
              },
              {
                "$ref": "#/$defs/DerivativeFilter"
              },
              {
                "$ref": "#/$defs/IntegralFilter"
              },
              {
                "$ref": "#/$defs/LowPassFilter"
              },
              {
                "$ref": "#/$defs/HighPassFilter"
              },
              {
                "$ref": "#/$defs/RollingMeanFilter"
              },
              {
                "$ref": "#/$defs/SavitzkyGolayFilter"
              },
              {
                "$ref": "#/$defs/ClipFilter"
              },
              {
                "$ref": "#/$defs/DeadbandFilter"
              },
              {
                "$ref": "#/$defs/TaringFilter"
              },
              {
                "$ref": "#/$defs/UnitFilter"
              },
              {
                "$ref": "#/$defs/RollingMedianFilter"
              },
              {
                "$ref": "#/$defs/NormalizeFilter"
              },
              {
                "$ref": "#/$defs/WrapFilter"
              },
              {
                "$ref": "#/$defs/RotationFilter"
              },
              {
                "$ref": "#/$defs/LogFilter"
              },
              {
                "$ref": "#/$defs/ExpFilter"
              },
              {
                "$ref": "#/$defs/PowerFilter"
              },
              {
                "$ref": "#/$defs/RoundFilter"
              },
              {
                "$ref": "#/$defs/TrigFilter"
              },
              {
                "$ref": "#/$defs/SignFilter"
              },
              {
                "$ref": "#/$defs/ComparisonFilter"
              },
              {
                "$ref": "#/$defs/MaxFilter"
              },
              {
                "$ref": "#/$defs/MinFilter"
              },
              {
                "$ref": "#/$defs/MeanFilter"
              },
              {
                "$ref": "#/$defs/MedianFilter"
              },
              {
                "$ref": "#/$defs/ModeFilter"
              },
              {
                "$ref": "#/$defs/StandardDeviationFilter"
              },
              {
                "$ref": "#/$defs/FirstFilter"
              },
              {
                "$ref": "#/$defs/LastFilter"
              },
              {
                "$ref": "#/$defs/SortFilter"
              },
              {
                "$ref": "#/$defs/ReverseFilter"
              }
            ]
          },
          "title": "Filters",
          "type": "array"
        },
        "dash": {
          "$ref": "#/$defs/DashStyle"
        },
        "marker": {
          "$ref": "#/$defs/MarkerSymbol"
        }
      },
      "required": [
        "label",
        "color",
        "width",
        "opacity",
        "filters",
        "dash",
        "marker"
      ],
      "title": "YAxisConfig",
      "type": "object"
    }
  },
  "description": "Complete serialisable state of a trial-viewer plot.",
  "properties": {
    "xAxis": {
      "$ref": "#/$defs/XAxisConfig"
    },
    "yAxes": {
      "additionalProperties": {
        "$ref": "#/$defs/YAxisConfig"
      },
      "title": "Yaxes",
      "type": "object"
    },
    "refFrame": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Refframe"
    },
    "grid": {
      "$ref": "#/$defs/GridMode"
    },
    "lineMode": {
      "$ref": "#/$defs/LineMode"
    },
    "interp": {
      "$ref": "#/$defs/InterpMode"
    },
    "hover": {
      "$ref": "#/$defs/HoverMode"
    },
    "title": {
      "title": "Title",
      "type": "string"
    },
    "xAxisTitle": {
      "title": "Xaxistitle",
      "type": "string"
    },
    "yAxisTitle": {
      "title": "Yaxistitle",
      "type": "string"
    },
    "showSpike": {
      "title": "Showspike",
      "type": "boolean"
    },
    "legendPos": {
      "$ref": "#/$defs/LegendPos"
    },
    "rangeX": {
      "anyOf": [
        {
          "maxItems": 2,
          "minItems": 2,
          "prefixItems": [
            {
              "anyOf": [
                {
                  "type": "number"
                },
                {
                  "type": "null"
                }
              ]
            },
            {
              "anyOf": [
                {
                  "type": "number"
                },
                {
                  "type": "null"
                }
              ]
            }
          ],
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Rangex"
    },
    "rangeY": {
      "anyOf": [
        {
          "maxItems": 2,
          "minItems": 2,
          "prefixItems": [
            {
              "anyOf": [
                {
                  "type": "number"
                },
                {
                  "type": "null"
                }
              ]
            },
            {
              "anyOf": [
                {
                  "type": "number"
                },
                {
                  "type": "null"
                }
              ]
            }
          ],
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "title": "Rangey"
    },
    "xScale": {
      "$ref": "#/$defs/ScaleType"
    },
    "yScale": {
      "$ref": "#/$defs/ScaleType"
    },
    "xLogBase": {
      "anyOf": [
        {
          "exclusiveMinimum": 0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Xlogbase"
    },
    "yLogBase": {
      "anyOf": [
        {
          "exclusiveMinimum": 0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Ylogbase"
    },
    "plotType": {
      "$ref": "#/$defs/PlotType",
      "default": "cartesian"
    },
    "vsEnabled": {
      "title": "Vsenabled",
      "type": "boolean"
    },
    "vsRange": {
      "maxItems": 2,
      "minItems": 2,
      "prefixItems": [
        {
          "type": "number"
        },
        {
          "type": "number"
        }
      ],
      "title": "Vsrange",
      "type": "array"
    },
    "annotations": {
      "items": {
        "$ref": "#/$defs/Annotation"
      },
      "title": "Annotations",
      "type": "array"
    },
    "shapes": {
      "items": {
        "discriminator": {
          "mapping": {
            "hline": "#/$defs/HlineShape",
            "rect": "#/$defs/RectShape",
            "vline": "#/$defs/VlineShape"
          },
          "propertyName": "type"
        },
        "oneOf": [
          {
            "$ref": "#/$defs/VlineShape"
          },
          {
            "$ref": "#/$defs/HlineShape"
          },
          {
            "$ref": "#/$defs/RectShape"
          }
        ]
      },
      "title": "Shapes",
      "type": "array"
    }
  },
  "required": [
    "yAxes",
    "refFrame",
    "grid",
    "lineMode",
    "interp",
    "hover",
    "title",
    "xAxisTitle",
    "yAxisTitle",
    "showSpike",
    "legendPos",
    "rangeX",
    "rangeY",
    "xScale",
    "yScale",
    "vsEnabled",
    "vsRange",
    "annotations",
    "shapes"
  ],
  "title": "PlotConfig",
  "type": "object"
};
