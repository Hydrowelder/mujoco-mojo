import { describe, expect, it } from "vitest";

import type { PlotConfig } from "../models";
import { validatePlotConfig, type LabRequirements, type PlotConfigContext } from "./config-validate";

const COLUMNS = ["time", "Bodies/B/xpos:x", "Bodies/B/xpos:y"];

const config = (xCol: string | undefined, yAxes: unknown): PlotConfig =>
  ({ xAxis: { col: xCol, filters: [] }, yAxes }) as unknown as PlotConfig;

const context = (over: Partial<PlotConfigContext> = {}): PlotConfigContext => ({
  schema: null,
  labSchemas: [],
  columns: COLUMNS,
  ...over,
});

const lab = (name: string, over: Partial<LabRequirements> = {}): LabRequirements => ({
  name,
  signal_in_columns: ["Bodies/B/xpos:x"],
  missing: [],
  ...over,
});

describe("signals in the telemetry", () => {
  it("accepts a config whose signals all exist", () => {
    expect(validatePlotConfig(config("time", { "Bodies/B/xpos:x": {} }), context())).toEqual([]);
  });

  it("names a missing x signal and a missing y signal", () => {
    expect(validatePlotConfig(config("nope", { "Bodies/B/xpos:x": {}, gone: {} }), context())).toEqual([
      'X-Axis "nope" not found in telemetry.',
      'Y-Axis "gone" not found in telemetry.',
    ]);
  });

  it("does not check an x axis with no column set", () => {
    expect(validatePlotConfig(config(undefined, {}), context())).toEqual([]);
    expect(validatePlotConfig(config("", {}), context())).toEqual([]);
  });

  it("reports each missing y signal", () => {
    expect(validatePlotConfig(config("time", { a: {}, b: {} }), context())).toEqual([
      'Y-Axis "a" not found in telemetry.',
      'Y-Axis "b" not found in telemetry.',
    ]);
  });

  it("insists yAxes is a map, not a list or a scalar", () => {
    expect(validatePlotConfig(config("time", []), context())).toEqual(["yAxes must be a hashmap."]);
    expect(validatePlotConfig(config("time", "text"), context())).toEqual(["yAxes must be a hashmap."]);
  });
});

describe("Lab signals", () => {
  const labSignal = (name: string, output = "out") => `Lab/${name}/${output}`;

  it("waits for the lab schemas before reporting anything about a lab", () => {
    expect(validatePlotConfig(config("time", { [labSignal("Any")]: {} }), context({ labSchemas: [] }))).toEqual([]);
  });

  it("accepts a lab whose inputs are all present", () => {
    const ctx = context({ labSchemas: [lab("Smooth")] });
    expect(validatePlotConfig(config("time", { [labSignal("Smooth")]: {} }), ctx)).toEqual([]);
  });

  it("names a lab that does not exist", () => {
    const ctx = context({ labSchemas: [lab("Smooth")] });
    expect(validatePlotConfig(config("time", { [labSignal("Gone")]: {} }), ctx)).toEqual(['Lab "Gone" not found.']);
  });

  it("names the inputs a lab needs and the ones missing", () => {
    const ctx = context({ labSchemas: [lab("Smooth", { signal_in_columns: ["a", "b"], missing: ["b"] })] });
    expect(validatePlotConfig(config("time", { [labSignal("Smooth")]: {} }), ctx)).toEqual([
      'Lab "Smooth" requires: a, b; missing: b.',
    ]);
  });

  it("reports a lab once however many of its outputs are plotted", () => {
    const ctx = context({ labSchemas: [lab("Smooth", { missing: ["b"] })] });
    const yAxes = { [labSignal("Smooth", "one")]: {}, [labSignal("Smooth", "two")]: {} };
    expect(validatePlotConfig(config("time", yAxes), ctx)).toHaveLength(1);
  });

  it("finds a lab in a folder by everything before the output name", () => {
    const ctx = context({ labSchemas: [lab("team/Smooth")] });
    expect(validatePlotConfig(config("time", { "Lab/team/Smooth/out": {} }), ctx)).toEqual([]);
    expect(validatePlotConfig(config("time", { "Lab/team/Other/out": {} }), ctx)).toEqual([
      'Lab "team/Other" not found.',
    ]);
  });

  it("checks a lab signal on the x axis too", () => {
    const ctx = context({ labSchemas: [lab("Smooth")] });
    expect(validatePlotConfig(config(labSignal("Gone"), {}), ctx)).toEqual(['Lab "Gone" not found.']);
  });
});

describe("the schema pass", () => {
  const schema = { type: "object", properties: { title: { type: "string" } } };

  it("runs first and reports structural problems ahead of missing signals", () => {
    const cfg = { ...config("nope", {}), title: 5 } as unknown as PlotConfig;
    expect(validatePlotConfig(cfg, context({ schema }))).toEqual([
      "config.title: must be of type string (got number)",
      'X-Axis "nope" not found in telemetry.',
    ]);
  });

  it("is skipped while the schema has not loaded", () => {
    const cfg = { ...config("time", {}), title: 5 } as unknown as PlotConfig;
    expect(validatePlotConfig(cfg, context({ schema: null }))).toEqual([]);
  });
});
