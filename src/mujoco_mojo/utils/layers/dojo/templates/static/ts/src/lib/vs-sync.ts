// versus mode's data syncing and hydration, moved out of trial-viewer.ts so it
// can be tested without an alpine component: which comparison trials to load
// and which columns, what is still missing, and the trial chips.

import { refFrameActive } from "./ref-frame";
import { trialOutcome } from "./trial-status";
import type { PlotConfig } from "./plot-config.generated";

// a range with its ends in order
export function orderedRange(range: [number, number]): [number, number] {
  return [Math.min(range[0], range[1]), Math.max(range[0], range[1])];
}

// the trials a comparison covers: those numbered inside the range and any
// pinned ones, leaving out the trial being viewed, as `exclude` decides
export function vsTargetIds(
  allTrials: string[],
  start: number,
  end: number,
  pinned: number[],
  exclude: (id: string, n: number) => boolean,
): string[] {
  const pinnedSet = new Set(pinned);
  return allTrials.filter((id) => {
    const n = parseInt(id.split("_").pop() ?? "");
    return ((n >= start && n <= end) || pinnedSet.has(n)) && !exclude(id, n);
  });
}

// every column a comparison trial needs: the plot's own, plus with a
// reference frame set the x, y and z of each signal's family and the frame's
// own quaternion and origin, so the frame can be applied to the comparison
// data too.
export function vsActiveColumns(config: PlotConfig): string[] {
  let activeCols = [config.xAxis.col!, ...Object.keys(config.yAxes)];

  if (refFrameActive(config.refFrame)) {
    const families = new Set<string>();
    Object.keys(config.yAxes).forEach((col) => {
      if (col.includes(":")) families.add(col.substring(0, col.lastIndexOf(":")));
    });
    families.forEach((fam) => activeCols.push(`${fam}:x`, `${fam}:y`, `${fam}:z`));
    const [refQuat, refOrigin] = config.refFrame;
    if (refQuat) activeCols.push(`${refQuat}:w`, `${refQuat}:x`, `${refQuat}:y`, `${refQuat}:z`);
    if (refOrigin) activeCols.push(`${refOrigin}:x`, `${refOrigin}:y`, `${refOrigin}:z`);
  }
  activeCols = [...new Set(activeCols)];
  return activeCols;
}

// whether a comparison trial's data needs fetching: it has none yet, lacks a
// column, or a reference frame is set (its data depends on the frame)
export function vsNeedsFetch(
  existing: Record<string, number[]> | undefined,
  cols: string[],
  frameActive: boolean,
): boolean {
  return (
    !existing ||
    cols.some((col) => !Object.prototype.hasOwnProperty.call(existing, col)) ||
    frameActive
  );
}

// the columns that have no data yet
export function missingColumns(cols: string[], data: Record<string, number[]> | null): string[] {
  return cols.filter((c) => !Object.prototype.hasOwnProperty.call(data ?? {}, c));
}

export function comparingNotice(count: number): string {
  return `Comparing ${count} trial${count === 1 ? "" : "s"}`;
}

// the same list in chunks of at most `size`, for loading columns a few at a time
export function chunked<T>(list: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < list.length; i += size) out.push(list.slice(i, i + size));
  return out;
}

// the range and pinned trials saved in this browser, over the ones given for
// whatever is missing from it or cannot be read.
export function parseStoredVs(
  raw: string | null,
  current: { range: [number, number]; pinned: number[] },
): { range: [number, number]; pinned: number[] } {
  let range = current.range;
  let pinned = current.pinned;
  try {
    if (raw) {
      const parsed = JSON.parse(raw) as {
        range?: [number, number];
        pinned?: number[];
      };
      if (parsed.range) range = parsed.range;
      if (parsed.pinned) pinned = parsed.pinned;
    }
  } catch {}
  return { range, pinned };
}

// the classes of a trial's chip in the comparison picker: the same coloring as
// the monitor page's success, failed and error trial badges (a translucent
// tinted background with a colored border and text), with a ring on pinned
// ones, and a plain accent outline for the trial being viewed.
export function vsChipClass(
  trialIdOfChip: string,
  currentTrialId: string,
  pinned: number[],
  errorTrialNums: number[],
  failureTrialNums: number[],
): string {
  const tn = parseInt(trialIdOfChip.split("_").pop() ?? "0");
  if (trialIdOfChip === currentTrialId)
    return "border-accent-500 text-accent-500 dark:text-accent-400 cursor-default";
  const ring = pinned.includes(tn) ? " ring-2 ring-accent-500" : "";
  const outcome = trialOutcome(tn, errorTrialNums, failureTrialNums);
  if (outcome === "error")
    return `bg-warning-50 dark:bg-warning-900/30 border-warning-400 dark:border-warning-500/50 text-warning-600 dark:text-warning-400 hover:bg-warning-100 dark:hover:bg-warning-800/50${ring}`;
  if (outcome === "failure")
    return `bg-danger-50 dark:bg-danger-900/30 border-danger-400 dark:border-danger-500/50 text-danger-600 dark:text-danger-400 hover:bg-danger-100 dark:hover:bg-danger-800/50${ring}`;
  return `bg-success-50 dark:bg-success-900/30 border-success-400 dark:border-success-500/50 text-success-600 dark:text-success-400 hover:bg-success-100 dark:hover:bg-success-800/50${ring}`;
}
