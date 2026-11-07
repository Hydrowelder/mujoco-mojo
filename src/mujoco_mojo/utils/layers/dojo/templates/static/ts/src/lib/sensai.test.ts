// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  STORAGE_KEY,
  chatHistory,
  chatRequestBody,
  composerSize,
  createSseParser,
  enabledFromSettings,
  historyExport,
  historyFileName,
  isAtBottom,
  loadMessages,
  messageLayout,
  resultContent,
  revealStep,
  saveMessages,
  storedMessages,
  type SensAIMessage,
  type SseEvent,
} from "./sensai";

const msg = (over: Partial<SensAIMessage> = {}): SensAIMessage => ({
  role: "user",
  content: "hello",
  ts: 1000,
  ...over,
});

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

const ev = (type: string, payload: object) => `event: ${type}\ndata: ${JSON.stringify(payload)}\n\n`;

describe("createSseParser", () => {
  const parseAll = (...chunks: string[]): SseEvent[] => {
    const p = createSseParser();
    return [...chunks.flatMap((c) => p.feed(c)), ...p.end()];
  };

  it("reads an event's type and its json data", () => {
    expect(parseAll(ev("result", { message: "hi" }))).toEqual([{ type: "result", payload: { message: "hi" } }]);
  });

  it("reads several events in a row", () => {
    expect(parseAll(ev("tool_call", { label: "looking" }) + ev("text_delta", { delta: "a" }) + ev("result", {}))).toEqual([
      { type: "tool_call", payload: { label: "looking" } },
      { type: "text_delta", payload: { delta: "a" } },
      { type: "result", payload: {} },
    ]);
  });

  it("waits for the end of a line before reading it", () => {
    const p = createSseParser();
    expect(p.feed("event: result\ndata: {\"message\": \"sp")).toEqual([]);
    expect(p.feed("lit\"}")).toEqual([]);
    expect(p.feed("\n\n")).toEqual([{ type: "result", payload: { message: "split" } }]);
  });

  it("gives the same events however the text is cut up", () => {
    const text = ev("tool_call", { label: "x" }) + ev("text_delta", { delta: "héllo ☃" }) + ev("result", { message: "done" });
    const whole = parseAll(text);
    for (const size of [1, 2, 3, 5, 7, 11]) {
      const chunks = text.match(new RegExp(`[\\s\\S]{1,${size}}`, "g"))!;
      expect(parseAll(...chunks)).toEqual(whole);
    }
    expect(whole).toHaveLength(3);
  });

  it("reads lines that end in a carriage return and a newline", () => {
    expect(parseAll('event: result\r\ndata: {"message": "crlf"}\r\n\r\n')).toEqual([
      { type: "result", payload: { message: "crlf" } },
    ]);
  });

  it("reads a last line that has no newline when the stream ends", () => {
    const p = createSseParser();
    expect(p.feed('event: result\ndata: {"message": "tail"}')).toEqual([]);
    expect(p.end()).toEqual([{ type: "result", payload: { message: "tail" } }]);
  });

  it("has nothing left to read when the stream ends on a newline", () => {
    const p = createSseParser();
    p.feed(ev("result", {}));
    expect(p.end()).toEqual([]);
    expect(createSseParser().end()).toEqual([]);
  });

  it("skips a data line that is not valid json and goes on", () => {
    expect(parseAll("event: result\ndata: {not json}\n\n" + ev("result", { message: "after" }))).toEqual([
      { type: "result", payload: { message: "after" } },
    ]);
  });

  it("gives data with no event line an empty type", () => {
    expect(parseAll('data: {"message": "orphan"}\n\n')).toEqual([{ type: "", payload: { message: "orphan" } }]);
  });

  it("forgets the type at a blank line", () => {
    expect(parseAll('event: result\n\ndata: {"message": "after blank"}\n\n')).toEqual([
      { type: "", payload: { message: "after blank" } },
    ]);
  });

  it("keeps the type for every data line until the blank line", () => {
    expect(parseAll('event: text_delta\ndata: {"delta": "a"}\ndata: {"delta": "b"}\n\n')).toEqual([
      { type: "text_delta", payload: { delta: "a" } },
      { type: "text_delta", payload: { delta: "b" } },
    ]);
  });

  it("ignores comments, other fields, and lines indented or missing the space after the colon", () => {
    const text = [
      ": a comment",
      "retry: 5",
      "id: 9",
      "event:result",
      'data:{"message": "no space"}',
      ' event: result',
      ' data: {"message": "indented"}',
      "",
      "",
    ].join("\n");
    expect(parseAll(text)).toEqual([]);
  });

  it("does not take an event line with no space after the colon as a type", () => {
    expect(parseAll('event:result\ndata: {"message": "x"}\n\n')).toEqual([{ type: "", payload: { message: "x" } }]);
  });

  it("ignores a data line with no space after the colon, even when the rest is valid json", () => {
    expect(parseAll("event: result\ndata:12345\n\n")).toEqual([]);
  });

  it("ignores spaces at the end of a line", () => {
    expect(parseAll('event: result   \ndata: {"message": "x"}   \n\n')).toEqual([
      { type: "result", payload: { message: "x" } },
    ]);
  });

  it("keeps non-ascii text intact", () => {
    expect(parseAll(ev("result", { message: "héllo wörld ☃ 日本語" }))[0]!.payload.message).toBe("héllo wörld ☃ 日本語");
  });
});

describe("resultContent", () => {
  it("is the final message when there is one", () => {
    expect(resultContent("final", "streamed so far")).toBe("final");
    expect(resultContent("  ", "streamed")).toBe("  ");
  });

  it("is what streamed in when the final message is empty or not text", () => {
    expect(resultContent("", "streamed so far")).toBe("streamed so far");
    expect(resultContent(undefined, "streamed so far")).toBe("streamed so far");
    expect(resultContent(42, "streamed so far")).toBe("streamed so far");
    expect(resultContent(null, "streamed so far")).toBe("streamed so far");
  });

  it("says there was no response when there is nothing at all", () => {
    expect(resultContent("", "")).toBe("(no response)");
    expect(resultContent(undefined, "")).toBe("(no response)");
    expect(resultContent(7, "")).toBe("(no response)");
  });
});

describe("revealStep", () => {
  it("reveals one character at a time for a short backlog", () => {
    expect(revealStep(1)).toBe(1);
    expect(revealStep(30)).toBe(1);
    expect(revealStep(0)).toBe(1);
  });

  it("grows with the backlog so a large burst drains quickly", () => {
    expect(revealStep(31)).toBe(2);
    expect(revealStep(60)).toBe(2);
    expect(revealStep(61)).toBe(3);
    expect(revealStep(300)).toBe(10);
    expect(revealStep(3000)).toBe(100);
  });

  // each tick takes a thirtieth of what is left, so the time to drain grows
  // with the log of the backlog (about 16 ms a tick), not with the backlog itself
  it.each([
    [1, 1],
    [30, 30],
    [100, 57],
    [300, 87],
    [3000, 154],
  ])("drains a backlog of %i characters in %i ticks", (backlog, expected) => {
    let left = backlog;
    let ticks = 0;
    while (left > 0) {
      left -= revealStep(left);
      ticks++;
    }
    expect(ticks).toBe(expected);
  });
});

describe("chatHistory", () => {
  const many = (n: number): SensAIMessage[] =>
    Array.from({ length: n }, (_, i) => msg({ role: i % 2 ? "assistant" : "user", content: `m${i}`, ts: i }));

  it("leaves out the message just sent", () => {
    expect(chatHistory([msg({ content: "old" }), msg({ content: "just sent" })]).map((m) => m.content)).toEqual(["old"]);
  });

  it("is empty when only the new message exists", () => {
    expect(chatHistory([msg()])).toEqual([]);
    expect(chatHistory([])).toEqual([]);
  });

  it("keeps the last twenty before the new message", () => {
    const h = chatHistory(many(30));
    expect(h).toHaveLength(20);
    expect(h[0]!.content).toBe("m9");
    expect(h[19]!.content).toBe("m28");
  });

  it("keeps all of a shorter history", () => {
    expect(chatHistory(many(21))).toHaveLength(20);
    expect(chatHistory(many(20))).toHaveLength(19);
    expect(chatHistory(many(4))).toHaveLength(3);
  });

  it("carries only the role and the text", () => {
    const [m] = chatHistory([msg({ role: "assistant", content: "a", error: true, routed_to: "x", plot_config_update: { t: 1 } }), msg()]);
    expect(m).toEqual({ role: "assistant", content: "a" });
  });
});

describe("chatRequestBody", () => {
  it("is the message, the history, and the plot config", () => {
    const body = chatRequestBody("what now", [msg({ content: "earlier" }), msg({ content: "what now" })], '{"title":"T"}');
    expect(body).toEqual({
      message: "what now",
      message_history: [{ role: "user", content: "earlier" }],
      all_columns: [],
      rotatable_vectors: [],
      available_quats: [],
      current_plot_config_json: '{"title":"T"}',
    });
  });

  it("sends null when there is no stored plot config", () => {
    expect((chatRequestBody("q", [msg()], null) as { current_plot_config_json: unknown }).current_plot_config_json).toBeNull();
  });
});

describe("saved messages", () => {
  it("round-trips through localStorage under its own key", () => {
    const messages = [msg({ content: "a", ts: 5 }), msg({ role: "assistant", content: "b", ts: 6, error: true })];
    saveMessages(messages);
    expect(STORAGE_KEY).toBe("sensai-messages");
    expect(JSON.parse(localStorage.getItem("sensai-messages")!)).toEqual(messages);
    expect(loadMessages()).toEqual(messages);
  });

  it("fills in a timestamp for a message saved without one, and keeps the ones it has", () => {
    vi.spyOn(Date, "now").mockReturnValue(777);
    localStorage.setItem(STORAGE_KEY, JSON.stringify([{ role: "user", content: "old" }, { role: "user", content: "zero", ts: 0 }, { role: "user", content: "x", ts: 9 }]));
    expect(loadMessages()!.map((m) => m.ts)).toEqual([777, 0, 9]);
  });

  it("is null when nothing is saved or what is saved cannot be read", () => {
    expect(loadMessages()).toBeNull();
    for (const bad of ["", "{broken", "{}", "null", "42"]) {
      localStorage.setItem(STORAGE_KEY, bad);
      expect(loadMessages()).toBeNull();
    }
  });

  it("is an empty history when the saved list is empty", () => {
    localStorage.setItem(STORAGE_KEY, "[]");
    expect(loadMessages()).toEqual([]);
  });

  it("does not throw when storage refuses to read or write", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    expect(loadMessages()).toBeNull();
    expect(() => saveMessages([msg()])).not.toThrow();
  });

  it("is read back exactly as stored for the download, with no timestamp added", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([{ role: "user", content: "old" }]));
    expect(storedMessages()).toEqual([{ role: "user", content: "old" }]);
  });

  it("is an empty list for the download when nothing or garbage is stored", () => {
    expect(storedMessages()).toEqual([]);
    localStorage.setItem(STORAGE_KEY, "{broken");
    expect(storedMessages()).toEqual([]);
  });
});

describe("historyExport", () => {
  const NOW = new Date("2026-03-04T05:06:07.000Z");
  const T = Date.parse("2026-03-04T01:02:03.000Z");

  it("records when it was exported", () => {
    expect(historyExport([], NOW)).toEqual({ exported_at: "2026-03-04T05:06:07.000Z", messages: [] });
  });

  it("gives each message a time, sender and text", () => {
    const out = historyExport([msg({ ts: T, content: "hi" }), msg({ role: "assistant", ts: T + 1000, content: "yo" })], NOW) as {
      messages: Array<Record<string, unknown>>;
    };
    expect(out.messages).toEqual([
      { timestamp: "2026-03-04T01:02:03.000Z", sender: "user", message: "hi" },
      { timestamp: "2026-03-04T01:02:04.000Z", sender: "sensai", message: "yo" },
    ]);
  });

  it("adds the error flag, route and plot update only when a message has them", () => {
    const out = historyExport(
      [
        msg({ role: "assistant", ts: T, error: true }),
        msg({ role: "assistant", ts: T, routed_to: "undo" }),
        msg({ role: "assistant", ts: T, plot_config_update: { title: "T" } }),
        msg({ role: "assistant", ts: T, plot_config_update: null }),
      ],
      NOW,
    ) as { messages: Array<Record<string, unknown>> };
    expect(out.messages[0]).toMatchObject({ error: true });
    expect(out.messages[1]).toMatchObject({ routed_to: "undo" });
    expect(out.messages[2]).toMatchObject({ plot_config_update: { title: "T" } });
    expect(out.messages[3]).toMatchObject({ plot_config_update: null });
    expect(Object.keys(out.messages[0]!)).toEqual(["timestamp", "sender", "message", "error"]);
  });

  it("leaves out a flag that is off, an empty route, and a missing plot update", () => {
    const out = historyExport([msg({ role: "assistant", ts: T, error: false, routed_to: "" })], NOW) as {
      messages: Array<Record<string, unknown>>;
    };
    expect(Object.keys(out.messages[0]!)).toEqual(["timestamp", "sender", "message"]);
  });

  it("keeps a plot update that is falsy but present", () => {
    const [m] = (historyExport([msg({ ts: T, plot_config_update: 0 as never })], NOW) as { messages: Array<Record<string, unknown>> }).messages;
    expect(m).toHaveProperty("plot_config_update", 0);
  });
});

describe("historyFileName", () => {
  it("is named for the day, in UTC", () => {
    expect(historyFileName(new Date("2026-03-04T05:06:07.000Z"))).toBe("sensai-chat-2026-03-04.json");
    expect(historyFileName(new Date("2026-12-31T23:59:59.000Z"))).toBe("sensai-chat-2026-12-31.json");
  });
});

describe("enabledFromSettings", () => {
  it("is the saved flag when the event carries one", () => {
    expect(enabledFromSettings({ dojo: { sensai: { enabled: true } } })).toBe(true);
    expect(enabledFromSettings({ dojo: { sensai: { enabled: false } } })).toBe(false);
  });

  it("is undefined when it carries no flag, or one that is not a boolean", () => {
    expect(enabledFromSettings({ dojo: { sensai: {} } })).toBeUndefined();
    expect(enabledFromSettings({ dojo: {} })).toBeUndefined();
    expect(enabledFromSettings({})).toBeUndefined();
    expect(enabledFromSettings(null)).toBeUndefined();
    expect(enabledFromSettings(undefined)).toBeUndefined();
    expect(enabledFromSettings({ dojo: { sensai: { enabled: "yes" as never } } })).toBeUndefined();
  });
});

describe("isAtBottom", () => {
  it("counts as the bottom within thirty pixels of the end", () => {
    expect(isAtBottom(1000, 600, 400)).toBe(true); // 0 away
    expect(isAtBottom(1000, 571, 400)).toBe(true); // 29 away
  });

  it("does not at thirty pixels or more", () => {
    expect(isAtBottom(1000, 570, 400)).toBe(false); // 30 away
    expect(isAtBottom(1000, 500, 400)).toBe(false);
  });

  it("counts a short list that fits as at the bottom", () => {
    expect(isAtBottom(300, 0, 400)).toBe(true);
  });
});

describe("composerSize", () => {
  it("fits its text, without a scrollbar, up to six lines", () => {
    expect(composerSize(30, "20px")).toEqual({ height: "30px", overflowY: "hidden" });
    expect(composerSize(120, "20px")).toEqual({ height: "120px", overflowY: "hidden" });
  });

  it("stops at six lines and scrolls", () => {
    expect(composerSize(121, "20px")).toEqual({ height: "120px", overflowY: "auto" });
    expect(composerSize(900, "20px")).toEqual({ height: "120px", overflowY: "auto" });
  });

  it("goes by the line height it is given", () => {
    expect(composerSize(200, "30px")).toEqual({ height: "180px", overflowY: "auto" });
    expect(composerSize(170, "30px")).toEqual({ height: "170px", overflowY: "hidden" });
  });

  it("assumes a 20px line when the line height is not a number", () => {
    expect(composerSize(500, "normal")).toEqual({ height: "120px", overflowY: "auto" });
    expect(composerSize(500, "")).toEqual({ height: "120px", overflowY: "auto" });
  });
});

describe("messageLayout", () => {
  it("shows a message of two and a half lines or fewer whole", () => {
    expect(messageLayout("user", 50, "20px")).toEqual({ single: true, open: true });
    expect(messageLayout("assistant", 20, "20px")).toEqual({ single: true, open: true });
  });

  it("starts a longer user message collapsed", () => {
    expect(messageLayout("user", 51, "20px")).toEqual({ single: false, open: false });
  });

  it("starts a longer assistant message open", () => {
    expect(messageLayout("assistant", 51, "20px")).toEqual({ single: false, open: true });
  });

  it("goes by the line height it is given", () => {
    expect(messageLayout("user", 75, "30px")).toEqual({ single: true, open: true });
    expect(messageLayout("user", 76, "30px")).toEqual({ single: false, open: false });
  });

  it("assumes a 22px line when the line height is not a number", () => {
    expect(messageLayout("user", 55, "normal")).toEqual({ single: true, open: true });
    expect(messageLayout("user", 56, "normal")).toEqual({ single: false, open: false });
  });
});
