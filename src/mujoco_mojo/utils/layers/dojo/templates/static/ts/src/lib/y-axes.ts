// the order of the plotted signals, which is the order of the y-axes map's keys

import type { YAxisConfig } from "../models";

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
