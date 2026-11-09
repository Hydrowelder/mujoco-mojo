// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  OPEN_KEY,
  PINNED_KEY,
  ACTIVE_TAB_KEY,
  STORAGE_KEY,
  TABS_KEY,
  applyToolEvent,
  blankTab,
  chatHistory,
  chatRequestBody,
  composerSize,
  createSseParser,
  defaultTabTitle,
  enabledFromSettings,
  finalToolCalls,
  historyExport,
  headerTooltip,
  historyFileName,
  isAtBottom,
  promptScrollTop,
  rememberedScroll,
  SCROLL_HOLD_MS,
  lastUserIndex,
  BUBBLE_MS,
  BUBBLE_SETTLE_MS,
  bubbleStyle,
  fullBubbleHeight,
  groupExchanges,
  loadMessages,
  loadOpen,
  loadPinned,
  loadSensAITabs,
  messageLayout,
  resultContent,
  revealStep,
  saveOpen,
  savePinned,
  saveSensAITabs,
  tabsExport,
  titleFromMessage,
  toolCallTooltip,
  toolCallsTitle,
  toolDotClass,
  type SensAIMessage,
  type SensAITab,
  type SensAIToolCall,
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
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

// storage that refuses a write or a read, as it does when it is full or blocked.
// the whole of `localStorage` is replaced: a spy on Storage.prototype does
// nothing once the page has used a method, because happy-dom keeps handing out
// the one it returned first, so a test that spied would pass without testing
function stubStorage(fail: { read?: boolean; write?: (key: string) => boolean }): Map<string, string> {
  const data = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => {
      if (fail.read) throw new Error("storage refused a read");
      return data.get(key) ?? null;
    },
    setItem: (key: string, value: string) => {
      if (fail.write?.(key)) throw new Error("storage refused a write");
      data.set(key, String(value));
    },
    removeItem: (key: string) => {
      data.delete(key);
    },
    clear: () => data.clear(),
  });
  return data;
}

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
    const body = chatRequestBody("what now", [msg({ content: "earlier" }), msg({ content: "what now" })], '{"title":"T"}', null);
    expect(body).toEqual({
      message: "what now",
      message_history: [{ role: "user", content: "earlier" }],
      all_columns: [],
      rotatable_vectors: [],
      available_quats: [],
      current_plot_config_json: '{"title":"T"}',
      versus: null,
    });
  });

  it("sends null when there is no stored plot config", () => {
    expect((chatRequestBody("q", [msg()], null, null) as { current_plot_config_json: unknown }).current_plot_config_json).toBeNull();
  });

  it("sends the trial's signals so the agent can check the names it uses", () => {
    const manifest = {
      all: ["time", "Bodies/B/xpos:x", "Bodies/B/quat:w"],
      rotatable_vectors: ["Bodies/B/xpos"],
      available_quats: ["Bodies/B/quat"],
    };

    expect(chatRequestBody("q", [msg()], null, manifest)).toMatchObject({
      all_columns: ["time", "Bodies/B/xpos:x", "Bodies/B/quat:w"],
      rotatable_vectors: ["Bodies/B/xpos"],
      available_quats: ["Bodies/B/quat"],
    });
  });

  it("sends empty lists away from a trial, where there are no signals", () => {
    expect(chatRequestBody("q", [msg()], null, null)).toMatchObject({
      all_columns: [],
      rotatable_vectors: [],
      available_quats: [],
    });
  });
});

describe("the history from before tabs", () => {
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

  it("does not throw when storage refuses to read", () => {
    stubStorage({ read: true });
    expect(loadMessages()).toBeNull();
  });
});

const tab = (over: Partial<SensAITab> = {}): SensAITab => ({
  id: "t1",
  title: "Chat 1",
  messages: [],
  ...over,
});

describe("defaultTabTitle", () => {
  it("is Chat 1 for the first chat", () => {
    expect(defaultTabTitle([])).toBe("Chat 1");
  });

  it("is one more than the largest number in use, so it never takes an open chat's name", () => {
    expect(defaultTabTitle([tab({ title: "Chat 1" }), tab({ title: "Chat 3" })])).toBe("Chat 4");
  });

  it("does not count a title the user or a message gave", () => {
    expect(defaultTabTitle([tab({ title: "Wheel speed" }), tab({ title: "Chat 2 notes" })])).toBe("Chat 1");
  });
});

describe("blankTab", () => {
  it("is empty, titled by number and still free to be retitled by its first message", () => {
    const blank = blankTab([tab({ title: "Chat 1" })]);
    expect(blank).toMatchObject({ title: "Chat 2", messages: [], autoTitled: true });
    expect(blank.id).not.toBe("");
  });

  it("gets an id no other chat has", () => {
    expect(blankTab([]).id).not.toBe(blankTab([]).id);
  });
});

describe("titleFromMessage", () => {
  it("is a short message as it is", () => {
    expect(titleFromMessage("plot box1")).toBe("plot box1");
  });

  it("is one line, with runs of whitespace and newlines made single spaces", () => {
    expect(titleFromMessage("  plot\n\nbox1   xpos  ")).toBe("plot box1 xpos");
  });

  it("keeps a whole sentence, so the tooltip can show a name the tab itself has to cut short", () => {
    const sentence = "add the angular velocity of the other body to the plot";
    expect(titleFromMessage(sentence)).toBe(sentence);
  });

  it("is cut with an ellipsis past 80 characters, 80 in all", () => {
    const title = titleFromMessage("word ".repeat(30));
    expect(title.length).toBeLessThanOrEqual(80);
    expect(title.endsWith("\u2026")).toBe(true);
    const long = titleFromMessage("a".repeat(200));
    expect(long).toHaveLength(80);
    expect(long.endsWith("\u2026")).toBe(true);
  });

  it("keeps a message of exactly 80 characters whole", () => {
    expect(titleFromMessage("a".repeat(80))).toBe("a".repeat(80));
  });

  it("does not leave a space in front of the ellipsis", () => {
    expect(titleFromMessage(`${"a".repeat(78)} bcd`)).toBe(`${"a".repeat(78)}\u2026`);
  });
});

describe("saved chats", () => {
  it("round-trip through localStorage, with which one was open", () => {
    const chats = [tab({ id: "a", title: "One", messages: [msg({ content: "hi", ts: 5 })] }), tab({ id: "b", title: "Two" })];
    saveSensAITabs(chats, "b");
    expect(loadSensAITabs()).toEqual({ tabs: chats, activeId: "b" });
    expect(TABS_KEY).toBe("sensai-tabs");
    expect(ACTIVE_TAB_KEY).toBe("sensai-active-tab");
  });

  it("start with one empty chat on a first visit", () => {
    const { tabs, activeId } = loadSensAITabs();
    expect(tabs).toHaveLength(1);
    expect(tabs[0]).toMatchObject({ title: "Chat 1", messages: [] });
    expect(activeId).toBe(tabs[0]!.id);
  });

  it("take the history from before tabs as the first chat", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([{ role: "user", content: "old", ts: 3 }]));
    const { tabs } = loadSensAITabs();
    expect(tabs).toHaveLength(1);
    expect(tabs[0]!.messages).toEqual([{ role: "user", content: "old", ts: 3 }]);
  });

  it("drop the history from before tabs once the chats are saved, so it cannot return as a copy", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([{ role: "user", content: "old", ts: 3 }]));
    saveSensAITabs(loadSensAITabs().tabs, "x");
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(loadSensAITabs().tabs[0]!.messages).toHaveLength(1);
  });

  it("do not drop the old history when the chats could not be written", () => {
    const data = stubStorage({ write: (key) => key === TABS_KEY });
    data.set(STORAGE_KEY, JSON.stringify([{ role: "user", content: "old", ts: 3 }]));

    saveSensAITabs([tab()], "t1");

    expect(data.has(TABS_KEY)).toBe(false);
    expect(data.has(STORAGE_KEY)).toBe(true);
  });

  it("open the one that was open, or the first when it is gone", () => {
    saveSensAITabs([tab({ id: "a" }), tab({ id: "b" })], "b");
    expect(loadSensAITabs().activeId).toBe("b");
    saveSensAITabs([tab({ id: "a" }), tab({ id: "b" })], "gone");
    expect(loadSensAITabs().activeId).toBe("a");
  });

  it("fill in a timestamp, a title and a message list that a saved chat lacks", () => {
    vi.spyOn(Date, "now").mockReturnValue(888);
    localStorage.setItem(TABS_KEY, JSON.stringify([{ id: "a", messages: [{ role: "user", content: "x" }] }, { id: "b", title: "B" }]));
    const { tabs } = loadSensAITabs();
    expect(tabs[0]).toMatchObject({ title: "Chat", messages: [{ role: "user", content: "x", ts: 888 }] });
    expect(tabs[1]).toMatchObject({ title: "B", messages: [] });
  });

  it("start afresh when the saved chats cannot be read, or are an empty list", () => {
    for (const bad of ["{broken", "[]", "null", "{}"]) {
      localStorage.setItem(TABS_KEY, bad);
      const { tabs } = loadSensAITabs();
      expect(tabs).toHaveLength(1);
      expect(tabs[0]!.messages).toEqual([]);
    }
  });

  it("do not throw when storage refuses to read or write", () => {
    stubStorage({ read: true, write: () => true });
    expect(loadSensAITabs().tabs).toHaveLength(1);
    expect(() => saveSensAITabs([tab()], "t1")).not.toThrow();
  });

  it("keep a chat's unsent text and its unread mark", () => {
    saveSensAITabs([tab({ draft: "half a thought", unread: true })], "t1");
    expect(loadSensAITabs().tabs[0]).toMatchObject({ draft: "half a thought", unread: true });
  });
});

describe("tabsExport", () => {
  const NOW = new Date("2026-03-04T05:06:07.000Z");
  const T = Date.parse("2026-03-04T01:02:03.000Z");

  it("records when it was exported, with no chats when there are none", () => {
    expect(tabsExport([], NOW)).toEqual({ exported_at: "2026-03-04T05:06:07.000Z", tabs: [] });
  });

  it("lists each chat by title with its messages as the single-chat export writes them", () => {
    const out = tabsExport(
      [
        tab({ title: "First", messages: [msg({ ts: T, content: "hi" }), msg({ role: "assistant", ts: T + 1000, content: "yo", model: "m1" })] }),
        tab({ title: "Second", messages: [msg({ ts: T, content: "other" })] }),
      ],
      NOW,
    ) as { tabs: Array<{ title: string; messages: Array<Record<string, unknown>> }> };
    expect(out.tabs.map((t) => t.title)).toEqual(["First", "Second"]);
    expect(out.tabs[0]!.messages).toEqual([
      { timestamp: "2026-03-04T01:02:03.000Z", sender: "user", message: "hi" },
      { timestamp: "2026-03-04T01:02:04.000Z", sender: "sensai", message: "yo", model: "m1" },
    ]);
    expect(out.tabs[1]!.messages).toHaveLength(1);
  });

  it("keeps an empty chat in the file", () => {
    const out = tabsExport([tab({ title: "Empty" })], NOW) as { tabs: Array<{ messages: unknown[] }> };
    expect(out.tabs[0]!.messages).toEqual([]);
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

describe("a reply's model", () => {
  const NOW = new Date("2026-03-04T05:06:07.000Z");
  const T = Date.parse("2026-03-04T01:02:03.000Z");

  it("is named in the header's tooltip", () => {
    expect(headerTooltip("gemini-3.5-flash-lite", true, true)).toBe("Response from gemini-3.5-flash-lite");
  });

  it("shares the tooltip with what a click does, on a message that can collapse", () => {
    expect(headerTooltip("m1", false, true)).toBe("Response from m1\nCollapse");
    expect(headerTooltip("m1", false, false)).toBe("Response from m1\nExpand");
  });

  it("leaves the click hint alone when the server did not say which model it was", () => {
    expect(headerTooltip(undefined, false, true)).toBe("Collapse");
    expect(headerTooltip(null, false, false)).toBe("Expand");
    expect(headerTooltip("", false, true)).toBe("Collapse");
  });

  it("has no tooltip at all with no model and nothing to collapse", () => {
    expect(headerTooltip(undefined, true, true)).toBe("");
  });

  it("is exported with the message, after its route, only when it has one", () => {
    const out = historyExport(
      [
        msg({ role: "assistant", ts: T, routed_to: "plot_config", model: "m1" }),
        msg({ role: "assistant", ts: T }),
      ],
      NOW,
    ) as { messages: Array<Record<string, unknown>> };
    expect(Object.keys(out.messages[0]!)).toEqual(["timestamp", "sender", "message", "routed_to", "model"]);
    expect(out.messages[0]).toMatchObject({ model: "m1" });
    expect(out.messages[1]).not.toHaveProperty("model");
  });

  it("survives a save and a load", () => {
    saveSensAITabs([tab({ messages: [msg({ role: "assistant", model: "m1" })] })], "t1");
    expect(loadSensAITabs().tabs[0]!.messages[0]).toMatchObject({ model: "m1" });
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

describe("groupExchanges", () => {
  const user = (content: string, ts = 0) => msg({ role: "user", content, ts });
  const reply = (content: string, ts = 0) => msg({ role: "assistant", content, ts });

  it("is nothing for an empty chat", () => {
    expect(groupExchanges([])).toEqual([]);
  });

  it("puts a question and its answer together, and the next question in a new exchange", () => {
    const messages = [user("q1"), reply("a1"), user("q2"), reply("a2")];

    const groups = groupExchanges(messages);

    expect(groups.map((g) => g.messages.map((m) => m.content))).toEqual([["q1", "a1"], ["q2", "a2"]]);
    expect(groups.map((g) => g.start)).toEqual([0, 2]);
  });

  it("holds the very messages it was given, not copies", () => {
    const messages = [user("q"), reply("a")];

    expect(groupExchanges(messages)[0]!.messages[1]).toBe(messages[1]);
  });

  it("marks only the last exchange", () => {
    const groups = groupExchanges([user("q1"), reply("a1"), user("q2")]);

    expect(groups.map((g) => g.last)).toEqual([false, true]);
  });

  it("is one exchange holding every answer after a question", () => {
    const [group, ...rest] = groupExchanges([user("q"), reply("a"), reply("b")]);

    expect(rest).toEqual([]);
    expect(group!.messages).toHaveLength(3);
  });

  it("gives a question with no answer yet an exchange of its own, and the last mark", () => {
    const groups = groupExchanges([user("q1"), user("q2")]);

    expect(groups.map((g) => [g.start, g.messages.length, g.last])).toEqual([[0, 1, false], [1, 1, true]]);
  });

  it("makes an answer with no question before it an exchange of its own", () => {
    const groups = groupExchanges([reply("hello"), user("q"), reply("a")]);

    expect(groups.map((g) => g.start)).toEqual([0, 1]);
    expect(groups[0]!.messages.map((m) => m.content)).toEqual(["hello"]);
  });
});

describe("bubbleStyle", () => {
  const state = (over: Partial<Parameters<typeof bubbleStyle>[0]>) => ({
    single: false,
    open: true,
    settled: true,
    fullHeight: 300,
    ...over,
  });

  it("has none for a single line", () => {
    expect(bubbleStyle(state({ single: true }))).toBe("");
    expect(bubbleStyle(state({ single: true, open: false }))).toBe("");
  });

  it("is short and faded when closed, whatever else is the case", () => {
    for (const settled of [true, false]) {
      const style = bubbleStyle(state({ open: false, settled }));
      expect(style).toContain("max-height: 3.5rem");
      expect(style).toContain("mask-image: linear-gradient");
    }
  });

  it("has no height limit once it is open and the change is over", () => {
    expect(bubbleStyle(state({ open: true, settled: true }))).toBe("max-height: none");
  });

  it("is the whole height in pixels while it is opening, so it animates to what is shown", () => {
    expect(bubbleStyle(state({ open: true, settled: false, fullHeight: 302 }))).toBe("max-height: 302px");
  });

  it("has no limit for a height it does not know, and not a limit of zero", () => {
    expect(bubbleStyle(state({ open: true, settled: false, fullHeight: 0 }))).toBe("max-height: none");
  });

  it("is not faded while it is open", () => {
    expect(bubbleStyle(state({ open: true, settled: false }))).not.toContain("mask");
  });
});

describe("fullBubbleHeight", () => {
  it("is the content's height plus the borders", () => {
    // 300 of content in a box clipped to 56, with a border of 1 on each side
    expect(fullBubbleHeight({ scrollHeight: 300, offsetHeight: 58, clientHeight: 56 })).toBe(302);
  });

  it("is just the content's height with no border", () => {
    expect(fullBubbleHeight({ scrollHeight: 120, offsetHeight: 56, clientHeight: 56 })).toBe(120);
  });
});

describe("how long a bubble takes to open", () => {
  it("is waited for a little longer than its transition lasts", () => {
    expect(BUBBLE_MS).toBe(300);
    expect(BUBBLE_SETTLE_MS).toBeGreaterThan(BUBBLE_MS);
  });
});

describe("how long a chat's list is held at its place", () => {
  it("is long enough for KaTeX to load and code editors to measure themselves, and short enough not to fight the user", () => {
    expect(SCROLL_HOLD_MS).toBeGreaterThanOrEqual(1000);
    expect(SCROLL_HOLD_MS).toBeLessThanOrEqual(3000);
  });
});

describe("rememberedScroll", () => {
  it("is where the chat's list was left", () => {
    expect(rememberedScroll({ scrollTop: 480 })).toBe(480);
    expect(rememberedScroll({ scrollTop: 0.5 })).toBe(0.5);
  });

  it("is the top for a chat that was never scrolled", () => {
    expect(rememberedScroll({})).toBe(0);
    expect(rememberedScroll({ scrollTop: 0 })).toBe(0);
    expect(rememberedScroll(undefined)).toBe(0);
  });

  it("is the top for a saved value that cannot be used", () => {
    for (const bad of [-20, Number.NaN, Number.POSITIVE_INFINITY, "300", null, {}, [5]]) {
      expect(rememberedScroll({ scrollTop: bad }), `${typeof bad} ${JSON.stringify(bad)}`).toBe(0);
    }
  });

  it("comes back with a chat that was saved and loaded", () => {
    localStorage.clear();
    const tab = { id: "t1", title: "Chat 1", messages: [], scrollTop: 612 };
    localStorage.setItem(TABS_KEY, JSON.stringify([tab]));
    localStorage.setItem(ACTIVE_TAB_KEY, "t1");

    expect(rememberedScroll(loadSensAITabs().tabs[0])).toBe(612);
  });
});

describe("promptScrollTop", () => {
  it("is how far the prompt is below the top of the list", () => {
    // the list starts at 100 on the screen, the prompt at 400, nothing scrolled
    expect(promptScrollTop(100, 0, 400)).toBe(300);
  });

  it("adds what the list has already scrolled", () => {
    // the same prompt after the list scrolled 50 up: it is at 350 now
    expect(promptScrollTop(100, 50, 350)).toBe(300);
    expect(promptScrollTop(100, 50, 350)).toBe(promptScrollTop(100, 0, 400));
  });

  it("is never negative", () => {
    expect(promptScrollTop(100, 0, 40)).toBe(0);
    expect(promptScrollTop(100, 20, 40)).toBe(0);
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

  it("starts a longer user message open when it is the latest one they sent", () => {
    expect(messageLayout("user", 51, "20px", true)).toEqual({ single: false, open: true });
    expect(messageLayout("user", 51, "20px", false)).toEqual({ single: false, open: false });
  });

  it("leaves the latest-message flag out of what an assistant message does", () => {
    expect(messageLayout("assistant", 51, "20px", true)).toEqual({ single: false, open: true });
    expect(messageLayout("assistant", 51, "20px", false)).toEqual({ single: false, open: true });
  });
});

describe("lastUserIndex", () => {
  it("is the position of the latest message the user sent", () => {
    const messages = [
      msg({ role: "user" }),
      msg({ role: "assistant" }),
      msg({ role: "user" }),
      msg({ role: "assistant" }),
    ];
    expect(lastUserIndex(messages)).toBe(2);
  });

  it("skips replies after it, and counts a message that has no reply yet", () => {
    expect(lastUserIndex([msg({ role: "assistant" }), msg({ role: "user" })])).toBe(1);
  });

  it("is -1 with no message from the user", () => {
    expect(lastUserIndex([])).toBe(-1);
    expect(lastUserIndex([msg({ role: "assistant" })])).toBe(-1);
  });
});

describe("open", () => {
  it("is closed when nothing was saved", () => {
    expect(loadOpen()).toBe(false);
  });

  it("is remembered once opened, and forgotten once closed", () => {
    saveOpen(true);
    expect(loadOpen()).toBe(true);
    saveOpen(false);
    expect(loadOpen()).toBe(false);
  });

  it("is kept apart from the pin", () => {
    saveOpen(true);
    expect(loadPinned()).toBe(false);
    savePinned(true);
    saveOpen(false);
    expect(loadPinned()).toBe(true);
    expect(loadOpen()).toBe(false);
  });

  it("stores a flag a person could read in the browser's storage tab", () => {
    saveOpen(true);
    expect(localStorage.getItem(OPEN_KEY)).toBe("1");
    saveOpen(false);
    expect(localStorage.getItem(OPEN_KEY)).toBe("0");
  });

  it("treats anything but the saved flag as closed", () => {
    localStorage.setItem(OPEN_KEY, "true");
    expect(loadOpen()).toBe(false);
  });

  it("survives storage that cannot be read or written", () => {
    stubStorage({ read: true, write: () => true });
    expect(loadOpen()).toBe(false);
    expect(() => saveOpen(true)).not.toThrow();
  });
});

describe("pinned", () => {
  it("is unpinned when nothing was saved", () => {
    expect(loadPinned()).toBe(false);
  });

  it("is remembered once pinned, and forgotten once unpinned", () => {
    savePinned(true);
    expect(loadPinned()).toBe(true);
    savePinned(false);
    expect(loadPinned()).toBe(false);
  });

  it("stores a flag a person could read in the browser's storage tab", () => {
    savePinned(true);
    expect(localStorage.getItem(PINNED_KEY)).toBe("1");
    savePinned(false);
    expect(localStorage.getItem(PINNED_KEY)).toBe("0");
  });

  it("treats anything but the saved flag as unpinned", () => {
    localStorage.setItem(PINNED_KEY, "yes");
    expect(loadPinned()).toBe(false);
  });

  it("survives storage that cannot be read or written", () => {
    stubStorage({ read: true, write: () => true });
    expect(loadPinned()).toBe(false);
    expect(() => savePinned(true)).not.toThrow();
  });
});

const tool = (over: Partial<SensAIToolCall> = {}): SensAIToolCall => ({
  id: 1,
  name: "edit_signal",
  agent: "plot_config",
  args: '{"name":"x"}',
  status: "ok",
  result: "Changed.",
  ...over,
});

describe("chatRequestBody and versus mode", () => {
  it("sends versus mode as the trial viewer has it", () => {
    const versus = { vsEnabled: true, vsRange: null, vsPinned: [4] };

    expect(chatRequestBody("hi", [msg()], null, null, versus)).toMatchObject({ versus });
  });

  it("sends none away from a trial", () => {
    expect(chatRequestBody("hi", [msg()], null, null)).toMatchObject({ versus: null });
  });
});

describe("applyToolEvent", () => {
  it("adds a call that starts, running, with the agent and arguments it came with", () => {
    const out = applyToolEvent([], "tool_start", { id: 1, name: "add_signals", agent: "plot_config", args: '{"names":["x"]}' });

    expect(out).toEqual([{ id: 1, name: "add_signals", agent: "plot_config", args: '{"names":["x"]}', status: "running" }]);
  });

  it("takes a call with no agent or arguments to be the chat agent's, with none", () => {
    expect(applyToolEvent([], "tool_start", { id: 1, name: "ask_docs_agent" })).toEqual([
      { id: 1, name: "ask_docs_agent", agent: "chat", args: "", status: "running" },
    ]);
  });

  it("keeps calls in the order they started", () => {
    const one = applyToolEvent([], "tool_start", { id: 1, name: "a" });
    const two = applyToolEvent(one, "tool_start", { id: 2, name: "b" });

    expect(two.map((c) => c.name)).toEqual(["a", "b"]);
  });

  it("settles the call with that id and leaves the others", () => {
    const calls = [tool({ id: 1, status: "running", result: null }), tool({ id: 2, status: "running", result: null })];

    const out = applyToolEvent(calls, "tool_end", { id: 2, status: "rejected", result: "no such field" });

    expect(out[0]).toEqual(calls[0]);
    expect(out[1]).toMatchObject({ id: 2, status: "rejected", result: "no such field" });
  });

  it("does not change the list it was given", () => {
    const calls = [tool({ id: 1, status: "running", result: null })];

    applyToolEvent(calls, "tool_end", { id: 1, status: "ok", result: "x" });

    expect(calls[0]!.status).toBe("running");
  });

  it("ignores a start that has no id or name, or whose id is already there", () => {
    const calls = [tool({ id: 1 })];

    expect(applyToolEvent(calls, "tool_start", { name: "a" })).toBe(calls);
    expect(applyToolEvent(calls, "tool_start", { id: 2 })).toBe(calls);
    expect(applyToolEvent(calls, "tool_start", { id: 1, name: "again" })).toBe(calls);
  });

  it("ignores an end for a call that was never started, and any other event", () => {
    const calls = [tool({ id: 1 })];

    expect(applyToolEvent(calls, "tool_end", { id: 9, status: "ok" })).toEqual(calls);
    expect(applyToolEvent(calls, "text_delta", { delta: "hi" })).toBe(calls);
  });

  it("takes an end with no status to have gone through", () => {
    const out = applyToolEvent([tool({ status: "running", result: null })], "tool_end", { id: 1 });

    expect(out[0]).toMatchObject({ status: "ok", result: null });
  });
});

describe("finalToolCalls", () => {
  it("prefers the list the server sent with the reply", () => {
    const sent = [tool({ id: 5 })];

    expect(finalToolCalls(sent, [tool({ id: 1 })])).toBe(sent);
  });

  it("takes the server's empty list as the answer, not a gap to fill", () => {
    expect(finalToolCalls([], [tool()])).toEqual([]);
  });

  it("falls back to the streamed calls when the reply has no list", () => {
    const streamed = [tool()];

    expect(finalToolCalls(undefined, streamed)).toBe(streamed);
  });
});

describe("toolCallsTitle", () => {
  it("counts the calls, in the singular for one", () => {
    expect(toolCallsTitle([tool()])).toBe("1 tool call");
    expect(toolCallsTitle([tool(), tool({ id: 2 })])).toBe("2 tool calls");
  });

  it("says how many were rejected or failed, and only when some were", () => {
    const calls = [tool({ id: 1 }), tool({ id: 2, status: "rejected" }), tool({ id: 3, status: "rejected" }), tool({ id: 4, status: "failed" })];

    expect(toolCallsTitle(calls)).toBe("4 tool calls, 2 rejected, 1 failed");
    expect(toolCallsTitle([tool()])).not.toMatch(/rejected|failed/);
  });

  it("handles a reply with no list", () => {
    expect(toolCallsTitle(undefined)).toBe("0 tool calls");
  });
});

describe("toolDotClass", () => {
  it("gives each outcome its own color, and a running call a pulse", () => {
    expect(toolDotClass("ok")).toBe("bg-success-500");
    expect(toolDotClass("rejected")).toBe("bg-warning-500");
    expect(toolDotClass("failed")).toBe("bg-danger-500");
    expect(toolDotClass("running")).toContain("animate-pulse");
  });

  it("treats a status it does not know as running, so a call is never drawn blank", () => {
    expect(toolDotClass("something new")).toBe(toolDotClass("running"));
  });
});

describe("toolCallTooltip", () => {
  it("gives the whole call and what it returned", () => {
    expect(toolCallTooltip(tool())).toBe('edit_signal {"name":"x"}\nReturned: Changed.');
  });

  it("says a rejected call was rejected, with the reason", () => {
    expect(toolCallTooltip(tool({ status: "rejected", result: "no such field" }))).toBe(
      'edit_signal {"name":"x"}\nRejected: no such field',
    );
  });

  it("is only the call while it has no result", () => {
    expect(toolCallTooltip(tool({ status: "running", result: null }))).toBe('edit_signal {"name":"x"}');
  });

  it("has no trailing space for a call with no arguments", () => {
    expect(toolCallTooltip(tool({ args: "", result: null }))).toBe("edit_signal");
  });
});

describe("the tool calls in a saved history", () => {
  const NOW = new Date("2026-03-04T05:06:07.000Z");

  it("are in the export beside the reply they belong to", () => {
    const calls = [tool()];

    const out = historyExport([msg({ role: "assistant", tool_calls: calls })], NOW) as { messages: Array<Record<string, unknown>> };

    expect(out.messages[0]!["tool_calls"]).toEqual(calls);
  });

  it("are left out of the export when a reply made none", () => {
    const out = historyExport([msg({ role: "assistant", tool_calls: [] }), msg({ role: "assistant" })], NOW) as {
      messages: Array<Record<string, unknown>>;
    };

    expect(out.messages[0]).not.toHaveProperty("tool_calls");
    expect(out.messages[1]).not.toHaveProperty("tool_calls");
  });

  it("are not sent to the model as context, which is role and text only", () => {
    const [m] = chatHistory([msg({ role: "assistant", tool_calls: [tool()] }), msg()]);

    expect(m).toEqual({ role: "assistant", content: "hello" });
  });

  it("come back from storage with their reply", () => {
    const tab = blankTab([]);
    tab.messages = [msg({ role: "assistant", tool_calls: [tool()] })];
    saveSensAITabs([tab], tab.id);

    expect(loadSensAITabs().tabs[0]!.messages[0]!.tool_calls).toEqual([tool()]);
  });
});

describe("the event stream's tool events", () => {
  it("are read as events of their own, with their payload", () => {
    const parser = createSseParser();

    const events = parser.feed(
      'event: tool_start\ndata: {"id":1,"name":"add_signals","agent":"plot_config","args":"{}","status":"running"}\n\n' +
        'event: tool_end\ndata: {"id":1,"status":"ok","result":"Added."}\n\n',
    );

    expect(events.map((e) => e.type)).toEqual(["tool_start", "tool_end"]);
    expect(events[1]!.payload).toEqual({ id: 1, status: "ok", result: "Added." });
  });
});
