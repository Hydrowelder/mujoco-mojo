// what the Monitor page says about a job: the stat cards, the page title, the
// notification text when trials finish, the progress bar's gradient, and the
// celebration's holiday theme. everything here is a function of the job
// status (or the date), so the page component only has to draw the results.

import type { JobStatus } from "../models";

export interface StatCard {
  label: string;
  value: string;
  color: string;
  subValue: string;
  tooltip: string;
}

export interface HolidayTheme {
  name: string;
  emojis?: string[];
  colors?: string[];
  isSnow?: boolean;
  audioUrl?: string;
}

export interface Notification {
  message: string;
  type: "success" | "error";
}

// the counters a status carries, taken at the previous update
export type OutcomeCounts = Pick<JobStatus, "n_done" | "n_failed" | "n_error">;

// the page title: a tick once the job is complete, the percent done until then
export function progressTitle(status: JobStatus): string {
  const totalDone = status.n_done || 0;
  const n_trial = status.n_trial || 1;
  const progress = ((totalDone / n_trial) * 100).toFixed(1);
  return `${status.is_complete ? "✓" : `(${progress}%)`} Monitor | MuJoCo Mojo`;
}

export function statCards(status: JobStatus): StatCard[] {
  const n_trial = status.n_trial || 1;

  const pctOfTotal = (n: number) => ((n / n_trial) * 100).toFixed(1);

  const lastSuccess = status.last_success_tn ?? "None";
  const lastFailure = status.last_failure_tn ?? "None";
  const lastError = status.last_error_tn ?? "None";

  return [
    {
      label: "Successes",
      value: `${status.n_success} (${pctOfTotal(status.n_success)}%)`,
      color: "text-success-500",
      subValue: `Last Success: Trial ${lastSuccess}`,
      tooltip: `Trials that completed and passed every registered requirement (or had none). Percentage is of all ${n_trial} trials.`,
    },
    {
      label: "Failures",
      value: `${status.n_failed} (${pctOfTotal(status.n_failed)}%)`,
      color: "text-danger-500",
      subValue: `Last Failure: Trial ${lastFailure}`,
      tooltip:
        "Trials that ran but failed one or more requirement checks, including early terminations triggered by a failing requirement. Not runtime errors.",
    },
    {
      label: "Errors",
      value: `${status.n_error} (${pctOfTotal(status.n_error)}%)`,
      color: "text-warning-500",
      subValue: `Last Error: Trial ${lastError}`,
      tooltip:
        "Trials that raised an unhandled runtime error while being processed. These runs broke; they were never judged against requirements.",
    },
    {
      label: "Time Elapsed",
      value: status.elapsed,
      color: "text-ink-secondary",
      subValue: `Started: ${status.start_time}`,
      tooltip: "Wall-clock time since the job started.",
    },
    {
      label: "Remaining",
      value: `${status.n_remaining} (${pctOfTotal(status.n_remaining)}%)`,
      color: "text-accent-500",
      subValue: `${status.throughput} trials/min - ${n_trial} trials total`,
      tooltip:
        "Trials that have not finished yet. Throughput is derived from the average duration of completed trials (successes and failures; errors excluded) and the number of trials running at once: the processors for a local run, measured for a SLURM job.",
    },
    {
      label: status.is_complete ? "Finished" : "Est. Remaining",
      value: status.is_complete ? "00:00:00" : status.time_remaining,
      color: "text-ink-secondary",
      subValue: status.is_complete ? `Finished: ${status.end_time}` : `ETA: ${status.end_time}`,
      tooltip: status.is_complete
        ? "The job has finished. Shows the local time at which the job completed."
        : "Estimated wall-clock time until all trials finish, based on the average completed-trial duration (errors excluded). ETA is the projected local completion time.",
    },
  ];
}

// what to tell the user about the trials that finished between two updates,
// or null when none did. one trial gets named with its outcome, several get a
// tally; it is an error notification if any of them failed or errored
export function trialNotification(prev: OutcomeCounts, data: JobStatus): Notification | null {
  const newDone = data.n_done - prev.n_done;
  if (newDone <= 0) return null;
  const newFailed = data.n_failed - prev.n_failed;
  const newError = data.n_error - prev.n_error;
  if (newDone === 1) {
    let verb = "succeeded";
    let trialId = data.success_tns.at(-1);
    if (newError === 1) {
      verb = "errored";
      trialId = data.error_tns.at(-1);
    } else if (newFailed === 1) {
      verb = "failed requirements";
      trialId = data.failure_tns.at(-1);
    }
    return { message: `Trial ${trialId} ${verb}`, type: verb === "succeeded" ? "success" : "error" };
  }
  const newOk = newDone - newFailed - newError;
  return {
    message: `${newDone} trials done - ${newOk} ok, ${newFailed} failed, ${newError} errored`,
    type: newFailed + newError > 0 ? "error" : "success",
  };
}

export function completionNotification(status: JobStatus): Notification {
  return {
    message: `Job complete in ${status.elapsed} - ${status.n_success} succeeded, ${status.n_failed} failed, ${status.n_error} errored`,
    type: status.n_failed + status.n_error > 0 ? "error" : "success",
  };
}

// builds a single left-to-right gradient across the filled bar: solid
// color in the middle of each outcome's share, soft blends at boundaries.
// outcomes with a count of zero are left out
export function outcomeGradient(outcomes: { color: string; n: number }[]): string {
  const segs = outcomes.filter((seg) => seg.n > 0);
  const [first] = segs;
  if (!first) return "transparent";
  if (segs.length === 1) return first.color;

  const total = segs.reduce((sum, seg) => sum + seg.n, 0);
  const blend = 5; // half-width of each blend zone, in % of the filled bar
  const stops: string[] = [];
  let acc = 0;
  segs.forEach((seg, i) => {
    const start = (acc / total) * 100;
    acc += seg.n;
    const end = (acc / total) * 100;
    const mid = (start + end) / 2;
    const lo = i === 0 ? 0 : Math.min(start + blend, mid);
    const hi = i === segs.length - 1 ? 100 : Math.max(end - blend, mid);
    stops.push(`${seg.color} ${lo.toFixed(2)}%`, `${seg.color} ${hi.toFixed(2)}%`);
  });
  return `linear-gradient(to right, ${stops.join(", ")})`;
}

// the celebration for a job finishing on `now`. the first matching rule wins,
// so the New Year days beat the winter snow around them
export function holidayTheme(now: Date): HolidayTheme {
  const m = now.getMonth();
  const d = now.getDate();

  if ((m === 11 && d === 31) || (m === 0 && d <= 2)) {
    return {
      name: "New Year",
      emojis: ["🎆", "✨", "🥂"],
      colors: ["#ffcc00", "#ffffff"],
    };
  }
  if (m === 2 && d === 14) {
    return { name: "Pi Day", emojis: ["π", "🥧"], colors: ["#ff9900"] };
  }
  if (m === 2 && d === 17) {
    return {
      name: "St. Patrick's Day",
      emojis: ["🍀", "🌈"],
      colors: ["#22c55e", "#166534"],
    };
  }
  if (m === 4 && d === 4) {
    return {
      name: "May the 4th",
      emojis: ["⚔️", "🌌", "✨"],
      colors: ["#FFE81F", "#2dd4bf"],
    };
  }
  if ((m === 9 && d >= 25) || (m === 10 && d === 1)) {
    return {
      name: "Halloween",
      emojis: ["🎃", "👻", "🦇"],
      colors: ["#ff6600", "#9437ff"],
    };
  }
  if (m === 11 || (m === 0 && d <= 15)) {
    return {
      name: "Winter Snow",
      emojis: ["❄️", "⛄", "🌨️"],
      isSnow: true,
    };
  }
  return {
    name: "Standard Mojo",
    colors: ["#06b6d4", "#3b82f6", "#22c55e"],
  };
}

// the key that remembers a job's completion was celebrated, so reloading or
// opening another page does not celebrate it again
export function celebrationKey(startTime: string | number | undefined): string {
  return `mojo_celebrated_${startTime}`;
}

// which sound a completion plays: none when the chime is switched off on the
// server or muted in this browser (a holiday sound is a chime too), the
// theme's own sound when it has one, else the default chime.
export function chimeChoice(
  chimeEnabled: boolean,
  isMuted: boolean,
  audioUrl: string | undefined,
): "none" | "holiday" | "default" {
  if (!chimeEnabled || isMuted) return "none";
  return audioUrl ? "holiday" : "default";
}
