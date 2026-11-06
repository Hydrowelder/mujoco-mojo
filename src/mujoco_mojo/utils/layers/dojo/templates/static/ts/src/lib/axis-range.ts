// a manual axis range: either end may be left empty to autoscale that side, and
// both empty means fully automatic (null)

import { evalMathExpr } from "./math-expr";

export type AxisRange = [number | null, number | null];

// reads the manual x/y axis min/max fields as strings for display; empty means autoscale
export function rangeBoundText(range: AxisRange | null | undefined, bound: "min" | "max"): string {
  if (!range) return "";
  const val = bound === "min" ? range[0] : range[1];
  return val === null ? "" : String(val);
}

// the range after the user types `text` into the min or max field: the number
// it evaluates to (an expression such as `2*pi` is fine), or that side
// cleared when it is blank. the range collapses to null when both sides end up
// empty. returns null, meaning leave everything as it was, when the text is
// not a number
export function applyRangeBound(
  current: AxisRange | null | undefined,
  bound: "min" | "max",
  text: string,
): { range: AxisRange | null } | null {
  const trimmed = text.trim();
  const num = trimmed === "" ? null : evalMathExpr(trimmed);
  if (trimmed !== "" && num === null) return null;

  const base = current ?? ([null, null] as AxisRange);
  const next: AxisRange = bound === "min" ? [num, base[1]] : [base[0], num];

  return { range: next[0] === null && next[1] === null ? null : next };
}

// resolves a possibly-partial axis range into a concrete [min, max], falling back
// to the padded data range for whichever side is unset. null for a fully
// automatic axis; `auto` is only called when a side needs it
export function resolveAxisRange(
  configRange: AxisRange | null,
  auto: () => [number, number],
): [number, number] | null {
  if (!configRange || (configRange[0] === null && configRange[1] === null)) return null;
  const [min, max] = configRange;
  if (min !== null && max !== null) return [min, max];
  const fallback = auto();
  return [min ?? fallback[0], max ?? fallback[1]];
}
