// the trial viewer's distributions table: which signals are listed (a name
// search plus a checkbox filter on each of category, type and units) and in what
// order. a facet's selection is a list of the values ticked, or null for "all"

import type { DistEntry } from "../models";

export type DistSortKey = "name" | "category" | "dist_type" | "nominal" | "sampled_value" | "stat";

// the distinct values, alphabetical: the options a facet's dropdown offers
export function distinctSorted(values: string[]): string[] {
  return Array.from(new Set(values)).sort();
}

// signal counts per dropdown option, shown right-justified next to each
// checkbox so users can see how many rows a filter choice covers
export function countBy(values: string[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const v of values) counts[v] = (counts[v] ?? 0) + 1;
  return counts;
}

// null = all selected; toggling derives the explicit set from the
// current selection (defaulting to "all" the first time) and only
// collapses back to null once it matches the full set again - it never
// re-expands to "all" just because the set happens to become empty
export function toggleFacet(selected: string[] | null, all: string[], value: string): string[] | null {
  const current = selected ?? all;
  const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
  return next.length === all.length ? null : next;
}

export interface DistFilter {
  // case-insensitive substring of the signal's name; blank matches everything
  name: string;
  categories: string[] | null;
  types: string[] | null;
  units: string[] | null;
  sortKey: DistSortKey;
  sortAsc: boolean;
}

// the rows that pass every filter, sorted. a missing nominal or sampled value
// sorts as the lowest; "stat" is the z-score, or the percentile as a fraction
// when there is no z-score
export function filterDists(dists: DistEntry[], f: DistFilter): DistEntry[] {
  const name = f.name.trim().toLowerCase();
  const filtered = dists.filter((d) => {
    if (name && !d.name.toLowerCase().includes(name)) return false;
    if (f.categories !== null && !f.categories.includes(d.category)) return false;
    if (f.types !== null && !f.types.includes(d.dist_type)) return false;
    if (f.units !== null && !f.units.includes(d.units)) return false;
    return true;
  });
  const dir = f.sortAsc ? 1 : -1;
  return filtered.slice().sort((a, b) => {
    switch (f.sortKey) {
      case "name":
        return dir * a.name.localeCompare(b.name);
      case "category":
        return dir * a.category.localeCompare(b.category);
      case "dist_type":
        return dir * a.dist_type.localeCompare(b.dist_type);
      case "nominal": {
        const av = a.nominal ?? -Infinity;
        const bv = b.nominal ?? -Infinity;
        return dir * (av - bv);
      }
      case "sampled_value": {
        const av = a.sampled_value ?? -Infinity;
        const bv = b.sampled_value ?? -Infinity;
        return dir * (av - bv);
      }
      case "stat": {
        const av = a.z_score ?? (a.percentile != null ? a.percentile / 100 : -Infinity);
        const bv = b.z_score ?? (b.percentile != null ? b.percentile / 100 : -Infinity);
        return dir * (av - bv);
      }
    }
  });
}
