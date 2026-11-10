// decisions behind the dojo's global store, moved out of store.ts so they can
// be tested without alpine: server connection changes, the job-status stream,
// page-load timing, the changelog, and what the confirm dialog answers.

import type { ChangelogEntry, ChangelogResponse, ChangelogSource, JobStatus } from "../models";

// the saved choice if there is one, else the server's default
export function initialFullscreen(
  stored: string | null,
  serverDefault: boolean,
): boolean {
  return stored === null ? serverDefault : stored === "true";
}

// what a change in the server connection means. The first connection only sets
// a baseline, with no message; after that a change in either direction is
// announced. `wasConnected` is null until the server has been seen up once.
export function connectionChange(
  wasConnected: boolean | null,
  connected: boolean,
): {
  wasConnected: boolean | null;
  notice: { message: string; type: "success" | "error" } | null;
} {
  if (wasConnected === null) {
    // initial connection - set baseline without notifying.
    return { wasConnected: connected ? true : null, notice: null };
  }
  if (connected === wasConnected) return { wasConnected, notice: null };
  return {
    wasConnected: connected,
    notice: {
      message: connected ? "Server connection restored" : "Server connection lost",
      type: connected ? "success" : "error",
    },
  };
}

// a new run started while we were idle after a completed job
export function newRunDetected(
  isComplete: boolean,
  statusIsComplete: boolean | undefined,
): boolean {
  return isComplete && statusIsComplete === false;
}

// the live job stream is only opened once, while auto-refresh is on and the job
// is still running
export function shouldStartSync(
  hasSource: boolean,
  isAutoRefresh: boolean,
  isComplete: boolean,
): boolean {
  return !hasSource && isAutoRefresh && !isComplete;
}

export type SyncEvent =
  | { kind: "none" }
  | { kind: "start" }
  | { kind: "progress"; value: number }
  | { kind: "final"; status: JobStatus | undefined; isComplete: boolean };

// one message from the job status stream. Throws for text that is not json
// (or is json null), like the stream handler it came from expects.
export function parseSyncEvent(raw: string): SyncEvent {
  const data = JSON.parse(raw) as {
    type: string;
    value?: number;
    status?: JobStatus;
  };
  if (data.type === "start") return { kind: "start" };
  if (data.type === "progress" && data.value !== undefined)
    return { kind: "progress", value: data.value };
  if (data.type === "final")
    return {
      kind: "final",
      status: data.status,
      isComplete: data.status?.is_complete ?? false,
    };
  return { kind: "none" };
}

// the failed and errored trial numbers of a job
export function jobOutcomes(data: JobStatus): { failure: number[]; error: number[] } {
  return {
    failure: (data.failure_tns ?? []).map(Number),
    error: (data.error_tns ?? []).map(Number),
  };
}

// whole seconds since the last update
export function secondsSince(lastUpdate: number, now: number): number {
  return Math.floor((now - lastUpdate) / 1000);
}

// how long to wait before showing the page: a loading screen stays up for at
// least two seconds (none when forced), counted from when loading started
export function pageReadyDelay(force: boolean, loadStartTime: number, now: number): number {
  const minDuration = force ? 0 : 2000;
  const elapsed = now - loadStartTime;
  return Math.max(0, minDuration - elapsed);
}

// a random loading phrase
export function randomPhraseIndex(count: number, rand: () => number): number {
  return Math.floor(rand() * count);
}

// a random loading phrase other than the one showing
export function nextPhraseIndex(current: number, count: number, rand: () => number): number {
  let nextIndex: number;
  do {
    nextIndex = Math.floor(rand() * count);
  } while (nextIndex === current);
  return nextIndex;
}

// whether loading the changelog should pop it open: only when it has entries
// the user has not seen, they have not turned the popup off, and the settings
// panel is not already open
export function shouldAutoOpenChangelog(data: ChangelogResponse, settingsOpen: boolean): boolean {
  return data.show_whats_changed && !settingsOpen && data.entries.some((e) => e.is_new);
}

// what the changelog modal says when its entries are not fresh from GitHub, or
// an empty string when they are (or when no changelog could be loaded, which
// has its own error)
export function changelogNotice(source: ChangelogSource | null): string {
  switch (source) {
    case "cache":
      return "Couldn't reach GitHub, so this is the last changelog saved on this machine. It may be out of date.";
    case "bundled":
      return "Couldn't reach GitHub, so this is the changelog that came with your installed version. Newer releases won't show here.";
    default:
      return "";
  }
}

// closing the changelog only needs to tell the server a version was seen when
// there was something new to see
export function needsMarkSeen(latestVersion: string | null, entries: ChangelogEntry[]): boolean {
  return !!latestVersion && entries.some((e) => e.is_new);
}

export function clearNewFlags(entries: ChangelogEntry[]): ChangelogEntry[] {
  return entries.map((e) => ({ ...e, is_new: false }));
}

// tells the server the changelog up to `version` was seen. true only when it
// took: an error response counts as not taken, like a request that never got
// there, so the "New" tags stay until it does
export async function markChangelogSeen(version: string): Promise<boolean> {
  try {
    const resp = await fetch("/changelog/mark-seen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version }),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

// an error's message, or the fallback for anything that is not an error
export function errorText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

// what the confirm/prompt dialog answers when confirmed: for a prompt the
// trimmed text (null when blank), for a plain confirm true
export function confirmResult(showInput: boolean, inputValue: string): string | boolean | null {
  return showInput ? inputValue.trim() || null : true;
}

// what it answers when cancelled: null for a prompt, false for a confirm
export function cancelResult(showInput: boolean): false | null {
  return showInput ? null : false;
}
