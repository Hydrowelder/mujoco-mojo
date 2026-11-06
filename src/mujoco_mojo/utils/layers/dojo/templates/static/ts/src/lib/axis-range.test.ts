import { describe, expect, it, vi } from "vitest";

import { applyRangeBound, rangeBoundText, resolveAxisRange, type AxisRange } from "./axis-range";

describe("rangeBoundText", () => {
  it("shows the number for a side that is set", () => {
    expect(rangeBoundText([1.5, 20], "min")).toBe("1.5");
    expect(rangeBoundText([1.5, 20], "max")).toBe("20");
    expect(rangeBoundText([0, null], "min")).toBe("0");
    expect(rangeBoundText([-3, null], "min")).toBe("-3");
  });

  it("is blank for a side that autoscales, or no range at all", () => {
    expect(rangeBoundText([null, 5], "min")).toBe("");
    expect(rangeBoundText([5, null], "max")).toBe("");
    expect(rangeBoundText(null, "min")).toBe("");
    expect(rangeBoundText(undefined, "max")).toBe("");
  });
});

describe("applyRangeBound", () => {
  it("sets one side and leaves the other as it was", () => {
    expect(applyRangeBound([1, 2], "min", "5")).toEqual({ range: [5, 2] });
    expect(applyRangeBound([1, 2], "max", "5")).toEqual({ range: [1, 5] });
  });

  it("starts a range from nothing", () => {
    expect(applyRangeBound(null, "min", "3")).toEqual({ range: [3, null] });
    expect(applyRangeBound(undefined, "max", "3")).toEqual({ range: [null, 3] });
  });

  it("evaluates an expression", () => {
    expect(applyRangeBound(null, "max", "2 * 10")).toEqual({ range: [null, 20] });
    expect(applyRangeBound(null, "min", " -1.5 ")).toEqual({ range: [-1.5, null] });
  });

  it("accepts zero as a real bound", () => {
    expect(applyRangeBound(null, "min", "0")).toEqual({ range: [0, null] });
  });

  it("clears a side when the field is emptied", () => {
    expect(applyRangeBound([1, 2], "min", "")).toEqual({ range: [null, 2] });
    expect(applyRangeBound([1, 2], "max", "   ")).toEqual({ range: [1, null] });
  });

  it("collapses to no range when both sides end up empty", () => {
    expect(applyRangeBound([1, null], "min", "")).toEqual({ range: null });
    expect(applyRangeBound(null, "max", "")).toEqual({ range: null });
  });

  it("rejects text that is not a number, so the caller changes nothing", () => {
    expect(applyRangeBound([1, 2], "min", "abc")).toBeNull();
    expect(applyRangeBound([1, 2], "max", "1/0")).toBeNull();
  });

  it("does not modify the range it is given", () => {
    const current: AxisRange = [1, 2];
    applyRangeBound(current, "min", "9");
    expect(current).toEqual([1, 2]);
  });
});

describe("resolveAxisRange", () => {
  const auto = () => [10, 90] as [number, number];

  it("is null for a fully automatic axis, without asking for the data range", () => {
    const spy = vi.fn(auto);
    expect(resolveAxisRange(null, spy)).toBeNull();
    expect(resolveAxisRange([null, null], spy)).toBeNull();
    expect(spy).not.toHaveBeenCalled();
  });

  it("is the range as set when both sides are, without asking for the data range", () => {
    const spy = vi.fn(auto);
    expect(resolveAxisRange([1, 2], spy)).toEqual([1, 2]);
    expect(spy).not.toHaveBeenCalled();
  });

  it("fills in whichever side is unset from the data range", () => {
    expect(resolveAxisRange([5, null], auto)).toEqual([5, 90]);
    expect(resolveAxisRange([null, 50], auto)).toEqual([10, 50]);
  });

  it("treats zero as set, not as missing", () => {
    expect(resolveAxisRange([0, null], auto)).toEqual([0, 90]);
  });
});
