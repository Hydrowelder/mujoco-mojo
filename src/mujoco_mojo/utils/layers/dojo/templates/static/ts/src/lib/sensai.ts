// sensai chat logic, moved out of sensai.ts so it can be tested without an
// alpine component: reading the server's event stream, what a reply says, the
// request a message sends, the saved history and its export, and the sizing
// rules for the composer and the message bubbles.

import type { ColumnManifest } from "../models";

export interface SensAIMessage {
  role: "user" | "assistant";
  content: string;
  error?: boolean;
  plot_config_update?: object | null;
  routed_to?: string;
  // the model that wrote an assistant reply, when the server said which
  model?: string;
  ts: number;
}

export interface SensAIResultPayload {
  message?: string;
  plot_config_update?: object | null;
  routed_to?: string;
  model?: string | null;
  detail?: string;
  label?: string;
}

export type SensAIEventPayload = SensAIResultPayload & { delta?: string };

export const STORAGE_KEY = "sensai-messages";
export const PINNED_KEY = "sensai-pinned";

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

export function saveMessages(messages: SensAIMessage[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  } catch {
    /* ignore */
  }
}

// whether the window was pinned open last time, so the choice survives going
// to another page; unpinned when nothing is saved or storage cannot be read
export function loadPinned(): boolean {
  try {
    return localStorage.getItem(PINNED_KEY) === "1";
  } catch {
    return false;
  }
}

export function savePinned(pinned: boolean): void {
  try {
    localStorage.setItem(PINNED_KEY, pinned ? "1" : "0");
  } catch {
    /* ignore */
  }
}

// the saved history exactly as stored, for the download
export function storedMessages(): SensAIMessage[] {
  const stored = localStorage.getItem(STORAGE_KEY);
  let messages: SensAIMessage[] = [];
  try {
    if (stored) messages = JSON.parse(stored) as SensAIMessage[];
  } catch {
    /* ignore */
  }
  return messages;
}

// the chat history file: the export time and each message with its time,
// sender, text and, when it has them, its error flag, route, model and plot
// update
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
      return entry;
    }),
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
