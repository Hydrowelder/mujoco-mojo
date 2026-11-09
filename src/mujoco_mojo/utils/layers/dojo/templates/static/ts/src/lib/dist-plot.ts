// the distribution tooltip of the trial viewer, moved out of trial-viewer.ts
// so it can be tested without an alpine component: where the tooltip sits, how
// wide it is, the chart it draws for each kind of distribution, and the
// parameter list under it.

import type { DistEntry } from "../models";
import { escapeHtml } from "./html";

// the theme colors the tooltip chart uses, resolved by the caller
export interface DistColors {
  bg: string;
  text: string;
  // the PDF curve, and the axis it sits on
  curve: string;
  cdf: string;
  fill: string;
  // the value(s) this trial sampled
  sampled: string;
  nominal: string;
}

// a distribution with neither a chart nor parameters has nothing to show
export function hasTooltipContent(entry: DistEntry): boolean {
  const hasChart = entry.pdf_x.length > 0 || entry.cat_labels.length > 0;
  const hasParams = Object.keys(entry.params).length > 0;
  return hasChart || hasParams;
}

// widen the tooltip for a categorical distribution with many choices so its bars have room
export function tooltipMinWidth(chartType: string, labelCount: number): number {
  return chartType === "categorical"
    ? Math.min(560, Math.max(340, labelCount * 52))
    : 340;
}

// where the tooltip goes: just right of and above the cursor, flipped to the
// left of it when too close to the right edge so the cursor never lands inside
// the tooltip (Plotly's SVG overrides pointer-events on child elements,
// causing mouseleave/mouseenter flicker if the cursor enters the tooltip
// bounds). Never closer than 8px to the left or top edge.
export function tooltipPosition(
  clientX: number,
  clientY: number,
  minWidth: number,
  innerWidth: number,
): { left: number; top: number } {
  const x = clientX + 18;
  const y = clientY - 110;
  const fitsRight = x + minWidth + 20 <= innerWidth;
  return {
    left: fitsRight ? x : Math.max(8, clientX - minWidth - 18),
    top: Math.max(8, y),
  };
}

// the chart for a distribution, or null when it has none (a permutation, or
// no chart type): bars of each choice's probability for a categorical one; for
// a continuous or discrete one the PDF (or PMF bars) with the CDF on a second
// axis, a dotted line at the nominal value and a line at each sampled value.
export function distPlot(
  entry: DistEntry,
  colors: DistColors,
): { traces: object[]; layout: object } | null {
  const chartType = entry.chart_type;
  const { bg, text: textColor, curve: curveColor, cdf: cdfColor, fill: fillColor, sampled: sampledColor } = colors;

  if (chartType === "permutation" || chartType === "none") return null;

  if (chartType === "categorical") {
    const barColors = entry.cat_labels.map((lbl) =>
      entry.sampled_labels?.includes(lbl) ? sampledColor : curveColor,
    );
    const traces = [
      {
        x: entry.cat_labels,
        y: entry.cat_probs,
        type: "bar",
        marker: { color: barColors, opacity: 0.85 },
        hoverinfo: "x+y",
      },
    ];
    const maxProb = Math.max(...entry.cat_probs.map((p) => p ?? 0), 0);
    const annotations = entry.cat_labels.map((lbl, i) => ({
      x: lbl,
      y: entry.cat_probs[i] ?? 0,
      text: `${((entry.cat_probs[i] ?? 0) * 100).toFixed(1)}%`,
      showarrow: false,
      yanchor: "bottom",
      yshift: 2,
      font: { size: 9, color: textColor },
    }));
    const layout = {
      paper_bgcolor: bg,
      plot_bgcolor: bg,
      margin: { t: 22, r: 10, b: 52, l: 52 },
      xaxis: {
        color: textColor,
        showgrid: false,
        tickfont: { size: 10 },
        tickangle: entry.cat_labels.length > 5 ? -30 : 0,
      },
      yaxis: {
        color: textColor,
        showgrid: false,
        tickfont: { size: 11 },
        title: {
          text: "Probability",
          font: { size: 13 },
          standoff: 4,
        },
        // extend range above max bar so annotations have room
        range: [0, maxProb * 1.2],
      },
      annotations,
      showlegend: false,
      font: { size: 11, color: textColor },
    };
    return { traces, layout };
  }

  // continuous or discrete: PDF/PMF + CDF on secondary y-axis
  const unitsLabel =
    entry.units !== "unset" && entry.units !== "" ? entry.units : "";

  const shapes: object[] = [];
  if (entry.nominal !== null && typeof entry.nominal === "number") {
    shapes.push({
      type: "line",
      x0: entry.nominal,
      x1: entry.nominal,
      y0: 0,
      y1: 1,
      yref: "paper",
      line: { color: colors.nominal, width: 1.5, dash: "dot" },
    });
  }
  for (const sampledValue of entry.sampled_values ?? []) {
    shapes.push({
      type: "line",
      x0: sampledValue,
      x1: sampledValue,
      y0: 0,
      y1: 1,
      yref: "paper",
      line: { color: sampledColor, width: 2, dash: "solid" },
    });
  }

  const pdfTrace: object =
    chartType === "discrete"
      ? {
          x: entry.pdf_x,
          y: entry.pdf_y,
          type: "bar",
          marker: { color: curveColor, opacity: 0.75 },
          name: "P(x)",
          hoverinfo: "x+y",
        }
      : {
          x: entry.pdf_x,
          y: entry.pdf_y,
          type: "scatter",
          mode: "lines",
          fill: "tozeroy",
          line: { color: curveColor, width: 1.5 },
          fillcolor: fillColor,
          name: "PDF",
          hoverinfo: "x+y",
        };

  const cdfTrace: object = {
    x: entry.cdf_x,
    y: entry.cdf_y,
    type: "scatter",
    mode: "lines",
    line: {
      color: cdfColor,
      width: 1.5,
      shape: chartType === "discrete" ? "hv" : "linear",
    },
    name: "CDF",
    yaxis: "y2",
    hoverinfo: "x+y",
  };

  const layout = {
    paper_bgcolor: bg,
    plot_bgcolor: bg,
    // only reserve bottom space for x-axis title when units are present
    margin: { t: 14, r: 48, b: unitsLabel ? 46 : 32, l: 64 },
    xaxis: {
      color: textColor,
      showgrid: false,
      tickfont: { size: 11 },
      ...(unitsLabel
        ? {
            title: {
              text: unitsLabel,
              font: { size: 13 },
              standoff: 4,
            },
          }
        : {}),
    },
    yaxis: {
      color: curveColor,
      showgrid: false,
      tickfont: { size: 11 },
      title: {
        text: chartType === "discrete" ? "Probability" : "Probability Density",
        font: { size: 13 },
        standoff: 4,
      },
    },
    // avoid setting `color` on yaxis2 - it bleeds into the x-axis ticks;
    // use per-property colors on tickfont and title.font instead
    yaxis2: {
      overlaying: "y",
      side: "right",
      range: [0, 1],
      showgrid: false,
      tickfont: { size: 10, color: cdfColor },
      title: {
        text: "CDF",
        font: { size: 12, color: cdfColor },
        standoff: 2,
      },
      tickformat: ".1f",
    },
    showlegend: false,
    shapes,
    font: { size: 11, color: textColor },
  };
  return { traces: [pdfTrace, cdfTrace], layout };
}

// a parameter value for the list under the chart: big and tiny numbers in
// scientific notation, others to four significant figures without trailing zeros
export function formatParam(v: string | number | boolean): string {
  if (typeof v === "number") {
    return Math.abs(v) >= 1000 || (Math.abs(v) < 0.01 && v !== 0)
      ? v.toExponential(3)
      : v.toPrecision(4).replace(/\.?0+$/, "");
  }
  return String(v);
}

// the parameter list under the chart, as html. A categorical distribution
// shows its probabilities as bar annotations, so it has no list.
export function paramsHtml(entry: DistEntry): string {
  if (entry.chart_type === "categorical") return "";
  return Object.entries(entry.params)
    .map(
      ([k, v]) =>
        `<span><span class="text-ink-muted">${escapeHtml(k)}:</span> ${escapeHtml(formatParam(v))}</span>`,
    )
    .join("");
}
