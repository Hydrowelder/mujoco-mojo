import { describe, expect, it } from "vitest";

import type { FilterEntry, FilterSchema, UnitGroup, YAxisConfig } from "../models";
import {
  addFilter,
  duplicateFilter,
  effectiveUnit,
  filterSummary,
  getUnitOptions,
  groupFilterSchemas,
  moveFilter,
  removeFilter,
  setFilterParam,
} from "./filter-stack";

const schema = (type: string, over: Partial<FilterSchema> = {}): FilterSchema => ({
  type,
  label: type,
  description: "",
  params: [],
  ...over,
});

const LOW_PASS = schema("low_pass", {
  category: "Smoothing",
  params: [
    { name: "cutoff", type: "float", default: 5 },
    { name: "order", type: "int", default: 2 },
    { name: "zero", type: "bool", default: true },
    { name: "mode", type: "string", default: "butter" },
    { name: "extra", type: "float", default: 1.5 },
  ],
});
const UNIT = schema("unit", {
  category: "Arithmetic",
  params: [
    { name: "fromUnit", type: "string", default: null },
    { name: "toUnit", type: "string", default: null },
  ],
});
const ROTATION = schema("rotation", { category: "Vector", params: [{ name: "quatCol", type: "quat_col", default: null }] });

const draft = (filters?: FilterEntry[]): YAxisConfig => (filters ? { color: "#111", filters } : { color: "#111" });
const types = (temp: YAxisConfig) => temp.filters?.map((f) => f.type);

describe("groupFilterSchemas", () => {
  it("groups by category in the menu's order and leaves out empty groups", () => {
    const out = groupFilterSchemas([UNIT, schema("median", { category: "Smoothing" }), LOW_PASS, ROTATION]);
    expect(out.map((g) => g.category)).toEqual(["Smoothing", "Arithmetic", "Vector"]);
    expect(out[0]!.schemas.map((s) => s.type)).toEqual(["median", "low_pass"]);
  });

  it("files a schema with no category under Misc", () => {
    expect(groupFilterSchemas([schema("abs")])).toEqual([{ category: "Misc", schemas: [schema("abs")] }]);
  });

  it("drops a category the menu has no slot for", () => {
    expect(groupFilterSchemas([schema("odd", { category: "Made Up" })])).toEqual([]);
  });

  it("is empty for no schemas", () => {
    expect(groupFilterSchemas([])).toEqual([]);
  });
});

describe("getUnitOptions", () => {
  const groups: UnitGroup[] = [
    { label: "Angle", units: ["rad", "deg"], dimension: "angle" },
    { label: "Length", units: ["m", "mm", "m/s^2"], dimension: "length" },
    { label: "Other", units: ["x"] },
  ];

  it("is empty when there are no groups", () => {
    expect(getUnitOptions(undefined, "rad")).toEqual([]);
  });

  it("offers only the group the signal's own unit is in", () => {
    expect(getUnitOptions(groups, "rad")).toEqual([groups[0]]);
    expect(getUnitOptions(groups, "mm")).toEqual([groups[1]]);
  });

  it("recognizes a unit written the way Pint prints it", () => {
    expect(getUnitOptions(groups, "m / s ** 2")).toEqual([groups[1]]);
  });

  it("falls back to the groups of the signal's dimension when its unit is not listed", () => {
    expect(getUnitOptions(groups, "furlong", "length")).toEqual([groups[1]]);
    expect(getUnitOptions(groups, null, "angle")).toEqual([groups[0]]);
  });

  it("offers every group when nothing narrows it down", () => {
    expect(getUnitOptions(groups, null)).toEqual(groups);
    expect(getUnitOptions(groups, "furlong", "no-such-dimension")).toEqual(groups);
    expect(getUnitOptions([groups[2]!], "furlong", "length")).toEqual([groups[2]]);
  });
});

describe("effectiveUnit", () => {
  const unit = (toUnit: string, enabled?: boolean): FilterEntry => ({ type: "unit", toUnit, enabled });

  it("is the recorded unit when no unit filter changes it", () => {
    expect(effectiveUnit("rad", [])).toBe("rad");
    expect(effectiveUnit("rad", [{ type: "low_pass" }])).toBe("rad");
    expect(effectiveUnit(null, [])).toBeNull();
  });

  it("follows each enabled unit filter in turn", () => {
    expect(effectiveUnit("rad", [unit("deg")])).toBe("deg");
    expect(effectiveUnit("rad", [unit("deg"), unit("rev")])).toBe("rev");
  });

  it("skips a disabled unit filter and one with no target", () => {
    expect(effectiveUnit("rad", [unit("deg", false)])).toBe("rad");
    expect(effectiveUnit("rad", [unit("")])).toBe("rad");
  });

  it("can start from nothing", () => {
    expect(effectiveUnit(null, [unit("deg")])).toBe("deg");
  });
});

describe("filterSummary", () => {
  it("is empty for a filter with no schema or no parameters", () => {
    expect(filterSummary({ type: "low_pass" }, undefined)).toBe("");
    expect(filterSummary({ type: "abs" }, schema("abs"))).toBe("");
  });

  it("lists the parameters that are set, as name=value", () => {
    expect(filterSummary({ type: "low_pass", cutoff: 5, mode: "butter" }, LOW_PASS)).toBe("cutoff=5, mode=butter");
  });

  it("writes booleans as on and off and numbers to four significant figures", () => {
    expect(filterSummary({ type: "low_pass", zero: true }, LOW_PASS)).toBe("zero=on");
    expect(filterSummary({ type: "low_pass", zero: false }, LOW_PASS)).toBe("zero=off");
    expect(filterSummary({ type: "low_pass", extra: 1.23456789 }, LOW_PASS)).toBe("extra=1.235");
  });

  it("skips parameters that are null or missing, and shows zero", () => {
    expect(filterSummary({ type: "low_pass", cutoff: null, order: 0 }, LOW_PASS)).toBe("order=0");
  });

  it("shows at most three parameters", () => {
    const full: FilterEntry = { type: "low_pass", cutoff: 1, order: 2, zero: true, mode: "m", extra: 9 };
    expect(filterSummary(full, LOW_PASS)).toBe("cutoff=1, order=2, zero=on");
  });

  describe("for a unit filter", () => {
    it("shows the conversion", () => {
      expect(filterSummary({ type: "unit", fromUnit: "rad", toUnit: "deg" }, UNIT)).toBe("rad → deg");
    });

    it("shows a question mark for a side that is not there", () => {
      expect(filterSummary({ type: "unit", fromUnit: "rad" }, UNIT)).toBe("rad → ?");
      expect(filterSummary({ type: "unit", toUnit: "deg" }, UNIT)).toBe("? → deg");
      expect(filterSummary({ type: "unit" }, UNIT)).toBe("? → ?");
    });

    it("shows a question mark for a side that is null", () => {
      expect(filterSummary({ type: "unit", fromUnit: null, toUnit: "deg" }, UNIT)).toBe("? → deg");
    });

    it("does not read the snake_case names, which no entry carries", () => {
      expect(filterSummary({ type: "unit", from_unit: "rad", to_unit: "deg" }, UNIT)).toBe("? → ?");
    });
  });
});

describe("addFilter", () => {
  it("appends a filter with every parameter at its default", () => {
    const temp = draft([]);
    addFilter(temp, LOW_PASS, "low_pass");
    expect(temp.filters).toEqual([
      { type: "low_pass", enabled: true, cutoff: 5, order: 2, zero: true, mode: "butter", extra: 1.5 },
    ]);
  });

  it("creates the stack when the draft has none", () => {
    const temp = draft();
    addFilter(temp, LOW_PASS, "low_pass");
    expect(types(temp)).toEqual(["low_pass"]);
  });

  it("adds to the end of the stack", () => {
    const temp = draft([{ type: "abs" }]);
    addFilter(temp, LOW_PASS, "low_pass");
    expect(types(temp)).toEqual(["abs", "low_pass"]);
  });

  it("does nothing for a type the server has no schema for", () => {
    const temp = draft([]);
    addFilter(temp, undefined, "nope");
    expect(temp.filters).toEqual([]);
    expect(draft().filters).toBeUndefined();
  });

  it("allows only one rotation filter", () => {
    const temp = draft([]);
    addFilter(temp, ROTATION, "rotation");
    addFilter(temp, ROTATION, "rotation");
    expect(types(temp)).toEqual(["rotation"]);
  });

  it("allows as many of any other kind as asked for", () => {
    const temp = draft([]);
    addFilter(temp, LOW_PASS, "low_pass");
    addFilter(temp, LOW_PASS, "low_pass");
    expect(types(temp)).toEqual(["low_pass", "low_pass"]);
  });

  it("starts a unit filter converting from the unit it is given", () => {
    const temp = draft([]);
    addFilter(temp, UNIT, "unit", "deg");
    expect(temp.filters![0]).toMatchObject({ type: "unit", fromUnit: "deg", toUnit: null });
  });

  it("leaves a unit filter's source empty when there is no unit to start from", () => {
    const temp = draft([]);
    addFilter(temp, UNIT, "unit");
    addFilter(temp, UNIT, "unit", null);
    expect(temp.filters!.map((f) => f["fromUnit"])).toEqual([null, null]);
  });

  it("ignores a starting unit for any other kind of filter", () => {
    const temp = draft([]);
    addFilter(temp, LOW_PASS, "low_pass", "deg");
    expect(temp.filters![0]).not.toHaveProperty("fromUnit");
  });
});

describe("editing the stack", () => {
  const stack = () => draft([{ type: "a" }, { type: "b" }, { type: "c" }]);

  it("removes a filter by position", () => {
    const temp = stack();
    removeFilter(temp, 1);
    expect(types(temp)).toEqual(["a", "c"]);
  });

  it("does nothing to a draft with no stack", () => {
    for (const edit of [
      (t: YAxisConfig) => removeFilter(t, 0),
      (t: YAxisConfig) => moveFilter(t, 0, 1),
      (t: YAxisConfig) => setFilterParam(t, 0, "x", 1),
      (t: YAxisConfig) => duplicateFilter(t, 0),
    ]) {
      const temp = draft();
      expect(() => edit(temp)).not.toThrow();
      expect(temp.filters).toBeUndefined();
    }
  });

  it("moves a filter up or down", () => {
    const temp = stack();
    moveFilter(temp, 2, -1);
    expect(types(temp)).toEqual(["a", "c", "b"]);
    moveFilter(temp, 0, 1);
    expect(types(temp)).toEqual(["c", "a", "b"]);
  });

  it("does not move a filter off either end", () => {
    const temp = stack();
    moveFilter(temp, 0, -1);
    moveFilter(temp, 2, 1);
    expect(types(temp)).toEqual(["a", "b", "c"]);
  });

  it("refuses a jump that would land past either end, rather than going as far as it can", () => {
    const temp = stack();
    moveFilter(temp, 1, 2);
    moveFilter(temp, 1, -2);
    expect(types(temp)).toEqual(["a", "b", "c"]);
  });

  it("sets one parameter of one filter", () => {
    const temp = stack();
    setFilterParam(temp, 1, "cutoff", 7);
    expect(temp.filters![1]).toEqual({ type: "b", cutoff: 7 });
    expect(temp.filters![0]).toEqual({ type: "a" });
  });

  it("ignores a parameter set on a position with no filter", () => {
    const temp = stack();
    setFilterParam(temp, 9, "cutoff", 7);
    expect(temp.filters).toEqual([{ type: "a" }, { type: "b" }, { type: "c" }]);
  });

  it("duplicates a filter just below it, as an independent copy", () => {
    const temp = draft([{ type: "a", nested: { k: 1 } }, { type: "b" }]);
    duplicateFilter(temp, 0);
    expect(types(temp)).toEqual(["a", "a", "b"]);
    (temp.filters![1]!["nested"] as { k: number }).k = 2;
    expect((temp.filters![0]!["nested"] as { k: number }).k).toBe(1);
  });

  it("ignores duplicating a position with no filter", () => {
    const temp = stack();
    duplicateFilter(temp, 7);
    expect(types(temp)).toEqual(["a", "b", "c"]);
  });
});
