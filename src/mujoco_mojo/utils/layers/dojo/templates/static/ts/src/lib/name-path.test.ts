import { describe, expect, it } from "vitest";

import { encodeNamePath } from "./name-path";

describe("encodeNamePath", () => {
  it("leaves a plain name alone", () => {
    expect(encodeNamePath("baseline")).toBe("baseline");
  });

  it("keeps the folder separators of a nested name", () => {
    expect(encodeNamePath("robotics/arm_reach/baseline")).toBe("robotics/arm_reach/baseline");
  });

  it("encodes each segment on its own", () => {
    expect(encodeNamePath("my lab/v#2")).toBe("my%20lab/v%232");
    expect(encodeNamePath("100%/ü")).toBe("100%25/%C3%BC");
    expect(encodeNamePath("what?/a&b")).toBe("what%3F/a%26b");
  });

  it("keeps empty segments", () => {
    expect(encodeNamePath("a//b")).toBe("a//b");
    expect(encodeNamePath("/a")).toBe("/a");
    expect(encodeNamePath("")).toBe("");
  });
});
