// the trial viewer's log table: which entries show, in what order, and how
// each level is colored

import type { LogEntry } from "../models";
import { notifTimeAgo } from "./format";

// matches Python's logging severity ordering
export const LOG_LEVEL_SEVERITY: Record<string, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40,
  CRITICAL: 50,
};

export type LogSortKey = "timestamp" | "level";

export interface LogFilter {
  // empty = every level
  levels: string[];
  message: string;
  // whether `message` is a regex (case-insensitive) rather than a substring
  regex: boolean;
  sortKey: LogSortKey;
  sortAsc: boolean;
}

// the entries that pass the level and message filters, sorted. an invalid
// regex quietly falls back to a substring match. sorting by level breaks ties
// oldest first whichever way the level order runs
export function filterLogEntries(entries: LogEntry[], filter: LogFilter): LogEntry[] {
  const text = filter.message.trim();
  let regex: RegExp | null = null;
  if (text && filter.regex) {
    try {
      regex = new RegExp(text, "i");
    } catch {
      regex = null;
    }
  }

  const filtered = entries.filter((e) => {
    if (filter.levels.length > 0 && !filter.levels.includes(e.level)) return false;
    if (text) {
      if (regex) {
        if (!regex.test(e.message)) return false;
      } else if (!e.message.toLowerCase().includes(text.toLowerCase())) {
        return false;
      }
    }
    return true;
  });

  const dir = filter.sortAsc ? 1 : -1;
  return filtered.slice().sort((a, b) => {
    if (filter.sortKey === "level") {
      const av = LOG_LEVEL_SEVERITY[a.level] ?? 0;
      const bv = LOG_LEVEL_SEVERITY[b.level] ?? 0;
      return av === bv ? a.timestamp - b.timestamp : (av - bv) * dir;
    }
    return (a.timestamp - b.timestamp) * dir;
  });
}

// the distinct levels present, least severe first
export function logLevelsOf(entries: LogEntry[]): string[] {
  return Array.from(new Set(entries.map((e) => e.level))).sort(
    (a, b) => (LOG_LEVEL_SEVERITY[a] ?? 0) - (LOG_LEVEL_SEVERITY[b] ?? 0),
  );
}

export function logLevelClass(level: string): string {
  switch (level) {
    case "CRITICAL":
      return "bg-danger-500 dark:bg-danger-900/50 text-white dark:text-white";
    case "ERROR":
      return "bg-danger-100 dark:bg-danger-900/50 text-danger-700 dark:text-danger-400";
    case "WARNING":
      return "bg-warning-100 dark:bg-warning-900/50 text-warning-700 dark:text-warning-400";
    case "INFO":
      return "bg-success-100 dark:bg-success-900/50 text-success-700 dark:text-success-400";
    case "DEBUG":
      return "bg-accent-100 dark:bg-accent-900/50 text-accent-700 dark:text-accent-400";
    default:
      return "bg-chip text-ink-secondary";
  }
}

// the file name and line a log entry came from, for the table cell
export function logSourceShort(entry: LogEntry): string {
  const file = entry.pathname.split("/").pop() ?? "";
  return entry.lineno != null ? `${file}:${entry.lineno}` : file;
}

// the full path and line, for the cell's tooltip
export function logSourceFull(entry: LogEntry): string {
  return entry.lineno != null ? `${entry.pathname}:${entry.lineno}` : entry.pathname;
}

// "5m ago" style for the last day, the full local date and time before that.
// `tick` is only there so a template expression re-evaluates when it changes
export function formatLogTime(timestamp: number, tick?: number): string {
  const diff = Date.now() - timestamp;
  if (diff < 24 * 60 * 60 * 1000) return notifTimeAgo(timestamp, tick);
  return new Date(timestamp).toLocaleString();
}

// the narrowest each log column can be dragged to
export const LOG_COL_MIN: Record<"time" | "level" | "source", number> = {
  time: 60,
  level: 56,
  source: 60,
};

// a log column's width while it is dragged: moved by the mouse, never below its minimum
export function resizedLogColumnWidth(
  col: "time" | "level" | "source",
  startWidth: number,
  dx: number,
): number {
  return Math.max(LOG_COL_MIN[col], startWidth + dx);
}

const HEADER_ICON_ALLOWANCE = 20; // sort chevron + gap
const CELL_PADDING = 16; // px-2 on the cell (8px each side)
const BADGE_PADDING = 16; // px-2 on the level badge (8px each side)

// a log column's width to fit its contents: the widest of its header (plus room
// for the sort chevron) and every cell, rounded up, plus the cell's padding
// (and the badge's, for the level column).
export function fittedLogColumnWidth(
  col: "time" | "level" | "source",
  headerWidth: number,
  contentWidths: number[],
): number {
  let width = headerWidth + HEADER_ICON_ALLOWANCE;
  for (const w of contentWidths) width = Math.max(width, w);
  const padding = col === "level" ? CELL_PADDING + BADGE_PADDING : CELL_PADDING;
  return Math.ceil(width) + padding;
}
