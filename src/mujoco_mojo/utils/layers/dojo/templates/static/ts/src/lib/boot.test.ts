import { describe, expect, it } from "vitest";

import { paddingLength, sharedLinkDecision, withoutSharedParam } from "./boot";

describe("paddingLength", () => {
  it("is the number in the padding style", () => {
    expect(paddingLength("trial_{:03d}")).toBe(3);
    expect(paddingLength("{:07d}")).toBe(7);
    expect(paddingLength("5")).toBe(5);
  });

  it("is the first number when there are several", () => {
    expect(paddingLength("a4b9")).toBe(4);
  });

  it("is the whole run of digits, not one digit", () => {
    expect(paddingLength("pad12")).toBe(12);
  });

  it("is 2 when the style has no number", () => {
    expect(paddingLength("no digits")).toBe(2);
    expect(paddingLength("")).toBe(2);
  });

  it("reads a leading zero as plain digits", () => {
    expect(paddingLength("08")).toBe(8);
    expect(paddingLength("00")).toBe(0);
  });
});

describe("sharedLinkDecision", () => {
  it("does nothing without a shared link", () => {
    expect(sharedLinkDecision(null, false)).toBe("none");
    expect(sharedLinkDecision(null, true)).toBe("none");
    expect(sharedLinkDecision("", true)).toBe("none");
  });

  it("uses the link outright when there are no saved tabs to lose", () => {
    expect(sharedLinkDecision("abc", false)).toBe("use");
  });

  it("asks first when the link would replace saved tabs", () => {
    expect(sharedLinkDecision("abc", true)).toBe("ask");
  });
});

describe("withoutSharedParam", () => {
  it("removes the v parameter", () => {
    expect(withoutSharedParam("http://localhost:8001/trial/run_1?v=abc")).toBe("http://localhost:8001/trial/run_1");
  });

  it("keeps the other parameters, the path and the hash", () => {
    expect(withoutSharedParam("http://h/p/q?x=1&v=abc&y=two%20words#top")).toBe("http://h/p/q?x=1&y=two+words#top");
  });

  it("removes every v parameter", () => {
    expect(withoutSharedParam("http://h/p?v=1&v=2")).toBe("http://h/p");
  });

  it("leaves an address with no v parameter as it was", () => {
    expect(withoutSharedParam("http://h/p?x=1")).toBe("http://h/p?x=1");
    expect(withoutSharedParam("http://h/p")).toBe("http://h/p");
  });

  it("does not take another parameter for v", () => {
    expect(withoutSharedParam("http://h/p?vv=1&v2=2")).toBe("http://h/p?vv=1&v2=2");
  });
});
