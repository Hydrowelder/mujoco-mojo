// @vitest-environment happy-dom
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { renderMarkdown } from "./lib/markdown";
import { BUBBLE_SETTLE_MS, SCROLL_HOLD_MS } from "./lib/sensai";
import {
  DEFAULT_PLACEHOLDER,
  ERASE_MS,
  GAP_MS,
  HOLD_MS,
  PLACEHOLDER_EXAMPLES,
  TYPE_MS,
} from "./lib/sensai-placeholder";
import {
  ACTIVE_TAB_KEY,
  OPEN_KEY,
  PINNED_KEY,
  STORAGE_KEY,
  TABS_KEY,
  loadSensAITabs,
  titleFromMessage,
  type SensAIMessage,
  type SensAITab,
  type SensAIToolCall,
} from "./lib/sensai";
import type { VersusState } from "./lib/plot-profile";

// the component object itself, not a copy of its logic: its methods are called
// on a real `sensai()` with the browser's storage and a fake `fetch` behind it
type SensAI = {
  open: boolean;
  pinned: boolean;
  tabs: SensAITab[];
  activeId: string;
  input: string;
  placeholder: string;
  destroy(): void;
  _startPlaceholder(): void;
  scrollToBottom(): void;
  resize(el: HTMLElement): void;
  _scrollToLastPrompt(): void;
  onScroll(el: HTMLElement): void;
  showExchange(from: HTMLElement): void;
  exchanges: Array<{ start: number; messages: SensAIMessage[]; last: boolean }>;
  atBottom: boolean;
  maxTabs: number;
  runningId: string | null;
  queue: string[];
  hasNewResponse: boolean;
  toolCalls: SensAIToolCall[];
  messages: SensAIMessage[];
  activeTab: SensAITab | undefined;
  toggle(): void;
  close(): void;
  dismiss(): void;
  togglePin(): void;
  newTab(): void;
  switchTab(id: string): void;
  closeTab(id: string): void;
  renameTab(id: string, value: string): void;
  send(): Promise<void>;
  isBusy(id: string): boolean;
  isRunning(id: string): boolean;
  isQueued(id: string): boolean;
  isLastUserMessage(i: number): boolean;
  init(): Promise<void>;
  $watch: () => void;
  $refs: Record<string, unknown>;
  $nextTick: (cb?: () => void) => Promise<void>;
};

let make: () => SensAI;

beforeAll(async () => {
  await import("./sensai");
  make = (window as unknown as { sensai: () => SensAI }).sensai;
});

// what a request to the server sees: its body, its abort signal, and the
// stream the test writes the reply into whenever it chooses, so it decides
// when each request finishes
class Reply {
  readonly stream: ReadableStream<Uint8Array>;
  private controller!: ReadableStreamDefaultController<Uint8Array>;
  private readonly encoder = new TextEncoder();
  closed = false;

  constructor(signal: AbortSignal | undefined) {
    this.stream = new ReadableStream<Uint8Array>({
      start: (controller) => {
        this.controller = controller;
      },
    });
    signal?.addEventListener("abort", () => {
      this.closed = true;
      this.controller.error(new DOMException("aborted", "AbortError"));
    });
  }

  // one event of the server's stream
  event(type: string, payload: object): void {
    this.controller.enqueue(this.encoder.encode(`event: ${type}\ndata: ${JSON.stringify(payload)}\n\n`));
  }

  // the answer, and the end of the stream
  answer(message: string, extra: object = {}): void {
    this.event("result", { message, plot_config_update: null, routed_to: "general", model: "test-model", ...extra });
    this.closed = true;
    this.controller.close();
  }
}

interface Call {
  body: {
    message: string;
    message_history: Array<{ role: string; content: string }>;
    current_plot_config_json: string | null;
    versus: VersusState | null;
  };
  signal: AbortSignal | undefined;
  reply: Reply;
}

let calls: Call[];
let failNextRequest: boolean;

// the dojo store the component reaches through Alpine, with a copy the tests can watch
const store = {
  columnManifest: null,
  versus: null as VersusState | null,
  copyText: vi.fn((_text: string, _message?: string) => Promise.resolve(true)),
};

beforeEach(() => {
  localStorage.clear();
  calls = [];
  failNextRequest = false;
  store.copyText.mockClear();
  vi.stubGlobal("Alpine", { store: () => store });
  vi.stubGlobal("fetch", (url: string, init?: RequestInit) => {
    if (url === "/sensai/config") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ enabled: true }) });
    }
    if (failNextRequest) {
      failNextRequest = false;
      return Promise.reject(new TypeError("network down"));
    }
    const signal = init?.signal ?? undefined;
    const reply = new Reply(signal);
    const body = typeof init?.body === "string" ? init.body : "{}";
    calls.push({ body: JSON.parse(body) as Call["body"], signal, reply });
    return Promise.resolve({ ok: true, body: reply.stream });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// lets the promises and the stream the component is waiting on settle
const settle = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

async function boot(refs: Record<string, unknown> = {}): Promise<SensAI> {
  const s = make();
  s.$watch = () => undefined;
  s.$refs = refs;
  s.$nextTick = (cb?: () => void) => {
    cb?.();
    return Promise.resolve();
  };
  await s.init();
  return s;
}

// types `text` in the open chat and sends it, without waiting for the reply
function ask(s: SensAI, text: string): Promise<void> {
  s.input = text;
  return s.send();
}

const first = (s: SensAI): SensAITab => s.tabs[0]!;
const second = (s: SensAI): SensAITab => s.tabs[1]!;

describe("the SensAI window", () => {
  it("closes for a click elsewhere or Escape when it is not pinned", async () => {
    const s = await boot();
    s.open = true;
    s.dismiss();
    expect(s.open).toBe(false);
  });

  it("stays open for a click elsewhere or Escape when it is pinned", async () => {
    const s = await boot();
    s.open = true;
    s.pinned = true;
    s.dismiss();
    expect(s.open).toBe(true);
  });

  it("can still be closed on purpose while pinned, by its own button", async () => {
    const s = await boot();
    s.open = true;
    s.pinned = true;
    s.close();
    expect(s.open).toBe(false);
  });

  it("closes for a click elsewhere again once it is unpinned", async () => {
    const s = await boot();
    s.open = true;
    s.pinned = true;
    s.dismiss();
    s.togglePin();
    s.dismiss();
    expect(s.pinned).toBe(false);
    expect(s.open).toBe(false);
  });

  it("remembers the pin for the next page", async () => {
    const s = await boot();
    s.togglePin();
    expect(localStorage.getItem(PINNED_KEY)).toBe("1");
    s.togglePin();
    expect(localStorage.getItem(PINNED_KEY)).toBe("0");
  });

  it("comes back pinned on the next page when it was left pinned", async () => {
    localStorage.setItem(PINNED_KEY, "1");
    const s = await boot();

    expect(s.pinned).toBe(true);
    // pinned alone does not open it: the window starts closed on every page
    expect(s.open).toBe(false);
  });

  it("starts unpinned and closed", async () => {
    const s = await boot();
    expect(s.pinned).toBe(false);
    expect(s.open).toBe(false);
  });

  it("knows which message is the latest the user sent", async () => {
    const s = await boot();
    first(s).messages = [
      { role: "user", content: "a", ts: 1 },
      { role: "assistant", content: "b", ts: 2 },
      { role: "user", content: "c", ts: 3 },
      { role: "assistant", content: "d", ts: 4 },
    ];
    expect(s.isLastUserMessage(2)).toBe(true);
    expect(s.isLastUserMessage(0)).toBe(false);
    expect(s.isLastUserMessage(3)).toBe(false);
  });
});

describe("the chats", () => {
  it("start as one empty chat that is open", async () => {
    const s = await boot();
    expect(s.tabs).toHaveLength(1);
    expect(first(s)).toMatchObject({ title: "Chat 1", messages: [] });
    expect(s.activeId).toBe(first(s).id);
    expect(s.messages).toEqual([]);
  });

  it("take the history from before tabs as the first chat, once", async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([{ role: "user", content: "old", ts: 3 }]));
    const s = await boot();

    expect(first(s).messages).toEqual([{ role: "user", content: "old", ts: 3 }]);
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(loadSensAITabs().tabs[0]!.messages).toHaveLength(1);
  });

  it("open a new empty chat and show it", async () => {
    const s = await boot();
    s.newTab();

    expect(s.tabs).toHaveLength(2);
    expect(second(s).title).toBe("Chat 2");
    expect(s.activeId).toBe(second(s).id);
    expect(s.messages).toEqual([]);
  });

  it("show the messages of whichever chat is open", async () => {
    const s = await boot();
    first(s).messages = [{ role: "user", content: "in the first", ts: 1 }];
    s.newTab();
    expect(s.messages).toEqual([]);

    s.switchTab(first(s).id);

    expect(s.messages.map((m) => m.content)).toEqual(["in the first"]);
  });

  it("number a new chat past the ones open, and open at most eight", async () => {
    const s = await boot();
    for (let i = 0; i < 12; i++) s.newTab();

    expect(s.tabs).toHaveLength(8);
    expect(s.tabs.map((t) => t.title)).toEqual(
      ["Chat 1", "Chat 2", "Chat 3", "Chat 4", "Chat 5", "Chat 6", "Chat 7", "Chat 8"],
    );
  });

  it("keep what was typed in each chat while another is open", async () => {
    const s = await boot();
    s.input = "half of a question";
    s.newTab();
    expect(s.input).toBe("");
    s.input = "another thought";

    s.switchTab(first(s).id);
    expect(s.input).toBe("half of a question");
    s.switchTab(second(s).id);
    expect(s.input).toBe("another thought");
  });

  it("are titled by their first message, and only the first", async () => {
    const s = await boot();
    const sent = ask(s, "plot the position of box1 and box2");
    await settle();
    calls[0]!.reply.answer("ok");
    await sent;

    expect(first(s).title).toBe(titleFromMessage("plot the position of box1 and box2"));

    const again = ask(s, "now something else entirely");
    await settle();
    calls[1]!.reply.answer("ok");
    await again;
    expect(first(s).title).toBe(titleFromMessage("plot the position of box1 and box2"));
  });

  it("keep the name the user gave, whatever the first message says", async () => {
    const s = await boot();
    s.renameTab(first(s).id, "Energy study");
    const sent = ask(s, "plot the kinetic energy");
    await settle();
    calls[0]!.reply.answer("ok");
    await sent;

    expect(first(s).title).toBe("Energy study");
  });

  it("keep the old name when the new one is empty", async () => {
    const s = await boot();
    s.renameTab(first(s).id, "   ");
    expect(first(s).title).toBe("Chat 1");
  });

  it("are saved, with which one is open, and come back the same", async () => {
    const s = await boot();
    first(s).messages = [{ role: "user", content: "kept", ts: 1 }];
    s.newTab();
    s.renameTab(second(s).id, "Second");

    const next = await boot();

    expect(next.tabs.map((t) => t.title)).toEqual(["Chat 1", "Second"]);
    expect(next.tabs[0]!.messages[0]!.content).toBe("kept");
    expect(next.activeId).toBe(next.tabs[1]!.id);
    expect(localStorage.getItem(ACTIVE_TAB_KEY)).toBe(next.activeId);
    expect(localStorage.getItem(TABS_KEY)).not.toBeNull();
  });

  it("close, and the chat next to a closed open one comes to the front", async () => {
    const s = await boot();
    s.newTab();
    s.newTab();
    const [a, b, c] = s.tabs.map((t) => t.id) as [string, string, string];
    s.switchTab(b);

    s.closeTab(b);

    expect(s.tabs.map((t) => t.id)).toEqual([a, c]);
    expect(s.activeId).toBe(c);
  });

  it("close without disturbing the one that is open", async () => {
    const s = await boot();
    s.newTab();
    const [a, b] = s.tabs.map((t) => t.id) as [string, string];

    s.closeTab(a);

    expect(s.tabs.map((t) => t.id)).toEqual([b]);
    expect(s.activeId).toBe(b);
  });

  it("leave one empty chat when the last is closed", async () => {
    const s = await boot();
    const [only] = s.tabs.map((t) => t.id) as [string];
    first(s).messages = [{ role: "user", content: "gone", ts: 1 }];

    s.closeTab(only);

    expect(s.tabs).toHaveLength(1);
    expect(first(s)).toMatchObject({ title: "Chat 1", messages: [] });
    expect(first(s).id).not.toBe(only);
    expect(s.activeId).toBe(first(s).id);
  });
});

describe("a request", () => {
  it("is answered in the chat that sent it", async () => {
    const s = await boot();
    const sent = ask(s, "question one");
    await settle();

    calls[0]!.reply.answer("answer one");
    await sent;

    expect(first(s).messages.map((m) => [m.role, m.content])).toEqual([
      ["user", "question one"],
      ["assistant", "answer one"],
    ]);
    expect(first(s).messages[1]).toMatchObject({ model: "test-model", routed_to: "general" });
  });

  it("carries only its own chat's earlier messages as context", async () => {
    const s = await boot();
    first(s).messages = [
      { role: "user", content: "earlier question", ts: 1 },
      { role: "assistant", content: "earlier answer", ts: 2 },
    ];
    s.newTab();
    second(s).messages = [
      { role: "user", content: "other chat question", ts: 1 },
      { role: "assistant", content: "other chat answer", ts: 2 },
    ];

    const sent = ask(s, "new question");
    await settle();
    calls[0]!.reply.answer("ok");
    await sent;

    expect(calls[0]!.body.message).toBe("new question");
    expect(calls[0]!.body.message_history.map((m) => m.content)).toEqual(["other chat question", "other chat answer"]);
  });

  it("is answered in the chat that sent it even after the user went to another one", async () => {
    const s = await boot();
    const sent = ask(s, "question one");
    await settle();
    s.newTab();

    calls[0]!.reply.answer("answer one");
    await sent;

    expect(first(s).messages.map((m) => m.content)).toEqual(["question one", "answer one"]);
    expect(second(s).messages).toEqual([]);
  });

  it("marks the chat unread when it is answered while another is open, until it is opened", async () => {
    const s = await boot();
    const sent = ask(s, "question one");
    await settle();
    s.newTab();
    calls[0]!.reply.answer("answer one");
    await sent;

    expect(first(s).unread).toBe(true);
    expect(second(s).unread).toBeFalsy();

    s.switchTab(first(s).id);
    expect(first(s).unread).toBe(false);
  });

  it("does not mark the open chat unread", async () => {
    const s = await boot();
    const sent = ask(s, "question one");
    await settle();
    calls[0]!.reply.answer("answer one");
    await sent;

    expect(first(s).unread).toBeFalsy();
  });

  it("makes the button show a new reply when the window is closed", async () => {
    const s = await boot();
    s.open = false;
    const sent = ask(s, "question one");
    await settle();
    calls[0]!.reply.answer("answer one");
    await sent;

    expect(s.hasNewResponse).toBe(true);
  });

  it("is reported in the chat that sent it when the network fails, whichever is open", async () => {
    const s = await boot();
    failNextRequest = true;
    const sent = ask(s, "question one");
    s.newTab();
    await sent;

    expect(first(s).messages.map((m) => [m.role, m.content, m.error ?? false])).toEqual([
      ["user", "question one", false],
      ["assistant", "Network error. Please try again.", true],
    ]);
    expect(second(s).messages).toEqual([]);
  });

  it("is an error in the chat when the server says so", async () => {
    const s = await boot();
    const sent = ask(s, "question one");
    await settle();

    calls[0]!.reply.event("error", { detail: "No response from model." });
    calls[0]!.reply.answer("");
    await sent;

    expect(first(s).messages[1]).toMatchObject({ error: true, content: "No response from model." });
  });
});

describe("the tool calls of a request", () => {
  const start = (id: number, name: string, extra: object = {}) => ({
    id,
    name,
    agent: "chat",
    args: "{}",
    status: "running",
    result: null,
    ...extra,
  });

  it("are listed while the request runs, each settled as it ends", async () => {
    const s = await boot();
    const sent = ask(s, "make it red");
    await settle();

    const reply = calls[0]!.reply;
    reply.event("tool_start", start(1, "ask_plot_config_agent", { args: '{"request":"make it red"}' }));
    reply.event("tool_start", start(2, "edit_signal", { agent: "plot_config" }));
    await settle();
    expect(s.toolCalls.map((c) => [c.name, c.status])).toEqual([
      ["ask_plot_config_agent", "running"],
      ["edit_signal", "running"],
    ]);

    reply.event("tool_end", { id: 2, status: "ok", result: "Changed the color." });
    await settle();
    expect(s.toolCalls.map((c) => [c.name, c.status, c.result ?? null])).toEqual([
      ["ask_plot_config_agent", "running", null],
      ["edit_signal", "ok", "Changed the color."],
    ]);

    reply.answer("Done.");
    await sent;
  });

  it("are kept with the reply, closed to the list the server sent, and are gone from the running list", async () => {
    const s = await boot();
    const sent = ask(s, "make it red");
    await settle();
    const list = [
      start(1, "ask_plot_config_agent", { status: "ok", result: "Done." }),
      start(2, "edit_signal", { agent: "plot_config", status: "ok", result: "Changed." }),
    ];

    calls[0]!.reply.event("tool_start", start(1, "ask_plot_config_agent"));
    calls[0]!.reply.answer("Done.", { tool_calls: list });
    await sent;

    expect(first(s).messages[1]!.tool_calls).toEqual(list);
    expect(s.toolCalls).toEqual([]);
  });

  it("are the ones that streamed in when the reply carries no list", async () => {
    const s = await boot();
    const sent = ask(s, "question");
    await settle();

    calls[0]!.reply.event("tool_start", start(1, "get_job_summary", { agent: "job_status" }));
    calls[0]!.reply.event("tool_end", { id: 1, status: "ok", result: "3 of 10" });
    await settle();
    calls[0]!.reply.answer("Three of ten.");
    await sent;

    expect(first(s).messages[1]!.tool_calls).toEqual([
      { id: 1, name: "get_job_summary", agent: "job_status", args: "{}", status: "ok", result: "3 of 10" },
    ]);
  });

  it("leave a reply that used no tools with no list at all", async () => {
    const s = await boot();
    const sent = ask(s, "hello");
    await settle();

    calls[0]!.reply.answer("Hi.", { tool_calls: [] });
    await sent;

    expect(first(s).messages[1]).not.toHaveProperty("tool_calls");
  });

  it("stay with an error, since what it tried is what explains it", async () => {
    const s = await boot();
    const sent = ask(s, "question");
    await settle();
    const tried = [start(1, "ask_job_status_agent", { status: "failed" })];

    calls[0]!.reply.event("error", { detail: "SensAI stopped after 12 model requests", tool_calls: tried });
    calls[0]!.reply.answer("");
    await sent;

    expect(first(s).messages[1]).toMatchObject({ error: true, tool_calls: tried });
  });

  it("do not carry over into the next request", async () => {
    const s = await boot();
    const one = ask(s, "first");
    await settle();
    calls[0]!.reply.event("tool_start", start(1, "ask_plot_config_agent"));
    await settle();
    calls[0]!.reply.answer("Done.", { tool_calls: [start(1, "ask_plot_config_agent", { status: "ok" })] });
    await one;

    const two = ask(s, "second");
    await settle();
    expect(s.toolCalls).toEqual([]);
    calls[1]!.reply.answer("Hi.");
    await two;

    expect(first(s).messages[3]).not.toHaveProperty("tool_calls");
  });
});

describe("versus mode and a request", () => {
  const before: VersusState = { vsEnabled: false, vsRange: [0, 2], vsPinned: [] };
  const after: VersusState = { vsEnabled: true, vsRange: null, vsPinned: [3, 4] };

  beforeEach(() => {
    store.versus = null;
  });

  it("is sent with the message as the trial viewer has it", async () => {
    store.versus = before;
    const s = await boot();
    const sent = ask(s, "compare 3");
    await settle();

    calls[0]!.reply.answer("ok");
    await sent;

    expect(calls[0]!.body.versus).toEqual(before);
  });

  it("is sent as null away from a trial", async () => {
    const s = await boot();
    const sent = ask(s, "hi");
    await settle();

    calls[0]!.reply.answer("ok");
    await sent;

    expect(calls[0]!.body.versus).toBeNull();
  });

  it("is changed in the trial viewer by what the reply says, after the plot", async () => {
    const heard: string[] = [];
    const listen = (e: Event) => heard.push(e.type);
    window.addEventListener("mojo-sensai-plot-config", listen);
    window.addEventListener("mojo-sensai-versus", listen);
    const detail: VersusState[] = [];
    window.addEventListener("mojo-sensai-versus", (e) => detail.push((e as CustomEvent<VersusState>).detail));
    const s = await boot();
    const sent = ask(s, "compare 3 and 4");
    await settle();

    calls[0]!.reply.answer("Done.", { plot_config_update: { title: "x" }, versus_update: after });
    await sent;
    window.removeEventListener("mojo-sensai-plot-config", listen);
    window.removeEventListener("mojo-sensai-versus", listen);

    expect(heard).toEqual(["mojo-sensai-plot-config", "mojo-sensai-versus"]);
    expect(detail).toEqual([after]);
  });

  it("is what the next request in line starts from, before the trial viewer has loaded the trials", async () => {
    store.versus = before;
    const s = await boot();
    const one = ask(s, "compare 3 and 4");
    await settle();
    s.newTab();
    const two = ask(s, "and what is set now?");
    await settle();

    calls[0]!.reply.answer("Done.", { versus_update: after });
    await settle();
    calls[1]!.reply.answer("ok");
    await Promise.all([one, two]);

    expect(calls[1]!.body.versus).toEqual(after);
  });

  it("is left alone by a reply that did not change it", async () => {
    store.versus = before;
    let fired = 0;
    const count = () => fired++;
    window.addEventListener("mojo-sensai-versus", count);
    const s = await boot();
    const sent = ask(s, "what is plotted");
    await settle();

    calls[0]!.reply.answer("One signal.", { versus_update: null });
    await sent;
    window.removeEventListener("mojo-sensai-versus", count);

    expect(fired).toBe(0);
    expect(store.versus).toEqual(before);
  });
});

describe("requests from different chats", () => {
  it("run one at a time: the second waits for the first", async () => {
    const s = await boot();
    const sentFirst = ask(s, "first chat question");
    await settle();
    s.newTab();
    const sentSecond = ask(s, "second chat question");
    await settle();

    expect(calls).toHaveLength(1);
    expect(s.isRunning(first(s).id)).toBe(true);
    expect(s.isQueued(second(s).id)).toBe(true);
    expect(s.isBusy(second(s).id)).toBe(true);

    calls[0]!.reply.answer("first answer");
    await settle();

    expect(calls).toHaveLength(2);
    expect(calls[1]!.body.message).toBe("second chat question");
    expect(s.isRunning(second(s).id)).toBe(true);
    expect(s.isQueued(second(s).id)).toBe(false);

    calls[1]!.reply.answer("second answer");
    await Promise.all([sentFirst, sentSecond]);

    expect(first(s).messages.map((m) => m.content)).toEqual(["first chat question", "first answer"]);
    expect(second(s).messages.map((m) => m.content)).toEqual(["second chat question", "second answer"]);
    expect(s.runningId).toBeNull();
    expect(s.queue).toEqual([]);
  });

  it("go in the order they were sent", async () => {
    const s = await boot();
    const sent: Array<Promise<void>> = [ask(s, "q1")];
    await settle();
    s.newTab();
    sent.push(ask(s, "q2"));
    s.newTab();
    sent.push(ask(s, "q3"));
    await settle();

    expect(s.queue).toEqual([second(s).id, s.tabs[2]!.id]);

    calls[0]!.reply.answer("a1");
    await settle();
    calls[1]!.reply.answer("a2");
    await settle();
    calls[2]!.reply.answer("a3");
    await Promise.all(sent);

    expect(calls.map((c) => c.body.message)).toEqual(["q1", "q2", "q3"]);
  });

  it("start from the plot the request ahead of them left, not the one before it", async () => {
    localStorage.setItem("mojo_mosaic_config", '{"title":"before"}');
    const s = await boot();
    const sentFirst = ask(s, "change the plot");
    await settle();
    s.newTab();
    const sentSecond = ask(s, "change it again");
    await settle();
    expect(calls[0]!.body.current_plot_config_json).toBe('{"title":"before"}');

    // the trial viewer saves the plot only after it has fetched any new signal's data,
    // so the update itself has to reach storage before the next request is read from it
    calls[0]!.reply.answer("done", { plot_config_update: { title: "after the first" } });
    await settle();

    expect(calls[1]!.body.current_plot_config_json).toBe('{"title":"after the first"}');
    calls[1]!.reply.answer("done");
    await Promise.all([sentFirst, sentSecond]);
  });

  it("let the chat that is waiting be closed, and never send its message", async () => {
    const s = await boot();
    const sentFirst = ask(s, "first chat question");
    await settle();
    s.newTab();
    void ask(s, "second chat question");
    await settle();
    const waiting = second(s).id;

    s.closeTab(waiting);
    // out of line at once, not only when its turn would have come
    expect(s.queue).toEqual([]);
    expect(s.isBusy(waiting)).toBe(false);

    calls[0]!.reply.answer("first answer");
    await sentFirst;
    await settle();

    expect(calls).toHaveLength(1);
  });

  it("let the chat that is running be closed: its request is stopped and the next goes ahead", async () => {
    const s = await boot();
    void ask(s, "first chat question");
    await settle();
    const running = first(s).id;
    s.newTab();
    const sentSecond = ask(s, "second chat question");
    await settle();

    s.closeTab(running);
    await settle();

    expect(calls[0]!.signal?.aborted).toBe(true);
    expect(calls).toHaveLength(2);
    expect(calls[1]!.body.message).toBe("second chat question");
    calls[1]!.reply.answer("second answer");
    await sentSecond;

    expect(s.tabs).toHaveLength(1);
    expect(first(s).messages.map((m) => m.content)).toEqual(["second chat question", "second answer"]);
    expect(first(s).messages.some((m) => m.error)).toBe(false);
  });

  it("stop the request of the only chat when it is closed, leaving an empty chat and no error", async () => {
    const s = await boot();
    const sent = ask(s, "question");
    await settle();
    const closed = first(s).id;

    s.closeTab(closed);
    await sent;

    expect(calls[0]!.signal?.aborted).toBe(true);
    expect(s.tabs).toHaveLength(1);
    expect(first(s).id).not.toBe(closed);
    expect(first(s).messages).toEqual([]);
    expect(s.isBusy(closed)).toBe(false);
    expect(s.isBusy(first(s).id)).toBe(false);
    expect(s.runningId).toBeNull();
  });

  it("carry the waiting chat's own context, even though another chat is open when its turn comes", async () => {
    const s = await boot();
    const sentFirst = ask(s, "first chat question");
    await settle();
    s.newTab();
    second(s).messages = [
      { role: "user", content: "second chat earlier question", ts: 1 },
      { role: "assistant", content: "second chat earlier answer", ts: 2 },
    ];
    const sentSecond = ask(s, "second chat new question");
    await settle();
    s.newTab();
    s.tabs[2]!.messages = [{ role: "user", content: "third chat question", ts: 1 }];

    calls[0]!.reply.answer("first answer");
    await settle();

    expect(calls[1]!.body.message).toBe("second chat new question");
    expect(calls[1]!.body.message_history.map((m) => m.content)).toEqual([
      "second chat earlier question",
      "second chat earlier answer",
    ]);
    calls[1]!.reply.answer("second answer");
    await Promise.all([sentFirst, sentSecond]);
  });
});

describe("a chat with a request in line", () => {
  it("takes no second message until it is answered", async () => {
    const s = await boot();
    const sent = ask(s, "first message");
    await settle();

    await ask(s, "second message");

    expect(first(s).messages.map((m) => m.content)).toEqual(["first message"]);
    // what was typed is kept, not thrown away
    expect(s.input).toBe("second message");
    expect(calls).toHaveLength(1);

    calls[0]!.reply.answer("answer");
    await sent;
  });

  it("takes no second message while it waits behind another chat", async () => {
    const s = await boot();
    const sentFirst = ask(s, "first chat question");
    await settle();
    s.newTab();
    void ask(s, "waiting message");
    await settle();

    await ask(s, "one too many");

    expect(second(s).messages.map((m) => m.content)).toEqual(["waiting message"]);
    expect(s.queue).toEqual([second(s).id]);

    calls[0]!.reply.answer("a");
    await settle();
    calls[1]!.reply.answer("b");
    await sentFirst;
  });

  it("lets another chat send while it is busy", async () => {
    const s = await boot();
    void ask(s, "first chat question");
    await settle();
    s.newTab();

    await Promise.resolve();
    const sentSecond = ask(s, "second chat question");
    await settle();

    expect(s.isBusy(second(s).id)).toBe(true);
    expect(second(s).messages.map((m) => m.content)).toEqual(["second chat question"]);

    calls[0]!.reply.answer("a");
    await settle();
    calls[1]!.reply.answer("b");
    await sentSecond;
  });

  it("does nothing for an empty message", async () => {
    const s = await boot();
    await ask(s, "   ");

    expect(calls).toHaveLength(0);
    expect(first(s).messages).toEqual([]);
    expect(s.queue).toEqual([]);
  });
});

describe("the code blocks of a reply", () => {
  const initBlocks = (container: HTMLElement): void =>
    (window as unknown as { initSensAICodeBlocks(el: HTMLElement): void }).initSensAICodeBlocks(container);

  // a reply as it is shown: the markdown rendered, then its blocks turned into editors
  function reply(markdown: string): HTMLElement {
    const container = document.createElement("div");
    container.innerHTML = renderMarkdown(markdown);
    document.body.appendChild(container);
    initBlocks(container);
    return container;
  }

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("gets an editor and a copy button for each fenced block, and none for inline code", () => {
    const container = reply("Run `mujoco-mojo init` first.\n\n```bash\nmujoco-mojo init\n```\n\n```bash\nbash run.sh\n```\n");

    const blocks = container.querySelectorAll(".sensai-cm-block");
    expect(blocks).toHaveLength(2);
    for (const block of blocks) {
      expect(block.querySelector(".cm-editor")).not.toBeNull();
      expect(block.querySelectorAll("button.sensai-cm-copy")).toHaveLength(1);
    }
    expect(container.querySelectorAll("button")).toHaveLength(2);
  });

  it("puts the button on a block of one line as well as one of many", () => {
    const container = reply("```bash\nbash run.sh\n```\n\n```bash\na \\\n  b \\\n  c\n```\n");

    expect(container.querySelectorAll("button.sensai-cm-copy")).toHaveLength(2);
  });

  it("copies the code of the block, whole and exactly", async () => {
    const container = reply("```bash\nmujoco-mojo run monte-carlo \\\n  -g sim.generate \\\n  -r sim.runtime\n```\n");

    container.querySelector<HTMLButtonElement>("button.sensai-cm-copy")!.click();
    await Promise.resolve();

    expect(store.copyText).toHaveBeenCalledOnce();
    expect(store.copyText).toHaveBeenCalledWith(
      "mujoco-mojo run monte-carlo \\\n  -g sim.generate \\\n  -r sim.runtime",
      "Code copied",
    );
  });

  it("copies each block's own code from its own button", async () => {
    const container = reply("```bash\nfirst\n```\n\n```bash\nsecond\n```\n");

    const buttons = container.querySelectorAll<HTMLButtonElement>("button.sensai-cm-copy");
    buttons[1]!.click();
    await Promise.resolve();

    expect(store.copyText).toHaveBeenCalledWith("second", "Code copied");
    expect(store.copyText).not.toHaveBeenCalledWith("first", expect.anything());
  });

  it("is set up once however many times the reply is laid out again", () => {
    const container = reply("```bash\nls\n```\n");

    initBlocks(container);
    initBlocks(container);

    expect(container.querySelectorAll("button.sensai-cm-copy")).toHaveLength(1);
    expect(container.querySelectorAll(".cm-editor")).toHaveLength(1);
  });

  it("has the button beside the editor, not inside it, so scrolling the code does not move it", () => {
    const container = reply("```bash\nls\n```\n");

    const button = container.querySelector("button.sensai-cm-copy")!;
    expect(button.parentElement).toBe(container.querySelector(".sensai-cm-block"));
    expect(container.querySelector(".cm-editor")!.contains(button)).toBe(false);
  });

  // the token classes CodeMirror gave the code of a rendered block
  const tokenClasses = (container: HTMLElement) =>
    new Set(
      [...container.querySelectorAll(".cm-line [class]")]
        .flatMap((el) => [...el.classList])
        .filter((name) => name.startsWith("tok-")),
    );

  const JSON_BLOCK = '```json\n{"a": 1, "b": "x", "c": true, "d": null, "e": [1.5]}\n```\n';
  const PYTHON_BLOCK =
    "```python\n# say hi\nimport mujoco_mojo as mojo\n\n@decorator\nclass Box(Base):\n" +
    '    def run(self, n=3):\n        """doc"""\n        return f"hi {n}" + str(n) if n > 1 else None\n```\n';
  const SHELL_BLOCK = '```bash\n# go\nmujoco-mojo run monte-carlo --n-trial 10 -w "out dir" | tee log.txt\nexport A=1\n```\n';

  it("marks the parts of JSON with token classes, which the stylesheet colors", () => {
    const classes = tokenClasses(reply(JSON_BLOCK));

    for (const expected of ["tok-propertyName", "tok-string", "tok-number", "tok-bool", "tok-punctuation"]) {
      expect(classes, expected).toContain(expected);
    }
  });

  it("marks the parts of Python with token classes", () => {
    const classes = tokenClasses(reply(PYTHON_BLOCK));

    // a comment, keywords, a decorator, the names a def and a class define, an operator, a number, a string
    for (const expected of ["tok-comment", "tok-keyword", "tok-meta", "tok-definition", "tok-operator", "tok-number", "tok-string"]) {
      expect(classes, expected).toContain(expected);
    }
  });

  it("marks the parts of a shell command with token classes", () => {
    const classes = tokenClasses(reply(SHELL_BLOCK));

    // a comment, an option, a number, a string, a keyword
    for (const expected of ["tok-comment", "tok-propertyName", "tok-number", "tok-string", "tok-keyword"]) {
      expect(classes, expected).toContain(expected);
    }
  });

  it("colors the same Python whichever way the fence names the language", () => {
    const named = (name: string) => [...tokenClasses(reply(`\`\`\`${name}\ndef f():\n    return 1\n\`\`\`\n`))].sort();

    expect(named("python")).toContain("tok-keyword");
    expect(named("py")).toEqual(named("python"));
    expect(named("Python")).toEqual(named("python"));
  });

  it("leaves a language it has no colors for as plain text", () => {
    expect(tokenClasses(reply('```toml\nname = "x"\n```\n')).size).toBe(0);
    expect(tokenClasses(reply('```\nname = "x"\n```\n')).size).toBe(0);
  });

  it("leaves no token class a block can produce without a color in the stylesheet, except plain names", () => {
    // the Jinja templates sit beside static/, not under it
    const css = readFileSync(resolve(import.meta.dirname, "../../../partials/_sensai.html"), "utf-8");
    // names of variables and commands are meant to be the theme's ordinary text color
    const plain = new Set(["tok-variableName"]);

    for (const block of [JSON_BLOCK, PYTHON_BLOCK, SHELL_BLOCK]) {
      const classes = tokenClasses(reply(block));
      expect(classes.size).toBeGreaterThan(0);
      for (const name of classes) {
        if (plain.has(name)) continue;
        expect(css, name).toMatch(new RegExp(`\\.sensai-cm-block \\.${name}\\b[^{]*\\{[^}]*color:`));
      }
    }
  });
});

describe("the SensAI window's header and tabs", () => {
  // the Jinja templates sit beside static/, not under it
  const template = readFileSync(resolve(import.meta.dirname, "../../../partials/_sensai.html"), "utf-8");

  it("has no Clear button: closing a chat does that", () => {
    expect(template).not.toMatch(/clear\(\)/);
    expect(template).not.toMatch(/>\s*Clear\s*</);
  });

  it("offers closing on every chat, the only one included, which leaves an empty chat", () => {
    // the button's own tag, up to its icon (an attribute can hold a `>`, as in `tabs.length > 1`)
    const at = template.indexOf('@click.stop="closeTab(tab.id)"');
    const tag = template.slice(template.lastIndexOf("<button", at), template.indexOf("<svg", at));

    expect(at).toBeGreaterThan(-1);
    // no condition on how many chats there are: with the Clear button gone it is the way to empty one
    expect(tag).not.toContain("x-show");
    expect(tag).toContain("Close chat, leaving an empty one");
  });

  it("has no way left to call clear on the component", async () => {
    const s = await boot();

    expect((s as unknown as { clear?: unknown }).clear).toBeUndefined();
  });
});

describe("the SensAI input's placeholder", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  // how long it takes to type out `text`: the first character shows at once
  const typing = (text: string) => (text.length - 1) * TYPE_MS;

  it("is the default text until the window is opened", async () => {
    const s = await boot();

    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER);
    vi.advanceTimersByTime(60_000);
    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("shows the default text for a moment when the window opens, and then starts to backspace it", async () => {
    const s = await boot();
    s.toggle();

    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER);
    vi.advanceTimersByTime(HOLD_MS - 1);
    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER);
    vi.advanceTimersByTime(1);
    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER.slice(0, -1));
  });

  it("empties the box, and then types an example drawn from the list", async () => {
    vi.spyOn(Math, "random").mockReturnValue(0);
    const s = await boot();
    s.toggle();

    vi.advanceTimersByTime(HOLD_MS + (DEFAULT_PLACEHOLDER.length - 1) * ERASE_MS);
    expect(s.placeholder).toBe("");

    vi.advanceTimersByTime(GAP_MS);
    expect(s.placeholder).toBe(PLACEHOLDER_EXAMPLES[0]!.slice(0, 1));

    vi.advanceTimersByTime(typing(PLACEHOLDER_EXAMPLES[0]!));
    expect(s.placeholder).toBe(PLACEHOLDER_EXAMPLES[0]);
  });

  it("holds the example, then backspaces it and moves on to a different one", async () => {
    vi.spyOn(Math, "random").mockReturnValue(0);
    const s = await boot();
    s.toggle();
    const [one, two] = [PLACEHOLDER_EXAMPLES[0]!, PLACEHOLDER_EXAMPLES[1]!];

    vi.advanceTimersByTime(HOLD_MS + (DEFAULT_PLACEHOLDER.length - 1) * ERASE_MS + GAP_MS + typing(one));
    vi.advanceTimersByTime(HOLD_MS - 1);
    expect(s.placeholder).toBe(one);

    vi.advanceTimersByTime(1 + (one.length - 1) * ERASE_MS);
    expect(s.placeholder).toBe("");
    vi.advanceTimersByTime(GAP_MS + typing(two));
    expect(s.placeholder).toBe(two);
  });

  it("goes on drawing from the list, and never shows the same example twice in a row", async () => {
    const s = await boot();
    s.toggle();
    const seen: string[] = [];

    for (let ms = 0; ms < 120_000; ms += 10) {
      vi.advanceTimersByTime(10);
      if (PLACEHOLDER_EXAMPLES.includes(s.placeholder) && seen.at(-1) !== s.placeholder) {
        seen.push(s.placeholder);
      }
    }

    expect(seen.length).toBeGreaterThan(5);
    expect(new Set(seen).size).toBeGreaterThan(3);
    // a repeat would need a screen emptied in between, so it shows as a repeat in `seen` only if none was skipped
    for (let i = 1; i < seen.length; i++) expect(seen[i]).not.toBe(seen[i - 1]);
  });

  it("stops when the window closes, and goes back to the default text", async () => {
    const s = await boot();
    s.toggle();
    vi.advanceTimersByTime(HOLD_MS + 200);
    expect(s.placeholder).not.toBe(DEFAULT_PLACEHOLDER);

    s.toggle();

    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER);
    expect(vi.getTimerCount()).toBe(0);
    vi.advanceTimersByTime(60_000);
    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER);
  });

  it("stops when the window is closed by its own button or by a click elsewhere", async () => {
    const s = await boot();
    s.toggle();
    s.close();
    expect(vi.getTimerCount()).toBe(0);

    s.toggle();
    s.dismiss();
    expect(vi.getTimerCount()).toBe(0);
    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER);
  });

  it("goes on while the window is pinned open through a click elsewhere", async () => {
    const s = await boot();
    s.toggle();
    s.pinned = true;

    s.dismiss();
    vi.advanceTimersByTime(HOLD_MS + 200);

    expect(s.open).toBe(true);
    expect(s.placeholder).not.toBe(DEFAULT_PLACEHOLDER);
  });

  it("starts again from the default text when the window opens again", async () => {
    const s = await boot();
    s.toggle();
    vi.advanceTimersByTime(HOLD_MS + 1000);
    s.toggle();

    s.toggle();

    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER);
    vi.advanceTimersByTime(HOLD_MS);
    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER.slice(0, -1));
  });

  it("never runs two animations at once", async () => {
    const s = await boot();
    s.toggle();
    const running = vi.getTimerCount();

    s._startPlaceholder();
    s._startPlaceholder();

    expect(vi.getTimerCount()).toBe(running);
  });

  it("is stopped when Alpine removes the component", async () => {
    const s = await boot();
    s.toggle();

    s.destroy();

    expect(vi.getTimerCount()).toBe(0);
    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER);
  });

  it("stays the default text with no animation for someone who asks for less motion", async () => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("reduce") }));
    const s = await boot();

    s.toggle();
    vi.advanceTimersByTime(60_000);

    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("animates when the browser does not report the preference", async () => {
    vi.stubGlobal("matchMedia", undefined);
    const s = await boot();

    s.toggle();
    vi.advanceTimersByTime(HOLD_MS);

    expect(s.placeholder).toBe(DEFAULT_PLACEHOLDER.slice(0, -1));
  });

  it("is what the input shows, not fixed text in the page", () => {
    const template = readFileSync(resolve(import.meta.dirname, "../../../partials/_sensai.html"), "utf-8");
    const at = template.indexOf('x-ref="inputArea"');
    const tag = template.slice(template.lastIndexOf("<textarea", at), template.indexOf("</textarea>", at));

    expect(tag).toContain(':placeholder="placeholder"');
    expect(tag).not.toMatch(/\splaceholder="/);
  });
});

// a message list with the positions the test gives it: happy-dom does no layout,
// so each element reports where the test says it is on the screen. `scrollTop`
// is how far the list has scrolled and `end` is the height of all its content
function messageList(options: { prompts: number[]; listTop?: number; scrollTop?: number; end?: number; promptHeight?: number }) {
  const list = document.createElement("div");
  list.getBoundingClientRect = () => ({ top: options.listTop ?? 100 }) as DOMRect;
  list.scrollTop = options.scrollTop ?? 0;
  Object.defineProperty(list, "scrollHeight", { value: options.end ?? 900 });
  list.scrollTo = vi.fn();
  for (const top of options.prompts) {
    const reply = document.createElement("div");
    reply.dataset["role"] = "assistant";
    reply.getBoundingClientRect = () => ({ top: top - 50 }) as DOMRect;
    const prompt = document.createElement("div");
    prompt.dataset["role"] = "user";
    prompt.getBoundingClientRect = () => ({ top, bottom: top + (options.promptHeight ?? 40) }) as DOMRect;
    list.append(reply, prompt);
  }
  return list;
}

describe("a chat remembers where its list was", () => {
  // the list as it is while a chat is open: the browser reports its height and how far it is scrolled
  function listAt(scrollTop: number, scrollHeight = 2000, clientHeight = 400) {
    const list = document.createElement("div");
    let top = scrollTop;
    const log: string[] = [];
    Object.defineProperty(list, "scrollTop", {
      get: () => top,
      set: (value: number) => {
        log.push(`scrollTop = ${value}`);
        top = value;
      },
    });
    Object.defineProperty(list, "scrollHeight", { value: scrollHeight });
    Object.defineProperty(list, "clientHeight", { value: clientHeight });
    list.scrollTo = vi.fn();
    return { list, log, get now() { return top; } };
  }

  // a window with two chats, the first open and its list at `scrollTop`
  async function twoChats(scrollTop: number, list = listAt(scrollTop)) {
    const s = await boot();
    s.newTab();
    s.switchTab(first(s).id);
    s.$refs = { messages: list.list };
    list.log.length = 0;
    return { s, ...list, list };
  }

  it("is recorded on the chat that is left, and the list goes to the other one's own place", async () => {
    const view = listAt(750);
    const { s } = await twoChats(750, view);
    second(s).scrollTop = 120;

    s.switchTab(second(s).id);

    expect(first(s).scrollTop).toBe(750);
    expect(view.now).toBe(120);
  });

  it("brings each chat back to where it was, however many times they are swapped", async () => {
    const view = listAt(750);
    const { s } = await twoChats(750, view);

    s.switchTab(second(s).id);
    // the user scrolls the second chat, which comes with the wheel (or a finger, the bar, a key)
    view.list.dispatchEvent(new Event("wheel"));
    view.list.scrollTop = 300;
    s.switchTab(first(s).id);
    expect(view.now).toBe(750);
    s.switchTab(second(s).id);
    expect(view.now).toBe(300);
  });

  it("puts a chat that was never scrolled at its top", async () => {
    const view = listAt(900);
    const { s } = await twoChats(900, view);

    s.switchTab(second(s).id);

    expect(second(s).scrollTop).toBeUndefined();
    expect(view.now).toBe(0);
  });

  it("does not scroll to anything of its own accord, smoothly or otherwise", async () => {
    const view = listAt(750);
    const { s } = await twoChats(750, view);
    first(s).messages.push({ role: "user", content: "a question", ts: 1 }, { role: "assistant", content: "an answer", ts: 2 });

    s.switchTab(second(s).id);
    s.switchTab(first(s).id);

    expect(view.list.scrollTo).not.toHaveBeenCalled();
  });

  it("puts the list back at once and not by scrolling to it", async () => {
    const view = listAt(750);
    const { s } = await twoChats(750, view);
    second(s).scrollTop = 120;

    s.switchTab(second(s).id);

    expect(view.log).toEqual(["scrollTop = 120"]);
  });

  it("does so after the messages have laid themselves out, since that changes the height of the list", async () => {
    const view = listAt(750);
    const { s } = await twoChats(750, view);
    second(s).scrollTop = 120;
    // Alpine runs what it is asked to do on the next tick after the work already waiting, in order, and a
    // message lays itself out on a tick of its own that the remeasure event asks for
    const waiting: Array<() => void> = [];
    s.$nextTick = (callback?: () => void) => {
      if (callback) waiting.push(callback);
      return Promise.resolve();
    };
    const laidOut = () => void s.$nextTick(() => view.log.push("messages laid out"));
    window.addEventListener("sensai-remeasure", laidOut);

    s.switchTab(second(s).id);
    for (let callback = waiting.shift(); callback; callback = waiting.shift()) callback();
    window.removeEventListener("sensai-remeasure", laidOut);

    // the log has each thing done to the list: the messages' layout, and the list put at a place
    expect(view.log).toEqual(["messages laid out", "scrollTop = 120"]);
  });

  describe("and whether it is at the bottom, which the scroll button goes by", () => {
    it("is not when the chat was left higher up", async () => {
      const view = listAt(750);
      const { s } = await twoChats(750, view);
      second(s).scrollTop = 100;

      s.switchTab(second(s).id);

      expect(s.atBottom).toBe(false);
    });

    it("is when the chat was left at the end", async () => {
      const view = listAt(750);
      const { s } = await twoChats(750, view);
      // 2000 high, 400 showing: the end is at 1600, and within 30 of it counts
      second(s).scrollTop = 1580;

      s.switchTab(second(s).id);

      expect(s.atBottom).toBe(true);
    });

    it("is not for a chat that was never scrolled and is taller than the window", async () => {
      const view = listAt(750);
      const { s } = await twoChats(750, view);

      s.switchTab(second(s).id);

      expect(s.atBottom).toBe(false);
    });

    it("is for a chat shorter than the window", async () => {
      const view = listAt(0, 300, 400);
      const { s } = await twoChats(0, view);

      s.switchTab(second(s).id);

      expect(s.atBottom).toBe(true);
    });
  });

  it("is saved with the chats, so it is kept when the page is loaded again", async () => {
    const view = listAt(640);
    const { s } = await twoChats(640, view);

    s.switchTab(second(s).id);

    const saved = JSON.parse(localStorage.getItem(TABS_KEY)!) as SensAITab[];
    expect(saved.find((tab) => tab.id === first(s).id)!.scrollTop).toBe(640);
  });

  it("is found again after a chat that has been saved is loaded, and ignored when it cannot be used", async () => {
    const view = listAt(0);
    const s = await boot();
    s.$refs = { messages: view.list };
    s.newTab();
    first(s).scrollTop = "far down" as unknown as number;
    s.switchTab(first(s).id);
    s.switchTab(second(s).id);
    view.log.length = 0;

    s.switchTab(first(s).id);

    expect(view.now).toBe(0);
  });

  it("is the next chat's own place when the open one is closed", async () => {
    const view = listAt(750);
    const { s } = await twoChats(750, view);
    second(s).scrollTop = 250;

    s.closeTab(first(s).id);

    expect(s.tabs).toHaveLength(1);
    expect(view.now).toBe(250);
  });

  it("is the top for the empty chat that replaces the last one closed", async () => {
    const view = listAt(900);
    const s = await boot();
    s.$refs = { messages: view.list };

    s.closeTab(first(s).id);

    expect(view.now).toBe(0);
    expect(view.list.scrollTo).not.toHaveBeenCalled();
  });

  it("is left alone when a chat that is not open is closed", async () => {
    const view = listAt(750);
    const { s } = await twoChats(750, view);

    s.closeTab(second(s).id);

    expect(view.log).toEqual([]);
  });

  it("is not changed by what is done in a chat that is already open", async () => {
    const view = listAt(750);
    const { s } = await twoChats(750, view);

    s.switchTab(first(s).id);

    expect(view.log).toEqual([]);
    expect(first(s).scrollTop).toBeUndefined();
  });

  describe("and is held there while the chat's contents take their final height", () => {
    // a stand-in for ResizeObserver, which the test fires by hand
    class FakeObserver {
      static all: FakeObserver[] = [];
      observed: Element[] = [];
      disconnected = false;
      constructor(readonly callback: () => void) {
        FakeObserver.all.push(this);
      }
      observe(element: Element) {
        this.observed.push(element);
      }
      unobserve() {}
      disconnect() {
        this.disconnected = true;
      }
    }
    const latest = () => FakeObserver.all[FakeObserver.all.length - 1]!;

    beforeEach(() => {
      FakeObserver.all = [];
      vi.stubGlobal("ResizeObserver", FakeObserver);
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    // the first chat open with its list at 750 and two exchanges in it, and the second chat remembered at 120
    async function held() {
      const view = listAt(750);
      view.list.append(document.createElement("div"), document.createElement("div"));
      const { s } = await twoChats(750, view);
      second(s).scrollTop = 120;
      s.switchTab(second(s).id);
      return { s, view, observer: latest() };
    }

    it("puts the list back at its place whenever the contents change size, which moves where it points", async () => {
      const { view, observer } = await held();
      expect(view.now).toBe(120);

      // the browser moves the list (a clamp, or its own correction) as an editor takes its height
      view.list.scrollTop = 300;
      observer.callback();

      expect(view.now).toBe(120);
    });

    it("does not touch the list when it is already at its place", async () => {
      const { view, observer } = await held();
      view.log.length = 0;

      observer.callback();

      expect(view.log).toEqual([]);
    });

    it("watches what is in the list, each exchange, since that is what changes size", async () => {
      const { view, observer } = await held();

      expect(observer.observed).toEqual([...view.list.children]);
      expect(observer.observed).toHaveLength(2);
    });

    it("works out again whether the list is at the bottom, which the scroll button goes by", async () => {
      const { s, view, observer } = await held();
      expect(s.atBottom).toBe(false);

      // the place is 120 of 2000, so wherever the list was moved to, it is put back and is not at the end
      view.list.scrollTop = 1590;
      s.atBottom = true;
      observer.callback();

      expect(s.atBottom).toBe(false);
    });

    it.each(["wheel", "touchstart", "pointerdown", "keydown"])("lets go when the user takes hold of the list: %s", async (name) => {
      const { view, observer } = await held();

      view.list.dispatchEvent(new Event(name));

      expect(observer.disconnected).toBe(true);
      // a callback that was already on its way does nothing
      view.list.scrollTop = 300;
      observer.callback();
      expect(view.now).toBe(300);
    });

    it("does not let go for events that are not the user's", async () => {
      const { view, observer } = await held();

      view.list.dispatchEvent(new Event("scroll"));
      view.list.dispatchEvent(new Event("click"));

      expect(observer.disconnected).toBe(false);
    });

    it("lets go after its time, and not before", async () => {
      const { observer } = await held();

      vi.advanceTimersByTime(SCROLL_HOLD_MS - 1);
      expect(observer.disconnected).toBe(false);
      vi.advanceTimersByTime(1);

      expect(observer.disconnected).toBe(true);
      expect(vi.getTimerCount()).toBe(0);
    });

    it("has no timer or listener left behind when it lets go", async () => {
      const { view, observer } = await held();
      const removed: string[] = [];
      const remove = view.list.removeEventListener.bind(view.list);
      view.list.removeEventListener = ((name: string, ...rest: [EventListenerOrEventListenerObject]) => {
        removed.push(name);
        remove(name, ...rest);
      }) as typeof view.list.removeEventListener;

      view.list.dispatchEvent(new Event("wheel"));

      expect(observer.disconnected).toBe(true);
      expect(removed.sort()).toEqual(["keydown", "pointerdown", "touchstart", "wheel"]);
      expect(vi.getTimerCount()).toBe(0);
    });

    it("lets the first go when the chats are swapped again, and holds the new place", async () => {
      const { s, view, observer } = await held();
      first(s).scrollTop = 750;

      s.switchTab(first(s).id);

      expect(observer.disconnected).toBe(true);
      expect(latest()).not.toBe(observer);
      expect(latest().disconnected).toBe(false);
      expect(view.now).toBe(750);
    });

    describe("when another chat is shown while the list is still being held", () => {
      // Alpine runs what it is asked to do on the next tick, so the list is put at its place a moment
      // after the chat is shown: nothing is done until the test lets the ticks run
      const deferred = (s: SensAI) => {
        const waiting: Array<() => void> = [];
        s.$nextTick = (callback?: () => void) => {
          if (callback) waiting.push(callback);
          return Promise.resolve();
        };
        return () => {
          for (let callback = waiting.shift(); callback; callback = waiting.shift()) callback();
        };
      };

      it("records the place that is held, not where the list happens to be while its contents settle", async () => {
        const { s, view } = await held();
        // the contents are still taking their height, and the browser has clamped the list
        view.list.scrollTop = 40;

        s.switchTab(first(s).id);

        expect(second(s).scrollTop).toBe(120);
      });

      it("records where the list is when it is not being held", async () => {
        const { s, view } = await held();
        view.list.dispatchEvent(new Event("wheel"));
        view.list.scrollTop = 333;

        s.switchTab(first(s).id);

        expect(second(s).scrollTop).toBe(333);
      });

      it("ends the old hold at once, before the new chat's place is put back", async () => {
        const { s, observer } = await held();
        const run = deferred(s);

        s.switchTab(first(s).id);

        // nothing has run yet, so only showing the chat can have ended it
        expect(observer.disconnected).toBe(true);
        run();
        expect(latest()).not.toBe(observer);
      });

      it("does the same when the open chat is closed and the next is shown", async () => {
        const { s, observer } = await held();
        const run = deferred(s);

        s.closeTab(second(s).id);

        expect(observer.disconnected).toBe(true);
        run();
        expect(latest()).not.toBe(observer);
        expect(latest().disconnected).toBe(false);
      });
    });

    it("lets go when anything else scrolls the list", async () => {
      for (const scroll of [
        (s: SensAI) => s.scrollToBottom(),
        (s: SensAI) => s._scrollToLastPrompt(),
      ]) {
        FakeObserver.all = [];
        const { s, observer } = await held();

        scroll(s);

        expect(observer.disconnected).toBe(true);
      }
    });

    it("lets go when the window is closed or removed", async () => {
      const ways = [
        (s: SensAI) => s.close(),
        (s: SensAI) => s.destroy(),
        // the window's button, which closes it when it is open
        (s: SensAI) => {
          s.open = true;
          s.toggle();
        },
      ];
      for (const end of ways) {
        const { s, observer } = await held();

        end(s);

        expect(observer.disconnected).toBe(true);
      }
    });

    describe("while the composer grows with a draft that is different from the last chat's", () => {
      const composer = () => {
        const box = document.createElement("textarea");
        Object.defineProperty(box, "scrollHeight", { value: 40 });
        return box;
      };

      beforeEach(() => {
        vi.stubGlobal("getComputedStyle", () => ({ lineHeight: "20px" }) as CSSStyleDeclaration);
      });

      it("does not pin the list to the bottom, which would undo the place", async () => {
        const { s, view } = await held();
        s.atBottom = true;
        view.log.length = 0;

        s.resize(composer());

        expect(view.log).toEqual([]);
        expect(view.now).toBe(120);
      });

      it("still pins it to the bottom otherwise, as it always did", async () => {
        const { s, view, observer } = await held();
        view.list.dispatchEvent(new Event("wheel"));
        expect(observer.disconnected).toBe(true);
        s.atBottom = true;
        view.log.length = 0;

        s.resize(composer());

        expect(view.log).toEqual(["scrollTop = 2000"]);
      });
    });

    it("still puts the list back where a chat was when this browser has no ResizeObserver", async () => {
      vi.stubGlobal("ResizeObserver", undefined);
      const view = listAt(750);
      const { s } = await twoChats(750, view);
      second(s).scrollTop = 120;

      expect(() => s.switchTab(second(s).id)).not.toThrow();

      expect(view.now).toBe(120);
      expect(FakeObserver.all).toEqual([]);
    });
  });

  it("needs no list yet to switch chats", async () => {
    const s = await boot();
    s.newTab();

    expect(() => s.switchTab(first(s).id)).not.toThrow();
  });
});

describe("where the SensAI window scrolls by itself", () => {
  // the list's top padding, as the browser would report it (happy-dom reports none)
  beforeEach(() => {
    vi.stubGlobal("getComputedStyle", () => ({ paddingTop: "12px", lineHeight: "20px" }) as CSSStyleDeclaration);
  });

  it("puts the last prompt at the very top of the list, whatever padding the list reports", async () => {
    const s = await boot();
    const list = messageList({ prompts: [200, 500], scrollTop: 40 });
    s.$refs = { messages: list };

    s._scrollToLastPrompt();

    // 500 - 100 + 40: the last prompt, not the earlier one
    expect(list.scrollTo).toHaveBeenCalledWith({ top: 440, behavior: "smooth" });
    expect(list.scrollTo).toHaveBeenCalledTimes(1);
  });

  describe("a question inside an exchange", () => {
    // the list has no padding above, so the room above a question is its exchange's, and the
    // question is put at the very top: the place it sticks, so it does not move as it sticks
    const inExchange = (padding: string, exchangeTop = -200, scrollTop = 600) => {
      // only the exchange has the padding, so reading it from any other element gives a wrong answer
      vi.stubGlobal(
        "getComputedStyle",
        (el: Element) => ({ paddingTop: el.classList.contains("sensai-exchange") ? padding : "99px" }) as CSSStyleDeclaration,
      );
      const list = messageList({ prompts: [], scrollTop });
      const exchange = document.createElement("div");
      exchange.className = "sensai-exchange";
      exchange.getBoundingClientRect = () => ({ top: exchangeTop }) as DOMRect;
      const question = document.createElement("div");
      question.dataset["role"] = "user";
      question.getBoundingClientRect = () => ({ top: 100 }) as DOMRect;
      exchange.append(question);
      list.append(exchange);
      return list;
    };

    it("is put where the exchange begins plus the exchange's own padding, so the question is flush with the top", async () => {
      const s = await boot();
      const list = inExchange("12px");
      s.$refs = { messages: list };

      s._scrollToLastPrompt();

      // -200 - 100 + 600 to reach the exchange, and 12 more to reach the question inside its padding
      expect(list.scrollTo).toHaveBeenCalledWith({ top: 312, behavior: "smooth" });
    });

    it("is put where the exchange begins when the exchange has no padding", async () => {
      const s = await boot();
      const list = inExchange("");
      s.$refs = { messages: list };

      s._scrollToLastPrompt();

      expect(list.scrollTo).toHaveBeenCalledWith({ top: 300, behavior: "smooth" });
    });

    it("never goes above the start of the list", async () => {
      const s = await boot();
      const list = inExchange("12px", -50, 0);
      s.$refs = { messages: list };

      s._scrollToLastPrompt();

      // the exchange is at -50 - 100 + 0 = -150, so 0, and then the padding
      expect(list.scrollTo).toHaveBeenCalledWith({ top: 12, behavior: "smooth" });
    });
  });

  it("goes to the end of the list while there is no prompt yet", async () => {
    const s = await boot();
    const list = messageList({ prompts: [], end: 777 });
    s.$refs = { messages: list };

    s._scrollToLastPrompt();

    expect(list.scrollTo).toHaveBeenCalledWith({ top: 777, behavior: "smooth" });
  });

  it("does nothing before the list is on the page", async () => {
    const s = await boot();

    expect(() => s._scrollToLastPrompt()).not.toThrow();
  });

  it("does that when a message is sent", async () => {
    const s = await boot();
    const list = messageList({ prompts: [300], scrollTop: 0 });
    s.$refs = { messages: list };

    const done = ask(s, "hello");
    await settle();
    calls[0]!.reply.answer("hi");
    await done;

    expect(list.scrollTo).toHaveBeenCalledWith({ top: 200, behavior: "smooth" });
  });

  it("does that for a message that has to wait its turn, which no request has started yet", async () => {
    const s = await boot();
    const running = ask(s, "first");
    await settle();
    s.newTab();
    const list = messageList({ prompts: [300] });
    s.$refs = { messages: list };

    const queued = ask(s, "second");
    await settle();

    expect(s.isQueued(s.activeId)).toBe(true);
    expect(list.scrollTo).toHaveBeenCalledWith({ top: 200, behavior: "smooth" });

    calls[0]!.reply.answer("one");
    await settle();
    calls[1]!.reply.answer("two");
    await Promise.all([running, queued]);
  });

  it("does that when the window opens", async () => {
    const s = await boot();
    const list = messageList({ prompts: [300] });
    s.$refs = { messages: list };

    s.toggle();

    expect(list.scrollTo).toHaveBeenCalledWith({ top: 200, behavior: "smooth" });
  });

  it("leaves the scroll button going to the very end of the list", async () => {
    const s = await boot();
    const list = messageList({ prompts: [300, 600], end: 1500 });
    s.$refs = { messages: list };
    s.atBottom = false;
    s.hasNewResponse = true;

    s.scrollToBottom();

    expect(list.scrollTo).toHaveBeenCalledWith({ top: 1500, behavior: "smooth" });
    expect(s.atBottom).toBe(true);
    expect(s.hasNewResponse).toBe(false);
  });

  it("is told which messages are the user's by the page", () => {
    const template = readFileSync(resolve(import.meta.dirname, "../../../partials/_sensai.html"), "utf-8");
    const at = template.indexOf('x-data="sensaiMsgData(');
    const tag = template.slice(template.lastIndexOf("<div", at), template.indexOf(">", template.indexOf(":class=", at)));

    expect(tag).toContain(':data-role="msg.role"');
  });
});

describe("the SensAI window being left open or closed", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("getComputedStyle", () => ({ paddingTop: "12px", lineHeight: "20px" }) as CSSStyleDeclaration);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // the server's answer to the page's question of whether SensAI is turned on
  const config = (reply: () => Promise<unknown>) =>
    vi.stubGlobal("fetch", (url: string) => (url === "/sensai/config" ? reply() : Promise.reject(new Error(url))));

  it("starts closed when nothing was saved", async () => {
    const s = await boot();

    expect(s.open).toBe(false);
    expect(localStorage.getItem(OPEN_KEY)).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("saves that it is open when it is opened, and closed when it is closed", async () => {
    const s = await boot();

    s.toggle();
    expect(localStorage.getItem(OPEN_KEY)).toBe("1");
    s.toggle();
    expect(localStorage.getItem(OPEN_KEY)).toBe("0");
  });

  it("saves closed when its own button or a click elsewhere closes it", async () => {
    const s = await boot();

    s.toggle();
    s.close();
    expect(localStorage.getItem(OPEN_KEY)).toBe("0");

    s.toggle();
    s.dismiss();
    expect(localStorage.getItem(OPEN_KEY)).toBe("0");
  });

  it("stays saved as open when it is pinned and a click elsewhere does not close it", async () => {
    const s = await boot();
    s.toggle();
    s.pinned = true;

    s.dismiss();

    expect(s.open).toBe(true);
    expect(localStorage.getItem(OPEN_KEY)).toBe("1");
  });

  it("comes back open on the next page when it was left open", async () => {
    localStorage.setItem(OPEN_KEY, "1");

    const s = await boot();

    expect(s.open).toBe(true);
  });

  it("comes back closed on the next page when it was left closed", async () => {
    localStorage.setItem(OPEN_KEY, "0");

    const s = await boot();

    expect(s.open).toBe(false);
  });

  it("is shown as it would be if it had just been opened", async () => {
    localStorage.setItem(OPEN_KEY, "1");
    const list = messageList({ prompts: [300] });
    const remeasured = vi.fn();
    window.addEventListener("sensai-remeasure", remeasured);

    const s = await boot({ messages: list });
    window.removeEventListener("sensai-remeasure", remeasured);

    // scrolled to the last prompt, laid out afresh, and its placeholder is animated
    expect(list.scrollTo).toHaveBeenCalledWith({ top: 200, behavior: "smooth" });
    expect(remeasured).toHaveBeenCalledTimes(1);
    expect(s.hasNewResponse).toBe(false);
    vi.advanceTimersByTime(HOLD_MS);
    expect(s.placeholder).not.toBe(DEFAULT_PLACEHOLDER);
  });

  it("does not run the placeholder when it comes back closed", async () => {
    localStorage.setItem(OPEN_KEY, "0");

    await boot();

    expect(vi.getTimerCount()).toBe(0);
  });

  it("stays closed, and still, when SensAI is turned off, and keeps what was saved", async () => {
    localStorage.setItem(OPEN_KEY, "1");
    config(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ enabled: false }) }));

    const s = await boot();

    expect(s.open).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
    expect(localStorage.getItem(OPEN_KEY)).toBe("1");
  });

  it("stays closed when the server cannot say whether SensAI is turned on", async () => {
    localStorage.setItem(OPEN_KEY, "1");
    config(() => Promise.reject(new TypeError("network down")));

    const s = await boot();

    expect(s.open).toBe(false);
  });

  it("opens when the server answers without saying, as it does for a SensAI that is on", async () => {
    localStorage.setItem(OPEN_KEY, "1");
    config(() => Promise.resolve({ ok: false }));

    const s = await boot();

    expect(s.open).toBe(true);
  });

  it("comes back pinned and open together", async () => {
    localStorage.setItem(OPEN_KEY, "1");
    localStorage.setItem(PINNED_KEY, "1");

    const s = await boot();

    expect(s.pinned).toBe(true);
    expect(s.open).toBe(true);
  });

  it("is the same for the next page that is opened", async () => {
    const first = await boot();
    first.toggle();

    const next = await boot();

    expect(next.open).toBe(true);
    next.close();
    expect((await boot()).open).toBe(false);
  });

  it("starts closed, without failing, when storage cannot be read", async () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("storage refused a read");
      },
      setItem: () => {
        throw new Error("storage refused a write");
      },
      removeItem: () => undefined,
      clear: () => undefined,
    });

    const s = await boot();
    expect(() => s.toggle()).not.toThrow();

    expect(s.open).toBe(true);
  });
});

// the template's tags up to `marker`, outermost first, as what each tag loops over or
// shows (its x-for or x-if) or its class, to see what a part of the page sits inside
function ancestorsOf(template: string, marker: string): string[] {
  const stack: string[] = [];
  const tag = /<(\/?)(div|template)\b([^>]*(?:"[^"]*"[^>]*)*)>/g;
  const upTo = template.slice(0, template.indexOf(marker));
  for (const [, closing, , attrs] of upTo.matchAll(tag)) {
    if (closing) stack.pop();
    else {
      const name = /x-for="([^"]*)"/.exec(attrs!)?.[1] ?? /x-if="([^"]*)"/.exec(attrs!)?.[1] ?? /class="([^"]*)"/.exec(attrs!)?.[1] ?? "";
      stack.push(name);
    }
  }
  return stack;
}

describe("a question that sticks to the top of the list", () => {
  const template = readFileSync(resolve(import.meta.dirname, "../../../partials/_sensai.html"), "utf-8");

  const chat = (s: SensAI, questions: string[]) => {
    for (const [i, question] of questions.entries()) {
      first(s).messages.push(
        { role: "user", content: question, ts: i * 2 },
        { role: "assistant", content: `answer ${i}`, ts: i * 2 + 1 },
      );
    }
  };

  describe("the exchanges the list is made of", () => {
    it("are one for each question with its answer", async () => {
      const s = await boot();
      chat(s, ["one", "two"]);

      expect(s.exchanges.map((g) => [g.start, g.messages.map((m) => m.content), g.last])).toEqual([
        [0, ["one", "answer 0"], false],
        [2, ["two", "answer 1"], true],
      ]);
    });

    it("are none for an empty chat", async () => {
      expect((await boot()).exchanges).toEqual([]);
    });

    it("are those of the chat that is open", async () => {
      const s = await boot();
      chat(s, ["in the first chat"]);
      s.newTab();
      second(s).messages.push({ role: "user", content: "in the second chat", ts: 9 });

      expect(s.exchanges.map((g) => g.messages[0]!.content)).toEqual(["in the second chat"]);
      s.switchTab(first(s).id);
      expect(s.exchanges.map((g) => g.messages[0]!.content)).toEqual(["in the first chat"]);
    });
  });

  describe("in the page", () => {
    it("is the question's own message, sticking to the top, and not a bar over the list", () => {
      const at = template.indexOf("x-data=\"sensaiMsgData(");
      const tag = template.slice(template.lastIndexOf("<div", at), template.indexOf(">", template.indexOf(":class=", at)));

      expect(tag).toMatch(/msg\.role === 'user' \? '[^']*\bsticky\b[^']*\btop-0\b/);
      expect(template).not.toContain("pinnedPrompt");
      expect(template).not.toContain("showPinnedPrompt");
    });

    it("covers what scrolls under it, across the whole width of the list", () => {
      const at = template.indexOf("x-data=\"sensaiMsgData(");
      const tag = template.slice(template.lastIndexOf("<div", at), template.indexOf(">", template.indexOf(":class=", at)));
      const user = /msg\.role === 'user' \? '([^']*)'/.exec(tag)![1]!;

      // the panel's own color from its top edge (see the style of .sensai-question), and as wide as the
      // list including its padding at the sides
      expect(user).toContain("sensai-question");
      expect(user).not.toContain("bg-surface");
      expect(user).toContain("-mx-3");
      expect(user).toContain("px-3");
      // room under the bubble for the fade, which the style sets to two rem, and no gap added by the
      // list's own spacing on top of it
      expect(user).toContain("pb-8");
      expect(user).toContain("mb-0");
      // above the copy buttons inside the answers, which sit at 2
      expect(user).toMatch(/\bz-10\b/);
    });

    it("is for a question only: an answer scrolls", () => {
      const at = template.indexOf("x-data=\"sensaiMsgData(");
      const tag = template.slice(template.lastIndexOf("<div", at), template.indexOf(">", template.indexOf(":class=", at)));

      expect(/: 'items-start'/.exec(tag)).not.toBeNull();
      expect(tag).not.toMatch(/: '[^']*sticky/);
    });

    it("sits in a box holding only its own answer, which is what pushes it off when the next question comes", () => {
      expect(ancestorsOf(template, 'x-data="sensaiMsgData(').slice(-3)).toEqual([
        "group in exchanges",
        "sensai-exchange space-y-3 pt-3",
        "(msg, i) in group.messages",
      ]);
    });

    it("keeps what shows while a request runs in the last exchange, so its question stays pinned as the reply streams", () => {
      for (const marker of ['x-show="streaming && isRunning(activeId)"', 'x-show="isRunning(activeId) && !streaming"', 'x-show="isQueued(activeId)"']) {
        expect(ancestorsOf(template, marker).slice(-4), marker).toEqual([
          "group in exchanges",
          "sensai-exchange space-y-3 pt-3",
          "group.last",
          "space-y-3",
        ]);
      }
    });

    it("takes the list up to the question when it is clicked, as well as opening it", () => {
      expect(template).toContain(`@click="expand(); if (msg.role === 'user') showExchange($el)"`);
    });
  });

  describe("clicking it", () => {
    // a list with an exchange in it, whose top is where the test says
    const exchangeIn = (exchangeTop: number, options: Parameters<typeof messageList>[0] = { prompts: [] }) => {
      const list = messageList(options);
      const exchange = document.createElement("div");
      exchange.className = "sensai-exchange";
      exchange.getBoundingClientRect = () => ({ top: exchangeTop }) as DOMRect;
      const bubble = document.createElement("div");
      exchange.append(bubble);
      list.append(exchange);
      return { list, exchange, bubble };
    };

    beforeEach(() => {
      vi.stubGlobal("getComputedStyle", () => ({ paddingTop: "12px" }) as CSSStyleDeclaration);
    });

    it("takes the list up to where its exchange begins", async () => {
      // scrolled 600 down, with the exchange's top 200 above the top of the list (at 100)
      const s = await boot();
      const { list, bubble } = exchangeIn(-200, { prompts: [], scrollTop: 600 });
      s.$refs = { messages: list };

      s.showExchange(bubble);

      // -200 - 100 + 600 to reach the exchange, and 12 more to reach the question inside its padding
      expect(list.scrollTo).toHaveBeenCalledWith({ top: 312, behavior: "smooth" });
      expect(list.scrollTo).toHaveBeenCalledTimes(1);
    });

    it("is left alone when it ends a selection of the question's text", async () => {
      vi.stubGlobal("getSelection", () => ({ toString: () => "some of the text" }));
      const s = await boot();
      const { list, bubble } = exchangeIn(-200, { prompts: [], scrollTop: 600 });
      s.$refs = { messages: list };

      s.showExchange(bubble);

      expect(list.scrollTo).not.toHaveBeenCalled();
    });

    it("scrolls when nothing is selected", async () => {
      vi.stubGlobal("getSelection", () => ({ toString: () => "" }));
      const s = await boot();
      const { list, bubble } = exchangeIn(-200, { prompts: [], scrollTop: 600 });
      s.$refs = { messages: list };

      s.showExchange(bubble);

      expect(list.scrollTo).toHaveBeenCalledTimes(1);
    });

    it("does nothing for a message that is not in an exchange, or before the list is there", async () => {
      const s = await boot();
      const loose = document.createElement("div");
      const list = messageList({ prompts: [] });
      s.$refs = { messages: list };

      s.showExchange(loose);
      expect(list.scrollTo).not.toHaveBeenCalled();

      s.$refs = {};
      expect(() => s.showExchange(loose)).not.toThrow();
    });

    it("scrolls to where the exchange begins even when the question is pinned at the top, which is not where it is", async () => {
      // the list's top is at 100: the pinned question is drawn there, while its exchange began far above
      const s = await boot();
      const { list, exchange } = exchangeIn(-500, { prompts: [], scrollTop: 700 });
      const pinned = document.createElement("div");
      pinned.dataset["role"] = "user";
      pinned.getBoundingClientRect = () => ({ top: 100 }) as DOMRect;
      exchange.prepend(pinned);
      s.$refs = { messages: list };

      s._scrollToLastPrompt();

      // -500 - 100 + 700 + 12: the exchange, and not the pinned question (which would be 700 + 12)
      expect(list.scrollTo).toHaveBeenCalledWith({ top: 112, behavior: "smooth" });
    });
  });
});

describe("opening and closing a message", () => {
  type Msg = {
    open: boolean;
    single: boolean;
    settled: boolean;
    fullHeight: number;
    bubbleStyle: string;
    toggle(): void;
    expand(): void;
    setOpen(next: boolean): void;
    measure(isLastUser?: boolean): void;
    $refs: Record<string, unknown>;
    $el: Element;
  };

  // the bubble, as the browser would report it: 300 of content with a border of 1, clipped to 56
  // while it is closed, and a log of what was done to it and in what order
  function bubble(log: string[] = []) {
    return {
      scrollHeight: 300,
      clientHeight: 56,
      get offsetHeight() {
        log.push("reflow");
        return 58;
      },
      style: {
        set maxHeight(value: string) {
          log.push(`max-height ${value}`);
        },
      },
    };
  }

  // `ref` is the bubble the message finds by its ref, or null for a message with none
  function message(role: string, isLastUser = false, ref: unknown = bubble()): Msg {
    const m = (window as unknown as { sensaiMsgData(r: string, l: boolean): Msg }).sensaiMsgData(role, isLastUser);
    m.$refs = ref === null ? {} : { bubble: ref };
    return m;
  }

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("starts open for an answer and for the latest question, and closed for an earlier one", () => {
    expect(message("assistant").open).toBe(true);
    expect(message("user", true).open).toBe(true);
    expect(message("user", false).open).toBe(false);
  });

  it("starts settled, so an open message has no height limit and nothing animates on first showing", () => {
    const m = message("assistant");
    m.single = false;

    expect(m.settled).toBe(true);
    expect(m.bubbleStyle).toBe("max-height: none");
  });

  it("opens to the height of its whole content, in pixels, so it animates as it grows", () => {
    const m = message("user", false);

    m.expand();

    expect(m.open).toBe(true);
    expect(m.settled).toBe(false);
    // 300 of content and 2 of border
    expect(m.fullHeight).toBe(302);
    expect(m.bubbleStyle).toBe("max-height: 302px");
  });

  it("has no height limit again once the opening is over, so what it holds can grow", () => {
    const m = message("user", false);
    m.expand();

    vi.advanceTimersByTime(BUBBLE_SETTLE_MS - 1);
    expect(m.bubbleStyle).toBe("max-height: 302px");
    vi.advanceTimersByTime(1);

    expect(m.settled).toBe(true);
    expect(m.bubbleStyle).toBe("max-height: none");
  });

  it("closes by giving the browser its height in pixels to start from, and then the short height", () => {
    const log: string[] = [];
    const m = message("assistant", false, bubble(log));

    m.toggle();

    // the height is set and the browser made to see it before the style changes to the closed one
    // (measuring it read the height once already, which is the first entry)
    expect(log.slice(log.indexOf("max-height 302px"))).toEqual(["max-height 302px", "reflow"]);
    expect(m.open).toBe(false);
    expect(m.bubbleStyle).toContain("max-height: 3.5rem");
  });

  it("closes without that step when it is still opening, because it already has a pixel height", () => {
    const log: string[] = [];
    const m = message("user", false, bubble(log));
    m.expand();
    const before = log.length;

    m.toggle();

    // nothing was set on the bubble and the browser was not made to catch up
    expect(log.slice(before)).toEqual([]);
    expect(m.open).toBe(false);
  });

  it("is not left open by an opening that was closed before it finished", () => {
    const m = message("user", false);
    m.expand();
    m.toggle();

    vi.advanceTimersByTime(BUBBLE_SETTLE_MS * 2);

    expect(m.open).toBe(false);
    expect(m.settled).toBe(false);
    expect(m.bubbleStyle).toContain("max-height: 3.5rem");
  });

  it("measures its height afresh each time it opens", () => {
    const tall = bubble();
    const m = message("user", false, tall);
    m.expand();
    vi.advanceTimersByTime(BUBBLE_SETTLE_MS);
    m.toggle();

    tall.scrollHeight = 500;
    m.expand();

    expect(m.fullHeight).toBe(502);
  });

  it("is left alone when asked to be as it already is", () => {
    const log: string[] = [];
    const open = message("assistant", false, bubble(log));
    const closed = message("user", false, bubble(log));
    closed.single = false;

    open.setOpen(true);
    closed.setOpen(false);

    // an open bubble stays settled with no limit, a closed one stays as it was, and neither was measured
    expect(open.settled).toBe(true);
    expect(open.bubbleStyle).toBe("max-height: none");
    expect(closed.bubbleStyle).toContain("max-height: 3.5rem");
    expect(log).toEqual([]);
    vi.advanceTimersByTime(BUBBLE_SETTLE_MS * 2);
    expect(open.bubbleStyle).toBe("max-height: none");
  });

  it("toggles open and closed", () => {
    const m = message("user", false);

    m.toggle();
    expect(m.open).toBe(true);
    m.toggle();
    expect(m.open).toBe(false);
  });

  it("is opened by a click only when it is closed, and a click on an open one leaves it open", () => {
    const m = message("assistant");

    m.expand();

    expect(m.open).toBe(true);
    expect(m.settled).toBe(true);
  });

  it("does nothing, and has no style, for a single line", () => {
    const m = message("user", false);
    m.single = true;

    m.toggle();
    m.expand();

    expect(m.open).toBe(false);
    expect(m.bubbleStyle).toBe("");
  });

  it("opens with no height limit when there is no bubble to measure", () => {
    const m = message("user", false, null);

    expect(() => m.expand()).not.toThrow();

    expect(m.open).toBe(true);
    expect(m.bubbleStyle).toBe("max-height: none");
  });

  it("is settled again when it is measured, whatever it was doing", () => {
    vi.stubGlobal("getComputedStyle", () => ({ lineHeight: "20px" }) as CSSStyleDeclaration);
    const m = message("user", false);
    m.expand();
    const content = document.createElement("p");
    Object.defineProperty(content, "scrollHeight", { value: 200 });
    m.$el = document.createElement("div");
    m.$el.append(content);

    m.measure(false);

    expect(m.settled).toBe(true);
    expect(m.single).toBe(false);
    expect(m.open).toBe(false);
  });

  it("is in the page: the header toggles it, the bubble opens on a click and is measured and styled by the component, with no fixed limit left", () => {
    const template = readFileSync(resolve(import.meta.dirname, "../../../partials/_sensai.html"), "utf-8");

    for (const handler of ["@mousedown.prevent", "@keydown.enter.prevent", "@keydown.space.prevent"]) {
      expect(template).toContain(`${handler}="toggle()"`);
    }
    expect(template).toContain('x-ref="bubble"');
    expect(template).toContain(':style="bubbleStyle"');
    expect(template).toContain("transition-[max-height] duration-300");
    expect(template).not.toContain("max-h-[10000px]");
    expect(template).not.toContain("max-h-14");
    expect(template).not.toMatch(/open = !open/);
  });
});

describe("the tool calls in the page", () => {
  const template = readFileSync(resolve(import.meta.dirname, "../../../partials/_sensai.html"), "utf-8");

  it("are drawn by one set of rows, for the running list and for a reply's", () => {
    expect(template.match(/\{% macro tool_call_rows\(/g)).toHaveLength(1);
    expect(template.match(/x-for="call in \{\{ list_expr \}\}"/g)).toHaveLength(1);
    expect(template).toContain("{{ tool_call_rows('msg.tool_calls') }}");
    expect(template).toContain("{{ tool_call_rows('toolCalls') }}");
  });

  it("are listed for the running request in the last exchange, so the question stays pinned while it works", () => {
    expect(ancestorsOf(template, 'x-show="isRunning(activeId) && toolCalls.length > 0"').slice(-4)).toEqual([
      "group in exchanges",
      "sensai-exchange space-y-3 pt-3",
      "group.last",
      "space-y-3",
    ]);
  });

  it("are in a reply only, above its text, and closed until asked for", () => {
    const list = template.indexOf("msg.role !== 'user' && msg.tool_calls?.length > 0");
    expect(list).toBeGreaterThan(template.indexOf('x-data="sensaiMsgData('));
    expect(list).toBeLessThan(template.indexOf('x-ref="bubble"'));
    expect(template).toContain('@click="toolsOpen = !toolsOpen"');
    expect(template).toContain('x-show="toolsOpen"');
  });

  it("keep a paragraph out of the rows, since a message is measured by its first `.sensai-md` or `p`", () => {
    const macro = template.slice(template.indexOf("{% macro tool_call_rows("), template.indexOf("{% endmacro %}"));
    expect(macro).not.toMatch(/<p[\s>]/);
  });
});
