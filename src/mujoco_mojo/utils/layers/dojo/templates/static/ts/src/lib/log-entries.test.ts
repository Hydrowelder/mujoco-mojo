import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LogEntry } from "../models";
import {
  filterLogEntries,
  formatLogTime,
  logLevelClass,
  logLevelsOf,
  logSourceFull,
  logSourceShort,
  fittedLogColumnWidth,
  LOG_COL_MIN,
  LOG_LEVEL_SEVERITY,
  resizedLogColumnWidth,
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

describe("LOG_COL_MIN", () => {
  it("is the narrowest each column can be dragged to", () => {
    expect(LOG_COL_MIN).toEqual({ time: 60, level: 56, source: 60 });
  });
});

describe("resizedLogColumnWidth", () => {
  it("moves the width by the drag", () => {
    expect(resizedLogColumnWidth("time", 100, 25)).toBe(125);
    expect(resizedLogColumnWidth("time", 100, -25)).toBe(75);
    expect(resizedLogColumnWidth("source", 200, 0)).toBe(200);
  });

  it("stops at each column's own minimum", () => {
    expect(resizedLogColumnWidth("time", 100, -500)).toBe(60);
    expect(resizedLogColumnWidth("level", 100, -500)).toBe(56);
    expect(resizedLogColumnWidth("source", 100, -500)).toBe(60);
  });

  it("can sit exactly on the minimum", () => {
    expect(resizedLogColumnWidth("time", 100, -40)).toBe(60);
    expect(resizedLogColumnWidth("level", 100, -44)).toBe(56);
  });

  it("is the minimum one pixel past it", () => {
    expect(resizedLogColumnWidth("level", 100, -43)).toBe(57);
    expect(resizedLogColumnWidth("level", 100, -45)).toBe(56);
  });

  it("lifts a column that started below its minimum", () => {
    expect(resizedLogColumnWidth("time", 10, 0)).toBe(60);
  });
});

describe("fittedLogColumnWidth", () => {
  it("is the header plus room for the sort chevron when it is the widest, with the cell padding", () => {
    expect(fittedLogColumnWidth("time", 50, [10, 20])).toBe(50 + 20 + 16);
  });

  it("is the widest cell when it beats the header, with the cell padding", () => {
    expect(fittedLogColumnWidth("source", 50, [10, 200, 80])).toBe(200 + 16);
  });

  it("adds the badge's padding for the level column", () => {
    expect(fittedLogColumnWidth("level", 40, [90])).toBe(90 + 32);
    expect(fittedLogColumnWidth("level", 100, [90])).toBe(100 + 20 + 32);
  });

  it("rounds the content up before adding the padding", () => {
    expect(fittedLogColumnWidth("source", 0, [100.2])).toBe(101 + 16);
    expect(fittedLogColumnWidth("source", 0, [100])).toBe(100 + 16);
    expect(fittedLogColumnWidth("time", 30.5, [])).toBe(51 + 16);
  });

  it("fits the header alone when there are no cells", () => {
    expect(fittedLogColumnWidth("time", 30, [])).toBe(30 + 20 + 16);
  });

  it("is a tie at the point where header and cell are equally wide", () => {
    expect(fittedLogColumnWidth("time", 30, [50])).toBe(50 + 16);
  });
});
