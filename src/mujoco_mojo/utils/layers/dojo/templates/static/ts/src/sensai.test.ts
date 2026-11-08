// @vitest-environment happy-dom
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { renderMarkdown } from "./lib/markdown";
import {
  ACTIVE_TAB_KEY,
  PINNED_KEY,
  STORAGE_KEY,
  TABS_KEY,
  loadSensAITabs,
  titleFromMessage,
  type SensAIMessage,
  type SensAITab,
} from "./lib/sensai";

// the component object itself, not a copy of its logic: its methods are called
// on a real `sensai()` with the browser's storage and a fake `fetch` behind it
type SensAI = {
  open: boolean;
  pinned: boolean;
  tabs: SensAITab[];
  activeId: string;
  input: string;
  maxTabs: number;
  runningId: string | null;
  queue: string[];
  hasNewResponse: boolean;
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
  };
  signal: AbortSignal | undefined;
  reply: Reply;
}

let calls: Call[];
let failNextRequest: boolean;

// the dojo store the component reaches through Alpine, with a copy the tests can watch
const store = {
  columnManifest: null,
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

async function boot(): Promise<SensAI> {
  const s = make();
  s.$watch = () => undefined;
  s.$refs = {};
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

  it("marks the parts of JSON with token classes, which the stylesheet colors", () => {
    const container = reply('```json\n{"a": 1, "b": "x", "c": true, "d": null, "e": [1.5]}\n```\n');

    const classes = new Set(
      [...container.querySelectorAll(".cm-line [class]")]
        .flatMap((el) => [...el.classList])
        .filter((name) => name.startsWith("tok-")),
    );

    for (const expected of ["tok-propertyName", "tok-string", "tok-number", "tok-bool", "tok-punctuation"]) {
      expect(classes, expected).toContain(expected);
    }
  });

  it("leaves no token class a block can produce without a color in the stylesheet", () => {
    const container = reply('```json\n{"a": 1, "b": "x", "c": true, "d": null, "e": [1.5]}\n```\n');
    // the Jinja templates sit beside static/, not under it
    const css = readFileSync(resolve(import.meta.dirname, "../../../partials/_sensai.html"), "utf-8");

    const classes = new Set(
      [...container.querySelectorAll(".cm-line [class]")]
        .flatMap((el) => [...el.classList])
        .filter((name) => name.startsWith("tok-")),
    );

    expect(classes.size).toBeGreaterThan(0);
    for (const name of classes) {
      expect(css, name).toMatch(new RegExp(`\\.sensai-cm-block \\.${name}\\b[^{]*\\{[^}]*color:`));
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

