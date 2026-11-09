// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PlotConfig, YAxisConfig } from "./plot-config.generated";
import { DEFAULT_CONFIG } from "./plot-defaults";
import { buildRefFrameFilter } from "./ref-frame";
import {
  MAX_CLOSED_PLOT_TABS,
  closedPlotTabEntry,
  duplicatePlotTab,
  isPlotTabDirty,
  loadClosedPlotTabs,
  makeBlankPlotTab,
  neededColumns,
  persistClosedPlotTabs,
  persistablePlotTabs,
  pushClosedPlotTabs,
  reopenPlotTab,
  type PlotTab,
} from "./plot-tabs";

const yAxis = (): YAxisConfig => ({ color: "#ff0000", filters: [] });
const aFilter = () => buildRefFrameFilter(["q", null]);

const config = (over: Partial<PlotConfig> = {}): PlotConfig => ({
  ...(JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as PlotConfig),
  ...over,
});

const withY = (cols: string[], over: Partial<PlotConfig> = {}): PlotConfig =>
  config({ yAxes: Object.fromEntries(cols.map((c) => [c, yAxis()])), ...over });

const tab = (id: string, over: Partial<PlotTab> = {}): PlotTab => ({
  id,
  config: config(),
  data: null,
  filterFingerprints: {},
  xAxisFilterFingerprint: "[]",
  historyStack: [],
  historyIndex: -1,
  savedSnapshot: null,
  ...over,
});

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("makeBlankPlotTab", () => {
  it("starts from a deep copy of the default config", () => {
    const blank = makeBlankPlotTab(DEFAULT_CONFIG);
    expect(blank.config).toEqual(DEFAULT_CONFIG);
    expect(blank.config).not.toBe(DEFAULT_CONFIG);
    blank.config.yAxes["body:x"] = yAxis();
    blank.config.xAxis.filters!.push(aFilter());
    expect(DEFAULT_CONFIG.yAxes).toEqual({});
    expect(DEFAULT_CONFIG.xAxis.filters).toEqual([]);
  });

  it("has no data, no fingerprints and empty history", () => {
    const blank = makeBlankPlotTab(DEFAULT_CONFIG);
    expect(blank.id).toMatch(/^t[0-9a-z]+$/);
    expect(blank).toMatchObject({
      data: null,
      filterFingerprints: {},
      xAxisFilterFingerprint: "[]",
      historyStack: [],
      historyIndex: -1,
    });
  });

  it("is not dirty until the user edits it", () => {
    const blank = makeBlankPlotTab(DEFAULT_CONFIG);
    expect(blank.savedSnapshot).toBe(JSON.stringify(blank.config));
    expect(isPlotTabDirty(blank)).toBe(false);
    blank.config.title = "edited";
    expect(isPlotTabDirty(blank)).toBe(true);
  });
});

describe("isPlotTabDirty", () => {
  it("is dirty when the tab was never saved", () => {
    expect(isPlotTabDirty(tab("a", { savedSnapshot: null }))).toBe(true);
    expect(isPlotTabDirty(tab("a", { savedSnapshot: "" }))).toBe(true);
  });

  it("is clean when the config still matches the saved snapshot", () => {
    const c = config({ title: "same" });
    expect(isPlotTabDirty(tab("a", { config: c, savedSnapshot: JSON.stringify(c) }))).toBe(false);
  });

  it("is dirty after any change, including a nested one", () => {
    const c = withY(["body:x"]);
    const t = tab("a", { config: c, savedSnapshot: JSON.stringify(c) });
    c.yAxes["body:x"]!.filters!.push(aFilter());
    expect(isPlotTabDirty(t)).toBe(true);
  });
});

describe("neededColumns", () => {
  it("is every plotted column when nothing is cached", () => {
    expect(neededColumns(withY(["a", "b"], { xAxis: { col: "time", filters: [] } }), null)).toEqual([
      "time",
      "a",
      "b",
    ]);
  });

  it("leaves out the columns that are cached", () => {
    const cfg = withY(["a", "b"], { xAxis: { col: "time", filters: [] } });
    expect(neededColumns(cfg, { time: [1], b: [2] })).toEqual(["a"]);
    expect(neededColumns(cfg, { time: [1], a: [1], b: [2] })).toEqual([]);
  });

  it("counts a cached empty series as present", () => {
    expect(neededColumns(withY(["a"], { xAxis: { col: "time", filters: [] } }), { time: [], a: [] })).toEqual([]);
  });

  it("skips an x-axis with no column, or no x-axis at all", () => {
    expect(neededColumns(withY(["a"], { xAxis: { col: "", filters: [] } }), null)).toEqual(["a"]);
    expect(neededColumns({ ...withY(["a"]), xAxis: undefined } as unknown as PlotConfig, null)).toEqual(["a"]);
  });

  it("tolerates a config with no y-axes", () => {
    const cfg = { ...config(), yAxes: undefined } as unknown as PlotConfig;
    expect(neededColumns(cfg, null)).toEqual(["time"]);
  });
});

describe("duplicatePlotTab", () => {
  const source = (): PlotTab =>
    tab("src", {
      config: withY(["a"], { title: "Arm" }),
      data: { a: [1, 2] },
      filterFingerprints: { a: "f1" },
      xAxisFilterFingerprint: "[x]",
      historyStack: ["h1", "h2"],
      historyIndex: 1,
      savedSnapshot: "saved",
    });

  it("copies the config deeply and appends copy to the title", () => {
    const src = source();
    const dup = duplicatePlotTab(src);
    expect(dup.config.title).toBe("Arm copy");
    expect(dup.config.yAxes).toEqual(src.config.yAxes);
    dup.config.yAxes["a"]!.filters!.push(aFilter());
    expect(src.config.yAxes["a"]!.filters).toEqual([]);
    expect(src.config.title).toBe("Arm");
  });

  it("leaves an empty title empty", () => {
    expect(duplicatePlotTab(tab("src")).config.title).toBe("");
  });

  it("gets its own id", () => {
    expect(duplicatePlotTab(source()).id).not.toBe("src");
  });

  it("copies the data cache and the fingerprints without sharing them", () => {
    const src = source();
    const dup = duplicatePlotTab(src);
    expect(dup.data).toEqual({ a: [1, 2] });
    expect(dup.data).not.toBe(src.data);
    expect(dup.filterFingerprints).toEqual({ a: "f1" });
    expect(dup.filterFingerprints).not.toBe(src.filterFingerprints);
    expect(dup.xAxisFilterFingerprint).toBe("[x]");
    expect(duplicatePlotTab(tab("src")).data).toBeNull();
  });

  it("starts with fresh history and counts as unsaved", () => {
    const dup = duplicatePlotTab(source());
    expect(dup.historyStack).toEqual([]);
    expect(dup.historyIndex).toBe(-1);
    expect(dup.savedSnapshot).toBeNull();
    expect(isPlotTabDirty(dup)).toBe(true);
  });
});

describe("persistablePlotTabs", () => {
  it("drops the data cache and keeps everything else", () => {
    const tabs = [tab("a", { data: { x: [1] }, savedSnapshot: "s", historyIndex: 2 }), tab("b")];
    const out = persistablePlotTabs(tabs);
    expect(out.map((t) => t.data)).toEqual([null, null]);
    expect(out[0]).toMatchObject({ id: "a", savedSnapshot: "s", historyIndex: 2 });
    expect(out.map((t) => t.id)).toEqual(["a", "b"]);
  });

  it("does not touch the live tabs", () => {
    const tabs = [tab("a", { data: { x: [1] } })];
    persistablePlotTabs(tabs);
    expect(tabs[0]!.data).toEqual({ x: [1] });
  });
});

describe("closedPlotTabEntry", () => {
  it("drops the data and records where the tab was", () => {
    const t = tab("a", { data: { x: [1] }, savedSnapshot: "s" });
    const entry = closedPlotTabEntry(t, 3);
    expect(entry).toMatchObject({ id: "a", data: null, closedAtIndex: 3, savedSnapshot: "s" });
    expect(t.data).toEqual({ x: [1] });
    expect(t.closedAtIndex).toBeUndefined();
  });

  it("records an unknown position as undefined", () => {
    expect(closedPlotTabEntry(tab("a"), undefined).closedAtIndex).toBeUndefined();
  });
});

describe("pushClosedPlotTabs", () => {
  const ids = (tabs: PlotTab[]) => tabs.map((t) => t.id);

  it("puts the most recently closed first", () => {
    expect(ids(pushClosedPlotTabs([tab("old")], [tab("new")]))).toEqual(["new", "old"]);
  });

  it("keeps the order of a group closed together, ahead of the older ones", () => {
    expect(ids(pushClosedPlotTabs([tab("old")], [tab("g1"), tab("g2")]))).toEqual(["g1", "g2", "old"]);
  });

  it("keeps only the ten most recent", () => {
    expect(MAX_CLOSED_PLOT_TABS).toBe(10);
    const closed = Array.from({ length: 10 }, (_, i) => tab(`c${i}`));
    const out = pushClosedPlotTabs(closed, [tab("new")]);
    expect(out).toHaveLength(10);
    expect(out[0]!.id).toBe("new");
    expect(out[9]!.id).toBe("c8");
  });

  it("keeps only the ten most recent of a group bigger than the cap", () => {
    const group = Array.from({ length: 12 }, (_, i) => tab(`g${i}`));
    expect(ids(pushClosedPlotTabs([tab("old")], group))).toEqual(group.slice(0, 10).map((t) => t.id));
  });

  it("does not change the list it was given", () => {
    const closed = [tab("old")];
    pushClosedPlotTabs(closed, [tab("new")]);
    expect(ids(closed)).toEqual(["old"]);
  });
});

describe("reopenPlotTab", () => {
  const closed = (closedAtIndex?: number) => tab("c", { closedAtIndex });

  it("goes back where it was closed from", () => {
    expect(reopenPlotTab(closed(1), 4).insertAt).toBe(1);
    expect(reopenPlotTab(closed(0), 4).insertAt).toBe(0);
  });

  it("goes at the end when its old position is past the end of the shorter list", () => {
    expect(reopenPlotTab(closed(99), 2).insertAt).toBe(2);
    expect(reopenPlotTab(closed(2), 2).insertAt).toBe(2);
  });

  it("goes at the end when its old position is unknown", () => {
    expect(reopenPlotTab(closed(undefined), 3).insertAt).toBe(3);
  });

  it("comes back without the closed marker, and the stored entry is untouched", () => {
    const entry = closed(2);
    const { tab: reopened } = reopenPlotTab(entry, 5);
    expect(reopened.closedAtIndex).toBeUndefined();
    expect(reopened.id).toBe("c");
    expect(entry.closedAtIndex).toBe(2);
  });
});

describe("closed tab storage", () => {
  it("round-trips through localStorage under the key a saved session uses", () => {
    const closed = [closedPlotTabEntry(tab("a"), 1), closedPlotTabEntry(tab("b"), 0)];
    persistClosedPlotTabs(closed);
    expect(JSON.parse(localStorage.getItem("mojo:plot:closedTabs")!)).toEqual(closed);
    expect(loadClosedPlotTabs()).toEqual(closed);
  });

  it("loads an empty list when nothing is stored or the stored text is not JSON", () => {
    expect(loadClosedPlotTabs()).toEqual([]);
    localStorage.setItem("mojo:plot:closedTabs", "{not json");
    expect(loadClosedPlotTabs()).toEqual([]);
  });

  it("does not throw when storage refuses to read or write", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    expect(loadClosedPlotTabs()).toEqual([]);
    expect(() => persistClosedPlotTabs([tab("a")])).not.toThrow();
  });
});
