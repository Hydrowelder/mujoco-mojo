// sensai chat logic, moved out of sensai.ts so it can be tested without an
// alpine component: reading the server's event stream, what a reply says, the
// request a message sends, the saved history and its export, and the sizing
// rules for the composer and the message bubbles.

import type { ColumnManifest } from "../models";
import type { VersusState } from "./plot-profile";
import {
  loadTabsFromStorage,
  newTabId,
  persistTabsToStorage,
} from "./tab-session";

// one tool call made while a message was answered, as the server records it:
// `agent` is "chat" for a hand-off to a specialist and the specialist's route
// ("plot_config", "job_status", ...) for its own calls. `args` and `result` are
// one line each, already cut to a length the chat can preview
export type SensAIToolStatus = "running" | "ok" | "rejected" | "failed";

export interface SensAIToolCall {
  id: number;
  name: string;
  agent: string;
  args: string;
  status: SensAIToolStatus;
  result?: string | null;
}

export interface SensAIMessage {
  role: "user" | "assistant";
  content: string;
  error?: boolean;
  plot_config_update?: object | null;
  routed_to?: string;
  // the model that wrote an assistant reply, when the server said which
  model?: string;
  // the tool calls made to get to this reply, in the order they started
  tool_calls?: SensAIToolCall[];
  ts: number;
}

export interface SensAIResultPayload {
  message?: string;
  plot_config_update?: object | null;
  routed_to?: string;
  model?: string | null;
  detail?: string;
  label?: string;
  tool_calls?: SensAIToolCall[];
  // versus mode as SensAI left it, when the message changed it
  versus_update?: VersusState | null;
}

// a `tool_start` event carries the whole call, and a `tool_end` event carries
// the call's id with how it went, so each is a part of a SensAIToolCall
export type SensAIEventPayload = SensAIResultPayload &
  Partial<SensAIToolCall> & { delta?: string };

// the one chat history there was before tabs, read once to become the first tab
export const STORAGE_KEY = "sensai-messages";
export const TABS_KEY = "sensai-tabs";
export const ACTIVE_TAB_KEY = "sensai-active-tab";
export const PINNED_KEY = "sensai-pinned";
export const OPEN_KEY = "sensai-open";

// how many chats can be open at once, so the saved history stays a size the
// browser's storage can hold
export const MAX_TABS = 8;

// a tab's title is the start of its first message, cut to this many characters.
// the tab shows only the first few (the strip cuts the rest off), so the title
// has to hold more than that for the tooltip to be able to show the whole name
const TITLE_LENGTH = 80;

// one chat: its own messages, so each carries its own context to the model
export interface SensAITab {
  id: string;
  title: string;
  messages: SensAIMessage[];
  // what was typed in this chat's box and not sent, kept while another chat is open
  draft?: string;
  // a reply arrived in this chat while another one was open
  unread?: boolean;
  // false once the user renamed it, so a first message no longer retitles it
  autoTitled?: boolean;
  // how far this chat's list was scrolled when it was last in view, so it comes back
  // to the same place
  scrollTop?: number;
}

// how long the list is held at the place a chat is put back to. what is in a chat
// (code editors, which correct their estimate of their own height a frame after they
// are made, and math, which is typeset once KaTeX has loaded) goes on taking its
// final height after the chat is shown, and each change above that place moves what it
// points at
export const SCROLL_HOLD_MS = 1500;

// where to put a chat's list when it comes back into view: where it was left, or the
// top for a chat that was never scrolled or whose saved value is not a usable number
export function rememberedScroll(tab: { scrollTop?: unknown } | undefined): number {
  const value = tab?.scrollTop;
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : 0;
}

// how many earlier messages a request carries along as context
const HISTORY_LENGTH = 20;

export interface SseEvent {
  type: string;
  payload: SensAIEventPayload;
}

// reads a server-sent event stream a chunk of text at a time. `event: name`
// sets the type of the `data: {json}` lines that follow, up to the next blank
// line; a data line with no valid JSON is skipped. Lines may be split across
// chunks, so `feed` only handles the complete ones and `end` handles what is
// left when the stream closes.
export function createSseParser(): {
  feed(chunk: string): SseEvent[];
  end(): SseEvent[];
} {
  let buffer = "";
  let eventType = "";

  const handleLine = (line: string, out: SseEvent[]): void => {
    const trimmed = line.trimEnd();
    if (trimmed.startsWith("event: ")) {
      eventType = trimmed.slice(7);
    } else if (trimmed.startsWith("data: ")) {
      try {
        out.push({
          type: eventType,
          payload: JSON.parse(trimmed.slice(6)) as SensAIEventPayload,
        });
      } catch {
        /* ignore malformed SSE lines */
      }
    } else if (trimmed === "") {
      eventType = "";
    }
  };

  return {
    feed(chunk) {
      const out: SseEvent[] = [];
      buffer += chunk;
      let newline: number;
      while ((newline = buffer.indexOf("\n")) !== -1) {
        handleLine(buffer.slice(0, newline), out);
        buffer = buffer.slice(newline + 1);
      }
      return out;
    },
    end() {
      const out: SseEvent[] = [];
      // flush any remaining content in the buffer
      if (buffer) handleLine(buffer, out);
      return out;
    },
  };
}

// the calls so far with one server event applied: `tool_start` adds the call
// (a repeat of an id already there is ignored) and `tool_end` settles the call
// with that id. an event that does not make sense (a start with no name, an end
// for a call that was never started) changes nothing
export function applyToolEvent(
  calls: SensAIToolCall[],
  type: string,
  payload: SensAIEventPayload,
): SensAIToolCall[] {
  if (type === "tool_start") {
    if (
      typeof payload.id !== "number" ||
      typeof payload.name !== "string" ||
      calls.some((c) => c.id === payload.id)
    ) {
      return calls;
    }
    return [
      ...calls,
      {
        id: payload.id,
        name: payload.name,
        agent: payload.agent ?? "chat",
        args: payload.args ?? "",
        status: "running",
      },
    ];
  }
  if (type === "tool_end") {
    return calls.map((c) =>
      c.id === payload.id
        ? {
            ...c,
            status: payload.status ?? "ok",
            result: payload.result ?? null,
          }
        : c,
    );
  }
  return calls;
}

// the calls to keep with a reply: the server's complete list when the reply
// carried one, else the ones that streamed in while it ran
export function finalToolCalls(
  fromServer: SensAIToolCall[] | undefined,
  streamed: SensAIToolCall[],
): SensAIToolCall[] {
  return Array.isArray(fromServer) ? fromServer : streamed;
}

// the line that opens or closes a reply's list of calls: how many there were,
// and how many did not go through
export function toolCallsTitle(calls: SensAIToolCall[] | undefined): string {
  const list = calls ?? [];
  const parts = [`${list.length} tool call${list.length === 1 ? "" : "s"}`];
  const rejected = list.filter((c) => c.status === "rejected").length;
  const failed = list.filter((c) => c.status === "failed").length;
  if (rejected > 0) parts.push(`${rejected} rejected`);
  if (failed > 0) parts.push(`${failed} failed`);
  return parts.join(", ");
}

// the color of the dot before a call: it pulses while the call runs, and a call
// that was turned away or never returned stands out from the ones that went through
export function toolDotClass(status: string): string {
  switch (status) {
    case "ok":
      return "bg-success-500";
    case "rejected":
      return "bg-warning-500";
    case "failed":
      return "bg-danger-500";
    default:
      return "bg-accent-500 animate-pulse";
  }
}

// the tooltip of a call's row: the whole call, and what it returned or why it was
// turned away, since the row itself cuts each to one line
export function toolCallTooltip(call: SensAIToolCall): string {
  const lines = [`${call.name} ${call.args}`.trim()];
  if (call.result) lines.push(`${call.status === "rejected" ? "Rejected" : "Returned"}: ${call.result}`);
  return lines.join("\n");
}

// what the assistant's reply says: the final message if it sent one, else
// whatever had streamed in by then
export function resultContent(
  message: unknown,
  streamingContent: string,
): string {
  return typeof message === "string"
    ? message || streamingContent || "(no response)"
    : streamingContent || "(no response)";
}

// the tooltip on a message's header row: which model wrote a reply, when the
// server said (not for an older saved message, an error, an undo, or a reply
// the server wrote itself), then what a click does if the message can collapse.
// both are on the row's own button, not on the name inside it, so the model
// does not depend on the browser giving a name inside a button a tooltip that
// beats the button's
export function headerTooltip(
  model: string | null | undefined,
  single: boolean,
  open: boolean,
): string {
  const lines: string[] = [];
  if (model) lines.push(`Response from ${model}`);
  if (!single) lines.push(open ? "Collapse" : "Expand");
  return lines.join("\n");
}

// how many characters of the backlog to reveal on each tick: a few at a
// time, growing with the backlog (a thirtieth of it per tick) so a large
// burst still drains in a second or two
export function revealStep(queueLength: number): number {
  return Math.max(1, Math.ceil(queueLength / 30));
}

// the earlier messages a request carries as context: the last twenty before
// the message just sent, role and text only
export function chatHistory(
  messages: SensAIMessage[],
): Array<{ role: SensAIMessage["role"]; content: string }> {
  return messages
    .slice(0, -1) // exclude the just-pushed user message
    .slice(-HISTORY_LENGTH)
    .map((m) => ({ role: m.role, content: m.content }));
}

export function chatRequestBody(
  message: string,
  messages: SensAIMessage[],
  currentPlotConfigJson: string | null,
  manifest: ColumnManifest | null,
  versus: VersusState | null = null,
): object {
  return {
    message,
    message_history: chatHistory(messages),
    // the open trial's signals, so the agent can check the names it uses (empty
    // away from a trial, where there is nothing to check them against)
    all_columns: manifest?.all ?? [],
    rotatable_vectors: manifest?.rotatable_vectors ?? [],
    available_quats: manifest?.available_quats ?? [],
    current_plot_config_json: currentPlotConfigJson,
    // versus mode as the trial viewer has it, so the agent can change it (null
    // away from a trial, where there is nothing to change)
    versus,
  };
}

// the saved chat history, with a timestamp filled in for any message that has
// none; null when nothing is saved or what is saved cannot be read
export function loadMessages(): SensAIMessage[] | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored) as SensAIMessage[];
      return parsed.map((m) => ({ ...m, ts: m.ts ?? Date.now() }));
    }
  } catch {
    /* ignore */
  }
  return null;
}

// "Chat N", one more than the largest number in use, so a new chat never takes
// the name of one that is open
export function defaultTabTitle(tabs: SensAITab[]): string {
  const used = tabs.map((t) => Number(/^Chat (\d+)$/.exec(t.title)?.[1] ?? 0));
  return `Chat ${Math.max(0, ...used) + 1}`;
}

export function blankTab(tabs: SensAITab[]): SensAITab {
  return {
    id: newTabId(),
    title: defaultTabTitle(tabs),
    messages: [],
    autoTitled: true,
  };
}

// the start of a message as a tab title: one line, cut with an ellipsis
export function titleFromMessage(message: string): string {
  const flat = message.replace(/\s+/g, " ").trim();
  return flat.length > TITLE_LENGTH
    ? `${flat.slice(0, TITLE_LENGTH - 1).trimEnd()}\u2026`
    : flat;
}

// the saved chats and which one was open, with a timestamp filled in for any
// message that has none. the history from before tabs becomes the first chat,
// and a first visit gets one empty chat, so there is always one to type in
export function loadSensAITabs(): { tabs: SensAITab[]; activeId: string } {
  const { tabs, activeId } = loadTabsFromStorage<SensAITab>(
    TABS_KEY,
    ACTIVE_TAB_KEY,
    () => {
      const tab = blankTab([]);
      tab.messages = loadMessages() ?? [];
      return { tabs: [tab], activeId: tab.id };
    },
  );
  return {
    tabs: tabs.map((t) => ({
      ...t,
      title: typeof t.title === "string" ? t.title : "Chat",
      messages: (Array.isArray(t.messages) ? t.messages : []).map((m) => ({
        ...m,
        ts: m.ts ?? Date.now(),
      })),
    })),
    activeId,
  };
}

// the old single history is dropped once the chats are saved, so it cannot
// come back as a second copy if the saved chats are ever lost
export function saveSensAITabs(tabs: SensAITab[], activeId: string): void {
  persistTabsToStorage(TABS_KEY, ACTIVE_TAB_KEY, tabs, activeId);
  try {
    if (localStorage.getItem(TABS_KEY) !== null) localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

// a yes-or-no choice kept in storage as "1" or "0": false when nothing is saved
// or storage cannot be read, and a failed write is ignored
function loadFlag(key: string): boolean {
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function saveFlag(key: string, value: boolean): void {
  try {
    localStorage.setItem(key, value ? "1" : "0");
  } catch {
    /* ignore */
  }
}

// whether the window was pinned open last time, so the choice survives going
// to another page; unpinned when nothing is saved or storage cannot be read
export function loadPinned(): boolean {
  return loadFlag(PINNED_KEY);
}

export function savePinned(pinned: boolean): void {
  saveFlag(PINNED_KEY, pinned);
}

// whether the window was open last time, so it is as it was left when a page is
// loaded or another page is opened; closed when nothing is saved or storage
// cannot be read
export function loadOpen(): boolean {
  return loadFlag(OPEN_KEY);
}

export function saveOpen(open: boolean): void {
  saveFlag(OPEN_KEY, open);
}

// the chat history file: the export time and each message with its time,
// sender, text and, when it has them, its error flag, route, model, plot
// update and tool calls
export function historyExport(messages: SensAIMessage[], now: Date): object {
  return {
    exported_at: now.toISOString(),
    messages: messages.map((m) => {
      const entry: Record<string, unknown> = {
        timestamp: new Date(m.ts).toISOString(),
        sender: m.role === "user" ? "user" : "sensai",
        message: m.content,
      };
      if (m.error) entry["error"] = true;
      if (m.routed_to) entry["routed_to"] = m.routed_to;
      if (m.model) entry["model"] = m.model;
      if (m.plot_config_update !== undefined)
        entry["plot_config_update"] = m.plot_config_update;
      if (m.tool_calls?.length) entry["tool_calls"] = m.tool_calls;
      return entry;
    }),
  };
}

// every chat in one file: the export time and, for each chat, its title and
// its messages as historyExport writes them
export function tabsExport(tabs: SensAITab[], now: Date): object {
  return {
    exported_at: now.toISOString(),
    tabs: tabs.map((t) => ({
      title: t.title,
      messages: (historyExport(t.messages, now) as { messages: object[] }).messages,
    })),
  };
}

export function historyFileName(now: Date): string {
  return `sensai-chat-${now.toISOString().slice(0, 10)}.json`;
}

// the enabled flag in a "mojo-settings-saved" event, when it carries one
export function enabledFromSettings(detail: {
  dojo?: { sensai?: { enabled?: boolean } };
} | null | undefined): boolean | undefined {
  const next = detail?.dojo?.sensai?.enabled;
  return typeof next === "boolean" ? next : undefined;
}

// within thirty pixels of the end counts as scrolled to the bottom
export function isAtBottom(
  scrollHeight: number,
  scrollTop: number,
  clientHeight: number,
): boolean {
  return scrollHeight - scrollTop - clientHeight < 30;
}

// how far to scroll the message list so something's top edge is at the top of
// the list: its distance below the list's top edge, plus how far the list is
// already scrolled. the browser stops at the end of the list, so something with
// little below it ends up lower than the top
export function promptScrollTop(listTop: number, listScrollTop: number, promptTop: number): number {
  return Math.max(0, promptTop - listTop + listScrollTop);
}

// a question and the answer to it. a chat is shown as one of these after another
// so that a question can stick to the top of the list while its own answer is
// read and be pushed off by the next question, which `position: sticky` does
// within the box that holds the question and its answer. `start` is the place
// of its first message in the chat, and `last` marks the final one, which also
// holds what is shown while a request runs
export interface Exchange {
  start: number;
  messages: SensAIMessage[];
  last: boolean;
}

// each message from the user begins an exchange. a reply with no question before
// it (a chat that begins with one) is an exchange of its own
export function groupExchanges(messages: SensAIMessage[]): Exchange[] {
  const groups: Exchange[] = [];
  messages.forEach((message, i) => {
    const current = groups[groups.length - 1];
    if (message.role === "user" || !current) {
      groups.push({ start: i, messages: [message], last: false });
    } else {
      current.messages.push(message);
    }
  });
  const final = groups[groups.length - 1];
  if (final) final.last = true;
  return groups;
}

// how long a bubble takes to open or close, as long as its transition (the
// class that sets it is `duration-300`), plus a little to be sure it is over
export const BUBBLE_MS = 300;
export const BUBBLE_SETTLE_MS = BUBBLE_MS + 50;

const COLLAPSED_HEIGHT = "3.5rem";
const FADE =
  "-webkit-mask-image: linear-gradient(to bottom, black 65%, transparent 100%); mask-image: linear-gradient(to bottom, black 65%, transparent 100%)";

// the style of a bubble that can open and close. a single line has none. closed
// it is a short, faded height; open it has no limit. while it is changing it is
// the height of the whole bubble, in pixels, on the open side too: a change to
// or from `none` cannot animate, and one to or from a huge height only seems to
// start moving at the very end, which is why opening used to look instant while
// closing took its time. `settled` is whether the change is over
export function bubbleStyle(state: {
  single: boolean;
  open: boolean;
  settled: boolean;
  fullHeight: number;
}): string {
  if (state.single) return "";
  if (!state.open) return `max-height: ${COLLAPSED_HEIGHT}; ${FADE}`;
  if (state.settled || state.fullHeight <= 0) return "max-height: none";
  return `max-height: ${state.fullHeight}px`;
}

// the height of a bubble's whole content, borders included, even while it is
// clipped to less
export function fullBubbleHeight(el: {
  scrollHeight: number;
  offsetHeight: number;
  clientHeight: number;
}): number {
  return el.scrollHeight + (el.offsetHeight - el.clientHeight);
}

// the composer grows with its text up to six lines, then scrolls
export function composerSize(
  scrollHeight: number,
  lineHeightText: string,
): { height: string; overflowY: "hidden" | "auto" } {
  const lineHeight = parseInt(lineHeightText, 10) || 20;
  const maxHeight = lineHeight * 6;
  return scrollHeight > maxHeight
    ? { height: maxHeight + "px", overflowY: "auto" }
    : { height: scrollHeight + "px", overflowY: "hidden" };
}

// the position of the latest message the user sent, -1 if they have sent none
export function lastUserIndex(messages: SensAIMessage[]): number {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i]!.role === "user") return i;
  }
  return -1;
}

// a message of two lines or fewer is shown whole; a longer assistant message
// starts open, and so does a longer user message when it is the latest one
// they sent (the one the reply is about), while earlier ones start collapsed
export function messageLayout(
  role: string,
  scrollHeight: number,
  lineHeightText: string,
  isLastUser = false,
): { single: boolean; open: boolean } {
  const lh = parseFloat(lineHeightText) || 22;
  const single = scrollHeight <= Math.ceil(lh * 2.5);
  return { single, open: single || role !== "user" || isLastUser };
}
