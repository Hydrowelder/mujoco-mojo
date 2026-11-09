// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  duplicateLabTab,
  evictLabData,
  evictedPlottedColumns,
  isReusableLabTab,
  labTabFor,
  labUrl,
  legacyLabTabs,
  makeBlankLabTab,
  resolveLabSchemas,
  staleLabs,
  type LabSchema,
  type LabTab,
  type RawLabSchema,
} from "./lab";

const raw = (name: string, ins: string[], outs: string[], over: Partial<RawLabSchema> = {}): RawLabSchema => ({
  name,
  signal_in_columns: ins,
  outputs: outs,
  modified: 1,
  is_template: false,
  template_inputs: [],
  template_outputs: [],
  ...over,
});

const schema = (name: string, ins: string[]): LabSchema => ({
  ...raw(name, ins, ["o"]),
  valid: true,
  missing: [],
});

const tab = (over: Partial<LabTab> = {}): LabTab => ({
  id: "t1",
  name: "",
  graph: null,
  savedState: null,
  dirty: false,
  viewport: null,
  ...over,
});

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("labUrl", () => {
  it("is the lab route plus the encoded name", () => {
    expect(labUrl("raw")).toBe("/mosaic/api/lab/raw");
    expect(labUrl("my lab/sub#1")).toBe("/mosaic/api/lab/my%20lab/sub%231");
  });
});

describe("resolveLabSchemas", () => {
  const COLUMNS = ["time", "body:x", "body:y"];
  const byName = (r: ReturnType<typeof resolveLabSchemas>) => Object.fromEntries(r.schemas.map((s) => [s.name, s]));

  it("marks a lab valid when the trial has all of its inputs", () => {
    const r = resolveLabSchemas([raw("a", ["body:x", "time"], ["o"])], COLUMNS);
    expect(r.schemas[0]).toMatchObject({ name: "a", valid: true, missing: [] });
  });

  it("lists the inputs the trial lacks as missing, and marks the lab invalid", () => {
    const r = resolveLabSchemas([raw("a", ["body:x", "nope", "also"], ["o"])], COLUMNS);
    expect(r.schemas[0]).toMatchObject({ valid: false, missing: ["also", "nope"] });
  });

  it("treats a lab with no inputs as valid", () => {
    expect(resolveLabSchemas([raw("a", [], ["o"])], COLUMNS).schemas[0]).toMatchObject({ valid: true, missing: [] });
  });

  it("sorts and de-duplicates inputs and outputs", () => {
    const [a] = resolveLabSchemas([raw("a", ["time", "body:x", "time"], ["z", "y", "z"])], COLUMNS).schemas;
    expect(a!.signal_in_columns).toEqual(["body:x", "time"]);
    expect(a!.outputs).toEqual(["y", "z"]);
  });

  it("fills in the template fields a server may leave out", () => {
    const bare = { name: "a", signal_in_columns: [], outputs: [], modified: 1 } as unknown as RawLabSchema;
    expect(resolveLabSchemas([bare], COLUMNS).schemas[0]).toMatchObject({
      is_template: false,
      template_inputs: [],
      template_outputs: [],
    });
  });

  it("keeps a template's own fields and the lab's other fields", () => {
    const t = raw("a", [], [], { is_template: true, template_inputs: ["i"], template_outputs: ["o"], modified: 7 });
    expect(resolveLabSchemas([t], COLUMNS).schemas[0]).toMatchObject({
      is_template: true,
      template_inputs: ["i"],
      template_outputs: ["o"],
      modified: 7,
    });
  });

  it("makes a lab's outputs available to labs that read them", () => {
    const r = resolveLabSchemas(
      [raw("a", ["body:x"], ["out"]), raw("b", ["Lab/a/out"], ["y"])],
      COLUMNS,
    );
    expect(byName(r)["b"]).toMatchObject({ valid: true, missing: [] });
    expect(r.columns).toContain("Lab/a/out");
    expect(r.columns).toContain("Lab/b/y");
  });

  it("resolves a chain whatever order the labs come in", () => {
    const labs = [
      raw("c", ["Lab/b/y"], ["z"]),
      raw("b", ["Lab/a/out"], ["y"]),
      raw("a", ["body:x"], ["out"]),
    ];
    for (const order of [labs, [...labs].reverse()]) {
      const r = resolveLabSchemas(order, COLUMNS);
      expect(r.schemas.every((s) => s.valid)).toBe(true);
    }
  });

  it("keeps the order the server gave the labs in", () => {
    const r = resolveLabSchemas([raw("z", [], ["o"]), raw("a", [], ["o"])], COLUMNS);
    expect(r.schemas.map((s) => s.name)).toEqual(["z", "a"]);
  });

  it("leaves a lab invalid when it depends on one that is invalid, and says what is missing", () => {
    const r = resolveLabSchemas(
      [raw("bad", ["nope"], ["o"]), raw("child", ["Lab/bad/o", "body:x"], ["y"])],
      COLUMNS,
    );
    expect(byName(r)["bad"]!.valid).toBe(false);
    expect(byName(r)["child"]).toMatchObject({ valid: false, missing: ["Lab/bad/o"] });
  });

  it("never validates labs that depend on each other in a cycle, or on themselves", () => {
    const r = resolveLabSchemas(
      [raw("a", ["Lab/b/o"], ["o"]), raw("b", ["Lab/a/o"], ["o"]), raw("self", ["Lab/self/o"], ["o"])],
      COLUMNS,
    );
    expect(r.schemas.map((s) => s.valid)).toEqual([false, false, false]);
  });

  it("supports lab names with folders", () => {
    const r = resolveLabSchemas([raw("team/a", ["body:x"], ["out"]), raw("team/b", ["Lab/team/a/out"], ["y"])], COLUMNS);
    expect(r.schemas.every((s) => s.valid)).toBe(true);
    expect(r.columns).toContain("Lab/team/a/out");
  });

  it("rebuilds the lab columns from scratch, dropping those of labs that are gone", () => {
    const r = resolveLabSchemas([raw("a", [], ["out"])], [...COLUMNS, "Lab/deleted/old"]);
    expect(r.columns).not.toContain("Lab/deleted/old");
    expect(r.columns).toContain("Lab/a/out");
  });

  it("does not trust old lab columns to satisfy a lab's inputs", () => {
    const r = resolveLabSchemas([raw("b", ["Lab/a/out"], ["y"])], [...COLUMNS, "Lab/a/out"]);
    expect(r.schemas[0]!.valid).toBe(false);
  });

  it("returns the trial's columns sorted, with the lab outputs added", () => {
    const r = resolveLabSchemas([raw("a", [], ["out"])], ["time", "body:y", "body:x"]);
    expect(r.columns).toEqual(["Lab/a/out", "body:x", "body:y", "time"]);
  });

  it("returns just the trial's columns, sorted, when there are no labs", () => {
    expect(resolveLabSchemas([], ["time", "a"])).toEqual({ schemas: [], columns: ["a", "time"] });
  });
});

describe("makeBlankLabTab", () => {
  it("is untitled, empty and clean", () => {
    expect(makeBlankLabTab()).toMatchObject({
      name: "",
      graph: null,
      savedState: null,
      viewport: null,
      dirty: false,
    });
    expect(makeBlankLabTab().id).toMatch(/^t[0-9a-z]+$/);
  });
});

describe("legacyLabTabs", () => {
  it("is one blank tab when nothing was saved", () => {
    const { tabs, activeId } = legacyLabTabs();
    expect(tabs).toHaveLength(1);
    expect(tabs[0]).toMatchObject({ name: "", graph: null, savedState: null, dirty: false, viewport: null });
    expect(activeId).toBe(tabs[0]!.id);
  });

  it("restores the single lab a page from before tabs left behind", () => {
    localStorage.setItem("mojo:lab:name", "old lab");
    localStorage.setItem("mojo:lab:draft", '{"nodes":[1,2]}');
    const { tabs } = legacyLabTabs();
    expect(tabs[0]).toMatchObject({ name: "old lab", graph: { nodes: [1, 2] } });
  });

  it("takes the name or the draft alone", () => {
    localStorage.setItem("mojo:lab:name", "just a name");
    expect(legacyLabTabs().tabs[0]).toMatchObject({ name: "just a name", graph: null });
    localStorage.clear();
    localStorage.setItem("mojo:lab:draft", '{"x":1}');
    expect(legacyLabTabs().tabs[0]).toMatchObject({ name: "", graph: { x: 1 } });
  });

  it("ignores a draft that is not JSON, or empty", () => {
    localStorage.setItem("mojo:lab:draft", "{broken");
    expect(legacyLabTabs().tabs[0]!.graph).toBeNull();
    localStorage.setItem("mojo:lab:draft", "");
    expect(legacyLabTabs().tabs[0]!.graph).toBeNull();
  });
});

describe("duplicateLabTab", () => {
  const source = (): LabTab =>
    tab({
      id: "src",
      name: "alpha",
      graph: { nodes: [{ id: 1 }] },
      savedState: "saved",
      dirty: false,
      viewport: { scale: 2, offset: [3, 4] },
    });

  it("appends copy to the name and gets its own id", () => {
    const dup = duplicateLabTab(source());
    expect(dup.name).toBe("alpha copy");
    expect(dup.id).not.toBe("src");
  });

  it("copies the graph deeply", () => {
    const src = source();
    const dup = duplicateLabTab(src);
    expect(dup.graph).toEqual(src.graph);
    expect(dup.graph).not.toBe(src.graph);
    (dup.graph as { nodes: unknown[] }).nodes.push({ id: 2 });
    expect((src.graph as { nodes: unknown[] }).nodes).toHaveLength(1);
  });

  it("copies the pan and zoom", () => {
    const src = source();
    const dup = duplicateLabTab(src);
    expect(dup.viewport).toEqual({ scale: 2, offset: [3, 4] });
    expect(dup.viewport).not.toBe(src.viewport);
  });

  it("starts out unsaved, since it has no file of its own yet", () => {
    const dup = duplicateLabTab(source());
    expect(dup.savedState).toBeNull();
    expect(dup.dirty).toBe(true);
  });

  it("copies an untitled, empty tab as another clean one", () => {
    const dup = duplicateLabTab(tab({ name: "", graph: null, viewport: null }));
    expect(dup).toMatchObject({ name: "", graph: null, viewport: null, savedState: null, dirty: false });
  });

  it("keeps an untitled tab untitled even when it has a graph", () => {
    const dup = duplicateLabTab(tab({ name: "", graph: { n: 1 } }));
    expect(dup.name).toBe("");
    expect(dup.dirty).toBe(true);
  });
});

describe("labTabFor", () => {
  it("is a clean tab holding the lab as loaded", () => {
    const graph = { nodes: [] };
    const t = labTabFor("alpha", graph);
    expect(t).toMatchObject({ name: "alpha", savedState: null, viewport: null, dirty: false });
    expect(t.graph).toBe(graph);
    expect(t.id).toMatch(/^t[0-9a-z]+$/);
  });
});

describe("isReusableLabTab", () => {
  it("is true for an untitled tab with no unsaved changes", () => {
    expect(isReusableLabTab(tab({ name: "", dirty: false }))).toBe(true);
  });

  it("is false once the tab has a name or unsaved changes", () => {
    expect(isReusableLabTab(tab({ name: "alpha", dirty: false }))).toBe(false);
    expect(isReusableLabTab(tab({ name: "", dirty: true }))).toBe(false);
    expect(isReusableLabTab(tab({ name: "alpha", dirty: true }))).toBe(false);
  });
});

describe("staleLabs", () => {
  it("is the saved lab itself when nothing reads it", () => {
    expect([...staleLabs([schema("a", ["body:x"]), schema("b", ["body:y"])], "a")]).toEqual(["a"]);
  });

  it("includes the labs that read the saved lab's outputs", () => {
    const labs = [schema("a", ["body:x"]), schema("b", ["Lab/a/o"]), schema("c", ["body:y"])];
    expect([...staleLabs(labs, "a")].sort()).toEqual(["a", "b"]);
  });

  it("includes labs that read it indirectly, in any listing order", () => {
    const labs = [schema("d", ["Lab/c/o"]), schema("c", ["Lab/b/o"]), schema("b", ["Lab/a/o"]), schema("a", [])];
    expect([...staleLabs(labs, "a")].sort()).toEqual(["a", "b", "c", "d"]);
    expect([...staleLabs([...labs].reverse(), "a")].sort()).toEqual(["a", "b", "c", "d"]);
  });

  it("does not go back up the chain", () => {
    const labs = [schema("a", []), schema("b", ["Lab/a/o"]), schema("c", ["Lab/b/o"])];
    expect([...staleLabs(labs, "b")].sort()).toEqual(["b", "c"]);
  });

  it("is finished when labs read each other in a cycle", () => {
    const labs = [schema("a", ["Lab/b/o"]), schema("b", ["Lab/a/o"])];
    expect([...staleLabs(labs, "a")].sort()).toEqual(["a", "b"]);
  });

  it("includes the saved lab even when it is not in the list yet", () => {
    expect([...staleLabs([schema("a", [])], "new")]).toEqual(["new"]);
  });

  it("lists a lab once however many ways it reads the saved lab", () => {
    const labs = [schema("a", []), schema("b", ["Lab/a/o", "Lab/a/p"])];
    expect([...staleLabs(labs, "a")].sort()).toEqual(["a", "b"]);
  });

  it("splits a folder lab's name from its output at the last slash", () => {
    const labs = [schema("team/a", []), schema("b", ["Lab/team/a/o"])];
    expect([...staleLabs(labs, "team/a")].sort()).toEqual(["b", "team/a"]);
  });

  it("ignores a lab column with no output part", () => {
    const labs = [schema("a", []), schema("b", ["Lab/a"])];
    expect([...staleLabs(labs, "a")]).toEqual(["a"]);
  });

  it("does not mistake a trial column with slashes for a lab output", () => {
    // 'robot/arm/hand:x' minus its first four characters would read as a lab named 't/arm'
    const labs = [schema("t/arm", []), schema("reader", ["robot/arm/hand:x"])];
    expect([...staleLabs(labs, "t/arm")]).toEqual(["t/arm"]);
  });
});

describe("evictLabData", () => {
  const data = () => ({
    time: [0],
    "Lab/a/o": [1],
    "Lab/a/p": [2],
    "Lab/b/o": [3],
    "Lab/ab/o": [4],
    "body:x": [5],
  });

  it("drops the outputs of the given labs and keeps everything else", () => {
    const r = evictLabData(data(), new Set(["a"]));
    expect(r.evicted).toBe(true);
    expect(Object.keys(r.data).sort()).toEqual(["Lab/ab/o", "Lab/b/o", "body:x", "time"]);
  });

  it("does not drop a lab whose name only starts the same", () => {
    expect(Object.keys(evictLabData(data(), new Set(["a"])).data)).toContain("Lab/ab/o");
  });

  it("drops several labs at once", () => {
    expect(Object.keys(evictLabData(data(), new Set(["a", "b"])).data).sort()).toEqual(["Lab/ab/o", "body:x", "time"]);
  });

  it("reports nothing evicted when the labs have no cached outputs", () => {
    const r = evictLabData(data(), new Set(["nothing"]));
    expect(r.evicted).toBe(false);
    expect(r.data).toEqual(data());
  });

  it("does not change the cache it was given", () => {
    const d = data();
    evictLabData(d, new Set(["a"]));
    expect(d).toEqual(data());
  });

  it("works on an empty cache", () => {
    expect(evictLabData(null, new Set(["a"]))).toEqual({ data: {}, evicted: false });
  });
});

describe("evictedPlottedColumns", () => {
  const labs = new Set(["a", "b"]);

  it("is the plotted columns of those labs that are no longer cached", () => {
    expect(evictedPlottedColumns(["Lab/a/o", "body:x"], "time", labs, { time: [0], "body:x": [1] })).toEqual(["Lab/a/o"]);
  });

  it("leaves out the ones still cached", () => {
    expect(evictedPlottedColumns(["Lab/a/o", "Lab/b/o"], "time", labs, { "Lab/b/o": [1] })).toEqual(["Lab/a/o"]);
  });

  it("leaves out columns of labs that did not change", () => {
    expect(evictedPlottedColumns(["Lab/c/o"], "time", labs, {})).toEqual([]);
  });

  it("does not match a lab whose name only starts the same", () => {
    expect(evictedPlottedColumns(["Lab/ab/o", "Lab/abc/o"], "time", new Set(["a"]), {})).toEqual([]);
  });

  it("lists the y-axes first, then the x-axis", () => {
    expect(evictedPlottedColumns(["Lab/a/y"], "Lab/b/x", labs, {})).toEqual(["Lab/a/y", "Lab/b/x"]);
  });

  it("skips an x-axis with no column, and ignores trial columns", () => {
    expect(evictedPlottedColumns(["body:x"], "", labs, {})).toEqual([]);
  });

  it("treats a missing cache as empty", () => {
    expect(evictedPlottedColumns(["Lab/a/o"], "time", labs, null)).toEqual(["Lab/a/o"]);
  });
});
