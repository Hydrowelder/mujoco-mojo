// signal lab logic for the trial viewer, moved out of trial-viewer.ts so it
// can be tested without an alpine component: which labs can run on a trial,
// the lab tab objects, the lab URL, and what a saved lab makes stale in the
// plot's data cache. the generic tab-strip mechanics live in tab-session.ts.

import { encodeNamePath } from "./name-path";
import { newTabId } from "./tab-session";

// one saved lab as the trial viewer holds it: what the server reports about
// it, plus whether this trial can run it
export interface LabSchema {
  name: string;
  signal_in_columns: string[];
  outputs: string[];
  modified: number;
  valid: boolean;
  missing: string[];
  is_template: boolean;
  template_inputs: string[];
  template_outputs: string[];
}

export interface LabTab {
  id: string;
  name: string;
  graph: object | null;
  savedState: string | null; // JSON of the graph at last save/load; null = never saved
  dirty: boolean;
  viewport: { scale: number; offset: [number, number] } | null; // remembered pan/zoom
}

export function labUrl(name: string): string {
  return `/mosaic/api/lab/${encodeNamePath(name)}`;
}

// what the server sends for a lab, before this trial has decided if it can run
export type RawLabSchema = Omit<LabSchema, "valid" | "missing">;

// decides which labs this trial can run, and which columns exist once they
// have. A lab is valid when all its inputs are available; labs that read other
// labs' outputs need several passes to resolve. Returns the labs with their
// `valid` and `missing` filled in, and the trial's column list rebuilt from
// scratch (which drops stale entries from deleted labs).
export function resolveLabSchemas(
  all: RawLabSchema[],
  columns: string[],
): { schemas: LabSchema[]; columns: string[] } {
  // deduplicate and sort inputs/outputs for each lab.
  const schemas = all.map((lab) => ({
    ...lab,
    signal_in_columns: [...new Set(lab.signal_in_columns)].sort(),
    outputs: [...new Set(lab.outputs)].sort(),
    is_template: lab.is_template ?? false,
    template_inputs: lab.template_inputs ?? [],
    template_outputs: lab.template_outputs ?? [],
  }));
  // iterative BFS: a lab is valid when all its inputs are already available.
  // Labs that read from other valid labs' outputs need multiple passes to resolve.
  const baseColumns = columns.filter((c) => !c.startsWith("Lab/"));
  const available = new Set(baseColumns);
  const validLabs = new Set<string>();
  let changed = true;
  while (changed) {
    changed = false;
    for (const lab of schemas) {
      if (validLabs.has(lab.name)) continue;
      if (lab.signal_in_columns.every((c) => available.has(c))) {
        validLabs.add(lab.name);
        lab.outputs.forEach((o) => available.add(`Lab/${lab.name}/${o}`));
        changed = true;
      }
    }
  }
  return {
    schemas: schemas.map((lab) => ({
      ...lab,
      missing: lab.signal_in_columns.filter((c) => !available.has(c)),
      valid: validLabs.has(lab.name),
    })),
    // rebuild virtual Lab columns from scratch - removes stale entries from deleted labs.
    columns: [...available].sort(),
  };
}

export function makeBlankLabTab(): LabTab {
  return {
    id: newTabId(),
    name: "",
    graph: null,
    savedState: null,
    viewport: null,
    dirty: false,
  };
}

// the tab a page load starts with when there is no saved tab list: the old
// single-lab format, a name and a draft graph under their own keys
export function legacyLabTabs(): { tabs: LabTab[]; activeId: string } {
  const name = localStorage.getItem("mojo:lab:name") ?? "";
  const graph = (() => {
    try {
      const s = localStorage.getItem("mojo:lab:draft");
      return s ? (JSON.parse(s) as object) : null;
    } catch {
      return null;
    }
  })();
  const id = newTabId();
  return {
    tabs: [
      {
        id,
        name,
        graph,
        savedState: null,
        dirty: false,
        viewport: null,
      },
    ],
    activeId: id,
  };
}

// the copy a "duplicate tab" makes: a deep copy of the graph with " copy"
// appended to a non-empty name
export function duplicateLabTab(source: LabTab): LabTab {
  return {
    id: newTabId(),
    name: source.name ? `${source.name} copy` : "",
    graph: source.graph
      ? (JSON.parse(JSON.stringify(source.graph)) as object)
      : null,
    // never saved under its own name yet, so it starts dirty (unless
    // it's an empty graph, matching a blank tab's own clean baseline)
    savedState: null,
    dirty: !!source.graph,
    viewport: source.viewport ? { ...source.viewport } : null,
  };
}

// a tab for a lab just fetched from the server
export function labTabFor(name: string, graph: object): LabTab {
  return {
    id: newTabId(),
    name,
    graph,
    savedState: null,
    viewport: null,
    dirty: false,
  };
}

// an untitled tab with no unsaved changes can be reused for the lab being
// opened instead of adding a new tab
export function isReusableLabTab(tab: LabTab): boolean {
  return !tab.name && !tab.dirty;
}

// compute the transitive closure of labs whose outputs may now be stale: the
// saved lab itself, plus any lab that (directly or transitively) reads from it.
export function staleLabs(schemas: LabSchema[], saved: string): Set<string> {
  const dependents = new Map<string, string[]>();
  for (const lab of schemas) {
    for (const col of lab.signal_in_columns) {
      if (col.startsWith("Lab/")) {
        // lab names may contain '/' (nested folders); the output label is
        // always the final segment, so split from the right
        const depRest = col.slice(4);
        const depSplitIdx = depRest.lastIndexOf("/");
        const src = depSplitIdx >= 0 ? depRest.slice(0, depSplitIdx) : "";
        if (src) {
          if (!dependents.has(src)) dependents.set(src, []);
          dependents.get(src)!.push(lab.name);
        }
      }
    }
  }
  const toInvalidate = new Set<string>([saved]);
  const bfsQueue = [saved];
  while (bfsQueue.length > 0) {
    const cur = bfsQueue.shift()!;
    for (const dep of dependents.get(cur) ?? []) {
      if (!toInvalidate.has(dep)) {
        toInvalidate.add(dep);
        bfsQueue.push(dep);
      }
    }
  }
  return toInvalidate;
}

// the data cache without the entries of the given labs' outputs, and whether
// anything was dropped; the given cache is not changed
export function evictLabData(
  data: Record<string, number[]> | null,
  labs: Set<string>,
): { data: Record<string, number[]>; evicted: boolean } {
  const newData = { ...(data ?? {}) };
  let evicted = false;
  for (const labName of labs) {
    const prefix = `Lab/${labName}/`;
    for (const key of Object.keys(newData)) {
      if (key.startsWith(prefix)) {
        delete newData[key];
        evicted = true;
      }
    }
  }
  return { data: newData, evicted };
}

// the plotted columns (y-axes, then the x-axis) that belong to one of the
// given labs and are missing from the data cache, so need fetching again
export function evictedPlottedColumns(
  yAxisCols: string[],
  xAxisCol: string,
  labs: Set<string>,
  data: Record<string, number[]> | null,
): string[] {
  return [...yAxisCols, xAxisCol].filter((c) => {
    for (const labName of labs) {
      if (
        c.startsWith(`Lab/${labName}/`) &&
        !Object.prototype.hasOwnProperty.call(data ?? {}, c)
      )
        return true;
    }
    return false;
  });
}
