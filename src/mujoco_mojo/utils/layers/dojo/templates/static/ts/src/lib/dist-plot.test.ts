import { describe, expect, it } from "vitest";

import type { DistEntry } from "../models";
import {
  distPlot,
  formatParam,
  hasTooltipContent,
  paramsHtml,
  tooltipMinWidth,
  tooltipPosition,
  type DistColors,
} from "./dist-plot";

// the traces and layout a plot has, read loosely since plotly's own types are not used here
interface PlotOut {
  traces: any[];
  layout: any;
}

const COLORS: DistColors = {
  bg: "#010101",
  text: "#020202",
  curve: "#030303",
  cdf: "#040404",
  fill: "#05050512",
  sampled: "#060606",
  nominal: "#070707",
};

const entry = (over: Partial<DistEntry> = {}): DistEntry => ({
  name: "mass",
  dist_type: "normal",
  category: "body",
  units: "kg",
  nominal: 1.5,
  nominal_label: null,
  sampled_value: null,
  sampled_values: null,
  sampled_labels: null,
  sampled_permutations: null,
  z_score: null,
  percentile: null,
  is_discrete: false,
  chart_type: "continuous",
  pdf_x: [0, 1, 2],
  pdf_y: [0.1, 0.4, 0.1],
  cdf_x: [0, 1, 2],
  cdf_y: [0.1, 0.5, 1],
  cat_labels: [],
  cat_probs: [],
  params: { mean: 1, std: 0.5 },
  ...over,
});

describe("hasTooltipContent", () => {
  it("is true with a curve to draw", () => {
    expect(hasTooltipContent(entry({ params: {} }))).toBe(true);
  });

  it("is true with categorical choices to draw", () => {
    expect(hasTooltipContent(entry({ pdf_x: [], params: {}, cat_labels: ["a"] }))).toBe(true);
  });

  it("is true with only parameters to list", () => {
    expect(hasTooltipContent(entry({ pdf_x: [], cat_labels: [], params: { n: 3 } }))).toBe(true);
  });

  it("is false with nothing to show", () => {
    expect(hasTooltipContent(entry({ pdf_x: [], cat_labels: [], params: {} }))).toBe(false);
  });
});

describe("tooltipMinWidth", () => {
  it("is 340px for anything but a categorical distribution", () => {
    for (const type of ["continuous", "discrete", "permutation", "none"]) {
      expect(tooltipMinWidth(type, 30)).toBe(340);
    }
  });

  it("grows with the number of choices of a categorical one, 52px each", () => {
    expect(tooltipMinWidth("categorical", 7)).toBe(364);
    expect(tooltipMinWidth("categorical", 8)).toBe(416);
    expect(tooltipMinWidth("categorical", 10)).toBe(520);
  });

  it("is at least 340px and at most 560px", () => {
    expect(tooltipMinWidth("categorical", 0)).toBe(340);
    expect(tooltipMinWidth("categorical", 6)).toBe(340);
    expect(tooltipMinWidth("categorical", 10)).toBe(520);
    expect(tooltipMinWidth("categorical", 11)).toBe(560);
    expect(tooltipMinWidth("categorical", 40)).toBe(560);
  });
});

describe("tooltipPosition", () => {
  it("sits right of and above the cursor when it fits", () => {
    expect(tooltipPosition(100, 300, 340, 1024)).toEqual({ left: 118, top: 190 });
  });

  it("still fits when it ends exactly 20px from the right edge", () => {
    // 600 + 18 + 340 + 20 = 978
    expect(tooltipPosition(600, 300, 340, 978)).toEqual({ left: 618, top: 190 });
  });

  it("flips to the left of the cursor when it would not fit", () => {
    expect(tooltipPosition(600, 300, 340, 977)).toEqual({ left: 242, top: 190 });
    expect(tooltipPosition(900, 300, 340, 1024)).toEqual({ left: 542, top: 190 });
  });

  it("never goes closer than 8px to the left edge", () => {
    expect(tooltipPosition(100, 300, 340, 200)).toEqual({ left: 8, top: 190 });
  });

  it("never goes closer than 8px to the top edge", () => {
    expect(tooltipPosition(100, 0, 340, 1024).top).toBe(8);
    expect(tooltipPosition(100, 118, 340, 1024).top).toBe(8);
    expect(tooltipPosition(100, 119, 340, 1024).top).toBe(9);
  });
});

describe("distPlot", () => {
  it("has no chart for a permutation or a distribution with no chart type", () => {
    expect(distPlot(entry({ chart_type: "permutation" }), COLORS)).toBeNull();
    expect(distPlot(entry({ chart_type: "none" }), COLORS)).toBeNull();
  });

  describe("categorical", () => {
    const cat = (over: Partial<DistEntry> = {}) =>
      entry({ chart_type: "categorical", cat_labels: ["a", "b", "c"], cat_probs: [0.2, 0.5, 0.3], pdf_x: [], ...over });
    const plot = (over: Partial<DistEntry> = {}): PlotOut => distPlot(cat(over), COLORS)!;

    it("draws one bar per choice", () => {
      expect(plot().traces).toEqual([
        { x: ["a", "b", "c"], y: [0.2, 0.5, 0.3], type: "bar", marker: { color: ["#030303", "#030303", "#030303"], opacity: 0.85 }, hoverinfo: "x+y" },
      ]);
    });

    it("colors the sampled choices differently", () => {
      expect(plot({ sampled_labels: ["b"] }).traces[0].marker.color).toEqual(["#030303", "#060606", "#030303"]);
      expect(plot({ sampled_labels: ["a", "c"] }).traces[0].marker.color).toEqual(["#060606", "#030303", "#060606"]);
    });

    it("labels each bar with its percentage to one decimal", () => {
      const { annotations } = plot().layout;
      expect(annotations.map((a: any) => [a.x, a.y, a.text])).toEqual([
        ["a", 0.2, "20.0%"],
        ["b", 0.5, "50.0%"],
        ["c", 0.3, "30.0%"],
      ]);
      expect(annotations[0]).toMatchObject({ showarrow: false, yanchor: "bottom", yshift: 2, font: { size: 9, color: "#020202" } });
    });

    it("counts a missing probability as zero", () => {
      const p = plot({ cat_probs: [null as unknown as number, 0.5] });
      expect(p.layout.annotations.map((a: any) => [a.y, a.text])).toEqual([
        [0, "0.0%"],
        [0.5, "50.0%"],
        [0, "0.0%"],
      ]);
    });

    it("leaves room above the tallest bar for its label", () => {
      expect(plot().layout.yaxis.range).toEqual([0, 0.5 * 1.2]);
      expect(plot({ cat_probs: [0, 0, 0] }).layout.yaxis.range).toEqual([0, 0]);
    });

    it("has a flat range, not an infinite one, with no choices at all", () => {
      const p = plot({ cat_labels: [], cat_probs: [] });
      expect(p.layout.yaxis.range).toEqual([0, 0]);
      expect(p.layout.annotations).toEqual([]);
    });

    it("tilts the labels once there are more than five choices", () => {
      const five = plot({ cat_labels: ["a", "b", "c", "d", "e"], cat_probs: [1, 1, 1, 1, 1] });
      const six = plot({ cat_labels: ["a", "b", "c", "d", "e", "f"], cat_probs: [1, 1, 1, 1, 1, 1] });
      expect(five.layout.xaxis.tickangle).toBe(0);
      expect(six.layout.xaxis.tickangle).toBe(-30);
    });

    it("uses the theme colors and hides the legend", () => {
      const { layout } = plot();
      expect(layout).toMatchObject({
        paper_bgcolor: "#010101",
        plot_bgcolor: "#010101",
        margin: { t: 22, r: 10, b: 52, l: 52 },
        showlegend: false,
        font: { size: 11, color: "#020202" },
      });
      expect(layout.yaxis.title).toEqual({ text: "Probability", font: { size: 13 }, standoff: 4 });
    });
  });

  describe("continuous", () => {
    const plot = (over: Partial<DistEntry> = {}): PlotOut => distPlot(entry(over), COLORS)!;

    it("draws the density as a filled line and the CDF on a second axis", () => {
      const { traces } = plot();
      expect(traces).toEqual([
        {
          x: [0, 1, 2],
          y: [0.1, 0.4, 0.1],
          type: "scatter",
          mode: "lines",
          fill: "tozeroy",
          line: { color: "#030303", width: 1.5 },
          fillcolor: "#05050512",
          name: "PDF",
          hoverinfo: "x+y",
        },
        {
          x: [0, 1, 2],
          y: [0.1, 0.5, 1],
          type: "scatter",
          mode: "lines",
          line: { color: "#040404", width: 1.5, shape: "linear" },
          name: "CDF",
          yaxis: "y2",
          hoverinfo: "x+y",
        },
      ]);
    });

    it("treats an unknown chart type as continuous", () => {
      expect(plot({ chart_type: "weird" as never }).traces[0].name).toBe("PDF");
    });

    it("titles the axes and puts the CDF axis on the right from 0 to 1", () => {
      const { layout } = plot();
      expect(layout.yaxis.title.text).toBe("Probability Density");
      expect(layout.yaxis.color).toBe("#030303");
      expect(layout.yaxis2).toMatchObject({ overlaying: "y", side: "right", range: [0, 1], tickformat: ".1f" });
      expect(layout.yaxis2.title).toEqual({ text: "CDF", font: { size: 12, color: "#040404" }, standoff: 2 });
      expect(layout.yaxis2.tickfont).toEqual({ size: 10, color: "#040404" });
    });

    it("names the x-axis with the units and makes room for the title", () => {
      const { layout } = plot({ units: "kg" });
      expect(layout.xaxis.title).toEqual({ text: "kg", font: { size: 13 }, standoff: 4 });
      expect(layout.margin).toEqual({ t: 14, r: 48, b: 46, l: 64 });
    });

    it("leaves the x-axis untitled with no units, or the unset marker", () => {
      for (const units of ["", "unset"]) {
        const { layout } = plot({ units });
        expect(layout.xaxis).not.toHaveProperty("title");
        expect(layout.margin).toEqual({ t: 14, r: 48, b: 32, l: 64 });
      }
    });

    it("marks the nominal value with a dotted line", () => {
      expect(plot({ nominal: 1.5 }).layout.shapes).toEqual([
        { type: "line", x0: 1.5, x1: 1.5, y0: 0, y1: 1, yref: "paper", line: { color: "#070707", width: 1.5, dash: "dot" } },
      ]);
    });

    it("marks a nominal of zero too", () => {
      expect(plot({ nominal: 0 }).layout.shapes).toHaveLength(1);
    });

    it("marks nothing for a missing or non-numeric nominal", () => {
      expect(plot({ nominal: null }).layout.shapes).toEqual([]);
      expect(plot({ nominal: "text" as unknown as number }).layout.shapes).toEqual([]);
    });

    it("marks each sampled value with a solid line, after the nominal", () => {
      const { shapes } = plot({ nominal: 1, sampled_values: [0.5, 2] }).layout;
      expect(shapes.map((s: any) => [s.x0, s.line.dash, s.line.width, s.line.color])).toEqual([
        [1, "dot", 1.5, "#070707"],
        [0.5, "solid", 2, "#060606"],
        [2, "solid", 2, "#060606"],
      ]);
    });

    it("marks no sampled values when there are none", () => {
      expect(plot({ nominal: null, sampled_values: null }).layout.shapes).toEqual([]);
      expect(plot({ nominal: null, sampled_values: [] }).layout.shapes).toEqual([]);
    });

    it("uses the theme colors and hides the legend", () => {
      expect(plot().layout).toMatchObject({
        paper_bgcolor: "#010101",
        plot_bgcolor: "#010101",
        showlegend: false,
        font: { size: 11, color: "#020202" },
      });
      expect(plot().layout.xaxis).toMatchObject({ color: "#020202", showgrid: false });
    });
  });

  describe("discrete", () => {
    const plot = (over: Partial<DistEntry> = {}): PlotOut => distPlot(entry({ chart_type: "discrete", ...over }), COLORS)!;

    it("draws the probabilities as bars", () => {
      expect(plot().traces[0]).toEqual({
        x: [0, 1, 2],
        y: [0.1, 0.4, 0.1],
        type: "bar",
        marker: { color: "#030303", opacity: 0.75 },
        name: "P(x)",
        hoverinfo: "x+y",
      });
    });

    it("draws the CDF as a step line", () => {
      expect(plot().traces[1].line).toEqual({ color: "#040404", width: 1.5, shape: "hv" });
    });

    it("titles the y-axis probability, not density", () => {
      expect(plot().layout.yaxis.title.text).toBe("Probability");
    });

    it("marks the nominal and sampled values like a continuous one", () => {
      expect(plot({ nominal: 2, sampled_values: [1] }).layout.shapes).toHaveLength(2);
    });
  });
});

describe("formatParam", () => {
  it.each([
    [0, "0"],
    [1, "1"],
    [10, "10"],
    [100, "100"],
    [120, "120"],
    [12.3456789, "12.35"],
    [0.5, "0.5"],
    [-3.5, "-3.5"],
    [999.9, "999.9"],
    [0.01, "0.01"],
    [0.0123, "0.01230".replace(/0+$/, "")],
  ])("shows %s as %s", (v, expected) => {
    expect(formatParam(v)).toBe(expected);
  });

  it.each([
    [1000, "1.000e+3"],
    [1234.5678, "1.235e+3"],
    [-5000, "-5.000e+3"],
    [5e12, "5.000e+12"],
    [0.00123, "1.230e-3"],
    [-0.005, "-5.000e-3"],
    [1e-9, "1.000e-9"],
  ])("shows %s in scientific notation as %s", (v, expected) => {
    expect(formatParam(v)).toBe(expected);
  });

  it("shows a string or boolean as it is", () => {
    expect(formatParam("normal")).toBe("normal");
    expect(formatParam(true)).toBe("true");
    expect(formatParam(false)).toBe("false");
    expect(formatParam("")).toBe("");
  });
});

describe("paramsHtml", () => {
  it("lists each parameter in order, its name dimmed", () => {
    expect(paramsHtml(entry({ params: { mean: 1, std: 0.5 } }))).toBe(
      '<span><span class="text-ink-muted">mean:</span> 1</span><span><span class="text-ink-muted">std:</span> 0.5</span>',
    );
  });

  it("formats the values", () => {
    expect(paramsHtml(entry({ params: { n: 12345, kind: "a", on: true } }))).toBe(
      '<span><span class="text-ink-muted">n:</span> 1.235e+4</span>' +
        '<span><span class="text-ink-muted">kind:</span> a</span>' +
        '<span><span class="text-ink-muted">on:</span> true</span>',
    );
  });

  it("is empty with no parameters", () => {
    expect(paramsHtml(entry({ params: {} }))).toBe("");
  });

  it("is empty for a categorical distribution, whose bars carry the numbers", () => {
    expect(paramsHtml(entry({ chart_type: "categorical", params: { a: 1 } }))).toBe("");
  });

  it("lists the parameters of discrete, permutation and unknown types too", () => {
    for (const chart_type of ["discrete", "permutation", "none", "continuous"] as const) {
      expect(paramsHtml(entry({ chart_type, params: { a: 1 } }))).toContain("a:");
    }
  });

  // the list is set as innerHTML, so a name or value with markup in it has to
  // be shown as text
  it("escapes html in a parameter name or value", () => {
    const html = paramsHtml(entry({ params: { "<img src=x>": "<b>bold</b>" } }));
    expect(html).toBe(
      '<span><span class="text-ink-muted">&lt;img src=x&gt;:</span> &lt;b&gt;bold&lt;/b&gt;</span>',
    );
  });

  it("escapes quotes and ampersands too", () => {
    const html = paramsHtml(entry({ params: { 'a"b': "x & 'y'" } }));
    expect(html).toContain('a&quot;b:');
    expect(html).toContain("x &amp; &#39;y&#39;");
  });

  it("leaves a number as formatParam writes it", () => {
    expect(paramsHtml(entry({ params: { mean: 1234.5 } }))).toContain("1.235e+3");
    expect(paramsHtml(entry({ params: { small: -0.5 } }))).toContain("-0.5");
  });
});
