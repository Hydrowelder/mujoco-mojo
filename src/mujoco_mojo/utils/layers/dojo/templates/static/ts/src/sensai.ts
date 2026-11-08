import type { DojoStore } from "./models";
import type { AlpineMagics } from "./types/global";
import {
  EditorView,
  EditorState,
  json,
  syntaxHighlighting,
  classHighlighter,
} from "./lib/codemirror";
import { addCopyButton } from "./lib/code-block";
import { renderMarkdown } from "./lib/markdown";
import {
  MAX_TABS,
  blankTab,
  chatRequestBody,
  composerSize,
  createSseParser,
  enabledFromSettings,
  headerTooltip,
  historyFileName,
  isAtBottom,
  lastUserIndex,
  loadPinned,
  loadSensAITabs,
  messageLayout,
  resultContent,
  revealStep,
  saveSensAITabs,
  savePinned,
  tabsExport,
  titleFromMessage,
  type SensAIMessage,
  type SensAITab,
  type SseEvent,
} from "./lib/sensai";
import { pickNextActiveOnClose } from "./lib/tab-session";

interface SensAIConfig {
  enabled: boolean;
}

function sensai() {
  return {
    open: false,
    // pinned keeps the window open when the user clicks elsewhere or presses
    // Escape; only the SensAI button closes it then
    pinned: false,
    // each chat is a tab with its own messages. requests run one at a time, in
    // the order they were sent: a plot edit comes back as the whole plot built
    // from the config the request started with, so two running together would
    // overwrite each other's changes
    tabs: [] as SensAITab[],
    activeId: "",
    maxTabs: MAX_TABS,
    renamingId: null as string | null,
    // the chat whose request is running, and the chats waiting their turn
    runningId: null as string | null,
    queue: [] as string[],
    streaming: false,
    streamingContent: "",
    thinkingLabel: null as string | null,
    enabled: null as boolean | null,
    input: "",
    atBottom: true,
    hasNewResponse: false,
    _revealQueue: "",
    _revealTimer: null as number | null,
    _abort: null as AbortController | null,
    _draining: null as Promise<void> | null,
    headerTooltip,

    get activeTab(): SensAITab | undefined {
      return this.tabs.find((t) => t.id === this.activeId);
    },

    // the open chat's messages, which is what the message list shows
    get messages(): SensAIMessage[] {
      return this.activeTab?.messages ?? [];
    },

    // whether message `i` is the latest one the user sent, which starts open
    isLastUserMessage(i: number): boolean {
      return lastUserIndex(this.messages) === i;
    },

    isRunning(id: string): boolean {
      return this.runningId === id;
    },

    isQueued(id: string): boolean {
      return this.queue.includes(id);
    },

    // a chat with a request running or waiting takes no second message
    isBusy(id: string): boolean {
      return this.isRunning(id) || this.isQueued(id);
    },

    async init() {
      const saved = loadSensAITabs();
      this.tabs = saved.tabs;
      this.activeId = saved.activeId;
      this.input = this.activeTab?.draft ?? "";
      // writes the chats back, which also retires the history from before tabs
      this._saveTabs();
      this.pinned = loadPinned();
      (this as unknown as AlpineMagics).$watch("input", () => {
        const el = (this as unknown as AlpineMagics).$refs["inputArea"];
        if (el) this.resize(el);
      });
      try {
        const resp = await fetch("/sensai/config");
        if (resp.ok) {
          const cfg = (await resp.json()) as SensAIConfig;
          this.enabled = cfg.enabled;
        }
      } catch {
        this.enabled = false;
      }

      // keeps this FAB in sync with dojo.sensai.enabled if the user flips it
      // in the settings panel without reloading the page - see settings-panel.ts's
      // _applySettingsWrite for the dispatch side.
      window.addEventListener("mojo-settings-saved", (e) => {
        const detail = (e as CustomEvent<{ dojo?: { sensai?: { enabled?: boolean } } }>).detail;
        const next = enabledFromSettings(detail);
        if (next !== undefined) this.enabled = next;
      });
    },

    toggle() {
      this.open = !this.open;
      if (this.open) {
        this.hasNewResponse = false;
        this._scrollToBottom();
        // dispatch after next tick so the panel is back in layout flow and scrollHeights are valid
        void (this as unknown as AlpineMagics).$nextTick(() => {
          window.dispatchEvent(new CustomEvent("sensai-remeasure"));
        });
      }
    },

    close() {
      this.open = false;
    },

    // what a click elsewhere on the page, or Escape, does: close the window,
    // unless it is pinned
    dismiss() {
      if (!this.pinned) this.close();
    },

    togglePin() {
      this.pinned = !this.pinned;
      savePinned(this.pinned);
    },

    // ---- chats (tabs) ----

    newTab() {
      if (this.tabs.length >= MAX_TABS) return;
      const tab = blankTab(this.tabs);
      this.tabs.push(tab);
      this.switchTab(tab.id);
    },

    switchTab(id: string) {
      if (id === this.activeId || !this.tabs.some((t) => t.id === id)) return;
      const from = this.activeTab;
      if (from) from.draft = this.input;
      this.renamingId = null;
      this.activeId = id;
      this._showActiveTab();
    },

    // what changes when another chat comes to the front: its unsent text goes
    // in the box, it is no longer unread, and its messages are laid out afresh
    _showActiveTab() {
      const tab = this.activeTab;
      this.input = tab?.draft ?? "";
      if (tab) tab.unread = false;
      this.atBottom = true;
      this.hasNewResponse = false;
      this._saveTabs();
      this._scrollToBottom();
      void (this as unknown as AlpineMagics).$nextTick(() => {
        window.dispatchEvent(new CustomEvent("sensai-remeasure"));
      });
    },

    // closes a chat, stopping its request if one is running or waiting. the
    // last one left is replaced by an empty chat
    closeTab(id: string) {
      const idx = this.tabs.findIndex((t) => t.id === id);
      if (idx === -1) return;
      this._cancel(id);
      const next = pickNextActiveOnClose(this.tabs, idx, this.activeId, () => blankTab([]));
      this.tabs = next.tabs;
      if (next.activeChanged) {
        this.renamingId = null;
        this.activeId = next.nextActiveId;
        this._showActiveTab();
      } else {
        this._saveTabs();
      }
    },

    startRename(id: string) {
      this.renamingId = id;
      void (this as unknown as AlpineMagics).$nextTick(() => {
        const el = (this as unknown as AlpineMagics).$refs["tabNameInput"] as
          | HTMLInputElement
          | undefined;
        el?.focus();
        el?.select();
      });
    },

    // an empty name keeps the old one; a typed one is the user's, so the
    // chat's first message no longer renames it
    renameTab(id: string, value: string) {
      this.renamingId = null;
      const tab = this.tabs.find((t) => t.id === id);
      const title = value.trim();
      if (!tab || !title) return;
      tab.title = title;
      tab.autoTitled = false;
      this._saveTabs();
    },

    // takes a chat's request off the queue, or stops it if it is the one running
    _cancel(id: string) {
      this.queue = this.queue.filter((q) => q !== id);
      if (this.runningId === id) this._abort?.abort();
    },

    // ---- sending ----

    // adds the message to the open chat and puts the chat in line for its
    // reply. the returned promise settles once every request in line, this
    // one included, has finished
    async send() {
      const tab = this.activeTab;
      const message = this.input.trim();
      if (!tab || !message || this.isBusy(tab.id)) return;

      tab.messages.push({ role: "user", content: message, ts: Date.now() });
      if (tab.autoTitled !== false && tab.messages.length === 1) {
        tab.title = titleFromMessage(message);
      }
      tab.draft = "";
      this.input = "";
      this._saveTabs();
      this.queue.push(tab.id);
      const finished = this._drain();
      await (this as unknown as AlpineMagics).$nextTick();
      this._scrollToBottom();
      await finished;
    },

    // runs the waiting requests one after another. a call while it is already
    // running joins that run instead of starting a second one
    _drain(): Promise<void> {
      if (this._draining) return this._draining;
      const run = (async () => {
        try {
          while (this.queue.length > 0) {
            const id = this.queue.shift()!;
            const tab = this.tabs.find((t) => t.id === id);
            if (tab) await this._run(tab);
          }
        } finally {
          this.runningId = null;
        }
      })();
      this._draining = run.finally(() => {
        this._draining = null;
      });
      return this._draining;
    },

    // sends one chat's latest message and puts what comes back in that chat,
    // whichever chat is open by then
    async _run(tab: SensAITab) {
      this.runningId = tab.id;
      this.streaming = false;
      this.streamingContent = "";
      this.thinkingLabel = null;
      const controller = new AbortController();
      this._abort = controller;
      if (tab.id === this.activeId) this._scrollToBottom();

      try {
        const pending = tab.messages[tab.messages.length - 1];
        if (!pending || pending.role !== "user") return;
        // read now, not when the message was sent: the request ahead of this
        // one may have changed the plot since
        const currentPlotConfigJson = localStorage.getItem("mojo_mosaic_config");

        const response = await fetch("/sensai/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            chatRequestBody(
              pending.content,
              tab.messages,
              currentPlotConfigJson,
              (Alpine.store("dojo") as DojoStore).columnManifest,
            ),
          ),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          let detail = "Request failed.";
          try {
            const err = (await response.json()) as { detail?: string };
            if (err.detail) detail = err.detail;
          } catch { /* ignore */ }
          tab.messages.push({ role: "assistant", content: detail, error: true, ts: Date.now() });
          return;
        }

        await this._streamSse(response.body, tab);
      } catch {
        // closing or clearing the chat stops its request on purpose, which is
        // not an error to report
        if (!controller.signal.aborted) {
          tab.messages.push({
            role: "assistant",
            content: "Network error. Please try again.",
            error: true,
            ts: Date.now(),
          });
        }
      } finally {
        this._abort = null;
        this._saveTabs();
        this.streaming = false;
        this.streamingContent = "";
        this.thinkingLabel = null;
        this._flushReveal();
        window.dispatchEvent(new CustomEvent("sensai-remeasure"));
        if (!controller.signal.aborted) this._noteReply(tab);
      }
    },

    // marks a reply the user has not seen: a chat that was not open gets a dot,
    // and the button shows one when the window is closed or scrolled up
    _noteReply(tab: SensAITab) {
      const elsewhere = tab.id !== this.activeId;
      if (elsewhere) tab.unread = true;
      if (!this.open || (!elsewhere && !this.atBottom)) this.hasNewResponse = true;
      if (elsewhere) this._saveTabs();
    },

    // applies one event from the server's stream to the chat that sent the
    // request; a throw while applying it is ignored, like a malformed line
    _handleSseEvent({ type: eventType, payload }: SseEvent, tab: SensAITab) {
      try {
        if (eventType === "tool_call" && typeof payload.label === "string") {
          this.thinkingLabel = payload.label;
        } else if (eventType === "text_delta" && typeof payload.delta === "string") {
          if (!this.streaming) {
            this.streaming = true;
            this.thinkingLabel = null;
          }
          this._revealQueue += payload.delta;
          this._startReveal();
        } else if (eventType === "result") {
          this._flushReveal();
          const content = resultContent(payload.message, this.streamingContent);
          tab.messages.push({
            role: "assistant",
            content,
            plot_config_update: payload.plot_config_update ?? null,
            routed_to: payload.routed_to,
            model: payload.model ?? undefined,
            ts: Date.now(),
          });
          if (payload.plot_config_update) {
            // saved here as well as by the trial viewer, which does so only after
            // it has fetched any new signal's data: the next request in line reads
            // the plot from storage and must not start from the one before this
            try {
              localStorage.setItem(
                "mojo_mosaic_config",
                JSON.stringify(payload.plot_config_update),
              );
            } catch { /* ignore */ }
            window.dispatchEvent(new CustomEvent("mojo-sensai-plot-config", {
              detail: payload.plot_config_update,
            }));
          }
          if (payload.routed_to === "undo") {
            window.dispatchEvent(new CustomEvent("mojo-sensai-undo"));
          }
          this.thinkingLabel = null;
          this.streaming = false;
          this.streamingContent = "";
        } else if (eventType === "error") {
          this._flushReveal();
          tab.messages.push({
            role: "assistant",
            content: payload.detail ?? "An error occurred.",
            error: true,
            ts: Date.now(),
          });
          this.thinkingLabel = null;
          this.streaming = false;
          this.streamingContent = "";
        }
      } catch { /* ignore */ }
    },

    async _streamSse(body: ReadableStream<Uint8Array>, tab: SensAITab) {
      const reader = body.getReader();
      const decoder = new TextDecoder();
      const parser = createSseParser();

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          for (const event of parser.feed(decoder.decode(value, { stream: true }))) {
            this._handleSseEvent(event, tab);
          }
        }
        for (const event of parser.end()) this._handleSseEvent(event, tab);
      } finally {
        reader.releaseLock();
      }
    },

    resize(el: HTMLElement) {
      const msgEl = (this as unknown as AlpineMagics).$refs["messages"];
      const wasAtBottom = this.atBottom;
      el.style.height = "auto";
      el.style.overflowY = "hidden";
      const size = composerSize(el.scrollHeight, getComputedStyle(el).lineHeight);
      el.style.height = size.height;
      el.style.overflowY = size.overflowY;
      if (wasAtBottom && msgEl) {
        msgEl.scrollTop = msgEl.scrollHeight;
      }
    },

    onScroll(el: HTMLElement) {
      this.atBottom = isAtBottom(el.scrollHeight, el.scrollTop, el.clientHeight);
      if (this.atBottom) this.hasNewResponse = false;
    },

    scrollToBottom() {
      const el = (this as unknown as AlpineMagics).$refs["messages"];
      if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      this.atBottom = true;
      this.hasNewResponse = false;
    },

    _saveTabs() {
      saveSensAITabs(this.tabs, this.activeId);
    },

    _scrollToBottom() {
      void (this as unknown as AlpineMagics).$nextTick(() => {
        const el = (this as unknown as AlpineMagics).$refs["messages"];
        if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      });
    },

    // Reveals streamingContent a few characters at a time on a fixed interval,
    // decoupled from how large each network chunk actually was - the model
    // (especially Gemini) often streams only a couple of large bursts per
    // reply rather than per-token, and dumping each straight into
    // streamingContent looked like it was appearing in big jumps. The step
    // size grows with the backlog so a large burst still drains in a second or
    // two (a thirtieth of what is left every 16 ms) instead of trailing far
    // behind the rest of the stream.
    _startReveal() {
      if (this._revealTimer !== null) return;
      this._revealTimer = window.setInterval(() => {
        if (this._revealQueue.length === 0) {
          window.clearInterval(this._revealTimer!);
          this._revealTimer = null;
          return;
        }
        const step = revealStep(this._revealQueue.length);
        this.streamingContent += this._revealQueue.slice(0, step);
        this._revealQueue = this._revealQueue.slice(step);
        if (this.open && this.atBottom) this._scrollToBottom();
      }, 16);
    },

    _flushReveal() {
      if (this._revealTimer !== null) {
        window.clearInterval(this._revealTimer);
        this._revealTimer = null;
      }
      this._revealQueue = "";
    },
  };
}

window.sensai = sensai;

function downloadSensAIHistory(): void {
  const now = new Date();
  const payload = tabsExport(loadSensAITabs().tabs, now);

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = historyFileName(now);
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  try {
    (Alpine.store("dojo") as { toast?: (m: string, t: string) => void }).toast?.(
      "SensAI chat history downloaded",
      "info",
    );
  } catch { /* store not ready */ }
}

window.downloadSensAIHistory = downloadSensAIHistory;

// ---------------------------------------------------------------------------
// markdown rendering — used by assistant message bubbles
// ---------------------------------------------------------------------------


function initSensAICodeBlocks(container: HTMLElement): void {
  try {
    const blocks = container.querySelectorAll<HTMLElement>(
      ".sensai-cm-block:not([data-cm-init])",
    );
    blocks.forEach(el => {
      el.setAttribute("data-cm-init", "1");
      const code = decodeURIComponent(el.getAttribute("data-code") ?? "");
      const rawLang = el.getAttribute("data-lang");
      const lang = rawLang ? decodeURIComponent(rawLang) : "";
      const extensions = [
        EditorView.editable.of(false),
        EditorState.readOnly.of(true),
        // classes, not colors: _sensai.html colors them with theme tokens, so a block
        // reads in dark mode too and follows the toggle with no reconfiguring here
        syntaxHighlighting(classHighlighter),
      ];
      if (lang === "json") extensions.unshift(json());
      new EditorView({
        state: EditorState.create({ doc: code, extensions }),
        parent: el,
      });
      addCopyButton(el, code, (text) =>
        (Alpine.store("dojo") as DojoStore).copyText(text, "Code copied"),
      );
    });
  } catch { /* no blocks present, or a block's data-code/data-lang malformed */ }
}

window.renderMarkdown = renderMarkdown;
window.initSensAICodeBlocks = initSensAICodeBlocks;

// ---------------------------------------------------------------------------
// per-message collapse/expand state
// ---------------------------------------------------------------------------

interface SensAIMsgState {
  open: boolean;
  single: boolean;
  _role: string;
}

// how long the copy button shows its check mark
const COPIED_MS = 1500;

function sensaiMsgData(role: string, isLastUser = false) {
  return {
    open: role !== "user" || isLastUser,
    single: false,
    copied: false,
    _role: role,
    // copies a message's own text (the markdown of a reply, not its rendering)
    async copy(text: string) {
      const ok = await (Alpine.store("dojo") as DojoStore).copyText(text, "Message copied");
      if (!ok) return;
      this.copied = true;
      setTimeout(() => {
        this.copied = false;
      }, COPIED_MS);
    },
    measure(isLastUser = false) {
      const self = this as unknown as SensAIMsgState & AlpineMagics;
      // assistant messages render into .sensai-md; user messages use a plain <p>
      const content = (
        self.$el.querySelector(".sensai-md") ??
        self.$el.querySelector("p")
      );
      if (!content || content.scrollHeight === 0) return;
      const layout = messageLayout(
        self._role,
        content.scrollHeight,
        getComputedStyle(content).lineHeight,
        isLastUser,
      );
      self.single = layout.single;
      self.open = layout.open;
    },
  };
}

window.sensaiMsgData = sensaiMsgData;
