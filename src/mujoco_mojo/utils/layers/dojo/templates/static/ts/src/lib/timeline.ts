// the monitor page's timeline chart, moved out of monitor.ts so it can be
// tested without an alpine component: one stacked bar per time bin, split by
// how each trial ended (or is still going).

import type { TimelineBin } from "../models";

// the theme colors the chart uses, resolved by the caller
export interface TimelineColors {
  font: string;
  grid: string;
  success: string;
  danger: string;
  warning: string;
  info: string;
  accent: string;
  tooltipBg: string;
  tooltipFont: string;
}

// below this width the horizontal legend does not fit above the plot
const NARROW_WIDTH = 560;

// on narrow screens the legend moves below the x-axis where it can wrap
// freely; an element that is not laid out yet (width 0) is not narrow
export function isNarrowTimeline(offsetWidth: number): boolean {
  return offsetWidth > 0 && offsetWidth < NARROW_WIDTH;
}

export function timelineTraces(bins: TimelineBin[], colors: TimelineColors): object[] {
  const x = bins.map((b) => b.label);
  return [
    { name: "Success", x, y: bins.map((b) => b.n_success), type: "bar", marker: { color: colors.success } },
    { name: "Failure", x, y: bins.map((b) => b.n_failed), type: "bar", marker: { color: colors.danger } },
    { name: "Error", x, y: bins.map((b) => b.n_error), type: "bar", marker: { color: colors.warning } },
    { name: "Running", x, y: bins.map((b) => b.n_running), type: "bar", marker: { color: colors.info } },
    { name: "Pending", x, y: bins.map((b) => b.n_pending), type: "bar", marker: { color: colors.accent } },
  ];
}

export function timelineLayout(narrow: boolean, colors: TimelineColors): object {
  return {
    autosize: true,
    barmode: "stack",
    bargap: 0.15,
    margin: { l: 45, r: 10, t: 10, b: narrow ? 110 : 55 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: colors.font, family: "monospace", size: 11 },
    xaxis: {
      // bin labels carry microsecond precision so distinct bins never
      // collide onto the same x position; force a real date axis (rather
      // than letting plotly infer a categorical string axis) and control
      // the tick format so it still reads as a plain clock time
      type: "date",
      tickformat: "%H:%M:%S",
      gridcolor: colors.grid,
      tickangle: -45,
      nticks: 8,
      showspikes: true,
      spikemode: "across",
      spikelinecolor: colors.accent,
      spikethickness: -2,
    },
    yaxis: { gridcolor: colors.grid, title: { text: "trials" } },
    legend: narrow
      ? { orientation: "h", x: 0.5, xanchor: "center", y: -0.45, yanchor: "top", font: { size: 10 } }
      : { orientation: "h", y: 1.15, x: 0 },
    hovermode: "x unified",
    hoverlabel: {
      bgcolor: colors.tooltipBg,
      bordercolor: colors.accent,
      font: {
        color: colors.tooltipFont,
        family: "monospace",
        size: 12,
      },
      align: "left",
    },
    showlegend: true,
  };
}
