import { describe, expect, it } from "vitest";

import type { PlotConfig } from "./plot-config.generated";
import { DEFAULT_CONFIG } from "./plot-defaults";
import {
  chunked,
  comparingNotice,
  missingColumns,
  orderedRange,
  parseStoredVs,
  vsActiveColumns,
  vsChipClass,
  vsNeedsFetch,
  vsTargetIds,
} from "./vs-sync";

const cfg = (
  yCols: string[],
  over: Partial<PlotConfig> = {},
): PlotConfig => ({
  ...(JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as PlotConfig),
  xAxis: { col: "time", filters: [] },
  yAxes: Object.fromEntries(yCols.map((c) => [c, { color: "#ff0000" }])),
  ...over,
});

describe("orderedRange", () => {
  it("keeps a range that is in order", () => {
    expect(orderedRange([2, 9])).toEqual([2, 9]);
    expect(orderedRange([4, 4])).toEqual([4, 4]);
  });

  it("puts a backwards range in order", () => {
    expect(orderedRange([9, 2])).toEqual([2, 9]);
  });
});

describe("vsTargetIds", () => {
  const trials = ["run_1", "run_2", "run_3", "run_4", "run_5", "run_20"];
  const none = () => false;

  it("is the trials numbered inside the range, both ends included", () => {
    expect(vsTargetIds(trials, 2, 4, [], none)).toEqual(["run_2", "run_3", "run_4"]);
  });

  it("adds pinned trials from outside the range", () => {
    expect(vsTargetIds(trials, 2, 3, [20, 1], none)).toEqual(["run_1", "run_2", "run_3", "run_20"]);
  });

  it("keeps the order of the trial list", () => {
    expect(vsTargetIds(["run_9", "run_1", "run_5"], 0, 10, [], none)).toEqual(["run_9", "run_1", "run_5"]);
  });

  it("leaves out whatever the caller excludes, handing it each id and its number", () => {
    const seen: Array<[string, number]> = [];
    const out = vsTargetIds(trials, 1, 3, [], (id, n) => {
      seen.push([id, n]);
      return n === 2;
    });
    expect(out).toEqual(["run_1", "run_3"]);
    expect(seen).toContainEqual(["run_2", 2]);
  });

  it("can exclude a pinned trial too", () => {
    expect(vsTargetIds(trials, 99, 99, [3], (id) => id === "run_3")).toEqual([]);
  });

  it("leaves out an id with no number", () => {
    expect(vsTargetIds(["weird", "run_x", "run_2"], 0, 10, [], none)).toEqual(["run_2"]);
  });

  it("is empty for a range that holds nothing", () => {
    expect(vsTargetIds(trials, 30, 40, [], none)).toEqual([]);
    expect(vsTargetIds([], 0, 10, [], none)).toEqual([]);
  });
});

describe("vsActiveColumns", () => {
  it("is the x column and each signal when no frame is set", () => {
    expect(vsActiveColumns(cfg(["a", "body:x"]))).toEqual(["time", "a", "body:x"]);
  });

  it("adds the x, y and z of each signal's family under a frame", () => {
    expect(vsActiveColumns(cfg(["body:pos:x", "a"], { refFrame: ["q", null] }))).toEqual([
      "time",
      "body:pos:x",
      "a",
      "body:pos:y",
      "body:pos:z",
      "q:w",
      "q:x",
      "q:y",
      "q:z",
    ]);
  });

  it("splits a family at the last colon, and gives a signal with no colon none", () => {
    const cols = vsActiveColumns(cfg(["a", "b:c:x"], { refFrame: [null, "o"] }));
    expect(cols).toContain("b:c:y");
    expect(cols).not.toContain("a:y");
    expect(cols).not.toContain("b:y");
  });

  it("adds the frame's quaternion as w, x, y and z", () => {
    expect(vsActiveColumns(cfg([], { refFrame: ["q", null] }))).toEqual(["time", "q:w", "q:x", "q:y", "q:z"]);
  });

  it("adds the frame's origin as x, y and z", () => {
    expect(vsActiveColumns(cfg([], { refFrame: [null, "o"] }))).toEqual(["time", "o:x", "o:y", "o:z"]);
  });

  it("adds both halves of a full frame", () => {
    expect(vsActiveColumns(cfg([], { refFrame: ["q", "o"] }))).toEqual(["time", "q:w", "q:x", "q:y", "q:z", "o:x", "o:y", "o:z"]);
  });

  it("lists each column once", () => {
    const cols = vsActiveColumns(cfg(["b:x", "b:y"], { refFrame: ["b", null] }));
    expect(cols.filter((c) => c === "b:x")).toHaveLength(1);
    expect(new Set(cols).size).toBe(cols.length);
  });

  it("adds nothing for the world frame", () => {
    expect(vsActiveColumns(cfg(["b:x"], { refFrame: [null, null] }))).toEqual(["time", "b:x"]);
  });
});

describe("vsNeedsFetch", () => {
  const have = { time: [1], a: [1] };

  it("is true for a trial with no data yet", () => {
    expect(vsNeedsFetch(undefined, ["time"], false)).toBe(true);
  });

  it("is true when a column is missing", () => {
    expect(vsNeedsFetch(have, ["time", "a", "b"], false)).toBe(true);
  });

  it("is false when it has every column", () => {
    expect(vsNeedsFetch(have, ["time", "a"], false)).toBe(false);
    expect(vsNeedsFetch(have, [], false)).toBe(false);
  });

  it("is true under a frame even with every column, since the data depends on the frame", () => {
    expect(vsNeedsFetch(have, ["time", "a"], true)).toBe(true);
  });

  it("counts a column with no values as present", () => {
    expect(vsNeedsFetch({ time: [] }, ["time"], false)).toBe(false);
  });
});

describe("missingColumns", () => {
  it("is the columns with no data", () => {
    expect(missingColumns(["a", "b", "c"], { a: [1], c: [] })).toEqual(["b"]);
  });

  it("is every column without any data", () => {
    expect(missingColumns(["a", "b"], null)).toEqual(["a", "b"]);
  });

  it("is empty when nothing is missing", () => {
    expect(missingColumns(["a"], { a: [1] })).toEqual([]);
    expect(missingColumns([], { a: [1] })).toEqual([]);
  });
});

describe("comparingNotice", () => {
  it("says trial for one and trials for the rest", () => {
    expect(comparingNotice(1)).toBe("Comparing 1 trial");
    expect(comparingNotice(2)).toBe("Comparing 2 trials");
    expect(comparingNotice(12)).toBe("Comparing 12 trials");
  });
});

describe("chunked", () => {
  it("splits a list into chunks of at most the size", () => {
    expect(chunked([1, 2, 3, 4, 5], 2)).toEqual([[1, 2], [3, 4], [5]]);
    expect(chunked([1, 2, 3, 4], 2)).toEqual([[1, 2], [3, 4]]);
  });

  it("is one chunk for a short list, and none for an empty one", () => {
    expect(chunked([1, 2], 10)).toEqual([[1, 2]]);
    expect(chunked([], 10)).toEqual([]);
  });

  it("splits twenty-five columns into three loads of ten", () => {
    const cols = Array.from({ length: 25 }, (_, i) => `c${i}`);
    expect(chunked(cols, 10).map((c) => c.length)).toEqual([10, 10, 5]);
    expect(chunked(cols, 10).flat()).toEqual(cols);
  });

  it("does not change the list it was given", () => {
    const list = [1, 2, 3];
    chunked(list, 2);
    expect(list).toEqual([1, 2, 3]);
  });
});

describe("parseStoredVs", () => {
  const current = { range: [3, 8] as [number, number], pinned: [4] };

  it("is the saved range and pinned trials", () => {
    expect(parseStoredVs('{"range":[2,5],"pinned":[1,9]}', current)).toEqual({ range: [2, 5], pinned: [1, 9] });
  });

  it("keeps the current value of whatever was not saved", () => {
    expect(parseStoredVs('{"range":[2,5]}', current)).toEqual({ range: [2, 5], pinned: [4] });
    expect(parseStoredVs('{"pinned":[1]}', current)).toEqual({ range: [3, 8], pinned: [1] });
    expect(parseStoredVs("{}", current)).toEqual(current);
  });

  it("keeps the current values when nothing, or nothing readable, was saved", () => {
    for (const raw of [null, "", "garbage", "null", '"str"', "{broken"]) {
      expect(parseStoredVs(raw, current)).toEqual(current);
    }
  });

  it("ignores a saved null", () => {
    expect(parseStoredVs('{"range":null,"pinned":null}', current)).toEqual(current);
  });

  it("does not reorder a saved range", () => {
    expect(parseStoredVs('{"range":[9,1]}', current).range).toEqual([9, 1]);
  });
});

describe("vsChipClass", () => {
  const chip = (id: string, over: { current?: string; pinned?: number[]; error?: number[]; failure?: number[] } = {}) =>
    vsChipClass(id, over.current ?? "run_7", over.pinned ?? [], over.error ?? [], over.failure ?? []);

  it("is a plain accent outline for the trial being viewed, ring or not", () => {
    const own = "border-accent-500 text-accent-500 dark:text-accent-400 cursor-default";
    expect(chip("run_7")).toBe(own);
    expect(chip("run_7", { pinned: [7], error: [7] })).toBe(own);
  });

  it("is success colored for a trial that passed", () => {
    expect(chip("run_1")).toContain("bg-success-50");
    expect(chip("run_1")).toContain("border-success-400");
    expect(chip("run_1")).not.toContain("ring-2");
  });

  it("is danger colored for a trial that failed", () => {
    expect(chip("run_4", { failure: [4] })).toContain("bg-danger-50");
    expect(chip("run_4", { failure: [4] })).toContain("text-danger-600");
  });

  it("is warning colored for a trial that errored", () => {
    expect(chip("run_3", { error: [3] })).toContain("bg-warning-50");
    expect(chip("run_3", { error: [3] })).toContain("text-warning-600");
  });

  it("shows an error ahead of a failure for the same trial", () => {
    expect(chip("run_9", { error: [9], failure: [9] })).toContain("bg-warning-50");
  });

  it("adds a ring to a pinned trial, keeping its outcome color", () => {
    expect(chip("run_1", { pinned: [1] })).toMatch(/ ring-2 ring-accent-500$/);
    expect(chip("run_1", { pinned: [1] })).toContain("bg-success-50");
    expect(chip("run_4", { pinned: [4], failure: [4] })).toMatch(/bg-danger-50.* ring-2 ring-accent-500$/);
    expect(chip("run_3", { pinned: [3], error: [3] })).toMatch(/bg-warning-50.* ring-2 ring-accent-500$/);
  });

  it("goes by the trial number, not the whole id", () => {
    expect(chip("other_4", { failure: [4] })).toContain("bg-danger-50");
  });

  it("is success colored for an id with no number", () => {
    expect(chip("weird")).toContain("bg-success-50");
  });
});
