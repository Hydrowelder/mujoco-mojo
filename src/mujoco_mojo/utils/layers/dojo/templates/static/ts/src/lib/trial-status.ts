// how the trial status panel draws the two steps a trial goes through,
// generating and solving

import type { TrialStatus } from "../models";

export type TrialStep = "generating" | "solving";

// The runner also resets `status.step` to "done" in its except handler, so
// that can't tell "this step is where things broke" from "finished cleanly".
// `started` is reliable instead: generating and solving run strictly
// sequentially, so whichever one has `started` set *last* is the one that was
// in flight when the trial errored. null when the trial did not error
export function errorStep(status: TrialStatus | null): TrialStep | null {
  if (!status || status.completion !== "error") return null;
  if (status.solving.started !== null) return "solving";
  if (status.generating.started !== null) return "generating";
  return null;
}

// the step's dot: amber where it errored, green once it has run, a pulse while
// it is the current step, gray otherwise
export function stepDotClass(status: TrialStatus | null, stepName: TrialStep): string {
  if (!status) return "bg-control";
  const step = status[stepName];
  if (errorStep(status) === stepName) return "bg-warning-500";
  if (step.elapsed !== null) return "bg-success-500";
  if (status.step === stepName) return "bg-accent-400 animate-pulse";
  return "bg-control";
}

export function stepTextClass(status: TrialStatus | null, stepName: TrialStep): string {
  if (!status) return "text-ink-disabled";
  const step = status[stepName];
  if (errorStep(status) === stepName) return "text-warning-500 dark:text-warning-400";
  if (step.elapsed !== null) return "text-ink-secondary";
  if (status.step === stepName) return "text-accent-500 dark:text-accent-400";
  return "text-ink-disabled";
}
