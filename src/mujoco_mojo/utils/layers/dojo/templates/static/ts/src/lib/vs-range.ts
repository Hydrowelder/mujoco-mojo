// versus mode: overlaying other trials on the one being viewed. these are the
// trial-number calculations behind the range presets and the "N trials"
// counts. a trial id is `trial_<number>`; the number is what ranges are over.

export interface TrialBounds {
  min: number;
  max: number;
}

// the number in a trial id such as `trial_007`
export function trialNumber(id: string): number {
  return parseInt(id.split("_").pop() ?? "");
}

// shared by every vs-range preset so "the actual set of trial numbers that
// exist" has exactly one computation. null when there are none
export function trialBounds(allTrials: string[]): TrialBounds | null {
  const nums = allTrials.map(trialNumber).filter((n) => !isNaN(n));
  if (!nums.length) return null;
  return { min: Math.min(...nums), max: Math.max(...nums) };
}

// the range of `delta` trials either side of the current one. each edge is
// clamped independently to the real trial range rather than just cur +/- delta
// - viewing trial 0 with "+/-10" should land on [0, 10], not [-10, 10] (trial
// numbers can't go negative, and more generally shouldn't run past whichever
// trial is actually last).
export function presetRange(currentId: string, delta: number, bounds: TrialBounds | null): [number, number] {
  const cur = trialNumber(currentId);
  const lo = bounds ? Math.max(bounds.min, cur - delta) : cur - delta;
  const hi = bounds ? Math.min(bounds.max, cur + delta) : cur + delta;
  return [lo, hi];
}

// how many trials other than the current one fall inside `range` (either end
// may be the larger)
export function countInRange(allTrials: string[], range: [number, number], currentId: string): number {
  const lo = Math.min(range[0], range[1]);
  const hi = Math.max(range[0], range[1]);
  const cur = trialNumber(currentId);
  return allTrials.filter((id) => {
    const n = trialNumber(id);
    return n >= lo && n <= hi && n !== cur;
  }).length;
}

// as countInRange, plus the pinned trials that fall outside the range
export function countWithPinned(
  allTrials: string[],
  range: [number, number],
  pinned: number[],
  currentId: string,
): number {
  const lo = Math.min(range[0], range[1]);
  const hi = Math.max(range[0], range[1]);
  const cur = trialNumber(currentId);
  const pinnedSet = new Set(pinned);
  return allTrials.filter((id) => {
    const n = trialNumber(id);
    return ((n >= lo && n <= hi) || pinnedSet.has(n)) && n !== cur;
  }).length;
}

// pins `n` if it isn't pinned and unpins it if it is; the result stays sorted
export function togglePinned(pinned: number[], n: number): number[] {
  return pinned.includes(n) ? pinned.filter((x) => x !== n) : [...pinned, n].sort((a, b) => a - b);
}
