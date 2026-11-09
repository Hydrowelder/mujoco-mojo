import { describe, expect, it } from "vitest";

import { pushSnapshot } from "./history";

describe("pushSnapshot", () => {
  it("starts a history from nothing", () => {
    expect(pushSnapshot({ stack: [], index: -1 }, "a", 50)).toEqual({ stack: ["a"], index: 0 });
  });

  it("appends a new state and moves to it", () => {
    expect(pushSnapshot({ stack: ["a", "b"], index: 1 }, "c", 50)).toEqual({ stack: ["a", "b", "c"], index: 2 });
  });

  it("does nothing when the state is the current one", () => {
    expect(pushSnapshot({ stack: ["a", "b"], index: 1 }, "b", 50)).toBeNull();
  });

  it("records a state equal to an older one, since only the current one is compared", () => {
    expect(pushSnapshot({ stack: ["a", "b"], index: 1 }, "a", 50)).toEqual({ stack: ["a", "b", "a"], index: 2 });
  });

  it("drops the undone states ahead of the index when something new is recorded", () => {
    expect(pushSnapshot({ stack: ["a", "b", "c"], index: 0 }, "x", 50)).toEqual({ stack: ["a", "x"], index: 1 });
  });

  it("treats an undone state as new when it differs from where the index is", () => {
    expect(pushSnapshot({ stack: ["a", "b", "c"], index: 1 }, "c", 50)).toEqual({ stack: ["a", "b", "c"], index: 2 });
  });

  it("keeps a stack that exactly reaches its limit", () => {
    expect(pushSnapshot({ stack: ["a", "b"], index: 1 }, "c", 3)).toEqual({ stack: ["a", "b", "c"], index: 2 });
  });

  it("drops the oldest state once the stack outgrows its limit", () => {
    expect(pushSnapshot({ stack: ["a", "b", "c"], index: 2 }, "d", 3)).toEqual({ stack: ["b", "c", "d"], index: 2 });
  });

  it("does not modify the history it is given", () => {
    const history = { stack: ["a", "b", "c"], index: 1 };
    pushSnapshot(history, "x", 50);
    expect(history).toEqual({ stack: ["a", "b", "c"], index: 1 });
  });
});
