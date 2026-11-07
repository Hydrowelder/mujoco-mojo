import { describe, expect, it } from "vitest";

import {
  activeColumns,
  filterFingerprint,
  needsRefFrameMigration,
  needsVsSync,
  planConfigChange,
} from "./config-change";
import type { FilterEntry, PlotConfig, YAxisConfig } from "./plot-config.generated";
import { DEFAULT_CONFIG } from "./plot-defaults";

const clip = (over: Partial<FilterEntry> = {}): FilterEntry => ({ type: "clip", min: 0, max: 5, ...over });
const rotation = (): FilterEntry => ({ type: "rotation", quatCol: "q", originCol: null, invert: true, enabled: true });

const cfg = (
  yAxes: Record<string, FilterEntry[] | undefined> = {},
  over: Partial<PlotConfig> = {},
): PlotConfig => ({
  ...(JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as PlotConfig),
  xAxis: { col: "time", filters: [] },
  yAxes: Object.fromEntries(
    Object.entries(yAxes).map(([k, filters]) => [k, { color: "#ff0000", filters } as YAxisConfig]),
  ),
  ...over,
});

describe("filterFingerprint", () => {
  it("is an empty list for no filters", () => {
    expect(filterFingerprint(undefined)).toBe("[]");
    expect(filterFingerprint([])).toBe("[]");
  });

  it("describes the enabled filters", () => {
    expect(filterFingerprint([clip()])).toBe(JSON.stringify([clip()]));
  });

  it("counts a filter with no enabled flag as enabled", () => {
    expect(filterFingerprint([{ type: "clip" }])).toBe('[{"type":"clip"}]');
    expect(filterFingerprint([{ type: "clip", enabled: true }])).toBe('[{"type":"clip","enabled":true}]');
  });

  it("leaves out disabled filters, so switching one off looks like removing it", () => {
    expect(filterFingerprint([clip({ enabled: false })])).toBe("[]");
    expect(filterFingerprint([clip({ enabled: false }), clip({ min: 1 })])).toBe(JSON.stringify([clip({ min: 1 })]));
  });

  it("does not change when only a disabled filter is edited", () => {
    expect(filterFingerprint([clip({ enabled: false, min: 1 })])).toBe(filterFingerprint([clip({ enabled: false, min: 9 })]));
  });

  it("depends on the order of the filters", () => {
    expect(filterFingerprint([clip(), { type: "unit" }])).not.toBe(filterFingerprint([{ type: "unit" }, clip()]));
  });
});

describe("planConfigChange", () => {
  it("finds nothing changed when every fingerprint is current", () => {
    const config = cfg({ a: [clip()], b: [] }, { xAxis: { col: "time", filters: [clip()] } });
    const plan = planConfigChange(
      config,
      { a: filterFingerprint([clip()]), b: "[]" },
      filterFingerprint([clip()]),
    );
    expect(plan).toEqual({
      changedFilterCols: [],
      filterFingerprints: {},
      xFilterChanged: false,
      xFilterFingerprint: filterFingerprint([clip()]),
      colsToRefetch: [],
    });
  });

  it("takes a signal with no recorded fingerprint as having no filters", () => {
    expect(planConfigChange(cfg({ a: [] }), {}, "[]").changedFilterCols).toEqual([]);
    expect(planConfigChange(cfg({ a: undefined }), {}, "[]").changedFilterCols).toEqual([]);
    expect(planConfigChange(cfg({ a: [clip()] }), {}, "[]").changedFilterCols).toEqual(["a"]);
  });

  it("lists the signals whose filters differ from what their data was fetched with", () => {
    const plan = planConfigChange(
      cfg({ a: [clip({ min: 1 })], b: [clip()], c: [] }),
      { a: filterFingerprint([clip()]), b: filterFingerprint([clip()]), c: filterFingerprint([clip()]) },
      "[]",
    );
    expect(plan.changedFilterCols).toEqual(["a", "c"]);
    expect(plan.filterFingerprints).toEqual({ a: filterFingerprint([clip({ min: 1 })]), c: "[]" });
    expect(plan.colsToRefetch).toEqual(["a", "c"]);
  });

  it("sees a filter switched off as a change", () => {
    const plan = planConfigChange(cfg({ a: [clip({ enabled: false })] }), { a: filterFingerprint([clip()]) }, "[]");
    expect(plan.changedFilterCols).toEqual(["a"]);
    expect(plan.filterFingerprints).toEqual({ a: "[]" });
  });

  it("does not see an edit to a switched-off filter as a change", () => {
    const plan = planConfigChange(cfg({ a: [clip({ enabled: false, min: 99 })] }), { a: "[]" }, "[]");
    expect(plan.changedFilterCols).toEqual([]);
  });

  it("refetches the x column first when its filters changed", () => {
    const plan = planConfigChange(
      cfg({ a: [clip()] }, { xAxis: { col: "angle", filters: [clip()] } }),
      {},
      "[]",
    );
    expect(plan.xFilterChanged).toBe(true);
    expect(plan.xFilterFingerprint).toBe(filterFingerprint([clip()]));
    expect(plan.colsToRefetch).toEqual(["angle", "a"]);
  });

  it("leaves the x column alone when only a signal changed", () => {
    const plan = planConfigChange(cfg({ a: [clip()] }), {}, "[]");
    expect(plan.xFilterChanged).toBe(false);
    expect(plan.colsToRefetch).toEqual(["a"]);
  });

  it("refetches just the x column when only its filters changed", () => {
    const plan = planConfigChange(cfg({}, { xAxis: { col: "time", filters: [clip()] } }), {}, "[]");
    expect(plan.colsToRefetch).toEqual(["time"]);
    expect(plan.changedFilterCols).toEqual([]);
  });

  it("takes a missing x-axis or x filter list as no filters", () => {
    const noAxis = { ...cfg({}), xAxis: undefined } as unknown as PlotConfig;
    expect(planConfigChange(noAxis, {}, "[]").xFilterChanged).toBe(false);
    expect(planConfigChange(cfg({}, { xAxis: { col: "time" } }), {}, "[]").xFilterChanged).toBe(false);
  });

  it("only reports fingerprints for the signals that changed", () => {
    const plan = planConfigChange(cfg({ a: [clip()], b: [] }), { b: "[]" }, "[]");
    expect(Object.keys(plan.filterFingerprints)).toEqual(["a"]);
  });

  it("does not change what it was given", () => {
    const fingerprints = { a: "[]" };
    planConfigChange(cfg({ a: [clip()] }), fingerprints, "[]");
    expect(fingerprints).toEqual({ a: "[]" });
  });
});

describe("needsVsSync", () => {
  const base = () => cfg({ a: [], b: [] });

  it("never syncs while versus mode is off", () => {
    expect(needsVsSync(false, cfg({ a: [] }), base())).toBe(false);
  });

  it("syncs when the x column changes", () => {
    expect(needsVsSync(true, cfg({ a: [], b: [] }, { xAxis: { col: "angle", filters: [] } }), base())).toBe(true);
  });

  it("syncs when signals are added or removed", () => {
    expect(needsVsSync(true, cfg({ a: [] }), base())).toBe(true);
    expect(needsVsSync(true, cfg({ a: [], b: [], c: [] }), base())).toBe(true);
  });

  it("syncs when one signal is swapped for another, though the count stays", () => {
    expect(needsVsSync(true, cfg({ a: [], z: [] }), base())).toBe(true);
    expect(needsVsSync(true, cfg({ y: [], b: [] }), base())).toBe(true);
    expect(needsVsSync(true, cfg({ x: [], y: [] }), base())).toBe(true);
  });

  it("syncs when a signal is added while another is removed", () => {
    expect(needsVsSync(true, cfg({ a: [], c: [] }), cfg({ a: [], b: [] }))).toBe(true);
  });

  it("does not sync when nothing about the plotted columns changed", () => {
    expect(needsVsSync(true, cfg({ a: [], b: [] }, { title: "New title" }), base())).toBe(false);
    expect(needsVsSync(true, cfg({ a: [], b: [] }), base())).toBe(false);
  });

  it("does not sync when only the order of the signals changed", () => {
    expect(needsVsSync(true, cfg({ b: [], a: [] }), base())).toBe(false);
  });

  it("does not sync for a change to a signal's own settings", () => {
    expect(needsVsSync(true, cfg({ a: [clip()], b: [] }), base())).toBe(false);
  });

  it("syncs when there was no earlier config", () => {
    expect(needsVsSync(true, base(), undefined)).toBe(true);
  });

  it("treats an earlier config with no signals field as having none", () => {
    const old = { ...base(), yAxes: undefined } as unknown as PlotConfig;
    expect(needsVsSync(true, cfg({}), old)).toBe(false);
    expect(needsVsSync(true, cfg({ a: [] }), old)).toBe(true);
  });
});

describe("needsRefFrameMigration", () => {
  it("is false for the world frame", () => {
    expect(needsRefFrameMigration(cfg({ a: [] }, { refFrame: [null, null] }))).toBe(false);
  });

  it("is true when a frame is set and no signal has the rotation filter", () => {
    expect(needsRefFrameMigration(cfg({ a: [] }, { refFrame: ["q", null] }))).toBe(true);
    expect(needsRefFrameMigration(cfg({ a: undefined }, { refFrame: [null, "o"] }))).toBe(true);
    expect(needsRefFrameMigration(cfg({ a: [clip()] }, { refFrame: ["q", "o"] }))).toBe(true);
  });

  it("is true when a frame is set and there are no signals", () => {
    expect(needsRefFrameMigration(cfg({}, { refFrame: ["q", null] }))).toBe(true);
  });

  it("is false once any signal has the rotation filter", () => {
    expect(needsRefFrameMigration(cfg({ a: [clip()], b: [rotation()] }, { refFrame: ["q", null] }))).toBe(false);
    expect(needsRefFrameMigration(cfg({ a: [rotation()], b: [] }, { refFrame: ["q", null] }))).toBe(false);
  });
});

describe("activeColumns", () => {
  it("is the x column, then each signal", () => {
    expect(activeColumns(cfg({ a: [], b: [] }, { xAxis: { col: "angle", filters: [] } }))).toEqual(["angle", "a", "b"]);
  });

  it("is just the x column with no signals", () => {
    expect(activeColumns(cfg({}))).toEqual(["time"]);
  });
});
