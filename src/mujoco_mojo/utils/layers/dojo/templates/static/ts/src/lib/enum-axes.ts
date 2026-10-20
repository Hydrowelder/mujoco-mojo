// helpers for plotting integer-coded ("enum") signals. a column whose metadata
// has an `enumeration_map` (label -> code) is drawn on a right-hand axis whose
// ticks read as the labels, and its tooltip shows the label next to the code.
// one axis serves every column that shares the same map. pure functions only
// (no Alpine or Plotly imports) so the maths stays easy to follow; trial-viewer.ts
// wires the results into the Plotly figure.

export type EnumMap = Record<string, number>;

export interface EnumGroup {
  // canonical key of the map shared by every column in the group
  key: string;
  columns: string[];
  // every code in the map with its label, ascending by code
  ticks: { code: number; label: string }[];
  labelByCode: Map<number, string>;
}

export interface EnumPlan {
  // one entry per distinct map, in order of first appearance among the columns
  groups: EnumGroup[];
  // column name -> index into `groups`
  groupOf: Map<string, number>;
}

export interface EnumAxisStyle {
  title: string;
  range: [number, number];
  // color of the tick labels and title
  color: string;
  // true when this axis takes the plot's primary y slot (no numeric columns to show)
  primary: boolean;
  grid: { color: string; show: boolean };
}

// longest tick label before it is cut with an ellipsis; the tooltip keeps the full label
const MAX_TICK_LABEL = 12;

// tick label size; smaller than the numeric axes' 14 so several enum axes fit beside the plot
const TICK_FONT_SIZE = 11;

// a code read from float telemetry counts as whole if it is this close to an integer
const CODE_TOLERANCE = 1e-9;

// plotly renders tick text and hover text as a small HTML subset, so a label
// containing `<` or `&` has to be escaped to show literally
function plotlyText(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

// the column's enumeration_map, or null if it has none (or an unusable one)
export function enumMapOf(
  meta: { enumeration_map?: unknown } | null | undefined,
): EnumMap | null {
  const raw = meta?.enumeration_map;
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) return null;
  const entries = Object.entries(raw as Record<string, unknown>);
  if (entries.length === 0) return null;
  const map: EnumMap = {};
  for (const [label, code] of entries) {
    if (typeof code !== "number" || !Number.isFinite(code)) return null;
    map[label] = code;
  }
  return map;
}

// identical maps give identical keys no matter how their entries were ordered
export function enumGroupKey(map: EnumMap): string {
  const entries = Object.entries(map).sort(([a], [b]) =>
    a < b ? -1 : a > b ? 1 : 0,
  );
  return JSON.stringify(entries);
}

function buildGroup(key: string, map: EnumMap): EnumGroup {
  const labelByCode = new Map<number, string>();
  // sorted by code; if two labels share a code (an invalid map) the first one wins
  for (const [label, code] of Object.entries(map).sort(
    ([, a], [, b]) => a - b,
  )) {
    if (!labelByCode.has(code)) labelByCode.set(code, label);
  }
  const ticks = [...labelByCode].map(([code, label]) => ({ code, label }));
  return { key, columns: [], ticks, labelByCode };
}

// groups the enum columns among `cols` by their map; columns without one are left out
export function planEnumAxes(
  cols: string[],
  meta: Record<string, { enumeration_map?: unknown } | undefined>,
): EnumPlan {
  const groups: EnumGroup[] = [];
  const indexByKey = new Map<string, number>();
  const groupOf = new Map<string, number>();
  for (const col of cols) {
    const map = enumMapOf(meta[col]);
    if (!map) continue;
    const key = enumGroupKey(map);
    let idx = indexByKey.get(key);
    if (idx === undefined) {
      idx = groups.length;
      indexByKey.set(key, idx);
      groups.push(buildGroup(key, map));
    }
    groups[idx]!.columns.push(col);
    groupOf.set(col, idx);
  }
  return { groups, groupOf };
}

// one tooltip string per point: `RUNNING (1)`, just the number for a code the map
// does not name, and an empty string for a gap
export function enumLabels(
  values: ArrayLike<number | null | undefined>,
  group: EnumGroup,
): string[] {
  const cache = new Map<number, string>();
  const out = new Array<string>(values.length);
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v == null || !Number.isFinite(v)) {
      out[i] = "";
      continue;
    }
    const code = Math.round(v);
    if (Math.abs(v - code) > CODE_TOLERANCE) {
      out[i] = String(v);
      continue;
    }
    let text = cache.get(code);
    if (text === undefined) {
      const label = group.labelByCode.get(code);
      text = label === undefined ? String(code) : `${plotlyText(label)} (${code})`;
      cache.set(code, text);
    }
    out[i] = text;
  }
  return out;
}

// the axis range: every code in the map plus any data outside it, padded so the
// outermost steps do not sit on the plot edge
export function enumRange(
  group: EnumGroup,
  series: ArrayLike<number | null | undefined>[],
): [number, number] {
  let lo = group.ticks[0]!.code;
  let hi = group.ticks[group.ticks.length - 1]!.code;
  for (const values of series) {
    for (let i = 0; i < values.length; i++) {
      const v = values[i];
      if (v == null || !Number.isFinite(v)) continue;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
  }
  const pad = Math.max(0.5, (hi - lo) * 0.06);
  return [lo - pad, hi + pad];
}

// where group `idx` lives: the trace's `yaxis` reference and the layout key. normally
// the primary y axis belongs to the numeric columns and enum groups start at axis 2;
// when `promoted` there are no numeric columns, so group 0 takes the primary slot.
export function enumAxisIds(
  idx: number,
  promoted: boolean,
): { traceRef: string; layoutKey: string } {
  const n = promoted ? idx + 1 : idx + 2;
  return n === 1
    ? { traceRef: "y", layoutKey: "yaxis" }
    : { traceRef: `y${n}`, layoutKey: `yaxis${n}` };
}

// the Plotly axis object for a group. extra axes overlay the primary one on the
// right and `autoshift` stacks them by their measured width, growing the right
// margin as needed. the axis is fixed (not zoomable) since its range is its codes.
export function enumAxisLayout(
  group: EnumGroup,
  style: EnumAxisStyle,
): Record<string, unknown> {
  return {
    type: "linear",
    side: "right",
    autorange: false,
    range: style.range,
    fixedrange: true,
    tickmode: "array",
    tickvals: group.ticks.map((t) => t.code),
    ticktext: group.ticks.map((t) =>
      plotlyText(truncate(t.label, MAX_TICK_LABEL)),
    ),
    tickfont: { color: style.color, size: TICK_FONT_SIZE },
    zeroline: false,
    showspikes: false,
    title: {
      text: style.title,
      font: { size: 14, color: style.color, family: "monospace" },
    },
    ...(style.primary
      ? {
          automargin: true,
          showgrid: style.grid.show,
          gridcolor: style.grid.color,
        }
      : {
          overlaying: "y",
          anchor: "free",
          autoshift: true,
          showgrid: false,
        }),
  };
}
