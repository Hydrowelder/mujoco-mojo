// small calculations behind the plot's mouse handling and popups, moved out of
// trial-viewer.ts so they can be tested without a plot on the page.

// the video time under the mouse while scrubbing: the axis time when the x
// axis is time (clamped to the video), else the mouse's fraction of the way
// across the plot, so phase-space plots still work. `axisTime` is the x-axis
// value under the mouse when x is time and null otherwise. null when there is
// no plot width to take a fraction of.
export function scrubTime(
  duration: number,
  axisTime: number | null,
  relX: number,
  plotAreaWidth: number,
): number | null {
  if (axisTime !== null) return Math.max(0, Math.min(duration, axisTime));
  if (plotAreaWidth <= 0) return null;
  return duration * Math.max(0, Math.min(1, relX / plotAreaWidth));
}

// where a popup 288px wide (w-72) goes: left of its button with a 16px gap,
// positioned relative to the document since the popup is x-teleport'd to <body>
export function popupCoords(
  rect: { top: number; left: number },
  scrollX: number,
  scrollY: number,
): { top: number; left: number } {
  return {
    top: rect.top + scrollY,
    left: rect.left + scrollX - 288 - 16,
  };
}

// the text of one of Plotly's own notifications, without its close mark
export function notifierText(raw: string | null | undefined): string | undefined {
  return raw?.replace(/×/g, "").trim();
}

// what a plotly relayout event (a zoom, pan or reset) does to the plot's
// saved ranges: an autorange on either axis resets both to automatic;
// otherwise an axis whose range moved gets its new ends. Axes the event does
// not mention keep what they had.
export function relayoutRanges(
  event: Record<string, unknown>,
): { reset: true } | { reset: false; rangeX?: [number, number]; rangeY?: [number, number] } {
  if (event["xaxis.autorange"] || event["yaxis.autorange"]) return { reset: true };
  const out: { reset: false; rangeX?: [number, number]; rangeY?: [number, number] } = { reset: false };
  if (event["xaxis.range[0]"] !== undefined) {
    out.rangeX = [event["xaxis.range[0]"] as number, event["xaxis.range[1]"] as number];
  }
  if (event["yaxis.range[0]"] !== undefined) {
    out.rangeY = [event["yaxis.range[0]"] as number, event["yaxis.range[1]"] as number];
  }
  return out;
}
