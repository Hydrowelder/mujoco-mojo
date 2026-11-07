import { describe, expect, it } from "vitest";

import {
  filterColumns,
  isSearchSegmentActive,
  quatBases,
  rotatableColumns,
  searchActiveLevels,
  searchAvailableSuffixes,
  searchSegmentsAtDepth,
  smartSort,
  toggleSearchSegment,
} from "./column-search";

const COLUMNS = [
  "time",
  "Bodies/B/xpos:x",
  "Bodies/B/xpos:y",
  "Bodies/B/xpos:z",
  "Bodies/B/quat:w",
  "Bodies/A/xpos:x",
  "Sensors/s1",
  "Sensors/s2",
];

const sorted = (list: string[]) => [...list].sort();

describe("smartSort", () => {
  it("puts time first, wherever and however it is written", () => {
    expect(smartSort(["b", "a", "time", "c"])[0]).toBe("time");
    expect(smartSort(["b", "TIME", "a"])[0]).toBe("TIME");
  });

  it("orders the rest case-insensitively", () => {
    expect(smartSort(["b", "A", "c", "a2"])).toEqual(["A", "a2", "b", "c"]);
  });

  it("sorts in place and returns the same array", () => {
    const list = ["b", "a"];
    expect(smartSort(list)).toBe(list);
    expect(list).toEqual(["a", "b"]);
  });
});

describe("filterColumns", () => {
  it("returns every column, time first, for an empty search", () => {
    const out = filterColumns(COLUMNS, "");
    expect(out[0]).toBe("time");
    expect(sorted(out)).toEqual(sorted(COLUMNS));
  });

  it("never modifies the list it searches", () => {
    const base = ["b", "a"];
    filterColumns(base, "");
    filterColumns(base, "a");
    expect(base).toEqual(["b", "a"]);
  });

  it("matches a case-insensitive substring", () => {
    expect(sorted(filterColumns(COLUMNS, "XPOS"))).toEqual(
      sorted(["Bodies/B/xpos:x", "Bodies/B/xpos:y", "Bodies/B/xpos:z", "Bodies/A/xpos:x"]),
    );
  });

  it("treats * as a wildcard", () => {
    expect(filterColumns(COLUMNS, "B/*:x")).toEqual(["Bodies/B/xpos:x"]);
  });

  it("lets a leading colon mean any column with that suffix", () => {
    expect(sorted(filterColumns(COLUMNS, ":x"))).toEqual(sorted(["Bodies/B/xpos:x", "Bodies/A/xpos:x"]));
  });

  it("lets a trailing slash mean that folder", () => {
    expect(sorted(filterColumns(COLUMNS, "Sensors/"))).toEqual(["Sensors/s1", "Sensors/s2"]);
  });

  it("matches the word time exactly rather than as a substring", () => {
    const cols = ["time", "timestamp", "runtime"];
    expect(filterColumns(cols, "time")).toEqual(["time"]);
    expect(filterColumns(cols, "TIME")).toEqual(["time"]);
    expect(sorted(filterColumns(cols, "tim"))).toEqual(["runtime", "time", "timestamp"]);
  });

  it("falls back to a plain substring match when the search is not a valid regex", () => {
    expect(filterColumns(["f(x)", "other"], "f(")).toEqual(["f(x)"]);
    expect(filterColumns(["f(x)", "other"], "[")).toEqual([]);
  });
});

describe("toggleSearchSegment", () => {
  const toggle = (search: string, seg: string, depth: number | "suffix", cols = COLUMNS) =>
    toggleSearchSegment(search, seg, depth, cols);

  it("adds a folder choice and a trailing slash when it names a folder", () => {
    expect(toggle("", "Bodies", 0)).toBe("Bodies/");
    expect(toggle("Bodies/", "B", 1)).toBe("Bodies/B/");
  });

  it("leaves off the slash for a name that is not a folder", () => {
    expect(toggle("", "gravity", 0, ["time", "gravity"])).toBe("gravity");
    expect(toggle("", "time", 0)).toBe("time");
  });

  it("removes a choice that is already made, and the levels below it", () => {
    expect(toggle("Bodies/", "Bodies", 0)).toBe("");
    // what is left, Bodies, is a folder, so it gets its slash back
    expect(toggle("Bodies/B/xpos", "B", 1)).toBe("Bodies/");
  });

  it("combines several choices at one level as a sorted group", () => {
    expect(toggle("Bodies/B/", "A", 1)).toBe("Bodies/(A|B)");
    expect(toggle("Bodies/(A|B)", "A", 1)).toBe("Bodies/B/");
  });

  it("builds the suffix part separately", () => {
    expect(toggle("Bodies/B/xpos", ":x", "suffix")).toBe("Bodies/B/xpos:x");
    expect(toggle("Bodies/B/xpos:x", ":y", "suffix")).toBe("Bodies/B/xpos:(x|y)");
    expect(toggle("Bodies/B/xpos:(x|y)", ":x", "suffix")).toBe("Bodies/B/xpos:y");
    expect(toggle("Bodies/B/xpos:x", ":x", "suffix")).toBe("Bodies/B/xpos");
  });
});

describe("searchSegmentsAtDepth", () => {
  it("lists the names at a level, time first", () => {
    expect(searchSegmentsAtDepth(COLUMNS, "", 0)).toEqual(["time", "Bodies", "Sensors"]);
  });

  it("only offers names consistent with the levels chosen above", () => {
    expect(searchSegmentsAtDepth(COLUMNS, "Bodies/", 1)).toEqual(["A", "B"]);
    expect(searchSegmentsAtDepth(COLUMNS, "Sensors/", 1)).toEqual(["s1", "s2"]);
    expect(searchSegmentsAtDepth(COLUMNS, "Bodies/B/", 2)).toEqual(["quat", "xpos"]);
  });

  it("keeps a choice already made even when no column matches it", () => {
    expect(searchSegmentsAtDepth(COLUMNS, "Bodies/Z", 1)).toEqual(["A", "B", "Z"]);
    expect(searchSegmentsAtDepth(COLUMNS, "Bodies/(A|B)", 1)).toEqual(["A", "B"]);
  });

  it("offers nothing below a leaf", () => {
    expect(searchSegmentsAtDepth(["time"], "time", 1)).toEqual([]);
  });
});

describe("searchAvailableSuffixes", () => {
  it("lists the suffixes of the columns the path matches", () => {
    expect(searchAvailableSuffixes(COLUMNS, "Bodies/B/xpos")).toEqual([":x", ":y", ":z"]);
    expect(searchAvailableSuffixes(COLUMNS, "Bodies/B/quat")).toEqual([":w"]);
  });

  it("covers every column for an empty path and skips ones with no suffix", () => {
    expect(searchAvailableSuffixes(COLUMNS, "")).toEqual([":w", ":x", ":y", ":z"]);
  });

  it("keeps a suffix already chosen", () => {
    expect(searchAvailableSuffixes(COLUMNS, "Bodies/B/quat:(x|y)")).toEqual([":w", ":x", ":y"]);
  });
});

describe("isSearchSegmentActive", () => {
  it("reads a path level, including a group of choices", () => {
    expect(isSearchSegmentActive("Bodies/B/xpos", "B", 1)).toBe(true);
    expect(isSearchSegmentActive("Bodies/B/xpos", "A", 1)).toBe(false);
    expect(isSearchSegmentActive("Bodies/(A|B)/xpos", "A", 1)).toBe(true);
    expect(isSearchSegmentActive("Bodies", "B", 1)).toBe(false);
  });

  it("reads the suffix part, with or without its colon", () => {
    expect(isSearchSegmentActive("p:(x|y)", ":x", "suffix")).toBe(true);
    expect(isSearchSegmentActive("p:(x|y)", "y", "suffix")).toBe(true);
    expect(isSearchSegmentActive("p:(x|y)", ":z", "suffix")).toBe(false);
    expect(isSearchSegmentActive("p", ":x", "suffix")).toBe(false);
  });
});

describe("searchActiveLevels", () => {
  it("has one row of chips per chosen level, plus the next to choose", () => {
    expect(searchActiveLevels("")).toEqual([0]);
    expect(searchActiveLevels("Bodies/")).toEqual([0, 1]);
    expect(searchActiveLevels("Bodies/B/xpos")).toEqual([0, 1, 2, 3]);
  });

  it("ignores the suffix", () => {
    expect(searchActiveLevels("Bodies/B/xpos:(x|y)")).toEqual([0, 1, 2, 3]);
  });
});

// the chip rows read the same search text filterColumns does, so the wildcard
// it accepts and a half-typed bracket must give chips instead of throwing
describe("a search with regex characters in it", () => {
  it("treats * as a wildcard in the levels above the chips", () => {
    expect(searchSegmentsAtDepth(COLUMNS, "*", 1)).toEqual(["A", "B", "s1", "s2"]);
    expect(searchSegmentsAtDepth(COLUMNS, "Bodies/*/", 2)).toEqual(["quat", "xpos"]);
    expect(searchSegmentsAtDepth(COLUMNS, "Sen*/", 1)).toEqual(["s1", "s2"]);
  });

  it("treats * as a wildcard in the path before the suffixes", () => {
    expect(searchAvailableSuffixes(COLUMNS, "B/*:x")).toEqual([":w", ":x", ":y", ":z"]);
    expect(searchAvailableSuffixes(COLUMNS, "Bodies/*/quat")).toEqual([":w"]);
  });

  it("matches an unbalanced bracket as written, so nothing matches it", () => {
    expect(searchSegmentsAtDepth(COLUMNS, "f(", 1)).toEqual([]);
    expect(searchSegmentsAtDepth(COLUMNS, "Bodies/[", 2)).toEqual([]);
    expect(searchAvailableSuffixes(COLUMNS, "Bodies/(")).toEqual([]);
    expect(searchAvailableSuffixes(COLUMNS, "Bodies/B/xpos[")).toEqual([]);
  });

  it("finds a column whose name has the half-typed bracket in it", () => {
    const odd = ["a(1)/b:x", "a(1)/c:y", "other/d:x"];
    expect(searchSegmentsAtDepth(odd, "a(", 1)).toEqual(["b", "c"]);
    expect(searchAvailableSuffixes(odd, "a(1")).toEqual([":x", ":y"]);
  });

  it("keeps the slashes optional when it matches a half-typed bracket as written", () => {
    const odd = ["a(1)/b(2):x", "a(1)b(2):y"];
    expect(searchAvailableSuffixes(odd, "a(1)/b(2")).toEqual([":x", ":y"]);
  });

  it("matches the half-typed text from the start of a name, not anywhere in it", () => {
    expect(searchAvailableSuffixes(["zz(a:x", "(a:y"], "(a")).toEqual([":y"]);
    expect(searchSegmentsAtDepth(["zz(a/q:x", "(a/r:y"], "(a/", 1)).toEqual(["r"]);
  });

  it("reads a balanced bracket as a group of choices, not as part of a name", () => {
    const odd = ["a(1)/b:x", "a1/c:y"];
    expect(searchSegmentsAtDepth(odd, "a(1)/", 1)).toEqual(["c"]);
    expect(searchAvailableSuffixes(odd, "a(1)/b")).toEqual([]);
  });

  it("keeps a choice already made when the text is half typed", () => {
    expect(searchSegmentsAtDepth(COLUMNS, "Bodies/(A", 1)).toEqual(["A", "B"]);
  });

  it("matches a literal bracket, dot or plus the way it was typed", () => {
    const names = ["a.b/c:x", "axb/c:y", "a+b/c:z"];
    expect(searchAvailableSuffixes(names, "a.b/c")).toEqual([":x", ":y", ":z"]);
    expect(searchAvailableSuffixes(names, "a+")).toEqual([":x", ":y", ":z"]);
    expect(searchAvailableSuffixes(names, "a+b[")).toEqual([]);
    expect(searchAvailableSuffixes(names, "a.b[")).toEqual([]);
  });
});

describe("quatBases", () => {
  it("names the quaternions among the columns by their :w component", () => {
    expect(quatBases(["time", "Bodies/B/quat:w", "Bodies/B/quat:x", "Bodies/A/quat:w", "Sensors/s1"])).toEqual([
      "Bodies/B/quat",
      "Bodies/A/quat",
    ]);
  });

  it("is empty when there are none", () => {
    expect(quatBases(["time", "a:x"])).toEqual([]);
    expect(quatBases([])).toEqual([]);
  });

  it("only counts a column that ends in :w", () => {
    expect(quatBases(["a:w:x", "a:wx", "w"])).toEqual([]);
  });
});

describe("rotatableColumns", () => {
  const cols = ["time", "Bodies/B/xpos:x", "Bodies/B/xpos:y", "Bodies/B/xpos:z", "Bodies/B/quat:w", "Bodies/C/xpos:x"];

  it("keeps the x, y and z components of the vectors named", () => {
    expect(rotatableColumns(cols, ["Bodies/B/xpos"])).toEqual([
      "Bodies/B/xpos:x",
      "Bodies/B/xpos:y",
      "Bodies/B/xpos:z",
    ]);
  });

  it("leaves out other components and other vectors", () => {
    expect(rotatableColumns(cols, ["Bodies/B/quat"])).toEqual([]);
    expect(rotatableColumns(cols, ["Bodies/C/xpos"])).toEqual(["Bodies/C/xpos:x"]);
  });

  it("is empty when no vector is named, and ignores columns with no component", () => {
    expect(rotatableColumns(cols, [])).toEqual([]);
    expect(rotatableColumns(["time"], ["time"])).toEqual([]);
  });

  it("splits a vector's name from its component at the last colon", () => {
    expect(rotatableColumns(["a:b:x", "a:b:u"], ["a:b"])).toEqual(["a:b:x"]);
  });

  it("also keeps a column the caller accepts, such as an enum signal, in column order", () => {
    const withEnum = [...cols, "Sensors/contact", "Bodies/B/quat:w"];
    const kept = rotatableColumns(withEnum, ["Bodies/B/xpos"], (c) => c === "Sensors/contact");
    expect(kept).toEqual(["Bodies/B/xpos:x", "Bodies/B/xpos:y", "Bodies/B/xpos:z", "Sensors/contact"]);
  });

  it("keeps only what is rotatable when nothing else is accepted", () => {
    expect(rotatableColumns(cols, ["Bodies/B/xpos"], () => false)).toEqual(rotatableColumns(cols, ["Bodies/B/xpos"]));
  });

  it("does not drop a rotatable column the caller rejects", () => {
    expect(rotatableColumns(cols, ["Bodies/C/xpos"], () => false)).toEqual(["Bodies/C/xpos:x"]);
  });
});
