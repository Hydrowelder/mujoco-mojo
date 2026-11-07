// reading back the plot config and its undo history from what this browser
// saved, and the raw json the editor holds, moved out of trial-viewer.ts so
// the handling of old and corrupt data can be tested without a page.

import type { PlotConfig } from "./plot-config.generated";
import { sanitizeRefFrame } from "./ref-frame";

// the saved plot config, with a reference frame from before frames were
// (quaternion, origin) pairs reset to the world frame. null when it cannot be
// read.
export function parseSavedConfig(raw: string): Partial<PlotConfig> | null {
  try {
    return sanitizeRefFrame(JSON.parse(raw) as Partial<PlotConfig>);
  } catch {
    return null;
  }
}

// the saved undo history: a stack of at least one snapshot and the index of the
// current one, which must be in it. null when it cannot be read or is not one,
// so the page starts a fresh history instead of undoing through a broken one
export function parseSavedHistory(raw: string): { stack: string[]; index: number } | null {
  try {
    const saved = JSON.parse(raw) as { stack?: unknown; index?: unknown } | null;
    const stack = saved?.stack;
    const index = saved?.index;
    if (
      !Array.isArray(stack) ||
      !stack.every((snapshot) => typeof snapshot === "string") ||
      typeof index !== "number" ||
      !Number.isInteger(index) ||
      index < 0 ||
      index >= stack.length
    ) {
      return null;
    }
    return { stack, index };
  } catch {
    return null;
  }
}

// what the json editor holds: whether it is json at all and, if it is an
// object, the config it describes (null for json that is not an object, such
// as a number or null).
export function parseRawConfig(
  raw: string,
): { json: false } | { json: true; config: PlotConfig | null } {
  try {
    const parsed = JSON.parse(raw) as PlotConfig;
    return { json: true, config: parsed && typeof parsed === "object" ? parsed : null };
  } catch {
    return { json: false };
  }
}
