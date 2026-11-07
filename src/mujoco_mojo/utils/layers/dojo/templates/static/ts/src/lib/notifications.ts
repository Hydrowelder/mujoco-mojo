// the notification history behind the bell icon, and what plotly's own
// warnings and messages turn into, moved out of store.ts so they can be tested
// without an alpine store.

import type { NotificationEntry } from "../models";

// how many notifications the history keeps
export const MAX_NOTIFICATIONS = 100;

// plotly repeats the same warning on every re-render, so the same text is
// shown at most once in this long (ms)
const LOG_REPEAT_WINDOW = 10_000;

// a saved notification history: the list and how many were unread. null when
// nothing is saved or what is saved cannot be read. Missing parts come back
// empty, not as the caller's current values.
export function parseNotifications(
  raw: string | null,
): { notifications: NotificationEntry[]; unreadCount: number } | null {
  try {
    if (raw) {
      const saved = JSON.parse(raw) as {
        n: NotificationEntry[];
        u: number;
      };
      return { notifications: saved.n ?? [], unreadCount: saved.u ?? 0 };
    }
  } catch {
    /* ignore corrupt data */
  }
  return null;
}

// a new entry: its id is the time plus a random fraction, so entries made in
// the same millisecond differ
export function newNotification(
  message: string,
  type: string,
  read: boolean,
  now: number,
  rand: number,
): NotificationEntry {
  return {
    id: now + rand,
    message,
    type: type as "success" | "error" | "info",
    timestamp: now,
    read,
  };
}

// puts the entry first, in place, and drops the oldest past the limit
export function prependNotification(
  list: NotificationEntry[],
  entry: NotificationEntry,
  limit = MAX_NOTIFICATIONS,
): void {
  list.unshift(entry);
  if (list.length > limit) list.length = limit;
}

export function markAllRead(list: NotificationEntry[]): void {
  list.forEach((n) => {
    n.read = true;
  });
}

// the first 160 characters of what plotly logged, its arguments joined
export function plotlyLogMessage(args: unknown[]): string {
  return args.map(String).join(" ").slice(0, 160);
}

// plotly prefixes the message it logs with "WARN:" or "ERROR:"
export function isPlotlyPrefix(first: string): boolean {
  return first === "WARN:" || first === "ERROR:";
}

export function plotlyLogType(prefix: string): "error" | "info" {
  return prefix === "ERROR:" ? "error" : "info";
}

// whether to show a plotly message: not when the same text was shown in the
// last ten seconds. Records the time it was last shown in `recent`.
export function shouldForwardLog(
  recent: Map<string, number>,
  msg: string,
  now: number,
): boolean {
  if (now - (recent.get(msg) ?? 0) < LOG_REPEAT_WINDOW) return false;
  recent.set(msg, now);
  return true;
}

// the text of one of plotly's on-page notes, without its close mark
export function notifierMessage(text: string | null): string {
  return (text ?? "").replace(/^\s*×/, "").trim();
}
