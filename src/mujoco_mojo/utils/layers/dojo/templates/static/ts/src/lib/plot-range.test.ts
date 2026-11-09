import { describe, expect, it } from "vitest";

import { paddedRange, selectVsDatasets } from "./plot-range";

describe("paddedRange", () => {
  it("widens the data extent by a sixteenth of the span either side", () => {
    expect(paddedRange([{ a: [0, 16] }], ["a"])).toEqual([-1, 17]);
    expect(paddedRange([{ a: [10, 26, 18] }], ["a"])).toEqual([9, 27]);
  });

  it("leaves the extent alone when padding is off", () => {
    expect(paddedRange([{ a: [0, 16] }], ["a"], false)).toEqual([0, 16]);
  });

  it("spans every named series in every dataset, and ignores the rest", () => {
    const datasets: Record<string, number[]>[] = [
      { a: [0, 4], b: [100, 200], other: [-999] },
      { a: [-8, 2] },
    ];
    expect(paddedRange(datasets, ["a"], false)).toEqual([-8, 4]);
    expect(paddedRange(datasets, ["a", "b"], false)).toEqual([-8, 200]);
  });

  it("skips a series a dataset does not have", () => {
    expect(paddedRange([{ a: [1, 3] }, {}], ["a", "missing"], false)).toEqual([1, 3]);
  });

  it("gives 0 to 1 when there is no data", () => {
    expect(paddedRange([], ["a"])).toEqual([0, 1]);
    expect(paddedRange([{ a: [] }], ["a"])).toEqual([0, 1]);
    expect(paddedRange([{ a: [1, 2] }], [])).toEqual([0, 1]);
  });

  it("gives one unit either side of a flat line, padding or not", () => {
    expect(paddedRange([{ a: [5, 5, 5] }], ["a"])).toEqual([4, 6]);
    expect(paddedRange([{ a: [5] }], ["a"], false)).toEqual([4, 6]);
  });

  it("reads a gap in a series as zero", () => {
    const withGap = [{ a: [5, null, 7] as unknown as number[] }];
    expect(paddedRange(withGap, ["a"], false)).toEqual([0, 7]);
  });

  it("ignores NaN", () => {
    expect(paddedRange([{ a: [1, Number.NaN, 3] }], ["a"], false)).toEqual([1, 3]);
  });
});

describe("selectVsDatasets", () => {
  const sets = {
    trial_00: { a: [0] },
    trial_05: { a: [5] },
    trial_09: { a: [9] },
    stray: { a: [-1] },
  };

  it("picks the trials whose number is inside the range, inclusive", () => {
    expect(selectVsDatasets(sets, [5, 9], [])).toEqual([sets.trial_05, sets.trial_09]);
    expect(selectVsDatasets(sets, [0, 0], [])).toEqual([sets.trial_00]);
  });

  it("adds pinned trials outside the range", () => {
    expect(selectVsDatasets(sets, [4, 6], [9])).toEqual([sets.trial_05, sets.trial_09]);
    expect(selectVsDatasets(sets, [20, 30], [0, 9])).toEqual([sets.trial_00, sets.trial_09]);
  });

  it("never picks an id with no trial number", () => {
    expect(selectVsDatasets(sets, [-100, 100], [])).not.toContain(sets.stray);
  });

  it("returns nothing when nothing matches", () => {
    expect(selectVsDatasets(sets, [20, 30], [])).toEqual([]);
    expect(selectVsDatasets({}, [0, 100], [1])).toEqual([]);
  });
});
