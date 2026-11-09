import { describe, expect, it } from "vitest";

import type { NotificationEntry } from "../models";
import {
  MAX_NOTIFICATIONS,
  isPlotlyPrefix,
  markAllRead,
  newNotification,
  notifierMessage,
  parseNotifications,
  plotlyLogMessage,
  plotlyLogType,
  prependNotification,
  shouldForwardLog,
} from "./notifications";

const entry = (id: number, over: Partial<NotificationEntry> = {}): NotificationEntry => ({
  id,
  message: `m${id}`,
  type: "info",
  timestamp: id,
  read: false,
  ...over,
});

describe("parseNotifications", () => {
  it("is the saved list and unread count", () => {
    const saved = [entry(1), entry(2, { read: true })];
    expect(parseNotifications(JSON.stringify({ n: saved, u: 3 }))).toEqual({ notifications: saved, unreadCount: 3 });
  });

  it("is empty for a part that was not saved", () => {
    expect(parseNotifications(JSON.stringify({ u: 2 }))).toEqual({ notifications: [], unreadCount: 2 });
    expect(parseNotifications(JSON.stringify({ n: [entry(1)] }))).toEqual({ notifications: [entry(1)], unreadCount: 0 });
    expect(parseNotifications("{}")).toEqual({ notifications: [], unreadCount: 0 });
  });

  it("keeps a saved count of zero", () => {
    expect(parseNotifications(JSON.stringify({ n: [], u: 0 }))?.unreadCount).toBe(0);
  });

  it("is empty for saved json that is a plain value", () => {
    expect(parseNotifications("5")).toEqual({ notifications: [], unreadCount: 0 });
    expect(parseNotifications('"text"')).toEqual({ notifications: [], unreadCount: 0 });
  });

  it("is null when nothing is saved or it cannot be read", () => {
    for (const raw of [null, "", "garbage", "{broken", "null"]) expect(parseNotifications(raw)).toBeNull();
  });
});

describe("newNotification", () => {
  it("is the message and type with the time, unread unless told otherwise", () => {
    expect(newNotification("hello", "success", false, 1000, 0.25)).toEqual({
      id: 1000.25,
      message: "hello",
      type: "success",
      timestamp: 1000,
      read: false,
    });
  });

  it("can start out read", () => {
    expect(newNotification("hello", "info", true, 1000, 0.5).read).toBe(true);
  });

  it("gives entries made in the same millisecond different ids", () => {
    expect(newNotification("a", "info", false, 1000, 0.1).id).not.toBe(newNotification("a", "info", false, 1000, 0.2).id);
  });

  it("passes the type through", () => {
    expect(newNotification("a", "weird", false, 1, 0).type).toBe("weird");
  });
});

describe("prependNotification", () => {
  it("puts the new entry first, in place", () => {
    const list = [entry(1), entry(2)];
    const same = list;
    prependNotification(list, entry(3));
    expect(list).toBe(same);
    expect(list.map((n) => n.id)).toEqual([3, 1, 2]);
  });

  it("keeps the newest hundred", () => {
    expect(MAX_NOTIFICATIONS).toBe(100);
    const list = Array.from({ length: 100 }, (_, i) => entry(i));
    prependNotification(list, entry(1000));
    expect(list).toHaveLength(100);
    expect(list[0]!.id).toBe(1000);
    expect(list[99]!.id).toBe(98);
  });

  it("does not drop anything below the limit", () => {
    const list = Array.from({ length: 99 }, (_, i) => entry(i));
    prependNotification(list, entry(1000));
    expect(list).toHaveLength(100);
    expect(list[99]!.id).toBe(98);
  });

  it("takes a limit of its own", () => {
    const list = [entry(1), entry(2), entry(3)];
    prependNotification(list, entry(4), 3);
    expect(list.map((n) => n.id)).toEqual([4, 1, 2]);
  });
});

describe("markAllRead", () => {
  it("marks every entry read, in place", () => {
    const list = [entry(1), entry(2, { read: true }), entry(3)];
    markAllRead(list);
    expect(list.every((n) => n.read)).toBe(true);
  });

  it("does nothing to an empty list", () => {
    const list: NotificationEntry[] = [];
    markAllRead(list);
    expect(list).toEqual([]);
  });
});

describe("plotlyLogMessage", () => {
  it("joins the arguments with spaces as text", () => {
    expect(plotlyLogMessage(["Invalid", 5, null, undefined, { toString: () => "obj" }])).toBe("Invalid 5 null undefined obj");
  });

  it("is empty for no arguments", () => {
    expect(plotlyLogMessage([])).toBe("");
  });

  it("keeps at most 160 characters", () => {
    expect(plotlyLogMessage(["x".repeat(160)])).toHaveLength(160);
    expect(plotlyLogMessage(["x".repeat(161)])).toHaveLength(160);
    expect(plotlyLogMessage(["x".repeat(500)])).toBe("x".repeat(160));
  });
});

describe("plotly log prefixes", () => {
  it("recognizes WARN: and ERROR: only", () => {
    expect(isPlotlyPrefix("WARN:")).toBe(true);
    expect(isPlotlyPrefix("ERROR:")).toBe(true);
    for (const other of ["", "warn:", "INFO:", "WARN", "error", "WARN: x"]) expect(isPlotlyPrefix(other)).toBe(false);
  });

  it("makes an error of ERROR: and an info of anything else", () => {
    expect(plotlyLogType("ERROR:")).toBe("error");
    expect(plotlyLogType("WARN:")).toBe("info");
  });
});

describe("shouldForwardLog", () => {
  // a real clock reading, far from time zero
  const T = 1_700_000_000_000;

  it("lets a message through the first time and remembers when", () => {
    const recent = new Map<string, number>();
    expect(shouldForwardLog(recent, "a", T)).toBe(true);
    expect(recent.get("a")).toBe(T);
  });

  it("holds the same message back for ten seconds", () => {
    const recent = new Map<string, number>();
    shouldForwardLog(recent, "a", T);
    expect(shouldForwardLog(recent, "a", T + 1)).toBe(false);
    expect(shouldForwardLog(recent, "a", T + 9999)).toBe(false);
  });

  it("lets it through again once ten seconds have passed", () => {
    const recent = new Map<string, number>();
    shouldForwardLog(recent, "a", T);
    expect(shouldForwardLog(recent, "a", T + 10_000)).toBe(true);
    expect(recent.get("a")).toBe(T + 10_000);
  });

  it("counts from the last time it was shown, not the last time it was seen", () => {
    const recent = new Map<string, number>();
    shouldForwardLog(recent, "a", T);
    expect(shouldForwardLog(recent, "a", T + 8000)).toBe(false);
    expect(recent.get("a")).toBe(T);
    expect(shouldForwardLog(recent, "a", T + 10_000)).toBe(true);
  });

  it("treats different messages separately", () => {
    const recent = new Map<string, number>();
    shouldForwardLog(recent, "a", T);
    expect(shouldForwardLog(recent, "b", T + 1)).toBe(true);
  });

  // a message never seen counts as seen at time zero, so only a clock reading
  // of ten seconds or more lets a first message through (always true in practice)
  it("holds back a first message when the clock reads under ten seconds", () => {
    expect(shouldForwardLog(new Map(), "a", 0)).toBe(false);
    expect(shouldForwardLog(new Map(), "a", 9999)).toBe(false);
    expect(shouldForwardLog(new Map(), "a", 10_000)).toBe(true);
  });
});

describe("notifierMessage", () => {
  it("is the note's text", () => {
    expect(notifierMessage("Double-click to zoom back out")).toBe("Double-click to zoom back out");
  });

  it("drops a leading close mark and the space around the text", () => {
    expect(notifierMessage("× Taking snapshot...")).toBe("Taking snapshot...");
    expect(notifierMessage("  ×  hello  ")).toBe("hello");
  });

  it("leaves a close mark that is not at the start", () => {
    expect(notifierMessage("a × b")).toBe("a × b");
    expect(notifierMessage("x×")).toBe("x×");
  });

  it("only drops the first close mark", () => {
    expect(notifierMessage("××")).toBe("×");
  });

  it("is empty for just a close mark, or no text", () => {
    expect(notifierMessage("×")).toBe("");
    expect(notifierMessage("  ")).toBe("");
    expect(notifierMessage(null)).toBe("");
  });
});
