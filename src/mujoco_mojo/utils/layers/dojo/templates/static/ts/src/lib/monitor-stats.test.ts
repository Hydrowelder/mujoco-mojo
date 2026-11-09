import { describe, expect, it } from "vitest";

import type { JobStatus } from "../models";
import {
  celebrationKey,
  chimeChoice,
  completionNotification,
  holidayTheme,
  outcomeGradient,
  progressTitle,
  statCards,
  trialNotification,
} from "./monitor-stats";

const status = (over: Partial<JobStatus> = {}): JobStatus => ({
  n_done: 0,
  n_success: 0,
  n_failed: 0,
  n_error: 0,
  n_remaining: 100,
  n_trial: 100,
  progress: 0,
  success_tns: [],
  failure_tns: [],
  error_tns: [],
  failure_tns_with_db: [],
  error_tns_with_db: [],
  last_success_tn: null,
  last_failure_tn: null,
  last_error_tn: null,
  padding_style: "03d",
  throughput: "12.5",
  avg_duration: "00:00:05",
  elapsed: "00:01:00",
  start_time: "10:00:00",
  time_remaining: "00:02:00",
  end_time: "10:03:00",
  is_complete: false,
  ...over,
});

const TICK = "✓";

describe("progressTitle", () => {
  it("shows the percent done to one decimal while the job runs", () => {
    expect(progressTitle(status({ n_done: 37, n_trial: 100 }))).toBe("(37.0%) Monitor | MuJoCo Mojo");
    expect(progressTitle(status({ n_done: 1, n_trial: 3 }))).toBe("(33.3%) Monitor | MuJoCo Mojo");
  });

  it("shows a tick instead once the job is complete", () => {
    expect(progressTitle(status({ n_done: 100, is_complete: true }))).toBe(`${TICK} Monitor | MuJoCo Mojo`);
  });

  it("does not divide by zero for a job with no trials yet", () => {
    expect(progressTitle(status({ n_done: 0, n_trial: 0 }))).toBe("(0.0%) Monitor | MuJoCo Mojo");
  });
});

describe("statCards", () => {
  const cards = (over: Partial<JobStatus> = {}) => statCards(status(over));

  it("makes the six cards in order", () => {
    expect(cards().map((c) => c.label)).toEqual([
      "Successes",
      "Failures",
      "Errors",
      "Time Elapsed",
      "Remaining",
      "Est. Remaining",
    ]);
  });

  it("shows each outcome count with its percent of all trials", () => {
    const out = cards({ n_trial: 200, n_success: 150, n_failed: 30, n_error: 20, n_remaining: 0 });
    expect(out.slice(0, 3).map((c) => c.value)).toEqual(["150 (75.0%)", "30 (15.0%)", "20 (10.0%)"]);
    expect(out[0]!.tooltip).toContain("all 200 trials");
  });

  it("names the last trial of each outcome, with None before there is one and 0 for trial zero", () => {
    expect(cards().map((c) => c.subValue).slice(0, 3)).toEqual([
      "Last Success: Trial None",
      "Last Failure: Trial None",
      "Last Error: Trial None",
    ]);
    const out = cards({ last_success_tn: 0, last_failure_tn: 7, last_error_tn: 12 });
    expect(out.map((c) => c.subValue).slice(0, 3)).toEqual([
      "Last Success: Trial 0",
      "Last Failure: Trial 7",
      "Last Error: Trial 12",
    ]);
  });

  it("colors the outcome cards by what they mean", () => {
    expect(cards().map((c) => c.color).slice(0, 3)).toEqual(["text-success-500", "text-danger-500", "text-warning-500"]);
  });

  it("shows the elapsed time, start, remaining count and throughput", () => {
    const out = cards({ n_trial: 80, n_remaining: 20, throughput: "4.2", elapsed: "00:09:09", start_time: "08:00:00" });
    expect(out[3]).toMatchObject({ value: "00:09:09", subValue: "Started: 08:00:00" });
    expect(out[4]).toMatchObject({ value: "20 (25.0%)", subValue: "4.2 trials/min - 80 trials total" });
  });

  it("shows an estimate and ETA while running", () => {
    expect(cards({ time_remaining: "00:05:00", end_time: "12:00:00" })[5]).toMatchObject({
      label: "Est. Remaining",
      value: "00:05:00",
      subValue: "ETA: 12:00:00",
    });
  });

  it("shows the finish time once complete", () => {
    expect(cards({ is_complete: true, end_time: "12:00:00" })[5]).toMatchObject({
      label: "Finished",
      value: "00:00:00",
      subValue: "Finished: 12:00:00",
    });
  });

  it("does not divide by zero for a job with no trials", () => {
    expect(cards({ n_trial: 0, n_success: 0, n_remaining: 0 })[0]!.value).toBe("0 (0.0%)");
  });
});

describe("trialNotification", () => {
  const prev = { n_done: 5, n_failed: 1, n_error: 1 };

  it("says nothing when no trial finished, or the count went down", () => {
    expect(trialNotification(prev, status({ n_done: 5, n_failed: 1, n_error: 1 }))).toBeNull();
    expect(trialNotification(prev, status({ n_done: 2, n_failed: 0, n_error: 0 }))).toBeNull();
  });

  it("names a single trial that succeeded", () => {
    const data = status({ n_done: 6, n_failed: 1, n_error: 1, success_tns: ["3", "9"] });
    expect(trialNotification(prev, data)).toEqual({ message: "Trial 9 succeeded", type: "success" });
  });

  it("names a single trial that failed its requirements", () => {
    const data = status({ n_done: 6, n_failed: 2, n_error: 1, failure_tns: ["4", "11"], success_tns: ["9"] });
    expect(trialNotification(prev, data)).toEqual({ message: "Trial 11 failed requirements", type: "error" });
  });

  it("names a single trial that errored", () => {
    const data = status({ n_done: 6, n_failed: 1, n_error: 2, error_tns: ["2", "13"], success_tns: ["9"] });
    expect(trialNotification(prev, data)).toEqual({ message: "Trial 13 errored", type: "error" });
  });

  it("tallies several trials, as an error if any of them failed or errored", () => {
    expect(trialNotification(prev, status({ n_done: 9, n_failed: 2, n_error: 2 }))).toEqual({
      message: "4 trials done - 2 ok, 1 failed, 1 errored",
      type: "error",
    });
  });

  it("tallies several trials as an error when only failures, or only errors, were among them", () => {
    expect(trialNotification(prev, status({ n_done: 8, n_failed: 3, n_error: 1 }))?.type).toBe("error");
    expect(trialNotification(prev, status({ n_done: 8, n_failed: 1, n_error: 3 }))?.type).toBe("error");
  });

  it("tallies several trials as a success when all of them were", () => {
    expect(trialNotification(prev, status({ n_done: 8, n_failed: 1, n_error: 1 }))).toEqual({
      message: "3 trials done - 3 ok, 0 failed, 0 errored",
      type: "success",
    });
  });
});

describe("completionNotification", () => {
  it("summarizes the run as a success when nothing failed or errored", () => {
    expect(completionNotification(status({ n_success: 10, elapsed: "00:03:00" }))).toEqual({
      message: "Job complete in 00:03:00 - 10 succeeded, 0 failed, 0 errored",
      type: "success",
    });
  });

  it("is an error notification if anything failed or errored", () => {
    expect(completionNotification(status({ n_success: 8, n_failed: 1 })).type).toBe("error");
    expect(completionNotification(status({ n_success: 8, n_error: 1 })).type).toBe("error");
  });
});

describe("outcomeGradient", () => {
  const S = "#111111";
  const F = "#222222";
  const E = "#333333";

  it("is transparent when nothing has finished", () => {
    expect(outcomeGradient([{ color: S, n: 0 }, { color: F, n: 0 }])).toBe("transparent");
    expect(outcomeGradient([])).toBe("transparent");
  });

  it("is a flat color when only one outcome has happened", () => {
    expect(outcomeGradient([{ color: S, n: 4 }, { color: F, n: 0 }, { color: E, n: 0 }])).toBe(S);
  });

  it("blends two outcomes in proportion to their counts", () => {
    expect(outcomeGradient([{ color: S, n: 3 }, { color: F, n: 1 }])).toBe(
      `linear-gradient(to right, ${S} 0.00%, ${S} 70.00%, ${F} 80.00%, ${F} 100.00%)`,
    );
  });

  it("blends three outcomes", () => {
    expect(outcomeGradient([{ color: S, n: 1 }, { color: F, n: 1 }, { color: E, n: 2 }])).toBe(
      `linear-gradient(to right, ${S} 0.00%, ${S} 20.00%, ${F} 30.00%, ${F} 45.00%, ${E} 55.00%, ${E} 100.00%)`,
    );
  });

  it("keeps a thin slice's blend zone inside the slice", () => {
    expect(outcomeGradient([{ color: S, n: 1 }, { color: F, n: 99 }])).toBe(
      `linear-gradient(to right, ${S} 0.00%, ${S} 0.50%, ${F} 6.00%, ${F} 100.00%)`,
    );
  });

  it("keeps the last slice's blend zone from running past the end of the bar", () => {
    expect(outcomeGradient([{ color: S, n: 99 }, { color: F, n: 1 }])).toBe(
      `linear-gradient(to right, ${S} 0.00%, ${S} 94.00%, ${F} 99.50%, ${F} 100.00%)`,
    );
  });

  it("skips an outcome that has not happened", () => {
    expect(outcomeGradient([{ color: S, n: 3 }, { color: F, n: 0 }, { color: E, n: 1 }])).toBe(
      outcomeGradient([{ color: S, n: 3 }, { color: E, n: 1 }]),
    );
  });
});

describe("holidayTheme", () => {
  // months here are the 0-based ones Date takes
  const on = (month: number, day: number) => holidayTheme(new Date(2026, month, day)).name;

  it("celebrates New Year from December 31 through January 2", () => {
    expect(on(11, 31)).toBe("New Year");
    expect(on(0, 1)).toBe("New Year");
    expect(on(0, 2)).toBe("New Year");
  });

  it("has snow for the rest of December and the first half of January", () => {
    expect(on(11, 1)).toBe("Winter Snow");
    expect(on(11, 30)).toBe("Winter Snow");
    expect(on(0, 3)).toBe("Winter Snow");
    expect(on(0, 15)).toBe("Winter Snow");
    expect(on(0, 16)).toBe("Standard Mojo");
  });

  it("marks Pi Day, St. Patrick's Day and May the 4th", () => {
    expect(on(2, 14)).toBe("Pi Day");
    expect(on(2, 17)).toBe("St. Patrick's Day");
    expect(on(4, 4)).toBe("May the 4th");
  });

  it("runs Halloween from October 25 to November 1", () => {
    expect(on(9, 24)).toBe("Standard Mojo");
    expect(on(9, 25)).toBe("Halloween");
    expect(on(9, 31)).toBe("Halloween");
    expect(on(10, 1)).toBe("Halloween");
    expect(on(10, 2)).toBe("Standard Mojo");
  });

  it("is the standard theme any other day", () => {
    expect(on(6, 4)).toBe("Standard Mojo");
    expect(on(2, 15)).toBe("Standard Mojo");
    expect(holidayTheme(new Date(2026, 6, 4)).colors).toHaveLength(3);
  });

  it("gives holidays emojis, and only the snow theme falls as snow", () => {
    expect(holidayTheme(new Date(2026, 9, 31)).emojis?.length).toBeGreaterThan(0);
    expect(holidayTheme(new Date(2026, 11, 15))).toMatchObject({ isSnow: true });
    expect(holidayTheme(new Date(2026, 9, 31)).isSnow).toBeUndefined();
    expect(holidayTheme(new Date(2026, 6, 4)).emojis).toBeUndefined();
  });

  it("has the same theme at any time of day", () => {
    expect(holidayTheme(new Date(2026, 2, 14, 0, 0, 1)).name).toBe("Pi Day");
    expect(holidayTheme(new Date(2026, 2, 14, 23, 59, 59)).name).toBe("Pi Day");
  });
});

describe("celebrationKey", () => {
  it("is the job's start time under a fixed prefix", () => {
    expect(celebrationKey("2026-03-14T01:02:03")).toBe("mojo_celebrated_2026-03-14T01:02:03");
    expect(celebrationKey(1700000000)).toBe("mojo_celebrated_1700000000");
  });

  it("is different for each job", () => {
    expect(celebrationKey("a")).not.toBe(celebrationKey("b"));
  });

  it("spells out an unknown start time as undefined, as saved", () => {
    expect(celebrationKey(undefined)).toBe("mojo_celebrated_undefined");
  });
});

describe("chimeChoice", () => {
  it("is the default chime when it is on and not muted", () => {
    expect(chimeChoice(true, false, undefined)).toBe("default");
    expect(chimeChoice(true, false, "")).toBe("default");
  });

  it("is the theme's own sound when it has one", () => {
    expect(chimeChoice(true, false, "/sounds/pi.mp3")).toBe("holiday");
  });

  it("is silent when the server has it switched off", () => {
    expect(chimeChoice(false, false, undefined)).toBe("none");
    expect(chimeChoice(false, false, "/sounds/pi.mp3")).toBe("none");
  });

  it("is silent when this browser muted it", () => {
    expect(chimeChoice(true, true, undefined)).toBe("none");
    expect(chimeChoice(true, true, "/sounds/pi.mp3")).toBe("none");
  });

  it("is silent when both say so", () => {
    expect(chimeChoice(false, true, "/sounds/pi.mp3")).toBe("none");
  });
});
