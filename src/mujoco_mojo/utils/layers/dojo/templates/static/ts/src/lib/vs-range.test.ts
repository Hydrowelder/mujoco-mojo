import { describe, expect, it } from "vitest";

import { countInRange, countWithPinned, presetRange, togglePinned, trialBounds, trialNumber } from "./vs-range";

const TRIALS = Array.from({ length: 10 }, (_, i) => `trial_${String(i).padStart(2, "0")}`);

describe("trialNumber", () => {
  it("reads the number after the last underscore", () => {
    expect(trialNumber("trial_07")).toBe(7);
    expect(trialNumber("trial_123")).toBe(123);
    expect(trialNumber("a_b_4")).toBe(4);
  });

  it("is NaN when there is no number", () => {
    expect(trialNumber("trial_x")).toBeNaN();
    expect(trialNumber("")).toBeNaN();
  });
});

describe("trialBounds", () => {
  it("is the lowest and highest trial number", () => {
    expect(trialBounds(["trial_03", "trial_10", "trial_07"])).toEqual({ min: 3, max: 10 });
    expect(trialBounds(["trial_5"])).toEqual({ min: 5, max: 5 });
  });

  it("skips ids with no number, and is null when none are left", () => {
    expect(trialBounds(["trial_x", "trial_2"])).toEqual({ min: 2, max: 2 });
    expect(trialBounds([])).toBeNull();
    expect(trialBounds(["junk"])).toBeNull();
  });
});

describe("presetRange", () => {
  const bounds = { min: 0, max: 20 };

  it("spans delta trials either side of the current one", () => {
    expect(presetRange("trial_10", 3, bounds)).toEqual([7, 13]);
  });

  it("clamps each edge to the trials that exist", () => {
    expect(presetRange("trial_00", 10, bounds)).toEqual([0, 10]);
    expect(presetRange("trial_19", 10, bounds)).toEqual([9, 20]);
    expect(presetRange("trial_10", 100, bounds)).toEqual([0, 20]);
  });

  it("does not clamp when there are no bounds to clamp to", () => {
    expect(presetRange("trial_02", 5, null)).toEqual([-3, 7]);
  });
});

describe("countInRange", () => {
  it("counts the other trials in an inclusive range", () => {
    expect(countInRange(TRIALS, [3, 6], "trial_04")).toBe(3);
    expect(countInRange(TRIALS, [3, 6], "trial_09")).toBe(4);
  });

  it("does not care which end of the range is larger", () => {
    expect(countInRange(TRIALS, [6, 3], "trial_09")).toBe(4);
  });

  it("is zero for a range of only the current trial", () => {
    expect(countInRange(TRIALS, [4, 4], "trial_04")).toBe(0);
  });
});

describe("countWithPinned", () => {
  it("adds pinned trials outside the range", () => {
    expect(countWithPinned(TRIALS, [3, 4], [8], "trial_00")).toBe(3);
  });

  it("does not count a trial twice for being in the range and pinned", () => {
    expect(countWithPinned(TRIALS, [3, 4], [4], "trial_00")).toBe(2);
  });

  it("never counts the current trial, even if it is pinned", () => {
    expect(countWithPinned(TRIALS, [3, 4], [3, 8], "trial_03")).toBe(2);
  });
});

describe("togglePinned", () => {
  it("pins a trial that is not pinned, keeping the list sorted", () => {
    expect(togglePinned([2, 9], 5)).toEqual([2, 5, 9]);
    expect(togglePinned([], 3)).toEqual([3]);
  });

  it("unpins a trial that is", () => {
    expect(togglePinned([2, 5, 9], 5)).toEqual([2, 9]);
  });

  it("does not modify its input", () => {
    const pinned = [2, 9];
    togglePinned(pinned, 5);
    expect(pinned).toEqual([2, 9]);
  });
});
