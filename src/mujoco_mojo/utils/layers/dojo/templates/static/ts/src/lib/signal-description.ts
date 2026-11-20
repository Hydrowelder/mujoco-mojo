// how a signal's `description` (the optional text a column's metadata carries)
// is shown: the hover tooltip of the signal pickers, and the readout under the
// Signal Lab's Signal In node. everything here is pure so it can be tested
// without a component, and the Lab's inline script (which is not bundled) gets
// `wrapText` through `window.mojoWrapText`.

import { escapeHtml } from "./html";

// the widest the picker tooltip gets, in px. the position below assumes it
export const SIGNAL_TIP_WIDTH = 320;

// the gap between a row and its tooltip, and the least room left at the screen's edges
const GAP = 8;

// the shortest tooltip is assumed to be this tall when keeping it on the screen
const SIGNAL_TIP_MIN_HEIGHT = 80;

// the tooltip's text as html: the signal's name in bold, then its description
// in italics. both are escaped since a column name and a description are
// whatever the model's author wrote. a signal with no description (or a blank
// one) shows its name alone, which the pickers' rows truncate. a `note` (the
// Lab's picker says which signals would make a circular dependency) goes on a
// line of its own below
export function signalTipHtml(
  name: string,
  description: string | undefined,
  note = "",
): string {
  const text = (description ?? "").trim();
  const head = text
    ? `<b>${escapeHtml(name)}:</b> <i>${escapeHtml(text)}</i>`
    : `<b>${escapeHtml(name)}</b>`;
  return note ? `${head}<br>${escapeHtml(note)}` : head;
}

export interface TipRow {
  left: number;
  right: number;
  top: number;
}

// where the tooltip goes for a row: beside the row (to its right, or to its
// left when there is no room on the right, `flip` meaning the tooltip's right
// edge is at `left`), level with the row's top and never off the screen. when
// the screen is too narrow for either side it is pinned to the right edge
export function signalTipPosition(
  row: TipRow,
  viewport: { width: number; height: number },
): { left: number; top: number; flip: boolean } {
  const top = Math.max(
    GAP,
    Math.min(row.top, viewport.height - SIGNAL_TIP_MIN_HEIGHT),
  );
  if (row.right + GAP + SIGNAL_TIP_WIDTH <= viewport.width) {
    return { left: row.right + GAP, top, flip: false };
  }
  if (row.left - GAP >= SIGNAL_TIP_WIDTH) {
    return { left: row.left - GAP, top, flip: true };
  }
  return {
    left: Math.max(GAP, viewport.width - SIGNAL_TIP_WIDTH - GAP),
    top,
    flip: false,
  };
}

// the descriptions of the columns that have one, keyed by column name, which
// is what the Signal Lab's nodes read
export function signalDescriptions(
  metadata: Record<string, { description?: string } | undefined>,
): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [column, meta] of Object.entries(metadata)) {
    const text = (meta?.description ?? "").trim();
    if (text) result[column] = text;
  }
  return result;
}

// what SensAI is told about a signal besides its name: the three fields its
// signal search reads and shows
export interface SignalSummary {
  description?: string;
  quantity?: string;
  unit?: string;
}

// the summaries of the columns that have anything to say, keyed by column
// name, which is all of a column's metadata the chat request needs (the rest
// would make every message heavier for nothing)
export function signalSummaries(
  metadata: Record<
    string,
    | { description?: string; quantity?: string | null; unit?: string | null }
    | undefined
  >,
): Record<string, SignalSummary> {
  const result: Record<string, SignalSummary> = {};
  for (const [column, meta] of Object.entries(metadata)) {
    const summary: SignalSummary = {};
    const description = (meta?.description ?? "").trim();
    if (description) summary.description = description;
    if (meta?.quantity) summary.quantity = meta.quantity;
    if (meta?.unit) summary.unit = meta.unit;
    if (Object.keys(summary).length > 0) result[column] = summary;
  }
  return result;
}

// `text` broken at spaces into lines of at most `maxChars` characters, and at
// most `maxLines` of them: when more would be needed the last line ends in an
// ellipsis. a word longer than a line is split. in a monospace font a line's
// width is its length, which is what the Signal In node draws it in
export function wrapText(
  text: string,
  maxChars: number,
  maxLines: number,
): string[] {
  if (maxChars < 1 || maxLines < 1) return [];
  const lines: string[] = [];
  let line = "";
  for (let word of text.split(/\s+/).filter(Boolean)) {
    while (word.length > maxChars) {
      if (line) {
        lines.push(line);
        line = "";
      }
      lines.push(word.slice(0, maxChars));
      word = word.slice(maxChars);
    }
    if (!line) {
      line = word;
    } else if (line.length + 1 + word.length <= maxChars) {
      line += ` ${word}`;
    } else {
      lines.push(line);
      line = word;
    }
  }
  if (line) lines.push(line);
  if (lines.length <= maxLines) return lines;
  const kept = lines.slice(0, maxLines);
  kept[maxLines - 1] = `${kept[maxLines - 1]!.slice(0, maxChars - 1).trimEnd()}…`;
  return kept;
}
