// the color and line style a newly plotted signal starts with

import type { DashStyle } from "./plot-config.generated";

// picks the lowest-index (color, dash) pair not already in use by `used`,
// so removing an earlier item in the cycle and adding a new one doesn't
// collide with a pair still in use. Cycles through every color before
// advancing to the next dash style, and falls back to round-robin by
// count once every color/dash combination is taken.
//
// `colorAt` gives the color for a palette position (0 up to numColors - 1)
export function nextAvailableStyle(
  used: { color: string; dash: DashStyle }[],
  numColors: number,
  colorAt: (index: number) => string,
  dashStyles: readonly DashStyle[],
): { color: string; dash: DashStyle } {
  const usedKeys = new Set(used.map((u) => `${u.color}|${u.dash}`));
  const numCombos = numColors * dashStyles.length;
  const styleAt = (i: number) => ({
    color: colorAt(i % numColors),
    dash: dashStyles[Math.floor(i / numColors) % dashStyles.length]!,
  });
  let i = 0;
  while (i < numCombos) {
    const style = styleAt(i);
    if (!usedKeys.has(`${style.color}|${style.dash}`)) return style;
    i++;
  }
  return styleAt(used.length);
}
