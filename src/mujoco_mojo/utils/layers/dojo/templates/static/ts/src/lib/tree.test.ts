import { describe, expect, it } from "vitest";

import {
  allTreeFolderPaths,
  anyTreeRowVisible,
  buildTreeRows,
  buildTreeRowsFromNames,
  sortTreeItems,
  visibleTreeRows,
  type TreeRow,
} from "./tree";

const items = (...names: string[]) => names.map((name) => ({ name }));
const paths = (rows: TreeRow<unknown>[]) => rows.map((r) => r.path);
const shown = (rows: TreeRow<unknown>[]) => paths(rows.filter((r) => !r.hidden));

describe("buildTreeRows", () => {
  it("puts folders before files, folders alphabetical, files in input order", () => {
    const rows = buildTreeRows(items("b/x", "a/z", "a/y", "top", "also"));
    expect(rows.map((r) => `${r.type}:${r.path}@${r.depth}`)).toEqual([
      "folder:a@0",
      "file:a/z@1",
      "file:a/y@1",
      "folder:b@0",
      "file:b/x@1",
      "file:top@0",
      "file:also@0",
    ]);
  });

  it("annotates name, depth and recursive file counts", () => {
    const rows = buildTreeRows(items("a/b/c", "a/b/d", "a/e"));
    const byPath = new Map(rows.map((r) => [r.path, r]));
    expect(byPath.get("a/b")).toMatchObject({ type: "folder", name: "b", depth: 1, fileCount: 2 });
    expect(byPath.get("a")).toMatchObject({ type: "folder", name: "a", depth: 0, fileCount: 3 });
    expect(byPath.get("a/b/c")).toMatchObject({ type: "file", name: "c", depth: 2, fileCount: 1 });
  });

  it("starts every row visible and keeps the source item on file rows only", () => {
    const source = items("a/b");
    const rows = buildTreeRows(source);
    expect(rows.every((r) => r.hidden === false)).toBe(true);
    expect(rows[0]!.item).toBeNull();
    expect(rows[1]!.item).toBe(source[0]);
  });

  it("sorts a file named time ahead of everything else at its level, case-insensitively", () => {
    expect(paths(buildTreeRows(items("z/q", "alpha", "time")))).toEqual(["time", "z", "z/q", "alpha"]);
    expect(paths(buildTreeRows(items("alpha", "Time")))).toEqual(["Time", "alpha"]);
    expect(paths(buildTreeRows(items("sig/b/x", "sig/a", "sig/time")))).toEqual([
      "sig",
      "sig/time",
      "sig/b",
      "sig/b/x",
      "sig/a",
    ]);
  });

  it("gives a file and a folder with the same name different keys", () => {
    const rows = buildTreeRows(items("body", "body/x"));
    expect(rows.map((r) => r.key)).toEqual(["folder:body", "file:body/x", "file:body"]);
    expect(new Set(rows.map((r) => r.key)).size).toBe(rows.length);
  });

  it("nests a colon-suffixed attribute one level under its base", () => {
    const rows = buildTreeRows(items("body/joint:ke_rot"));
    expect(rows.map((r) => `${r.type}:${r.path}`)).toEqual([
      "folder:body",
      "folder:body/joint",
      "file:body/joint/ke_rot",
    ]);
  });

  it("splits only on the first colon", () => {
    const rows = buildTreeRows(items("a:b:c"));
    expect(rows.map((r) => `${r.type}:${r.path}`)).toEqual(["folder:a", "file:a/b:c"]);
  });

  it("ignores empty path segments and drops names with nothing in them", () => {
    expect(paths(buildTreeRows(items("a//b", "/c/", "a/b:")))).toEqual(["a", "a/b", "a/b", "c"]);
    expect(buildTreeRows(items("", "/", ":"))).toEqual([]);
  });

  it("orders folders by their best-ranked item when asked for input order", () => {
    const input = items("z/a", "m/b", "a/c");
    expect(paths(buildTreeRows(input, "alpha").filter((r) => r.type === "folder"))).toEqual(["a", "m", "z"]);
    expect(paths(buildTreeRows(input, "input").filter((r) => r.type === "folder"))).toEqual(["z", "m", "a"]);
  });

  it("ranks a parent folder by the best item anywhere beneath it", () => {
    const rows = buildTreeRows(items("x/deep/f", "w/g"), "input");
    expect(paths(rows.filter((r) => r.depth === 0))).toEqual(["x", "w"]);
  });
});

describe("sortTreeItems", () => {
  const entries = [
    { name: "b/Zed", modified: 1 },
    { name: "a/alpha", modified: 3 },
    { name: "Mid", modified: 2 },
  ];

  it("sorts by leaf name ascending and case-insensitively by default", () => {
    expect(sortTreeItems(entries, "name").map((e) => e.name)).toEqual(["a/alpha", "Mid", "b/Zed"]);
  });

  it("sorts by modified time newest first by default", () => {
    expect(sortTreeItems(entries, "modified").map((e) => e.modified)).toEqual([3, 2, 1]);
  });

  it("honors an explicit direction in either mode", () => {
    expect(sortTreeItems(entries, "name", "desc").map((e) => e.name)).toEqual(["b/Zed", "Mid", "a/alpha"]);
    expect(sortTreeItems(entries, "modified", "asc").map((e) => e.modified)).toEqual([1, 2, 3]);
  });

  it("returns a new array and leaves the input alone", () => {
    const before = [...entries];
    const sorted = sortTreeItems(entries, "modified");
    expect(sorted).not.toBe(entries);
    expect(entries).toEqual(before);
  });
});

describe("visibleTreeRows", () => {
  // rows: a, a/b, a/b/y, a/x, c
  const rows = buildTreeRowsFromNames(["a/x", "a/b/y", "c"]);
  const everything = () => true;

  it("shows everything when nothing is collapsed", () => {
    expect(shown(visibleTreeRows(rows, {}, "", everything))).toEqual(["a", "a/b", "a/b/y", "a/x", "c"]);
  });

  it("hides a collapsed folder's descendants but never the folder itself", () => {
    expect(shown(visibleTreeRows(rows, { a: true }, "", everything))).toEqual(["a", "c"]);
    expect(shown(visibleTreeRows(rows, { "a/b": true }, "", everything))).toEqual(["a", "a/b", "a/x", "c"]);
  });

  it("does not treat a folder whose name starts the same as inside the collapsed one", () => {
    const sibling = buildTreeRowsFromNames(["a/x", "ab/y"]);
    expect(shown(visibleTreeRows(sibling, { a: true }, "", everything))).toEqual(["a", "ab", "ab/y"]);
  });

  it("returns every row in the same order, annotated rather than filtered", () => {
    const out = visibleTreeRows(rows, { a: true }, "", everything);
    expect(paths(out)).toEqual(paths(rows));
    expect(rows.every((r) => r.hidden === false)).toBe(true);
  });

  describe("hideInvalid", () => {
    const withInvalid = buildTreeRowsFromNames(["a/x", "a/b/y", "c", "d/z"]);
    const isValid = (item: string) => item === "a/b/y" || item === "c";

    it("hides invalid files and folders left with nothing valid", () => {
      expect(shown(visibleTreeRows(withInvalid, {}, "", everything, undefined, isValid, true))).toEqual([
        "a",
        "a/b",
        "a/b/y",
        "c",
      ]);
    });

    it("hides nothing when off", () => {
      expect(shown(visibleTreeRows(withInvalid, {}, "", everything, undefined, isValid, false))).toEqual(
        paths(withInvalid),
      );
    });

    it("keeps collapse state working while on", () => {
      expect(shown(visibleTreeRows(withInvalid, { a: true }, "", everything, undefined, isValid, true))).toEqual([
        "a",
        "c",
      ]);
    });
  });

  describe("with a query", () => {
    const endsWithY = (item: string) => item.endsWith("y");

    it("shows only matches and their ancestor folders", () => {
      expect(shown(visibleTreeRows(rows, {}, "y", endsWithY))).toEqual(["a", "a/b", "a/b/y"]);
    });

    it("ignores collapse state so a match is never hidden", () => {
      expect(shown(visibleTreeRows(rows, { a: true, "a/b": true }, "y", endsWithY))).toEqual(["a", "a/b", "a/b/y"]);
    });

    it("treats a whitespace-only query as no query", () => {
      expect(shown(visibleTreeRows(rows, { a: true }, "   ", endsWithY))).toEqual(["a", "c"]);
    });

    it("also drops invalid matches when hideInvalid is on", () => {
      const notY = (item: string) => !item.endsWith("y");
      expect(shown(visibleTreeRows(rows, {}, "a", (i) => i.startsWith("a"), undefined, notY, true))).toEqual([
        "a",
        "a/x",
      ]);
    });

    it("hides every row when nothing matches", () => {
      const out = visibleTreeRows(rows, {}, "zzz", () => false);
      expect(shown(out)).toEqual([]);
      expect(anyTreeRowVisible(out)).toBe(false);
    });
  });

  describe("reusing the previous output", () => {
    it("returns the same row object when its hidden flag did not change", () => {
      const first = visibleTreeRows(rows, {}, "", everything);
      const second = visibleTreeRows(rows, { a: true }, "", everything, first);
      const byPath = (list: TreeRow<string>[]) => new Map(list.map((r) => [r.path, r]));
      const before = byPath(first);
      const after = byPath(second);
      // folder a and the root file c keep their hidden flag, so keep their identity
      expect(after.get("a")).toBe(before.get("a"));
      expect(after.get("c")).toBe(before.get("c"));
      // the descendants flipped, so they are new objects
      expect(after.get("a/b")).not.toBe(before.get("a/b"));
      expect(after.get("a/b")!.hidden).toBe(true);
    });

    it("never mutates the rows it was given", () => {
      const first = visibleTreeRows(rows, {}, "", everything);
      visibleTreeRows(rows, { a: true }, "", everything, first);
      expect(rows.every((r) => r.hidden === false)).toBe(true);
      expect(first.every((r) => r.hidden === false)).toBe(true);
    });
  });
});

describe("helpers", () => {
  const rows = buildTreeRowsFromNames(["a/b/y", "a/x", "c"]);

  it("allTreeFolderPaths lists every folder and no files", () => {
    expect(allTreeFolderPaths(rows)).toEqual(["a", "a/b"]);
    expect(allTreeFolderPaths(buildTreeRowsFromNames(["only"]))).toEqual([]);
  });

  it("anyTreeRowVisible is true when at least one row is not hidden", () => {
    expect(anyTreeRowVisible(rows)).toBe(true);
    expect(anyTreeRowVisible(rows.map((r) => ({ ...r, hidden: true })))).toBe(false);
    expect(anyTreeRowVisible([])).toBe(false);
  });

  it("buildTreeRowsFromNames puts the plain string on file rows", () => {
    const built = buildTreeRowsFromNames(["a/b", "c"]);
    expect(built.map((r) => r.item)).toEqual([null, "a/b", "c"]);
  });
});
