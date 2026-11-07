import { describe, expect, it } from "vitest";

import type { YAxisConfig } from "../models";
import { newYAxisConfig, reorderYAxes, usedStyles, withoutYAxis, yRangeToggles } from "./y-axes";

const axes = (...keys: string[]): Record<string, YAxisConfig> =>
  Object.fromEntries(keys.map((k) => [k, { color: `#${k}`, label: k }]));

// callers only offer a move that stays inside the list, so these test those
describe("reorderYAxes", () => {
  it("is null when there are fewer than two signals to reorder", () => {
    expect(reorderYAxes({}, 0, 1)).toBeNull();
    expect(reorderYAxes(axes("a"), 0, 1)).toBeNull();
  });

  it("moves a signal one place down or up", () => {
    expect(Object.keys(reorderYAxes(axes("a", "b", "c"), 0, 1)!)).toEqual(["b", "a", "c"]);
    expect(Object.keys(reorderYAxes(axes("a", "b", "c"), 2, -1)!)).toEqual(["a", "c", "b"]);
    expect(Object.keys(reorderYAxes(axes("a", "b", "c"), 1, 1)!)).toEqual(["a", "c", "b"]);
  });

  it("sends a signal to the very top or the very bottom", () => {
    expect(Object.keys(reorderYAxes(axes("a", "b", "c", "d"), 2, -1, true)!)).toEqual(["c", "a", "b", "d"]);
    expect(Object.keys(reorderYAxes(axes("a", "b", "c", "d"), 1, 1, true)!)).toEqual(["a", "c", "d", "b"]);
  });

  it("keeps every signal's own settings", () => {
    const input = axes("a", "b", "c");
    const out = reorderYAxes(input, 0, 1)!;
    for (const k of ["a", "b", "c"]) expect(out[k]).toBe(input[k]);
  });

  it("returns a new map and leaves the input in its order", () => {
    const input = axes("a", "b", "c");
    const out = reorderYAxes(input, 0, 1);
    expect(out).not.toBe(input);
    expect(Object.keys(input)).toEqual(["a", "b", "c"]);
  });
});

describe("usedStyles", () => {
  it("is empty with no signals", () => {
    expect(usedStyles({})).toEqual([]);
  });

  it("lists the color and dash of each signal, in order", () => {
    const yAxes: Record<string, YAxisConfig> = {
      a: { color: "#111", label: "a", dash: "dash" },
      b: { color: "#222", label: "b", dash: "dot" },
    };
    expect(usedStyles(yAxes)).toEqual([
      { color: "#111", dash: "dash" },
      { color: "#222", dash: "dot" },
    ]);
  });

  it("reads a signal with no dash as solid", () => {
    expect(usedStyles({ a: { color: "#111", label: "a" } })).toEqual([{ color: "#111", dash: "solid" }]);
  });

  it("leaves everything else about a signal out", () => {
    const out = usedStyles({ a: { color: "#111", label: "a", width: 5, opacity: 0.5 } });
    expect(Object.keys(out[0]!).sort()).toEqual(["color", "dash"]);
  });
});

describe("withoutYAxis", () => {
  it("drops the named signal and keeps the rest in order", () => {
    expect(Object.keys(withoutYAxis(axes("a", "b", "c"), "b"))).toEqual(["a", "c"]);
  });

  it("keeps each remaining signal's config", () => {
    expect(withoutYAxis(axes("a", "b"), "a")).toEqual({ b: { color: "#b", label: "b" } });
  });

  it("is a copy with the same contents when the signal is not there", () => {
    const input = axes("a", "b");
    const out = withoutYAxis(input, "zzz");
    expect(out).toEqual(input);
    expect(out).not.toBe(input);
  });

  it("leaves the input as it was", () => {
    const input = axes("a", "b");
    withoutYAxis(input, "a");
    expect(Object.keys(input)).toEqual(["a", "b"]);
  });
});

describe("newYAxisConfig", () => {
  const STYLE = { color: "#abc", dash: "dashdot" } as const;
  const WORLD: [string | null, string | null] = [null, null];

  it("is solid defaults in the style it was given", () => {
    expect(newYAxisConfig(STYLE, WORLD, false)).toEqual({
      color: "#abc",
      label: "",
      width: 3,
      opacity: 1,
      filters: [],
      dash: "dashdot",
      marker: "none",
    });
  });

  it("passes the dash through as it is, including none", () => {
    expect(newYAxisConfig({ color: "#abc", dash: undefined }, WORLD, false).dash).toBeUndefined();
    expect(newYAxisConfig({ color: "#abc", dash: "dot" }, WORLD, false).dash).toBe("dot");
  });

  it("starts with the rotation filter under a reference frame", () => {
    const out = newYAxisConfig(STYLE, ["body_quat", "body_pos"], false);
    expect(out.filters).toEqual([
      { type: "rotation", quatCol: "body_quat", originCol: "body_pos", invert: true, enabled: true },
    ]);
  });

  it("applies a frame with only one half set", () => {
    expect(newYAxisConfig(STYLE, ["body_quat", null], false).filters).toHaveLength(1);
    expect(newYAxisConfig(STYLE, [null, "body_pos"], false).filters).toHaveLength(1);
  });

  it("leaves an enum signal unfiltered, frame or not", () => {
    expect(newYAxisConfig(STYLE, ["body_quat", "body_pos"], true).filters).toEqual([]);
  });

  it("gives each signal a filter list of its own", () => {
    const a = newYAxisConfig(STYLE, WORLD, false);
    const b = newYAxisConfig(STYLE, WORLD, false);
    expect(a.filters).not.toBe(b.filters);
  });
});

describe("yRangeToggles", () => {
  const rows = ["a", "b", "c", "d", "e"].map((c) => ({ path: `p/${c}`, item: c }));
  const none = () => false;

  it("is null when the last clicked row is not in the list", () => {
    expect(yRangeToggles(rows, "p/zzz", "p/c", false, none)).toBeNull();
  });

  it("is null when the clicked row is not in the list", () => {
    expect(yRangeToggles(rows, "p/a", "p/zzz", false, none)).toBeNull();
  });

  it("is null for an empty list", () => {
    expect(yRangeToggles([], "p/a", "p/c", false, none)).toBeNull();
  });

  it("selects every unselected signal from the last click down to this one", () => {
    expect(yRangeToggles(rows, "p/b", "p/d", false, none)).toEqual(["b", "c", "d"]);
  });

  it("takes the range the same way from the other direction", () => {
    expect(yRangeToggles(rows, "p/d", "p/b", false, none)).toEqual(["b", "c", "d"]);
  });

  it("is the one signal when both clicks were on it", () => {
    expect(yRangeToggles(rows, "p/c", "p/c", false, none)).toEqual(["c"]);
    expect(yRangeToggles(rows, "p/c", "p/c", true, () => true)).toEqual(["c"]);
  });

  it("includes the first and last rows of the list", () => {
    expect(yRangeToggles(rows, "p/a", "p/e", false, none)).toEqual(["a", "b", "c", "d", "e"]);
  });

  it("skips signals that are already selected when selecting", () => {
    expect(yRangeToggles(rows, "p/a", "p/e", false, (c) => c === "b" || c === "d")).toEqual(["a", "c", "e"]);
  });

  it("deselects the selected signals when the click turned one off", () => {
    expect(yRangeToggles(rows, "p/a", "p/e", true, (c) => c === "b" || c === "d")).toEqual(["b", "d"]);
  });

  it("leaves signals outside the range alone", () => {
    expect(yRangeToggles(rows, "p/b", "p/c", false, none)).toEqual(["b", "c"]);
  });

  it("follows the order of the list, not the path or name", () => {
    const shuffled = [
      { path: "p/z", item: "z" },
      { path: "p/a", item: "a" },
      { path: "p/m", item: "m" },
    ];
    expect(yRangeToggles(shuffled, "p/z", "p/m", false, none)).toEqual(["z", "a", "m"]);
  });

  it("matches rows by path, not by signal name", () => {
    const dup = [
      { path: "x/one", item: "same" },
      { path: "y/one", item: "other" },
      { path: "z/one", item: "same" },
    ];
    expect(yRangeToggles(dup, "y/one", "z/one", false, none)).toEqual(["other", "same"]);
  });
});
