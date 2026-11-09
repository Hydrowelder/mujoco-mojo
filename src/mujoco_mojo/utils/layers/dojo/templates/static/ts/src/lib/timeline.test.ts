import { describe, expect, it } from "vitest";

import type { TimelineBin } from "../models";
import { isNarrowTimeline, timelineLayout, timelineTraces, type TimelineColors } from "./timeline";

const COLORS: TimelineColors = {
  font: "#010101",
  grid: "#020202",
  success: "#030303",
  danger: "#040404",
  warning: "#050505",
  info: "#060606",
  accent: "#070707",
  tooltipBg: "#080808",
  tooltipFont: "#090909",
};

const bin = (i: number, over: Partial<TimelineBin> = {}): TimelineBin => ({
  t: i,
  label: `2026-01-01T00:00:0${i}.000123`,
  n_success: i,
  n_failed: i + 10,
  n_error: i + 20,
  n_running: i + 30,
  n_pending: i + 40,
  ...over,
});

describe("isNarrowTimeline", () => {
  it("is narrow below 560px", () => {
    expect(isNarrowTimeline(1)).toBe(true);
    expect(isNarrowTimeline(300)).toBe(true);
    expect(isNarrowTimeline(559)).toBe(true);
  });

  it("is not narrow from 560px up", () => {
    expect(isNarrowTimeline(560)).toBe(false);
    expect(isNarrowTimeline(900)).toBe(false);
  });

  it("is not narrow before it has been laid out", () => {
    expect(isNarrowTimeline(0)).toBe(false);
  });
});

describe("timelineTraces", () => {
  const bins = [bin(1), bin(2), bin(3)];

  it("makes one bar series per outcome, in stacking order", () => {
    const t = timelineTraces(bins, COLORS) as Array<{ name: string; type: string }>;
    expect(t.map((x) => [x.name, x.type])).toEqual([
      ["Success", "bar"],
      ["Failure", "bar"],
      ["Error", "bar"],
      ["Running", "bar"],
      ["Pending", "bar"],
    ]);
  });

  it("takes each series from its own count, over the bins' labels", () => {
    const t = timelineTraces(bins, COLORS) as Array<{ x: string[]; y: number[] }>;
    const labels = bins.map((b) => b.label);
    for (const series of t) expect(series.x).toEqual(labels);
    expect(t.map((x) => x.y)).toEqual([
      [1, 2, 3],
      [11, 12, 13],
      [21, 22, 23],
      [31, 32, 33],
      [41, 42, 43],
    ]);
  });

  it("colors each outcome with its own theme color", () => {
    const t = timelineTraces(bins, COLORS) as Array<{ marker: { color: string } }>;
    expect(t.map((x) => x.marker.color)).toEqual(["#030303", "#040404", "#050505", "#060606", "#070707"]);
  });

  it("is five empty series with no bins", () => {
    const t = timelineTraces([], COLORS) as Array<{ x: string[]; y: number[] }>;
    expect(t).toHaveLength(5);
    expect(t.every((s) => s.x.length === 0 && s.y.length === 0)).toBe(true);
  });
});

describe("timelineLayout", () => {
  const wide = timelineLayout(false, COLORS) as Record<string, any>;
  const narrow = timelineLayout(true, COLORS) as Record<string, any>;

  it("stacks the bars in a transparent chart", () => {
    expect(wide).toMatchObject({
      autosize: true,
      barmode: "stack",
      bargap: 0.15,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      showlegend: true,
      hovermode: "x unified",
    });
  });

  it("makes room below the plot for a legend that wrapped, on narrow screens", () => {
    expect(wide["margin"]).toEqual({ l: 45, r: 10, t: 10, b: 55 });
    expect(narrow["margin"]).toEqual({ l: 45, r: 10, t: 10, b: 110 });
  });

  it("puts the legend above the plot, or below it on a narrow screen", () => {
    expect(wide["legend"]).toEqual({ orientation: "h", y: 1.15, x: 0 });
    expect(narrow["legend"]).toEqual({ orientation: "h", x: 0.5, xanchor: "center", y: -0.45, yanchor: "top", font: { size: 10 } });
  });

  it("reads the x-axis as a clock time, with a spike line across the plot", () => {
    expect(wide["xaxis"]).toEqual({
      type: "date",
      tickformat: "%H:%M:%S",
      gridcolor: "#020202",
      tickangle: -45,
      nticks: 8,
      showspikes: true,
      spikemode: "across",
      spikelinecolor: "#070707",
      spikethickness: -2,
    });
  });

  it("titles the y-axis trials", () => {
    expect(wide["yaxis"]).toEqual({ gridcolor: "#020202", title: { text: "trials" } });
  });

  it("uses the theme colors for text and the tooltip", () => {
    expect(wide["font"]).toEqual({ color: "#010101", family: "monospace", size: 11 });
    expect(wide["hoverlabel"]).toEqual({
      bgcolor: "#080808",
      bordercolor: "#070707",
      font: { color: "#090909", family: "monospace", size: 12 },
      align: "left",
    });
  });
});
