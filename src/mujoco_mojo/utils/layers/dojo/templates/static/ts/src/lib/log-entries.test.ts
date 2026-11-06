import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LogEntry } from "../models";
import {
  filterLogEntries,
  formatLogTime,
  logLevelClass,
  logLevelsOf,
  logSourceFull,
  logSourceShort,
  LOG_LEVEL_SEVERITY,
  type LogFilter,
} from "./log-entries";

const entry = (timestamp: number, level: string, message: string): LogEntry => ({
  timestamp,
  level,
  message,
  pathname: "mod.py",
  lineno: 1,
});

const ENTRIES = [
  entry(300, "ERROR", "Sensor timed out"),
  entry(100, "INFO", "Started trial"),
  entry(500, "DEBUG", "step 12"),
  entry(200, "WARNING", "Low battery"),
  entry(400, "INFO", "Finished"),
];

const filter = (over: Partial<LogFilter> = {}): LogFilter => ({
  levels: [],
  message: "",
  regex: false,
  sortKey: "timestamp",
  sortAsc: true,
  ...over,
});

const times = (list: LogEntry[]) => list.map((e) => e.timestamp);

describe("filterLogEntries", () => {
  it("returns everything oldest first by default", () => {
    expect(times(filterLogEntries(ENTRIES, filter()))).toEqual([100, 200, 300, 400, 500]);
  });

  it("reverses the order newest first", () => {
    expect(times(filterLogEntries(ENTRIES, filter({ sortAsc: false })))).toEqual([500, 400, 300, 200, 100]);
  });

  it("keeps only the chosen levels, and every level when none is chosen", () => {
    expect(times(filterLogEntries(ENTRIES, filter({ levels: ["INFO", "ERROR"] })))).toEqual([100, 300, 400]);
    expect(filterLogEntries(ENTRIES, filter({ levels: [] }))).toHaveLength(5);
  });

  it("matches the message as a case-insensitive substring", () => {
    expect(times(filterLogEntries(ENTRIES, filter({ message: "STEP" })))).toEqual([500]);
    // surrounding spaces in the query are ignored
    expect(times(filterLogEntries(ENTRIES, filter({ message: "  TIMED  " })))).toEqual([300]);
  });

  it("treats regex characters literally unless regex mode is on", () => {
    expect(filterLogEntries(ENTRIES, filter({ message: "step \\d+" }))).toEqual([]);
    expect(times(filterLogEntries(ENTRIES, filter({ message: "step \\d+", regex: true })))).toEqual([500]);
    expect(times(filterLogEntries(ENTRIES, filter({ message: "^(started|finished)", regex: true })))).toEqual([
      100, 400,
    ]);
  });

  it("falls back to a substring match when the regex is invalid", () => {
    expect(filterLogEntries(ENTRIES, filter({ message: "(unclosed", regex: true }))).toEqual([]);
    const withParen = [entry(1, "INFO", "call f(x"), entry(2, "INFO", "other")];
    expect(times(filterLogEntries(withParen, filter({ message: "f(x", regex: true })))).toEqual([1]);
  });

  it("combines level and message filters", () => {
    expect(times(filterLogEntries(ENTRIES, filter({ levels: ["INFO"], message: "fin" })))).toEqual([400]);
  });

  describe("sorted by level", () => {
    it("runs least to most severe, oldest first within a level", () => {
      const out = filterLogEntries(ENTRIES, filter({ sortKey: "level" }));
      expect(out.map((e) => e.level)).toEqual(["DEBUG", "INFO", "INFO", "WARNING", "ERROR"]);
      expect(times(out)).toEqual([500, 100, 400, 200, 300]);
    });

    it("runs most to least severe when descending, still oldest first within a level", () => {
      const out = filterLogEntries(ENTRIES, filter({ sortKey: "level", sortAsc: false }));
      expect(out.map((e) => e.level)).toEqual(["ERROR", "WARNING", "INFO", "INFO", "DEBUG"]);
      expect(times(out)).toEqual([300, 200, 100, 400, 500]);
    });

    it("puts a level it does not know before DEBUG", () => {
      const out = filterLogEntries([entry(1, "DEBUG", "a"), entry(2, "TRACE", "b")], filter({ sortKey: "level" }));
      expect(out.map((e) => e.level)).toEqual(["TRACE", "DEBUG"]);
    });
  });

  it("does not modify its input", () => {
    const before = [...ENTRIES];
    filterLogEntries(ENTRIES, filter({ sortAsc: false }));
    expect(ENTRIES).toEqual(before);
  });
});

describe("logLevelsOf", () => {
  it("lists each level present once, least severe first", () => {
    expect(logLevelsOf(ENTRIES)).toEqual(["DEBUG", "INFO", "WARNING", "ERROR"]);
    expect(logLevelsOf([])).toEqual([]);
  });
});

describe("LOG_LEVEL_SEVERITY", () => {
  it("increases from DEBUG to CRITICAL", () => {
    const order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((l) => LOG_LEVEL_SEVERITY[l]!);
    expect(order).toEqual([...order].sort((a, b) => a - b));
    expect(new Set(order).size).toBe(5);
  });
});

describe("logLevelClass", () => {
  const levels = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"];

  it("gives every known level its own classes", () => {
    const classes = levels.map(logLevelClass);
    expect(new Set(classes).size).toBe(levels.length);
    for (const c of classes) expect(c.length).toBeGreaterThan(0);
  });

  it("colors by what the level means", () => {
    expect(logLevelClass("CRITICAL")).toContain("danger");
    expect(logLevelClass("ERROR")).toContain("danger");
    expect(logLevelClass("WARNING")).toContain("warning");
    expect(logLevelClass("INFO")).toContain("success");
    expect(logLevelClass("DEBUG")).toContain("accent");
  });

  it("gives an unknown level a neutral style", () => {
    expect(logLevelClass("TRACE")).toBe("bg-chip text-ink-secondary");
    expect(logLevelClass("")).toBe("bg-chip text-ink-secondary");
  });
});

describe("logSourceShort and logSourceFull", () => {
  const at = (pathname: string, lineno: number | null): LogEntry => ({ ...entry(1, "INFO", "m"), pathname, lineno });

  it("show the file name and line, or the full path and line for the tooltip", () => {
    expect(logSourceShort(at("/src/pkg/runner.py", 42))).toBe("runner.py:42");
    expect(logSourceFull(at("/src/pkg/runner.py", 42))).toBe("/src/pkg/runner.py:42");
  });

  it("leave the line off when there isn't one, but keep line zero", () => {
    expect(logSourceShort(at("/src/pkg/runner.py", null))).toBe("runner.py");
    expect(logSourceFull(at("/src/pkg/runner.py", null))).toBe("/src/pkg/runner.py");
    expect(logSourceShort(at("/src/pkg/runner.py", 0))).toBe("runner.py:0");
  });

  it("cope with a bare file name and with no path at all", () => {
    expect(logSourceShort(at("runner.py", 7))).toBe("runner.py:7");
    expect(logSourceShort(at("", null))).toBe("");
    expect(logSourceFull(at("", null))).toBe("");
  });
});

describe("formatLogTime", () => {
  const NOW = new Date("2026-06-15T12:00:00Z").getTime();

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("says how long ago for the last day", () => {
    expect(formatLogTime(NOW - 5_000)).toBe("Just now");
    expect(formatLogTime(NOW - 5 * 60_000)).toBe("5m ago");
    expect(formatLogTime(NOW - 23 * 3_600_000)).toBe("23h ago");
  });

  it("gives the local date and time from a day back", () => {
    const old = NOW - 24 * 3_600_000;
    expect(formatLogTime(old)).toBe(new Date(old).toLocaleString());
    expect(formatLogTime(NOW - 400 * 86_400_000)).toBe(new Date(NOW - 400 * 86_400_000).toLocaleString());
  });

  it("ignores the tick, which is only there to make a template re-run it", () => {
    expect(formatLogTime(NOW - 120_000, 1)).toBe(formatLogTime(NOW - 120_000, 99));
  });
});
