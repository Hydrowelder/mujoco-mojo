import { describe, expect, it } from "vitest";

import type { DistEntry } from "../models";
import { countBy, distinctSorted, filterDists, toggleFacet, type DistFilter } from "./dist-table";

const dist = (name: string, over: Partial<DistEntry> = {}): DistEntry =>
  ({
    name,
    category: "mass",
    dist_type: "normal",
    units: "kg",
    nominal: null,
    sampled_value: null,
    z_score: null,
    percentile: null,
    ...over,
  }) as DistEntry;

const filter = (over: Partial<DistFilter> = {}): DistFilter => ({
  name: "",
  categories: null,
  types: null,
  units: null,
  sortKey: "name",
  sortAsc: true,
  ...over,
});

const names = (list: DistEntry[]) => list.map((d) => d.name);

describe("distinctSorted and countBy", () => {
  it("lists each value once, alphabetically", () => {
    expect(distinctSorted(["kg", "m", "kg", "", "m"])).toEqual(["", "kg", "m"]);
    expect(distinctSorted([])).toEqual([]);
  });

  it("counts how often each value occurs", () => {
    expect(countBy(["kg", "m", "kg", "kg"])).toEqual({ kg: 3, m: 1 });
    expect(countBy([])).toEqual({});
  });
});

describe("toggleFacet", () => {
  const all = ["a", "b", "c"];

  it("starts from everything ticked when nothing has been chosen yet", () => {
    expect(toggleFacet(null, all, "b")).toEqual(["a", "c"]);
  });

  it("ticks a value back on, and goes back to 'all' (null) once every value is ticked", () => {
    expect(toggleFacet(["a"], all, "b")).toEqual(["a", "b"]);
    expect(toggleFacet(["a", "c"], all, "b")).toBeNull();
  });

  it("unticks a value from an explicit list", () => {
    expect(toggleFacet(["a", "b"], all, "a")).toEqual(["b"]);
  });

  it("can untick down to nothing without turning back into 'all'", () => {
    expect(toggleFacet(["a"], all, "a")).toEqual([]);
    expect(toggleFacet(null, ["only"], "only")).toEqual([]);
  });

  it("can tick from nothing", () => {
    expect(toggleFacet([], all, "a")).toEqual(["a"]);
    expect(toggleFacet([], ["only"], "only")).toBeNull();
  });

  it("does not modify the list it is given", () => {
    const selected = ["a"];
    toggleFacet(selected, all, "b");
    expect(selected).toEqual(["a"]);
  });
});

describe("filterDists", () => {
  const dists = [
    dist("Mass", { category: "mass", dist_type: "normal", units: "kg" }),
    dist("length", { category: "geometry", dist_type: "uniform", units: "m" }),
    dist("Width", { category: "geometry", dist_type: "normal", units: "m" }),
    dist("color", { category: "visual", dist_type: "choice", units: "" }),
  ];

  it("keeps everything when nothing is filtered", () => {
    expect(filterDists(dists, filter())).toHaveLength(4);
  });

  it("searches names by case-insensitive substring, ignoring surrounding spaces", () => {
    expect(names(filterDists(dists, filter({ name: "  WI " })))).toEqual(["Width"]);
    expect(names(filterDists(dists, filter({ name: "o" })))).toEqual(["color"]);
  });

  it("keeps only the ticked categories, types and units", () => {
    expect(names(filterDists(dists, filter({ categories: ["geometry"] })))).toEqual(["length", "Width"]);
    expect(names(filterDists(dists, filter({ types: ["normal"] })))).toEqual(["Mass", "Width"]);
    expect(names(filterDists(dists, filter({ units: ["kg", ""] })))).toEqual(["color", "Mass"]);
  });

  it("combines the filters", () => {
    expect(names(filterDists(dists, filter({ categories: ["geometry"], types: ["normal"], name: "w" })))).toEqual([
      "Width",
    ]);
  });

  it("shows nothing for an empty selection, which is not the same as null", () => {
    expect(filterDists(dists, filter({ categories: [] }))).toEqual([]);
  });

  it("does not modify the list", () => {
    const before = names(dists);
    filterDists(dists, filter({ sortAsc: false }));
    expect(names(dists)).toEqual(before);
  });

  describe("sorting", () => {
    it("sorts text columns alphabetically, case-insensitively, in either direction", () => {
      expect(names(filterDists(dists, filter({ sortKey: "name" })))).toEqual(["color", "length", "Mass", "Width"]);
      expect(names(filterDists(dists, filter({ sortKey: "name", sortAsc: false })))).toEqual([
        "Width",
        "Mass",
        "length",
        "color",
      ]);
      expect(filterDists(dists, filter({ sortKey: "category" })).map((d) => d.category)).toEqual([
        "geometry",
        "geometry",
        "mass",
        "visual",
      ]);
      expect(filterDists(dists, filter({ sortKey: "dist_type" })).map((d) => d.dist_type)).toEqual([
        "choice",
        "normal",
        "normal",
        "uniform",
      ]);
    });

    it("sorts a number column numerically, putting a missing value lowest", () => {
      const nums = [dist("b", { nominal: 10 }), dist("a", { nominal: 2 }), dist("none"), dist("c", { nominal: -1 })];
      expect(names(filterDists(nums, filter({ sortKey: "nominal" })))).toEqual(["none", "c", "a", "b"]);
      expect(names(filterDists(nums, filter({ sortKey: "nominal", sortAsc: false })))).toEqual(["b", "a", "c", "none"]);
      const sampled = [dist("x", { sampled_value: 5 }), dist("y", { sampled_value: null }), dist("z", { sampled_value: 1 })];
      expect(names(filterDists(sampled, filter({ sortKey: "sampled_value" })))).toEqual(["y", "z", "x"]);
    });

    it("sorts the stat column by z-score, falling back to the percentile as a fraction", () => {
      const stats = [
        dist("high-z", { z_score: 2.5 }),
        dist("pct-95", { percentile: 95 }), // 0.95
        dist("none"),
        dist("low-z", { z_score: -1.2 }),
        dist("pct-10", { percentile: 10 }), // 0.1
        dist("z-wins", { z_score: 0.5, percentile: 99 }), // the z-score, 0.5
      ];
      expect(names(filterDists(stats, filter({ sortKey: "stat" })))).toEqual([
        "none",
        "low-z",
        "pct-10",
        "z-wins",
        "pct-95",
        "high-z",
      ]);
    });
  });
});
