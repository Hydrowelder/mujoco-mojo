// plot-tab bookkeeping for the trial viewer, moved out of trial-viewer.ts so
// it can be tested without an Alpine component. The generic tab-strip
// mechanics (ids, reorder, pick-next-on-close) live in tab-session.ts; this
// file is what is specific to a plot tab: its fields, when it counts as
// unsaved, which columns it still needs, and the closed-tab history.

import type { PlotConfig } from "./plot-config.generated";
import { newTabId } from "./tab-session";

// how many recently-closed plot tabs reopenLastClosedPlotTab() can recover
export const MAX_CLOSED_PLOT_TABS = 10;

// no separate "name" field - a plot tab's label is its config.title (see
// _macros.html's tab_strip() call in _chart.html), since a plot tab has no
// on-disk file identity the way a saved Signal Lab graph does.
export interface PlotTab {
  id: string;
  config: PlotConfig;
  data: Record<string, number[]> | null;
  filterFingerprints: Record<string, string>;
  xAxisFilterFingerprint: string;
  historyStack: string[];
  historyIndex: number;
  savedSnapshot: string | null; // JSON of config as of last profile save/load; null = never saved
  // set only while sitting in closedPlotTabs - its index in plotTabs at the
  // moment it was closed, so reopenLastClosedPlotTab() can reinsert it back
  // where it was rather than always appending at the end.
  closedAtIndex?: number;
}

const CLOSED_TABS_KEY = "mojo:plot:closedTabs";

export function makeBlankPlotTab(defaultConfig: PlotConfig): PlotTab {
  const config = JSON.parse(JSON.stringify(defaultConfig)) as PlotConfig;
  return {
    id: newTabId(),
    config,
    data: null,
    filterFingerprints: {},
    xAxisFilterFingerprint: "[]",
    historyStack: [],
    historyIndex: -1,
    // baselined against its own just-created state, not null/dirty - an
    // untouched new tab has nothing unsaved to warn about; savedSnapshot
    // only diverges once the user actually edits something in it.
    savedSnapshot: JSON.stringify(config),
  };
}

// shared by the tab strip's dirty dot (_plot_tabs.html) and
// closePlotTab()'s confirm-before-discard check, so the two can't drift.
export function isPlotTabDirty(tab: PlotTab): boolean {
  return !tab.savedSnapshot || JSON.stringify(tab.config) !== tab.savedSnapshot;
}

// columns a tab's config plots that its data cache does not hold yet
export function neededColumns(
  cfg: PlotConfig,
  cache: Record<string, number[]> | null,
): string[] {
  const needed: string[] = [];
  if (cfg.xAxis?.col && !cache?.[cfg.xAxis.col]) needed.push(cfg.xAxis.col);
  for (const col of Object.keys(cfg.yAxes ?? {})) {
    if (!cache?.[col]) needed.push(col);
  }
  return needed;
}

// the copy a "duplicate tab" makes: a deep config copy with " copy" appended
// to a non-empty title, a shallow copy of the data cache and fingerprints,
// and fresh history. savedSnapshot is null so the copy starts out unsaved.
export function duplicatePlotTab(source: PlotTab): PlotTab {
  const config = JSON.parse(JSON.stringify(source.config)) as PlotConfig;
  if (config.title) config.title = `${config.title} copy`;
  return {
    id: newTabId(),
    config,
    data: source.data ? { ...source.data } : null,
    filterFingerprints: { ...source.filterFingerprints },
    xAxisFilterFingerprint: source.xAxisFilterFingerprint,
    historyStack: [],
    historyIndex: -1,
    savedSnapshot: null,
  };
}

// the tab list as it is written to localStorage: WITHOUT the large,
// always-refetchable data cache - unlike a LabTab's graph (small, needed to
// restore the canvas), raw telemetry arrays would bloat localStorage for no
// benefit, so every tab's data starts null again after a page reload.
export function persistablePlotTabs(tabs: PlotTab[]): PlotTab[] {
  return tabs.map((t) => ({
    ...t,
    data: null,
  }));
}

// a closed tab as it sits in closedPlotTabs: data stripped same as
// persistablePlotTabs() - always re-fetched on reopen via the activate step's
// own needed-columns check; closedAtIndex is the tab's position before it
// was removed, so reopening can reinsert it back where it was.
export function closedPlotTabEntry(tab: PlotTab, closedAtIndex: number | undefined): PlotTab {
  return { ...tab, data: null, closedAtIndex };
}

// most-recently-closed first, capped at MAX_CLOSED_PLOT_TABS
export function pushClosedPlotTabs(closed: PlotTab[], newlyClosed: PlotTab[]): PlotTab[] {
  return [...newlyClosed, ...closed].slice(0, MAX_CLOSED_PLOT_TABS);
}

// where a reopened tab goes: back at the index it was closed from, or the
// end of the list when that is unknown or past the end of the shorter list
export function reopenPlotTab(
  mostRecent: PlotTab,
  tabCount: number,
): { tab: PlotTab; insertAt: number } {
  const insertAt = Math.min(mostRecent.closedAtIndex ?? tabCount, tabCount);
  return { tab: { ...mostRecent, closedAtIndex: undefined }, insertAt };
}

export function loadClosedPlotTabs(): PlotTab[] {
  try {
    const raw = localStorage.getItem(CLOSED_TABS_KEY);
    return raw ? (JSON.parse(raw) as PlotTab[]) : [];
  } catch {
    return [];
  }
}

export function persistClosedPlotTabs(closed: PlotTab[]): void {
  try {
    localStorage.setItem(CLOSED_TABS_KEY, JSON.stringify(closed));
  } catch {}
}
