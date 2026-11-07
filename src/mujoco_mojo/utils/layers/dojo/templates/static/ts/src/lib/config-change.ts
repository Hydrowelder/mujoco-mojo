// what the trial viewer does when the plot config changes, moved out of
// trial-viewer.ts so it can be tested without an alpine component: telling
// which signals' filters changed since their data was fetched, deciding
// whether the comparison trials need syncing, and the boot-time checks on a
// config.

import type { FilterEntry } from "../models";
import type { PlotConfig } from "./plot-config.generated";
import { refFrameActive } from "./ref-frame";

// the enabled filters of a signal as one string, so two filter stacks compare
// equal when they would give the same data
export function filterFingerprint(filters: FilterEntry[] | undefined): string {
  return JSON.stringify((filters ?? []).filter((f) => f.enabled !== false));
}

export interface ConfigChangePlan {
  // the signals whose filters differ from what their data was fetched with
  changedFilterCols: string[];
  // the new fingerprint of each of those
  filterFingerprints: Record<string, string>;
  xFilterChanged: boolean;
  xFilterFingerprint: string;
  // the columns to fetch again: the x column if its filters changed, then the changed signals
  colsToRefetch: string[];
}

// compares the config's filters against the fingerprints of the last fetch,
// not against the previous config, because Alpine's $watch does not reliably
// deep-clone the old value for nested reactive objects - both may point to the
// same data.
export function planConfigChange(
  config: PlotConfig,
  filterFingerprints: Record<string, string>,
  xAxisFilterFingerprint: string,
): ConfigChangePlan {
  const changedFilterCols = Object.keys(config.yAxes).filter((col) => {
    const current = filterFingerprint(config.yAxes[col]?.filters);
    return current !== (filterFingerprints[col] ?? "[]");
  });
  const xFilterFingerprint = filterFingerprint(config.xAxis?.filters);
  const xFilterChanged = xFilterFingerprint !== xAxisFilterFingerprint;
  return {
    changedFilterCols,
    filterFingerprints: Object.fromEntries(
      changedFilterCols.map((col) => [col, filterFingerprint(config.yAxes[col]?.filters)]),
    ),
    xFilterChanged,
    xFilterFingerprint,
    colsToRefetch: [
      ...(xFilterChanged ? [config.xAxis.col!] : []),
      ...changedFilterCols,
    ],
  };
}

// comparison trials need syncing again when the x column changes or the set of
// signals does (one added, removed or swapped for another), since each trial's
// data holds just the plotted columns. reordering the signals changes nothing
// they hold
export function needsVsSync(
  vsEnabled: boolean,
  value: PlotConfig,
  oldValue: PlotConfig | undefined,
): boolean {
  if (!vsEnabled) return false;
  if (value.xAxis.col! !== oldValue?.xAxis?.col) return true;
  const signals = Object.keys(value.yAxes);
  const oldSignals = new Set(Object.keys(oldValue?.yAxes ?? {}));
  return (
    signals.length !== oldSignals.size ||
    signals.some((col) => !oldSignals.has(col))
  );
}

// an old profile can set a reference frame without the rotation filter that
// applies it; such a config needs the filter added
export function needsRefFrameMigration(config: PlotConfig): boolean {
  if (!refFrameActive(config.refFrame)) return false;
  const hasRotation = Object.values(config.yAxes).some((y) =>
    (y.filters ?? []).some((f) => f.type === "rotation"),
  );
  return !hasRotation;
}

// the columns a plot shows: the x column, then each signal
export function activeColumns(config: PlotConfig): string[] {
  return [config.xAxis.col!, ...Object.keys(config.yAxes)];
}
