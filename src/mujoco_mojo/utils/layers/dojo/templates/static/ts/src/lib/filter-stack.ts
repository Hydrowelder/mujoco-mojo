// a signal's filter stack as edited in the series panel: the filters applied to
// it in order, each a type plus parameters. these work on the draft (`temp`)
// the editor holds until Apply, and on the schemas the server sends describing
// which filters exist and what parameters they take

import type { FilterEntry, FilterSchema, UnitGroup, YAxisConfig } from "../models";
import { formatNum } from "./format";

// the order the "add filter" menu lists its categories in; a category not
// named here is not offered
const CATEGORY_ORDER = [
  "Smoothing",
  "Arithmetic",
  "Trigonometry",
  "Calculus",
  "Vector",
  "Comparison",
  "Bounding",
  "Misc",
];

// the filter schemas grouped by category in the menu's order, leaving out
// empty groups. a schema with no category is under Misc
export function groupFilterSchemas(schemas: FilterSchema[]): { category: string; schemas: FilterSchema[] }[] {
  const groups: Record<string, FilterSchema[]> = {};
  for (const s of schemas) {
    const cat = s.category ?? "Misc";
    (groups[cat] ??= []).push(s);
  }
  return CATEGORY_ORDER.filter((c) => groups[c]?.length).map((c) => ({
    category: c,
    schemas: groups[c]!,
  }));
}

// the unit groups to offer in a unit filter's dropdown: the one group the
// signal's own unit belongs to, else the groups of its physical dimension,
// else all of them
export function getUnitOptions(
  groups: UnitGroup[] | undefined,
  fromUnit: string | null | undefined,
  colDimension?: string | null,
): UnitGroup[] {
  if (!groups) return [];
  // normalize Pint canonical strings ("m / s ** 2") to compact ("m/s^2") for matching
  const normalize = (u: string) => u.replace(/\s+/g, "").replace(/\*\*/g, "^");
  if (fromUnit) {
    const norm = normalize(fromUnit);
    const match = groups.find((g) => g.units.some((u) => u === fromUnit || u === norm));
    if (match) return [match];
  }
  // fall back to dimension-based group filtering when column dimension is known
  if (colDimension && groups.some((g) => g.dimension)) {
    const compatible = groups.filter((g) => g.dimension === colDimension);
    if (compatible.length > 0) return compatible;
  }
  return groups;
}

// the unit a signal ends up in after its enabled unit filters run, starting
// from the unit it was recorded in: each unit filter that names a target
// replaces it
export function effectiveUnit(recordedUnit: string | null, filters: FilterEntry[]): string | null {
  let unit = recordedUnit;
  for (const f of filters) {
    if (f.enabled === false || f.type !== "unit") continue;
    const to = (f as Record<string, unknown>)["toUnit"] as string | undefined;
    if (to) unit = to;
  }
  return unit;
}

// a unit's name, or a question mark when it is not set
function unitText(unit: unknown): string {
  return typeof unit === "string" ? unit : "?";
}

// the one-line summary shown on a filter's chip: up to three of its set
// parameters as `name=value`, or the unit conversion for a unit filter. empty
// for a filter with no parameters, or one the server has no schema for
export function filterSummary(entry: FilterEntry, schema: FilterSchema | undefined): string {
  if (!schema || schema.params.length === 0) return "";
  if (entry.type === "unit") return `${unitText(entry["fromUnit"])} → ${unitText(entry["toUnit"])}`;
  const parts = schema.params
    .filter((p) => (entry as Record<string, unknown>)[p.name] != null)
    .map((p) => {
      const val = (entry as Record<string, unknown>)[p.name];
      if (typeof val === "boolean") return `${p.name}=${val ? "on" : "off"}`;
      if (typeof val === "number") return `${p.name}=${formatNum(val)}`;
      return `${p.name}=${val as string}`;
    });
  return parts.slice(0, 3).join(", ");
}

// appends a new filter of `filterType` to the draft, with each parameter at
// its default. a draft holds at most one rotation filter, so a second is
// refused. a unit filter starts converting from `prefillUnit` when given
export function addFilter(
  temp: YAxisConfig,
  schema: FilterSchema | undefined,
  filterType: string,
  prefillUnit?: string | null,
): void {
  if (!schema) return;
  if (!temp.filters) temp.filters = [];
  if (filterType === "rotation" && temp.filters.some((f) => f.type === "rotation")) return;
  const entry: FilterEntry = { type: filterType, enabled: true };
  for (const p of schema.params) {
    (entry as Record<string, unknown>)[p.name] = p.default;
  }
  // prefill fromUnit with a known unit group string; prefer group_unit (pre-resolved by
  // Python to the nearest group equivalent), then unit (when a display unit system is
  // active), so the dropdown shows a valid pre-selected option rather than "- select -"
  if (filterType === "unit" && prefillUnit) {
    (entry as Record<string, unknown>)["fromUnit"] = prefillUnit;
  }
  temp.filters.push(entry);
}

export function removeFilter(temp: YAxisConfig, index: number): void {
  if (!temp.filters) return;
  temp.filters.splice(index, 1);
}

// moves the filter at `index` by `direction` places (-1 up, 1 down); a move
// off either end does nothing
export function moveFilter(temp: YAxisConfig, index: number, direction: number): void {
  if (!temp.filters) return;
  const newIdx = index + direction;
  if (newIdx < 0 || newIdx >= temp.filters.length) return;
  const [item] = temp.filters.splice(index, 1);
  if (item) temp.filters.splice(newIdx, 0, item);
}

export function setFilterParam(temp: YAxisConfig, filterIndex: number, paramName: string, value: unknown): void {
  if (!temp.filters?.[filterIndex]) return;
  (temp.filters[filterIndex] as Record<string, unknown>)[paramName] = value;
}

// inserts an independent copy of the filter just below it
export function duplicateFilter(temp: YAxisConfig, index: number): void {
  if (!temp.filters?.[index]) return;
  const copy = JSON.parse(JSON.stringify(temp.filters[index])) as FilterEntry;
  temp.filters.splice(index + 1, 0, copy);
}
