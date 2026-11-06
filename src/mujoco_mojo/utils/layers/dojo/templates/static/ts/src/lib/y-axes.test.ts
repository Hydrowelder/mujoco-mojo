import { describe, expect, it } from "vitest";

import type { YAxisConfig } from "../models";
import { reorderYAxes } from "./y-axes";

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
