import type { FilterEntry } from "../models";

// A reference frame is (quaternion base, origin base); either half may be
// null and (null, null) is the world frame. The server decides which series
// actually get translated to the origin (positions) and which are only
// rotated (free vectors), so every series gets the same pair.
export type RefFrame = [string | null, string | null];

export function refFrameActive(frame: RefFrame): boolean {
  return frame[0] !== null || frame[1] !== null;
}

export function sameRefFrame(a: RefFrame, b: RefFrame): boolean {
  return a[0] === b[0] && a[1] === b[1];
}

export function refFrameLabel(frame: RefFrame): string {
  const [quat, origin] = frame;
  if (quat && origin) return `${quat} @ ${origin}`;
  return quat ?? (origin ? `@ ${origin}` : "world");
}

// each half of a frame that is set must exist in the trial: the quaternion as
// a :w family, the origin as an :x/:y/:z family
export function refFrameAvailable(
  frame: RefFrame,
  quats: Set<string>,
  cols: Set<string>,
): boolean {
  const [quat, origin] = frame;
  return (!quat || quats.has(quat)) && (!origin || cols.has(`${origin}:x`));
}

export function buildRefFrameFilter(frame: RefFrame): FilterEntry {
  return {
    type: "rotation",
    quatCol: frame[0],
    originCol: frame[1],
    invert: true,
    enabled: true,
  };
}

// A saved config from before the frame became a (quat, origin) pair stores
// null (world) or a plain string; both reset to the world frame instead of
// being misread as a pair.
export function sanitizeRefFrame<T extends { refFrame?: unknown }>(cfg: T): T {
  const v = cfg.refFrame;
  if (v === undefined) return cfg;
  const valid =
    Array.isArray(v) &&
    v.length === 2 &&
    v.every((x) => x === null || typeof x === "string");
  return valid ? cfg : { ...cfg, refFrame: [null, null] };
}

// a signal's filter stack with its rotation filter set for `frame`: replaced in
// place when the stack has one (so it keeps the user's chosen position),
// otherwise put at the front. for the world frame the rotation filter is taken
// out. returns `filters` itself, untouched, when there was nothing to remove
export function withRefFrameFilter(filters: FilterEntry[], frame: RefFrame): FilterEntry[] {
  const idx = filters.findIndex((f) => f.type === "rotation");
  if (refFrameActive(frame)) {
    const newEntry = buildRefFrameFilter(frame);
    if (idx >= 0) {
      // Replace in-place to preserve the user's chosen position in the stack
      return [...filters.slice(0, idx), newEntry, ...filters.slice(idx + 1)];
    }
    return [newEntry, ...filters];
  }
  if (idx >= 0) return [...filters.slice(0, idx), ...filters.slice(idx + 1)];
  return filters;
}
