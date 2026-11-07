import { describe, expect, it } from "vitest";

import {
  enumContext,
  enumTrace,
  lineShape,
  primaryTraces,
  traceMode,
  vsTraces,
  yHover,
  type Series,
  type TraceColors,
  type TraceContext,
  type YProps,
} from "./plot-traces";

const COLORS: TraceColors = { tooltipBg: "#111111", tooltipFont: "#222222", tooltipBorder: "#333333" };

const ON_OFF = { OFF: 0, ON: 1 };
const META = {
  mode: { enumeration_map: ON_OFF },
  state: { enumeration_map: { A: 0, B: 1, C: 2 } },
  gear: { enumeration_map: ON_OFF },
};

const props = (name: string, over: Partial<YProps> = {}): YProps => ({
  name,
  label: name,
  color: "#ff0000",
  width: 3,
  opacity: 1,
  dash: "solid",
  marker: "none",
  ...over,
});

const sig = (key: string, over: Partial<YProps> = {}, unit: string | null = null): Series => ({
  key,
  props: props(key, over),
  unit,
});

const data = (extra: Record<string, number[]> = {}): Record<string, number[]> => ({
  time: [0, 1, 2],
  a: [10, 11, 12],
  b: [20, 21, 22],
  mode: [0, 1, 1],
  state: [2, 0, 1],
  ...extra,
});

const ctxFor = (
  yKeys: string[],
  over: { isPolar?: boolean; interp?: string; lineMode?: string; data?: Record<string, number[]>; meta?: typeof META } = {},
): TraceContext => {
  const isPolar = over.isPolar ?? false;
  return {
    isPolar,
    interp: over.interp ?? "linear",
    lineMode: over.lineMode ?? "lines",
    enum: enumContext(yKeys, over.data ?? data(), over.meta ?? META, isPolar),
  };
};

describe("enumContext", () => {
  it("has no enum axes when no plotted signal is enum-coded", () => {
    const e = enumContext(["a", "b"], data(), META, false);
    expect(e.plan.groups).toEqual([]);
    expect(e.numericKeys).toEqual(["a", "b"]);
    expect(e.hasEnumAxes).toBe(false);
    expect(e.enumPromoted).toBe(false);
  });

  it("keeps enum signals out of the numeric ones and puts them on their own axes", () => {
    const e = enumContext(["a", "mode", "b"], data(), META, false);
    expect(e.numericKeys).toEqual(["a", "b"]);
    expect(e.plan.groups).toHaveLength(1);
    expect(e.plan.groupOf.get("mode")).toBe(0);
    expect(e.hasEnumAxes).toBe(true);
    expect(e.enumPromoted).toBe(false);
  });

  it("shares one axis between signals with the same map, and gives another map its own", () => {
    const e = enumContext(["mode", "gear", "state"], data({ gear: [1, 0, 1] }), META, false);
    expect(e.plan.groups.map((g) => g.columns)).toEqual([["mode", "gear"], ["state"]]);
  });

  it("promotes the first enum axis when only enum signals have data", () => {
    expect(enumContext(["mode", "state"], data(), META, false).enumPromoted).toBe(true);
    expect(enumContext(["mode"], data(), META, false).enumPromoted).toBe(true);
  });

  it("promotes it when the numeric signals have no data to draw", () => {
    const e = enumContext(["a", "mode"], { time: [0], mode: [0] }, META, false);
    expect(e.enumPromoted).toBe(true);
    expect(e.numericKeys).toEqual(["a"]);
  });

  it("does not promote it while a numeric signal has data", () => {
    expect(enumContext(["a", "mode"], data(), META, false).enumPromoted).toBe(false);
  });

  it("leaves a plot of signals with no data unpromoted", () => {
    const e = enumContext(["a"], { time: [0] }, META, false);
    expect(e.enumPromoted).toBe(false);
    expect(e.hasEnumAxes).toBe(false);
  });

  it("ignores enum signals that have no data", () => {
    const e = enumContext(["a", "mode"], { time: [0], a: [1] }, META, false);
    expect(e.plan.groups).toEqual([]);
    expect(e.hasEnumAxes).toBe(false);
    expect(e.enumPromoted).toBe(false);
    // still counted as non-numeric
    expect(e.numericKeys).toEqual(["a"]);
  });

  it("has no enum axes in a polar plot", () => {
    const e = enumContext(["mode", "state"], data(), META, true);
    expect(e.hasEnumAxes).toBe(false);
    expect(e.enumPromoted).toBe(false);
    expect(e.plan.groups).toHaveLength(2);
  });
});

describe("traceMode", () => {
  it("is the plot's line mode when the signal has a marker", () => {
    for (const lineMode of ["lines", "markers", "lines+markers"]) {
      expect(traceMode("circle", lineMode)).toBe(lineMode);
    }
  });

  it("hides the markers when the marker symbol is none", () => {
    expect(traceMode("none", "lines+markers")).toBe("lines");
    expect(traceMode("none", "markers")).toBe("none");
    expect(traceMode("none", "lines")).toBe("lines");
  });
});

describe("lineShape", () => {
  it("follows the plot's interpolation for a numeric signal", () => {
    expect(lineShape("a", ctxFor(["a"], { interp: "spline" }))).toBe("spline");
  });

  it("is a step line for an enum signal, so no values appear that never happened", () => {
    expect(lineShape("mode", ctxFor(["mode"], { interp: "spline" }))).toBe("hv");
  });

  it("is a plain line for an enum signal in a polar plot", () => {
    expect(lineShape("mode", ctxFor(["mode"], { isPolar: true, interp: "spline" }))).toBe("linear");
  });
});

describe("yHover", () => {
  it("shows a number to four decimals for a numeric signal", () => {
    const ctx = ctxFor(["a"]);
    expect(yHover("a", "y", ctx)).toBe("%{y:.4f}");
    expect(yHover("a", "r", ctx)).toBe("%{r:.4f}");
  });

  it("shows the label for an enum signal", () => {
    const ctx = ctxFor(["mode"]);
    expect(yHover("mode", "y", ctx)).toBe("%{customdata}");
    expect(yHover("mode", "r", ctx)).toBe("%{customdata}");
  });
});

describe("enumTrace", () => {
  it("adds nothing for a numeric signal", () => {
    expect(enumTrace("a", [1, 2], ctxFor(["a"]))).toEqual({});
  });

  it("labels each point and puts the trace on the group's own axis", () => {
    const ctx = ctxFor(["a", "mode", "state"]);
    expect(enumTrace("mode", [0, 1, 1], ctx)).toEqual({ customdata: ["OFF (0)", "ON (1)", "ON (1)"], yaxis: "y2" });
    expect(enumTrace("state", [2, 0], ctx)).toEqual({ customdata: ["C (2)", "A (0)"], yaxis: "y3" });
  });

  it("keeps the trace on the primary axis when the first enum axis was promoted", () => {
    const ctx = ctxFor(["mode", "state"]);
    expect(ctx.enum.enumPromoted).toBe(true);
    expect(enumTrace("mode", [0, 1], ctx)).toEqual({ customdata: ["OFF (0)", "ON (1)"] });
    expect(enumTrace("state", [0], ctx)).toEqual({ customdata: ["A (0)"], yaxis: "y2" });
  });

  it("labels the points but names no axis in a polar plot", () => {
    expect(enumTrace("mode", [0, 1], ctxFor(["a", "mode"], { isPolar: true }))).toEqual({
      customdata: ["OFF (0)", "ON (1)"],
    });
  });

  it("gives a code the map does not name as the number", () => {
    expect((enumTrace("mode", [5], ctxFor(["a", "mode"])) as { customdata: string[] }).customdata).toEqual(["5"]);
  });
});

describe("primaryTraces", () => {
  const trace = (series: Series[], over: Parameters<typeof ctxFor>[1] = {}, d = data()) =>
    primaryTraces(series, d, "time", ctxFor(series.map((s) => s.key), { data: d, ...over }), COLORS);

  it("draws a signal as a line against the x column", () => {
    expect(trace([sig("a", { color: "#00ff00", width: 5, dash: "dash", opacity: 0.5 })])).toEqual([
      {
        x: [0, 1, 2],
        y: [10, 11, 12],
        name: "a",
        mode: "lines",
        type: "scatter",
        line: { width: 5, color: "#00ff00", shape: "linear", dash: "dash" },
        marker: { size: 6, symbol: "none" },
        opacity: 0.5,
        hoverlabel: {
          namelength: -1,
          bgcolor: "#111111",
          bordercolor: "#333333",
          font: { family: "monospace", size: 12, color: "#222222" },
        },
        hovertemplate: "<b>a</b><br>%{x}: %{y:.4f}<extra></extra>",
      },
    ]);
  });

  it("names a trace with its label and, if it has one, its unit with the spaces taken out", () => {
    const [t] = trace([sig("a", { label: "Speed" }, "m / s")]) as Array<{ name: string }>;
    expect(t!.name).toBe("Speed (m/s)");
    const [u] = trace([sig("a", { label: "Speed" }, null)]) as Array<{ name: string }>;
    expect(u!.name).toBe("Speed");
    const [v] = trace([sig("a", { label: "Speed" }, "")]) as Array<{ name: string }>;
    expect(v!.name).toBe("Speed");
  });

  it("keys the hover text by the signal's column name, not its label", () => {
    const [t] = trace([sig("a", { label: "Speed" })]) as Array<{ hovertemplate: string }>;
    expect(t!.hovertemplate).toContain("<b>a</b>");
  });

  it("skips a signal with no data and keeps the order of the rest", () => {
    const out = trace([sig("b"), sig("nodata"), sig("a")]) as Array<{ name: string }>;
    expect(out.map((t) => t.name)).toEqual(["b", "a"]);
  });

  it("is empty for no signals", () => {
    expect(trace([])).toEqual([]);
  });

  it("follows the plot's interpolation and line mode", () => {
    const [t] = trace([sig("a", { marker: "circle" })], { interp: "spline", lineMode: "markers" }) as Array<{
      mode: string;
      line: { shape: string };
    }>;
    expect(t!.line.shape).toBe("spline");
    expect(t!.mode).toBe("markers");
  });

  it("hides the markers of a signal whose marker is none, but not of one that has one", () => {
    const out = trace([sig("a", { marker: "none" }), sig("b", { marker: "circle" })], { lineMode: "lines+markers" }) as Array<{
      mode: string;
      marker: { symbol: string };
    }>;
    expect(out.map((t) => t.mode)).toEqual(["lines", "lines+markers"]);
    expect(out.map((t) => t.marker.symbol)).toEqual(["none", "circle"]);
  });

  it("draws an enum signal as a step line with its labels on its own axis", () => {
    const [t] = trace([sig("a"), sig("mode")]).slice(1) as Array<Record<string, unknown>>;
    expect(t).toMatchObject({
      y: [0, 1, 1],
      line: { shape: "hv" },
      customdata: ["OFF (0)", "ON (1)", "ON (1)"],
      yaxis: "y2",
      hovertemplate: "<b>mode</b><br>%{x}: %{customdata}<extra></extra>",
    });
  });

  it("draws a polar plot as r against theta", () => {
    const [t] = trace([sig("a", { width: 2 })], { isPolar: true }) as Array<Record<string, unknown>>;
    expect(t).toEqual({
      r: [10, 11, 12],
      theta: [0, 1, 2],
      name: "a",
      mode: "lines",
      type: "scatterpolar",
      line: { width: 2, color: "#ff0000", shape: "linear", dash: "solid" },
      marker: { size: 6, symbol: "none" },
      opacity: 1,
      hoverlabel: {
        namelength: -1,
        bgcolor: "#111111",
        bordercolor: "#333333",
        font: { family: "monospace", size: 12, color: "#222222" },
      },
      hovertemplate: "<b>a</b><br>θ: %{theta:.4f}<br>r: %{r:.4f}<extra></extra>",
    });
  });

  it("labels an enum signal in a polar plot but gives it no axis", () => {
    const [t] = trace([sig("a"), sig("mode")], { isPolar: true }).slice(1) as Array<Record<string, unknown>>;
    expect(t).toMatchObject({
      type: "scatterpolar",
      line: { shape: "linear" },
      customdata: ["OFF (0)", "ON (1)", "ON (1)"],
    });
    expect(t).not.toHaveProperty("yaxis");
    expect((t as { hovertemplate: string }).hovertemplate).toContain("r: %{customdata}");
  });

  it("uses the x column it is given", () => {
    const [t] = primaryTraces([sig("a")], data(), "b", ctxFor(["a"]), COLORS) as Array<{ x: number[] }>;
    expect(t!.x).toEqual([20, 21, 22]);
  });
});

describe("vsTraces", () => {
  const D = (a: number[]) => ({ time: [0, 1, 2], a, b: [7, 8, 9], mode: [0, 1, 0] });
  const run = (
    datasets: Record<string, Record<string, number[]>>,
    vs: { range: [number, number]; pinned?: number[] } = { range: [1, 10] },
    series: Series[] = [sig("a")],
    over: Parameters<typeof ctxFor>[1] = {},
    trialId = "run_5",
  ) => vsTraces(series, datasets, vs, trialId, "time", ctxFor(series.map((s) => s.key), { data: data(), ...over })) as Array<
    Record<string, any>
  >;

  it("is empty with no comparison trials", () => {
    expect(run({})).toEqual([]);
  });

  it("draws a faint dotted line for each signal of each trial in range", () => {
    const [t] = run({ run_2: D([1, 2, 3]) }, { range: [1, 10] }, [sig("a", { label: "Speed", color: "#00ff00", marker: "circle" })]);
    expect(t).toEqual({
      x: [0, 1, 2],
      y: [1, 2, 3],
      name: "Speed (<i>vs.</i>)",
      legendgroup: "group_a",
      showlegend: true,
      mode: "lines",
      type: "scatter",
      line: { width: 1, color: "#00ff00", shape: "linear", dash: "dot" },
      opacity: 0.35,
      marker: { size: 4, symbol: "circle" },
      hoverlabel: { namelength: -1 },
      hovertemplate: "<b>a</b> (#2)<br>%{x}: %{y:.4f}<extra></extra>",
    });
  });

  it("orders trials by their number, not as text", () => {
    const out = run({ run_10: D([10]), run_2: D([2]), run_1: D([1]) }, { range: [0, 99] });
    expect(out.map((t) => t.y[0])).toEqual([1, 2, 10]);
  });

  it("includes both ends of the range and nothing outside it", () => {
    const out = run({ run_1: D([1]), run_2: D([2]), run_3: D([3]), run_4: D([4]) }, { range: [2, 3] });
    expect(out.map((t) => t.y[0])).toEqual([2, 3]);
  });

  it("includes a pinned trial outside the range", () => {
    const out = run({ run_1: D([1]), run_8: D([8]), run_9: D([9]) }, { range: [1, 1], pinned: [8] });
    expect(out.map((t) => t.y[0])).toEqual([1, 8]);
  });

  it("works without any pinned trials", () => {
    expect(run({ run_2: D([2]) }, { range: [1, 5] })).toHaveLength(1);
  });

  it("leaves out the trial being viewed", () => {
    const out = run({ run_4: D([4]), run_5: D([5]), run_6: D([6]) }, { range: [1, 10] }, [sig("a")], {}, "run_5");
    expect(out.map((t) => t.y[0])).toEqual([4, 6]);
  });

  it("leaves out a trial id with no number", () => {
    expect(run({ weird: D([1]), run_x: D([2]) }, { range: [0, 99] })).toEqual([]);
  });

  it("shows a signal's legend entry once, on the first trial that has it", () => {
    const out = run({ run_1: D([1]), run_2: D([2]), run_3: D([3]) }, { range: [1, 3] }, [sig("a"), sig("b")]);
    const who = (t: Record<string, any>) => /<b>(\w+)<\/b> \(#(\d+)\)/.exec(t.hovertemplate)!.slice(1, 3).join("#");
    expect(out.map((t) => [who(t), t.showlegend])).toEqual([
      ["a#1", true],
      ["b#1", true],
      ["a#2", false],
      ["b#2", false],
      ["a#3", false],
      ["b#3", false],
    ]);
  });

  it("gives the legend entry to the first trial that has the signal when earlier ones lack it", () => {
    const out = run({ run_1: { time: [0], b: [1] }, run_2: D([2]) }, { range: [1, 2] }, [sig("a")]);
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({ showlegend: true });
    expect(out[0]!.hovertemplate).toContain("(#2)");
  });

  it("groups a signal's traces so one legend click toggles them all", () => {
    const out = run({ run_1: D([1]), run_2: D([2]) }, { range: [1, 2] });
    expect(out.map((t) => t.legendgroup)).toEqual(["group_a", "group_a"]);
  });

  it("skips signals a trial has no data for", () => {
    const out = run({ run_1: D([1]) }, { range: [1, 1] }, [sig("a"), sig("nodata"), sig("b")]);
    expect(out.map((t) => t.y)).toEqual([[1], [7, 8, 9]]);
  });

  it("follows the plot's interpolation and hides markers for a marker of none", () => {
    const [t] = run({ run_1: D([1]) }, { range: [1, 1] }, [sig("a", { marker: "none" })], { interp: "spline", lineMode: "lines+markers" });
    expect(t).toMatchObject({ mode: "lines", line: { shape: "spline" } });
  });

  it("draws a polar plot as r against theta", () => {
    const [t] = run({ run_2: D([1, 2, 3]) }, { range: [1, 10] }, [sig("a")], { isPolar: true });
    expect(t).toMatchObject({
      r: [1, 2, 3],
      theta: [0, 1, 2],
      type: "scatterpolar",
      opacity: 0.35,
      marker: { size: 4, symbol: "none" },
      hoverlabel: { namelength: -1 },
      hovertemplate: "<b>a</b> (#2)<br>θ: %{theta:.4f}<br>r: %{r:.4f}<extra></extra>",
    });
  });

  it("groups a polar signal's traces by its column name too, whatever its label", () => {
    const [t] = run({ run_2: D([1]) }, { range: [1, 10] }, [sig("a", { label: "Speed" })], { isPolar: true });
    expect(t).toMatchObject({ legendgroup: "group_a", name: "Speed (<i>vs.</i>)" });
  });

  it("labels an enum signal's points and puts it on its axis", () => {
    const out = run({ run_2: D([1]) }, { range: [1, 10] }, [sig("a"), sig("mode")]);
    expect(out[1]).toMatchObject({ customdata: ["OFF (0)", "ON (1)", "OFF (0)"], yaxis: "y2", line: { shape: "hv" } });
    expect(out[1]!.hovertemplate).toContain("%{customdata}");
  });

  it("labels an enum signal in a polar plot without an axis", () => {
    const out = run({ run_2: D([1]) }, { range: [1, 10] }, [sig("a"), sig("mode")], { isPolar: true });
    expect(out[1]).toMatchObject({ customdata: ["OFF (0)", "ON (1)", "OFF (0)"], line: { shape: "linear" } });
    expect(out[1]).not.toHaveProperty("yaxis");
  });
});
