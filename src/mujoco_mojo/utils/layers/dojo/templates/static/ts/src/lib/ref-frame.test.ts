import { describe, expect, it } from "vitest";

import type { FilterEntry } from "../models";

import {
  buildRefFrameFilter,
  refFrameActive,
  refFrameAvailable,
  refFrameLabel,
  sameRefFrame,
  sanitizeRefFrame,
  withRefFrameFilter,
  type RefFrame,
} from "./ref-frame";

const WORLD: RefFrame = [null, null];

describe("refFrameActive", () => {
  it("is false only for the world frame", () => {
    expect(refFrameActive(WORLD)).toBe(false);
    expect(refFrameActive(["q", null])).toBe(true);
    expect(refFrameActive([null, "o"])).toBe(true);
    expect(refFrameActive(["q", "o"])).toBe(true);
  });
});

describe("sameRefFrame", () => {
  it("compares both halves", () => {
    expect(sameRefFrame(["q", "o"], ["q", "o"])).toBe(true);
    expect(sameRefFrame(WORLD, [null, null])).toBe(true);
    expect(sameRefFrame(["q", "o"], ["q", "x"])).toBe(false);
    expect(sameRefFrame(["q", "o"], ["x", "o"])).toBe(false);
    expect(sameRefFrame(["q", null], [null, "q"])).toBe(false);
  });
});

describe("refFrameLabel", () => {
  it.each([
    [[null, null], "world"],
    [["Bodies/B/quat", null], "Bodies/B/quat"],
    [[null, "Bodies/B/xpos"], "@ Bodies/B/xpos"],
    [["Bodies/B/quat", "Bodies/C/xpos"], "Bodies/B/quat @ Bodies/C/xpos"],
  ] as [RefFrame, string][])("%j -> %s", (frame, label) => {
    expect(refFrameLabel(frame)).toBe(label);
  });
});

describe("refFrameAvailable", () => {
  const quats = new Set(["Bodies/B/quat"]);
  const cols = new Set(["Bodies/B/xpos:x", "Bodies/B/xpos:y", "Bodies/B/xpos:z", "time"]);

  it("is always available for the world frame", () => {
    expect(refFrameAvailable(WORLD, new Set(), new Set())).toBe(true);
  });

  it("needs the quaternion family to exist", () => {
    expect(refFrameAvailable(["Bodies/B/quat", null], quats, cols)).toBe(true);
    expect(refFrameAvailable(["Bodies/Z/quat", null], quats, cols)).toBe(false);
  });

  it("needs the origin to exist as an :x family", () => {
    expect(refFrameAvailable([null, "Bodies/B/xpos"], quats, cols)).toBe(true);
    expect(refFrameAvailable([null, "Bodies/Z/xpos"], quats, cols)).toBe(false);
    // the bare name is not a column on its own
    expect(refFrameAvailable([null, "time"], quats, cols)).toBe(false);
  });

  it("needs both halves when both are set", () => {
    expect(refFrameAvailable(["Bodies/B/quat", "Bodies/B/xpos"], quats, cols)).toBe(true);
    expect(refFrameAvailable(["Bodies/B/quat", "Bodies/Z/xpos"], quats, cols)).toBe(false);
    expect(refFrameAvailable(["Bodies/Z/quat", "Bodies/B/xpos"], quats, cols)).toBe(false);
  });
});

describe("buildRefFrameFilter", () => {
  it("makes an inverted rotation filter from the pair", () => {
    expect(buildRefFrameFilter(["q", "o"])).toEqual({
      type: "rotation",
      quatCol: "q",
      originCol: "o",
      invert: true,
      enabled: true,
    });
  });

  it("carries a missing half as null", () => {
    expect(buildRefFrameFilter(["q", null])).toMatchObject({ quatCol: "q", originCol: null });
    expect(buildRefFrameFilter([null, "o"])).toMatchObject({ quatCol: null, originCol: "o" });
  });
});

describe("sanitizeRefFrame", () => {
  it("returns the same object when there is no frame or a valid one", () => {
    const none: { refFrame?: unknown; title: string } = { title: "t" };
    const valid = { refFrame: ["q", null] };
    expect(sanitizeRefFrame(none)).toBe(none);
    expect(sanitizeRefFrame(valid)).toBe(valid);
    expect(sanitizeRefFrame({ refFrame: [null, null] })).toEqual({ refFrame: [null, null] });
  });

  it.each([
    ["the old null world frame", null],
    ["the old plain string", "Bodies/B/quat"],
    ["a list that is too short", ["q"]],
    ["a list that is too long", ["q", "o", "x"]],
    ["a list with a non-string", ["q", 5]],
    ["an object", { quat: "q" }],
  ])("resets %s to the world frame", (_label, refFrame) => {
    expect(sanitizeRefFrame({ refFrame, title: "kept" })).toEqual({ refFrame: [null, null], title: "kept" });
  });

  it("does not modify the config it is given", () => {
    const old = { refFrame: "legacy" };
    sanitizeRefFrame(old);
    expect(old).toEqual({ refFrame: "legacy" });
  });
});

describe("withRefFrameFilter", () => {
  const rotation = (quatCol: string | null, originCol: string | null): FilterEntry => ({
    type: "rotation",
    quatCol,
    originCol,
    invert: true,
    enabled: true,
  });
  const other = (type: string): FilterEntry => ({ type, enabled: true });
  const types = (filters: FilterEntry[]) => filters.map((f) => f.type);

  it("puts a rotation filter at the front of a stack that has none", () => {
    const out = withRefFrameFilter([other("low_pass"), other("abs")], ["q", "o"]);
    expect(types(out)).toEqual(["rotation", "low_pass", "abs"]);
    expect(out[0]).toEqual(rotation("q", "o"));
  });

  it("replaces an existing rotation filter where it is, keeping the user's order", () => {
    const out = withRefFrameFilter([other("low_pass"), rotation("old", null), other("abs")], ["q", null]);
    expect(types(out)).toEqual(["low_pass", "rotation", "abs"]);
    expect(out[1]).toEqual(rotation("q", null));
  });

  it("takes the rotation filter out for the world frame", () => {
    const out = withRefFrameFilter([other("low_pass"), rotation("q", null), other("abs")], [null, null]);
    expect(types(out)).toEqual(["low_pass", "abs"]);
  });

  it("returns the very same array when the world frame has nothing to remove", () => {
    const filters = [other("low_pass")];
    expect(withRefFrameFilter(filters, [null, null])).toBe(filters);
    const empty: FilterEntry[] = [];
    expect(withRefFrameFilter(empty, [null, null])).toBe(empty);
  });

  it("returns a new array whenever it changes something, and never modifies its input", () => {
    const filters = [other("low_pass"), rotation("q", null)];
    const before = JSON.stringify(filters);
    expect(withRefFrameFilter(filters, ["z", null])).not.toBe(filters);
    expect(withRefFrameFilter(filters, [null, null])).not.toBe(filters);
    expect(JSON.stringify(filters)).toBe(before);
  });
});
