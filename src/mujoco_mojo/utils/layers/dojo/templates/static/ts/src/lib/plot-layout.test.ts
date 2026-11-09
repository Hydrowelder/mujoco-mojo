import { describe, expect, it } from "vitest";

import type { PlotConfig, YAxisConfig } from "./plot-config.generated";
import { DEFAULT_CONFIG } from "./plot-defaults";
import {
  buildLayout,
  cartesianAxis,
  enumAxesLayout,
  frameLabel,
  hoverFlags,
  legendLayout,
  plotMargins,
  polarLayout,
  xAxisText,
  yAxisText,
  type LayoutColors,
  type LayoutInput,
} from "./plot-layout";
import { enumContext } from "./plot-traces";

const COLORS: LayoutColors = {
  text: "#010101",
  majorGrid: "#020202",
  minorGrid: "#030303",
  tooltipBg: "#040404",
  tooltipFont: "#050505",
  tooltipBorder: "#060606",
  spike: "#070707",
  title: "#080808",
};

describe("hoverFlags", () => {
  it("shows no spikes and no hover when hovering is off", () => {
    expect(hoverFlags("none", true)).toEqual({ isHoverDisabled: true, showX: false, showY: false });
  });

  it("shows both spikes on the closest point", () => {
    expect(hoverFlags("closest", true)).toEqual({ isHoverDisabled: false, showX: true, showY: true });
  });

  it("shows the x spike for x hover modes and the y spike for y modes", () => {
    for (const hover of ["x", "x unified"]) {
      expect(hoverFlags(hover, true)).toEqual({ isHoverDisabled: false, showX: true, showY: false });
    }
    for (const hover of ["y", "y unified"]) {
      expect(hoverFlags(hover, true)).toEqual({ isHoverDisabled: false, showX: false, showY: true });
    }
  });

  it("shows no spikes when they are switched off", () => {
    for (const hover of ["closest", "x", "y", "x unified", "y unified"]) {
      const f = hoverFlags(hover, false);
      expect([f.showX, f.showY]).toEqual([false, false]);
      expect(f.isHoverDisabled).toBe(false);
    }
  });
});

describe("xAxisText", () => {
  it("is the title set in the config", () => {
    expect(xAxisText("Time axis", "time", "s")).toBe("Time axis");
  });

  it("is the column with its unit, spaces removed, when no title is set", () => {
    expect(xAxisText("", "angle", "deg / s")).toBe("angle (deg/s)");
  });

  it("is just the column when it has no unit", () => {
    expect(xAxisText("", "angle", null)).toBe("angle");
    expect(xAxisText("", "angle", "")).toBe("angle");
  });
});

describe("yAxisText", () => {
  it("is the title set in the config", () => {
    expect(yAxisText("Torque", ["a"], ["N m"])).toBe("Torque");
  });

  it("mirrors the x-axis for a single signal", () => {
    expect(yAxisText("", ["speed"], ["m / s"])).toBe("speed (m/s)");
    expect(yAxisText("", ["speed"], [null])).toBe("speed");
  });

  it("is the shared unit when several signals agree on one", () => {
    expect(yAxisText("", ["a", "b"], ["N m", "N m"])).toBe("N m");
  });

  it("is blank when several signals disagree on their units, or one has none", () => {
    expect(yAxisText("", ["a", "b"], ["N m", "m"])).toBe("");
    expect(yAxisText("", ["a", "b"], ["N m", null])).toBe("");
    expect(yAxisText("", ["a", "b"], [null, null])).toBe("");
  });

  it("is blank with no numeric signals", () => {
    expect(yAxisText("", [], [])).toBe("");
  });

  it("does not say the unit twice for one signal that has none shared with others", () => {
    expect(yAxisText("", ["a", "b", "c"], ["m", "m", "m"])).toBe("m");
  });
});

describe("frameLabel", () => {
  it("is empty for the world frame", () => {
    expect(frameLabel([null, null], "#111111")).toBe("");
  });

  it("names the frame, in the text color, under the title", () => {
    expect(frameLabel(["body", "wing"], "#111111")).toBe(
      '<br><span style="color: #111111; font-size: 14px; opacity: 0.6;">[Frame: body @ wing]</span>',
    );
    expect(frameLabel(["body", null], "#111111")).toContain("[Frame: body]");
    expect(frameLabel([null, "wing"], "#111111")).toContain("[Frame: @ wing]");
  });
});

describe("cartesianAxis", () => {
  const axis = (over: Partial<Parameters<typeof cartesianAxis>[0]> = {}) =>
    cartesianAxis({
      scale: "linear",
      logBase: null,
      resolvedRange: null,
      grid: "all",
      title: "Title",
      showSpikes: true,
      colors: COLORS,
      ...over,
    }) as Record<string, any>;

  it("is a linear axis plotly sizes itself, by default", () => {
    expect(axis()).toEqual({
      type: "linear",
      autorange: true,
      dtick: undefined,
      gridcolor: "#020202",
      showgrid: true,
      minor: { showgrid: true, gridcolor: "#030303" },
      zeroline: false,
      tickfont: { color: "#010101", size: 14 },
      title: { text: "Title", font: { size: 14, color: "#010101", family: "monospace" } },
      showspikes: true,
      spikemode: "across",
      spikelinecolor: "#070707",
      spikethickness: -2,
    });
  });

  it("is linear when no scale is set", () => {
    expect(axis({ scale: undefined }).type).toBe("linear");
    expect(axis({ scale: null }).type).toBe("linear");
  });

  it("fixes the range when one is given", () => {
    const a = axis({ resolvedRange: [1, 5] });
    expect(a.autorange).toBe(false);
    expect(a.range).toEqual([1, 5]);
  });

  it("gives a log axis its range as exponents", () => {
    const a = axis({ scale: "log", resolvedRange: [1, 1000] });
    expect(a.type).toBe("log");
    expect(a.range).toEqual([0, 3]);
  });

  it("raises a log range's non-positive ends to 1e-6 first", () => {
    expect(axis({ scale: "log", resolvedRange: [0, 100] }).range).toEqual([-6, 2]);
    expect(axis({ scale: "log", resolvedRange: [-5, 100] }).range).toEqual([-6, 2]);
    expect(axis({ scale: "log", resolvedRange: [1, 0] }).range).toEqual([0, -6]);
  });

  it("does not take the log of a linear range", () => {
    expect(axis({ scale: "linear", resolvedRange: [0, 100] }).range).toEqual([0, 100]);
  });

  it("puts ticks a power of the log base apart on a log axis with a base", () => {
    expect(axis({ scale: "log", logBase: 10 }).dtick).toBe(1);
    expect(axis({ scale: "log", logBase: 100 }).dtick).toBe(2);
    expect(axis({ scale: "log", logBase: 2 }).dtick).toBeCloseTo(0.30103, 5);
  });

  it("leaves the tick spacing alone without a base, or on a linear axis", () => {
    expect(axis({ scale: "log", logBase: null }).dtick).toBeUndefined();
    expect(axis({ scale: "linear", logBase: 10 }).dtick).toBeUndefined();
  });

  it("shows the grid by mode: none, major lines only, or major and minor", () => {
    expect([axis({ grid: "none" }).showgrid, axis({ grid: "none" }).minor.showgrid]).toEqual([false, false]);
    expect([axis({ grid: "major" }).showgrid, axis({ grid: "major" }).minor.showgrid]).toEqual([true, false]);
    expect([axis({ grid: "all" }).showgrid, axis({ grid: "all" }).minor.showgrid]).toEqual([true, true]);
  });

  it("turns the spike lines on or off", () => {
    expect(axis({ showSpikes: false }).showspikes).toBe(false);
  });
});

describe("enumAxesLayout", () => {
  const D = { time: [0, 1, 2], a: [1, 2, 3], mode: [0, 1, 1], gear: [1, 0, 1], state: [0, 1, 4] };
  const META = {
    mode: { enumeration_map: { OFF: 0, ON: 1 } },
    gear: { enumeration_map: { OFF: 0, ON: 1 } },
    state: { enumeration_map: { A: 0, B: 1, C: 2 } },
  };
  const layout = (yKeys: string[], yAxisTitle = "", grid = "all") => {
    const ctx = enumContext(yKeys, D, META, false);
    return { ctx, out: enumAxesLayout(ctx, yAxisTitle, (c) => `label of ${c}`, D, COLORS, grid) as Record<string, any> };
  };

  it("is empty with no enum signals", () => {
    expect(layout(["a"]).out).toEqual({});
  });

  it("puts the first enum axis on yaxis2 beside numeric signals, overlaying the primary", () => {
    const { out } = layout(["a", "mode"]);
    expect(Object.keys(out)).toEqual(["yaxis2"]);
    expect(out["yaxis2"]).toMatchObject({
      side: "right",
      overlaying: "y",
      anchor: "free",
      autoshift: true,
      showgrid: false,
      tickvals: [0, 1],
      ticktext: ["OFF", "ON"],
    });
  });

  it("names the axis of a lone signal by that signal's label", () => {
    expect(layout(["a", "mode"]).out["yaxis2"].title.text).toBe("label of mode");
  });

  it("names a shared axis by how many signals it carries", () => {
    expect(layout(["a", "mode", "gear"]).out["yaxis2"].title.text).toBe("2 signals");
  });

  it("gives each distinct map its own axis, in order", () => {
    const { out } = layout(["a", "mode", "state"]);
    expect(Object.keys(out)).toEqual(["yaxis2", "yaxis3"]);
    expect(out["yaxis3"].tickvals).toEqual([0, 1, 2]);
  });

  it("sets each axis's range from its codes and the data outside them", () => {
    const { out } = layout(["a", "state"]);
    // codes 0..2, data reaches 4, padded by 6%
    expect(out["yaxis2"].range[0]).toBeCloseTo(-0.5);
    expect(out["yaxis2"].range[1]).toBeCloseTo(4.5);
  });

  it("takes the primary slot when promoted, with the grid and the config's y title", () => {
    const { ctx, out } = layout(["mode", "state"], "Custom y");
    expect(ctx.enumPromoted).toBe(true);
    expect(Object.keys(out)).toEqual(["yaxis", "yaxis2"]);
    expect(out["yaxis"]).toMatchObject({ automargin: true, showgrid: true, gridcolor: "#020202" });
    expect(out["yaxis"].overlaying).toBeUndefined();
    expect(out["yaxis"].title.text).toBe("Custom y");
    // only the primary axis takes the config's title
    expect(out["yaxis2"].title.text).toBe("label of state");
  });

  it("falls back to the signal's label for the primary axis without a y title", () => {
    expect(layout(["mode"]).out["yaxis"].title.text).toBe("label of mode");
  });

  it("shows the primary axis's grid unless the plot has none", () => {
    expect(layout(["mode"], "", "none").out["yaxis"].showgrid).toBe(false);
    expect(layout(["mode"], "", "major").out["yaxis"].showgrid).toBe(true);
    expect(layout(["mode"], "", "all").out["yaxis"].showgrid).toBe(true);
  });

  it("draws the ticks and title in the text color", () => {
    const { out } = layout(["a", "mode"]);
    expect(out["yaxis2"].tickfont.color).toBe("#010101");
    expect(out["yaxis2"].title.font.color).toBe("#010101");
  });
});

describe("polarLayout", () => {
  it("titles the radial axis with the y text and the angular axis with the x text", () => {
    const p = polarLayout(COLORS, "Torque", "angle") as { polar: Record<string, any> };
    expect(p.polar["radialaxis"].title.text).toBe("Torque");
    expect(p.polar["angularaxis"].title.text).toBe("angle");
  });

  it("calls the radial axis r when there is no y text", () => {
    expect((polarLayout(COLORS, "", "angle") as { polar: Record<string, any> }).polar["radialaxis"].title.text).toBe("r");
  });

  it("is transparent and drawn in the theme colors", () => {
    const { polar } = polarLayout(COLORS, "y", "x") as { polar: Record<string, any> };
    expect(polar["bgcolor"]).toBe("rgba(0,0,0,0)");
    for (const axis of [polar["radialaxis"], polar["angularaxis"]]) {
      expect(axis.color).toBe("#010101");
      expect(axis.gridcolor).toBe("#020202");
      expect(axis.tickfont).toEqual({ color: "#010101", size: 14, family: "monospace" });
    }
  });
});

describe("legendLayout", () => {
  it("runs down the right edge when the legend is on the right", () => {
    expect(legendLayout("right", false, "#111111")).toEqual({
      orientation: "v",
      x: 1.02,
      y: 1,
      font: { family: "monospace", size: 14, color: "#111111" },
      groupclick: "togglegroup",
    });
  });

  it("anchors to the container edge instead beside enum axes", () => {
    expect(legendLayout("right", true, "#111111")).toMatchObject({
      orientation: "v",
      xref: "container",
      x: 1,
      xanchor: "right",
      y: 1,
    });
  });

  it("runs along the bottom otherwise", () => {
    const expected = {
      orientation: "h",
      y: -0.2,
      x: 0.5,
      xanchor: "center",
      font: { family: "monospace", size: 14, color: "#111111" },
      groupclick: "togglegroup",
    };
    expect(legendLayout("bottom", false, "#111111")).toEqual(expected);
    expect(legendLayout("bottom", true, "#111111")).toEqual(expected);
    expect(legendLayout("hidden", false, "#111111")).toEqual(expected);
  });
});

describe("plotMargins", () => {
  it("is 30 all round except room for the bottom legend and the y title", () => {
    expect(plotMargins("", "bottom", false, false, "")).toEqual({ t: 30, r: 30, b: 80, l: 60 });
  });

  it("makes room for a title", () => {
    expect(plotMargins("My plot", "bottom", false, false, "").t).toBe(60);
  });

  it("makes room for a right-hand legend, but not beside enum axes", () => {
    expect(plotMargins("", "right", false, false, "").r).toBe(150);
    expect(plotMargins("", "right", true, false, "").r).toBe(30);
    expect(plotMargins("", "bottom", false, false, "").r).toBe(30);
  });

  it("leaves less room at the bottom without a bottom legend", () => {
    expect(plotMargins("", "right", false, false, "").b).toBe(50);
    expect(plotMargins("", "hidden", false, false, "").b).toBe(50);
  });

  it("makes more room at the left for a y title, and little when an enum axis took that slot", () => {
    expect(plotMargins("", "bottom", false, false, "Torque").l).toBe(80);
    expect(plotMargins("", "bottom", false, false, "").l).toBe(60);
    expect(plotMargins("", "bottom", true, true, "Torque").l).toBe(30);
  });
});

describe("buildLayout", () => {
  const yAxis = (): YAxisConfig => ({ color: "#ff0000", filters: [] });
  const cfg = (over: Partial<PlotConfig> = {}): PlotConfig => ({
    ...(JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as PlotConfig),
    yAxes: { a: yAxis() },
    ...over,
  });
  const D = { time: [0, 1, 2], a: [1, 2, 3], b: [4, 5, 6], mode: [0, 1, 0] };
  const META = { mode: { enumeration_map: { OFF: 0, ON: 1 } } };

  const input = (config: PlotConfig, over: Partial<LayoutInput> = {}): LayoutInput => {
    const isPolar = config.plotType === "polar";
    return {
      trialId: "run_7",
      config,
      isPolar,
      enum: enumContext(Object.keys(config.yAxes), D, META, isPolar),
      resolvedRangeX: null,
      resolvedRangeY: null,
      xUnit: null,
      yUnitList: [null],
      labelOf: (c) => c,
      data: D,
      colors: COLORS,
      overlays: { annotations: [], shapes: [] },
      ...over,
    };
  };
  const build = (config: PlotConfig, over: Partial<LayoutInput> = {}) => buildLayout(input(config, over)) as Record<string, any>;

  it("lays a plain plot out with axes, a legend below and no title", () => {
    const l = build(cfg());
    expect(l["title"]).toBeNull();
    expect(l["paper_bgcolor"]).toBe("rgba(0,0,0,0)");
    expect(l["plot_bgcolor"]).toBe("rgba(0,0,0,0)");
    expect(l["margin"]).toEqual({ t: 30, r: 30, b: 80, l: 80 });
    expect(l["hovermode"]).toBe("closest");
    expect(l["showlegend"]).toBe(true);
    expect(l["legend"]).toMatchObject({ orientation: "h", y: -0.2 });
    expect(l["xaxis"].title.text).toBe("time");
    expect(l["yaxis"].title.text).toBe("a");
    expect(l["annotations"]).toEqual([]);
    expect(l["shapes"]).toEqual([]);
    expect(l).not.toHaveProperty("polar");
  });

  it("names the plot's view by trial, x column, signals and type, so a change of any resets the zoom", () => {
    const l = build(cfg({ yAxes: { a: yAxis(), b: yAxis() } }));
    expect(l["uirevision"]).toBe("run_7_time_a_b_cartesian");
    expect(build(cfg({ plotType: "polar" }))["uirevision"]).toBe("run_7_time_a_polar");
    expect(build(cfg(), { trialId: "run_8" })["uirevision"]).toBe("run_8_time_a_cartesian");
  });

  it("shows a title in bold monospace at the left, with more room above it", () => {
    const l = build(cfg({ title: "My plot" }));
    expect(l["title"]).toEqual({
      text: "My plot",
      font: { family: "monospace", size: 16, color: "#080808", weight: "bold" },
      x: 0,
      xanchor: "left",
    });
    expect(l["margin"].t).toBe(60);
  });

  it("has no hover when hovering is off, and otherwise the hover mode", () => {
    expect(build(cfg({ hover: "none" }))["hovermode"]).toBe(false);
    expect(build(cfg({ hover: "x unified" }))["hovermode"]).toBe("x unified");
  });

  it("styles the tooltip with the theme colors", () => {
    expect(build(cfg())["hoverlabel"]).toEqual({
      bgcolor: "#040404",
      bordercolor: "#060606",
      font: { family: "monospace", size: 12, color: "#050505" },
      align: "left",
    });
  });

  it("hides the legend when asked to", () => {
    expect(build(cfg({ legendPos: "hidden" }))["showlegend"]).toBe(false);
    expect(build(cfg({ legendPos: "right" }))["showlegend"]).toBe(true);
  });

  it("shows the spike lines on the axes the hover mode calls for", () => {
    const l = build(cfg({ hover: "x", showSpike: true }));
    expect([l["xaxis"].showspikes, l["yaxis"].showspikes]).toEqual([true, false]);
  });

  it("puts the unit in the axis titles", () => {
    const l = build(cfg(), { xUnit: "s", yUnitList: ["m / s"] });
    expect(l["xaxis"].title.text).toBe("time (s)");
    expect(l["yaxis"].title.text).toBe("a (m/s)");
  });

  it("puts the reference frame under the y-axis title", () => {
    const l = build(cfg({ refFrame: ["body", null] }));
    expect(l["yaxis"].title.text).toBe(
      'a<br><span style="color: #010101; font-size: 14px; opacity: 0.6;">[Frame: body]</span>',
    );
  });

  it("fixes the axes to the ranges it is given", () => {
    const l = build(cfg(), { resolvedRangeX: [1, 2], resolvedRangeY: [3, 4] });
    expect(l["xaxis"]).toMatchObject({ autorange: false, range: [1, 2] });
    expect(l["yaxis"]).toMatchObject({ autorange: false, range: [3, 4] });
  });

  it("uses each axis's own scale and log base", () => {
    const l = build(cfg({ xScale: "log", xLogBase: 10, yScale: "linear", yLogBase: 10 }));
    expect([l["xaxis"].type, l["xaxis"].dtick]).toEqual(["log", 1]);
    expect([l["yaxis"].type, l["yaxis"].dtick]).toEqual(["linear", undefined]);
  });

  it("passes the annotations and shapes through", () => {
    const l = build(cfg(), { overlays: { annotations: [{ n: 1 }], shapes: [{ s: 1 }, { s: 2 }] } });
    expect(l["annotations"]).toEqual([{ n: 1 }]);
    expect(l["shapes"]).toEqual([{ s: 1 }, { s: 2 }]);
  });

  it("adds a right-hand axis per enum map, and takes the legend and margin off the plot edge", () => {
    const l = build(cfg({ yAxes: { a: yAxis(), mode: yAxis() }, legendPos: "right" }), { yUnitList: [null] });
    expect(l["yaxis2"]).toMatchObject({ side: "right", tickvals: [0, 1] });
    expect(l["legend"]).toMatchObject({ xref: "container", x: 1 });
    expect(l["margin"].r).toBe(30);
    // the numeric axis is named after the numeric signal only
    expect(l["yaxis"].title.text).toBe("a");
  });

  it("lets an enum axis take the primary slot when only enum signals are drawn", () => {
    const l = build(cfg({ yAxes: { mode: yAxis() } }), { yUnitList: [] });
    expect(l["yaxis"]).toMatchObject({ side: "right", tickvals: [0, 1] });
    expect(l["margin"].l).toBe(30);
  });

  it("lays a polar plot out with a polar axis pair instead of x and y axes", () => {
    const l = build(cfg({ plotType: "polar", yAxisTitle: "Torque" }), { xUnit: "rad" });
    expect(l["polar"].radialaxis.title.text).toBe("Torque");
    expect(l["polar"].angularaxis.title.text).toBe("time (rad)");
    expect(l).not.toHaveProperty("xaxis");
    expect(l).not.toHaveProperty("yaxis");
    expect(Object.keys(l).some((k) => /^yaxis\d/.test(k))).toBe(false);
  });

  it("gives a polar plot no enum axes, whatever it plots", () => {
    const l = build(cfg({ plotType: "polar", yAxes: { a: yAxis(), mode: yAxis() } }));
    expect(Object.keys(l).some((k) => k.startsWith("yaxis"))).toBe(false);
  });
});
