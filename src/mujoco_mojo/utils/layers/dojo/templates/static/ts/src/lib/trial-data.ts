// the request the trial viewer makes for a trial's data, moved out of
// trial-viewer.ts so it can be tested without a server: which columns, which
// filters, which unit system and point limit.

import type { FilterEntry } from "./plot-config.generated";

export interface DataRequestConfig {
  yAxes: Record<string, { filters?: FilterEntry[] }>;
  xAxis?: { col?: string; filters?: FilterEntry[] };
  displayUnitSystem?: string | null;
  maxPoints?: number | null;
}

// the filters that are switched on, without their enabled flag
function toActiveFilters(filters: FilterEntry[]): object[] {
  return filters
    .filter((f) => f.enabled !== false)
    .map((f) => Object.fromEntries(Object.entries(f).filter(([k]) => k !== "enabled")));
}

// builds the data URL for the given columns (all of them when none are named).
// The filters of each requested column go along so the server filters the data
// it sends: a signal's own, except an enum signal's (a filter would scramble
// its codes), and the x column's. The display unit system and the point limit
// go along when set.
export function trialDataUrl(
  id: string,
  requiredCols: string[],
  config: DataRequestConfig,
  isEnumCol: (col: string) => boolean,
): string {
  let url = `/mosaic/${id}/data`;
  const colParams = new URLSearchParams();
  if (requiredCols.length > 0) colParams.append("cols", requiredCols.join(","));

  // include active filter stacks for requested columns (x-axis and y-axes)
  const filtersPayload: Record<string, object[]> = {};
  for (const col of requiredCols) {
    const yConfig = config.yAxes[col];
    if (yConfig?.filters && yConfig.filters.length > 0 && !isEnumCol(col)) {
      const active = toActiveFilters(yConfig.filters);
      if (active.length > 0) filtersPayload[col] = active;
    }
    if (col === config.xAxis!.col!) {
      const xFilters = config.xAxis?.filters ?? [];
      if (xFilters.length > 0) {
        const active = toActiveFilters(xFilters);
        if (active.length > 0) filtersPayload[col] = active;
      }
    }
  }
  if (Object.keys(filtersPayload).length > 0) {
    colParams.append("filters", JSON.stringify(filtersPayload));
  }
  if (config.displayUnitSystem) {
    colParams.append("display_unit_system", config.displayUnitSystem);
  }
  if (config.maxPoints != null) {
    colParams.append("max_points", String(config.maxPoints));
  }

  const queryStr = colParams.toString();
  if (queryStr) url += `?${queryStr}`;
  return url;
}

// the filter error messages not already on screen, each once
export function unseenFilterErrors(errors: string[], shown: ReadonlySet<string>): string[] {
  return [...new Set(errors.filter((m) => !shown.has(m)))];
}
