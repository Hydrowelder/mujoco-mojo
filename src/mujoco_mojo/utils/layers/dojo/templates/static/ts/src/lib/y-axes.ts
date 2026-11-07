// the order of the plotted signals, which is the order of the y-axes map's keys

import type { FilterEntry, YAxisConfig } from "../models";
import type { DashStyle } from "./plot-config.generated";
import { buildRefFrameFilter, refFrameActive, type RefFrame } from "./ref-frame";

// the signals with the one at `index` moved by `direction` places (-1 up, 1
// down), or sent to the very top (direction -1) or bottom (anything else)
// when `toEnd` is set. null when there are fewer than two signals to reorder
export function reorderYAxes(
  yAxes: Record<string, YAxisConfig>,
  index: number,
  direction: number,
  toEnd = false,
): Record<string, YAxisConfig> | null {
  const keys = Object.keys(yAxes);
  if (keys.length < 2) return null;
  const newKeys = [...keys];
  const movedKey = newKeys.splice(index, 1)[0]!;
  if (toEnd) {
    direction === -1 ? newKeys.unshift(movedKey) : newKeys.push(movedKey);
  } else {
    newKeys.splice(index + direction, 0, movedKey);
  }
  const reordered: Record<string, YAxisConfig> = {};
  newKeys.forEach((k) => {
    reordered[k] = yAxes[k]!;
  });
  return reordered;
}

// the colors and dashes the plotted signals already use, so a new signal can be
// given a style none of them has
export function usedStyles(
  yAxes: Record<string, YAxisConfig>,
): Array<{ color: string; dash: DashStyle }> {
  return Object.values(yAxes).map((y) => ({
    color: y.color,
    dash: y.dash ?? "solid",
  }));
}

// the signals without the one named
export function withoutYAxis(
  yAxes: Record<string, YAxisConfig>,
  col: string,
): Record<string, YAxisConfig> {
  const { [col]: _, ...rest } = yAxes;
  return rest;
}

// a signal being added: solid and three pixels wide in the style it was
// given, with no markers. Under a reference frame it starts with the rotation
// filter that applies the frame, except an enum signal, since a filter or
// frame rotation on a code stream is meaningless.
export function newYAxisConfig(
  style: { color: string; dash: YAxisConfig["dash"] },
  refFrame: RefFrame,
  isEnum: boolean,
): YAxisConfig {
  const initFilters: FilterEntry[] =
    refFrameActive(refFrame) && !isEnum ? [buildRefFrameFilter(refFrame)] : [];
  return {
    color: style.color,
    label: "",
    width: 3,
    opacity: 1,
    filters: initFilters,
    dash: style.dash,
    marker: "none",
  };
}

// which signals a shift-click should toggle: every row between the last
// clicked row and this one (in either order, in the list's visible order) that
// is not already in the state this click is moving to (selected if the
// clicked signal was off, deselected if it was on). null when there is no
// range to take, because either row is not in the list.
export function yRangeToggles(
  rows: Array<{ path: string; item: string }>,
  lastPath: string,
  clickedPath: string,
  clickedWasOn: boolean,
  isOn: (col: string) => boolean,
): string[] | null {
  const fromIdx = rows.findIndex((r) => r.path === lastPath);
  const toIdx = rows.findIndex((r) => r.path === clickedPath);
  if (fromIdx === -1 || toIdx === -1) return null;
  const [lo, hi] = fromIdx < toIdx ? [fromIdx, toIdx] : [toIdx, fromIdx];
  const shouldSelect = !clickedWasOn;
  const toggles: string[] = [];
  for (let i = lo; i <= hi; i++) {
    const c = rows[i]!.item;
    if (shouldSelect !== isOn(c)) toggles.push(c);
  }
  return toggles;
}
