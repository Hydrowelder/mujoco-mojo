import { describe, expect, it } from "vitest";

import type { StepStatus, TrialStatus } from "../models";
import { errorStep, stepDotClass, stepTextClass, type TrialStep } from "./trial-status";

const STARTED = "2026-01-01T00:00:00";
const NOT_RUN: StepStatus = { started: null, elapsed: null };
const RUNNING: StepStatus = { started: STARTED, elapsed: null };
const DONE: StepStatus = { started: STARTED, elapsed: 1.5 };

const status = (over: Partial<TrialStatus> = {}): TrialStatus => ({
  trial_num: 3,
  step: "pending",
  completion: "incomplete",
  pending: NOT_RUN,
  generating: NOT_RUN,
  solving: NOT_RUN,
  requirements: [],
  requirements_passed: null,
  ...over,
});

describe("errorStep", () => {
  it("is null when there is no status or the trial did not error", () => {
    expect(errorStep(null)).toBeNull();
    for (const completion of ["incomplete", "success", "failure", "terminated"] as const) {
      expect(errorStep(status({ completion, generating: DONE, solving: RUNNING }))).toBeNull();
    }
  });

  it("is the step that started last, since the runner resets the current step on an error", () => {
    expect(errorStep(status({ completion: "error", generating: RUNNING }))).toBe("generating");
    expect(errorStep(status({ completion: "error", generating: DONE, solving: RUNNING }))).toBe("solving");
    // even though the runner has already marked it done
    expect(errorStep(status({ completion: "error", step: "done", generating: DONE, solving: RUNNING }))).toBe(
      "solving",
    );
  });

  it("is null for an error before any step started", () => {
    expect(errorStep(status({ completion: "error" }))).toBeNull();
  });
});

describe("stepDotClass and stepTextClass", () => {
  const both = (s: TrialStatus | null, step: TrialStep) => [stepDotClass(s, step), stepTextClass(s, step)];

  it("are muted when there is no status yet", () => {
    expect(both(null, "solving")).toEqual(["bg-control", "text-ink-disabled"]);
  });

  it("are muted for a step that has not run", () => {
    expect(both(status({ step: "generating", generating: RUNNING }), "solving")).toEqual([
      "bg-control",
      "text-ink-disabled",
    ]);
  });

  it("pulse while the step is the current one", () => {
    expect(both(status({ step: "generating", generating: RUNNING }), "generating")).toEqual([
      "bg-accent-400 animate-pulse",
      "text-accent-500 dark:text-accent-400",
    ]);
  });

  it("turn green once the step has finished", () => {
    expect(both(status({ step: "solving", generating: DONE, solving: RUNNING }), "generating")).toEqual([
      "bg-success-500",
      "text-ink-secondary",
    ]);
  });

  it("turn amber on the step that errored", () => {
    const errored = status({ completion: "error", step: "done", generating: DONE, solving: RUNNING });
    expect(both(errored, "solving")).toEqual(["bg-warning-500", "text-warning-500 dark:text-warning-400"]);
    expect(both(errored, "generating")).toEqual(["bg-success-500", "text-ink-secondary"]);
  });

  it("show a finished trial's two steps as done", () => {
    const finished = status({ completion: "success", step: "done", generating: DONE, solving: DONE });
    expect(both(finished, "generating")).toEqual(["bg-success-500", "text-ink-secondary"]);
    expect(both(finished, "solving")).toEqual(["bg-success-500", "text-ink-secondary"]);
  });
});
