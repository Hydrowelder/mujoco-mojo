import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DistEntry } from "../models";
import {
  breakableLabel,
  formatDefaultValue,
  formatNum,
  formatPercentile,
  formatSampled,
  formatSigFig,
  formatTimeAgo,
  notifTimeAgo,
  relativeTime,
} from "./format";

describe("formatNum", () => {
  it("shows a dash for null and undefined", () => {
    expect(formatNum(null)).toBe("-");
    expect(formatNum(undefined)).toBe("-");
  });

  it("passes non-finite numbers through as text", () => {
    expect(formatNum(Number.NaN)).toBe("NaN");
    expect(formatNum(Number.POSITIVE_INFINITY)).toBe("Infinity");
    expect(formatNum(Number.NEGATIVE_INFINITY)).toBe("-Infinity");
  });

  it("shows zero as 0", () => {
    expect(formatNum(0)).toBe("0");
    expect(formatNum(-0)).toBe("0");
  });

  it("rounds ordinary magnitudes to four significant digits and trims zeros", () => {
    expect(formatNum(3.14159)).toBe("3.142");
    expect(formatNum(1234.4)).toBe("1234");
    expect(formatNum(100)).toBe("100");
    expect(formatNum(0.00012)).toBe("0.00012");
    expect(formatNum(-2.5)).toBe("-2.5");
  });

  it("switches to scientific notation at and above 10^sigDigits", () => {
    expect(formatNum(12340)).toBe("1.234e+4");
    expect(formatNum(10000)).toBe("1e+4");
    expect(formatNum(-12340)).toBe("-1.234e+4");
  });

  it("switches to scientific notation below 1e-4 and trims trailing zeros", () => {
    expect(formatNum(0.00001)).toBe("1e-5");
    expect(formatNum(0.000015)).toBe("1.5e-5");
    expect(formatNum(0.0000105)).toBe("1.05e-5");
  });

  it("honors a custom number of significant digits", () => {
    expect(formatNum(3.14159, 2)).toBe("3.1");
    expect(formatNum(12345.6, 6)).toBe("12345.6");
    expect(formatNum(1234.5, 2)).toBe("1.2e+3");
  });
});

describe("breakableLabel", () => {
  it("adds a zero-width space after every slash and colon", () => {
    expect(breakableLabel("Bodies/B/xpos:x")).toBe("Bodies/​B/​xpos:​x");
  });

  it("leaves text with no separators alone", () => {
    expect(breakableLabel("time")).toBe("time");
    expect(breakableLabel("")).toBe("");
  });
});

describe("formatTimeAgo", () => {
  it.each([
    [0, "0s ago"],
    [1, "1s ago"],
    [59, "59s ago"],
    [60, "1m ago"],
    [119, "1m ago"],
    [3599, "59m ago"],
    [3600, "1h ago"],
    [7300, "2h ago"],
  ])("%d seconds -> %s", (seconds, text) => {
    expect(formatTimeAgo(seconds)).toBe(text);
  });

  it("treats NaN like zero", () => {
    expect(formatTimeAgo(Number.NaN)).toBe("0s ago");
  });
});

describe("notifTimeAgo", () => {
  const NOW = new Date("2026-01-01T12:00:00Z").getTime();

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const secondsAgo = (s: number) => NOW - s * 1000;

  it.each([
    [0, "Just now"],
    [59, "Just now"],
    [60, "1m ago"],
    [3599, "59m ago"],
    [3600, "1h ago"],
    [86399, "23h ago"],
    [86400, "1d ago"],
    [86400 * 3 + 5, "3d ago"],
  ])("%d seconds ago -> %s", (s, text) => {
    expect(notifTimeAgo(secondsAgo(s))).toBe(text);
  });

  it("calls a timestamp in the future just now", () => {
    expect(notifTimeAgo(NOW + 60_000)).toBe("Just now");
  });

  it("ignores the tick argument", () => {
    expect(notifTimeAgo(secondsAgo(120), 1)).toBe(notifTimeAgo(secondsAgo(120), 999));
  });
});

// the dash the dist table shows for a value it does not have
const NONE = "\u2014";

describe("formatSigFig", () => {
  it("shows a dash for null and a plain zero for zero", () => {
    expect(formatSigFig(null)).toBe(NONE);
    expect(formatSigFig(0)).toBe("0");
  });

  it("uses four significant figures and trims trailing zeros between 1e-4 and 1e4", () => {
    expect(formatSigFig(3.14159)).toBe("3.142");
    expect(formatSigFig(-2.5)).toBe("-2.5");
    expect(formatSigFig(100)).toBe("100");
    expect(formatSigFig(9999)).toBe("9999");
    expect(formatSigFig(0.0001)).toBe("0.0001");
  });

  it("switches to exponential notation from 1e4 up and below 1e-4, without trimming zeros", () => {
    expect(formatSigFig(12340)).toBe("1.234e+4");
    expect(formatSigFig(10000)).toBe("1.000e+4");
    expect(formatSigFig(0.00001234)).toBe("1.234e-5");
    expect(formatSigFig(-12340)).toBe("-1.234e+4");
  });
});

describe("formatSampled", () => {
  const entry = (over: Partial<DistEntry>) =>
    ({ sampled_values: null, sampled_labels: null, sampled_permutations: null, ...over }) as DistEntry;

  it("joins numeric draws with four significant figures", () => {
    expect(formatSampled(entry({ sampled_values: [1.5, 2, 12340] }))).toBe("1.5, 2, 1.234e+4");
  });

  it("joins label draws", () => {
    expect(formatSampled(entry({ sampled_labels: ["red", "blue"] }))).toBe("red, blue");
  });

  it("shows each permutation in brackets", () => {
    expect(formatSampled(entry({ sampled_permutations: [["a", "b"], [1, 2, 3]] }))).toBe("[a, b]; [1, 2, 3]");
  });

  it("prefers permutations, then numbers, then labels", () => {
    const all = entry({ sampled_permutations: [["p"]], sampled_values: [1], sampled_labels: ["l"] });
    expect(formatSampled(all)).toBe("[p]");
    expect(formatSampled({ ...all, sampled_permutations: null })).toBe("1");
    expect(formatSampled({ ...all, sampled_permutations: null, sampled_values: null })).toBe("l");
  });

  it("shows a dash when nothing was drawn, treating empty lists as nothing", () => {
    expect(formatSampled(entry({}))).toBe(NONE);
    expect(formatSampled(entry({ sampled_values: [], sampled_labels: [], sampled_permutations: [] }))).toBe(NONE);
  });
});

describe("formatPercentile", () => {
  it("writes P and one decimal place", () => {
    expect(formatPercentile(95.7)).toBe("P95.7");
    expect(formatPercentile(50)).toBe("P50.0");
    expect(formatPercentile(0)).toBe("P0.0");
    expect(formatPercentile(12.34)).toBe("P12.3");
  });
});

describe("formatDefaultValue", () => {
  it("writes null and undefined as None, the way the server renders Python's None", () => {
    expect(formatDefaultValue(null)).toBe("None");
    expect(formatDefaultValue(undefined)).toBe("None");
  });

  it("writes booleans in lowercase", () => {
    expect(formatDefaultValue(true)).toBe("true");
    expect(formatDefaultValue(false)).toBe("false");
  });

  it("writes an empty string as (empty) and any other string as it is", () => {
    expect(formatDefaultValue("")).toBe("(empty)");
    expect(formatDefaultValue("lines+markers")).toBe("lines+markers");
  });

  it("writes numbers and structures as JSON", () => {
    expect(formatDefaultValue(0)).toBe("0");
    expect(formatDefaultValue(2.5)).toBe("2.5");
    expect(formatDefaultValue([1, 2])).toBe("[1,2]");
    expect(formatDefaultValue({ a: 1 })).toBe('{"a":1}');
  });
});

describe("relativeTime", () => {
  const NOW = new Date("2026-01-01T12:00:00Z").getTime();
  const ago = (s: number) => relativeTime(NOW - s * 1000, NOW);

  it.each([
    [0, "just now"],
    [59, "just now"],
    [60, "1m ago"],
    [3599, "59m ago"],
    [3600, "1h ago"],
    [86399, "23h ago"],
    [86400, "yesterday"],
    [172799, "yesterday"],
    [172800, "2d ago"],
    [86400 * 10, "10d ago"],
  ])("%d seconds ago -> %s", (seconds, text) => {
    expect(ago(seconds)).toBe(text);
  });

  it("says just now for a time in the future", () => {
    expect(ago(-300)).toBe("just now");
  });

  it("defaults to the current time", () => {
    expect(relativeTime(Date.now() - 5 * 60_000)).toBe("5m ago");
  });
});
