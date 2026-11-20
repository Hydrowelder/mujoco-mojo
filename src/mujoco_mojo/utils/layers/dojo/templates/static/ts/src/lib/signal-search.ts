// the signal pickers' search settings: whether the box reads what is typed as a
// regular expression or as plain text, and whether it also searches the
// signals' descriptions. one setting for every picker (x, y, reference frame
// and the Signal Lab's), kept in the browser so it is the same on the next visit

import type { SearchMode } from "./column-search";

export interface SignalSearch {
  mode: SearchMode;
  metadata: boolean;
}

export const DEFAULT_SIGNAL_SEARCH: SignalSearch = {
  mode: "regex",
  metadata: false,
};

const STORAGE_KEY = "mojo-signal-search";

// the other mode, which is what the toggle in the search box does
export function nextSearchMode(mode: SearchMode): SearchMode {
  return mode === "regex" ? "text" : "regex";
}

// the saved settings, or the defaults when nothing is saved or what is saved
// cannot be read
export function loadSignalSearch(): SignalSearch {
  try {
    const saved = JSON.parse(
      localStorage.getItem(STORAGE_KEY) ?? "null",
    ) as Partial<SignalSearch> | null;
    return {
      mode: saved?.mode === "text" ? "text" : "regex",
      metadata: saved?.metadata === true,
    };
  } catch {
    return { ...DEFAULT_SIGNAL_SEARCH };
  }
}

export function saveSignalSearch(search: SignalSearch): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(search));
  } catch {
    /* ignore: the setting just is not kept */
  }
}
