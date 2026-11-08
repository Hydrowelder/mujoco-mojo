import type { DojoStore } from "./models";
import type { AlpineMagics } from "./types/global";
import {
  EditorView,
  EditorState,
  syntaxHighlighting,
  classHighlighter,
} from "./lib/codemirror";
import { codeLanguage } from "./lib/code-language";
import { addCopyButton } from "./lib/code-block";
import { renderMath } from "./lib/math";
import { renderMarkdown } from "./lib/markdown";
import {
  MAX_TABS,
  blankTab,
  bubbleStyle,
  chatRequestBody,
  composerSize,
  createSseParser,
  enabledFromSettings,
  fullBubbleHeight,
  groupExchanges,
  headerTooltip,
  historyFileName,
  isAtBottom,
  lastUserIndex,
  loadOpen,
  loadPinned,
  loadSensAITabs,
  messageLayout,
  promptScrollTop,
  rememberedScroll,
  resultContent,
  revealStep,
  saveOpen,
  saveSensAITabs,
  savePinned,
  tabsExport,
  titleFromMessage,
  BUBBLE_SETTLE_MS,
  SCROLL_HOLD_MS,
  type Exchange,
  type SensAIMessage,
  type SensAITab,
  type SseEvent,
} from "./lib/sensai";
import {
  DEFAULT_PLACEHOLDER,
  HOLD_MS,
  advance,
  pickNext,
  startTyper,
  visibleText,
  type Typer,
} from "./lib/sensai-placeholder";
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
    // the input's placeholder, which types out examples of what to ask while the
    // window is open (see lib/sensai-placeholder.ts)
    placeholder: DEFAULT_PLACEHOLDER,
    _typer: null as Typer | null,
    _typerTimer: null as number | null,
    // ends the hold that keeps the list at a chat's place while its contents settle, when there is one
    _holdStop: null as (() => void) | null,
    // the place it holds the list at
    _holdPlace: null as number | null,
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

    // the open chat as questions with their answers, which is how the list shows it
    get exchanges(): Exchange[] {
      return groupExchanges(this.messages);
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

      // the window is as it was left, unless SensAI is turned off, when it is
      // neither shown nor animated (the saved choice is kept for when it is on)
      if (this.enabled !== false && loadOpen()) {
        this.open = true;
        this._showWindow();
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
      saveOpen(this.open);
      if (this.open) this._showWindow();
      else {
        this._stopHold();
        this._stopPlaceholder();
      }
    },

    close() {
      this.open = false;
      saveOpen(false);
      this._stopHold();
      this._stopPlaceholder();
    },

    // what happens when the window comes up, from a click or from being left open
    _showWindow() {
      this.hasNewResponse = false;
      this._scrollToLastPrompt();
      this._startPlaceholder();
      // dispatch after next tick so the panel is back in layout flow and scrollHeights are valid
      void (this as unknown as AlpineMagics).$nextTick(() => {
        window.dispatchEvent(new CustomEvent("sensai-remeasure"));
      });
    },

    // called by Alpine when the component is removed from the page
    destroy() {
      this._stopHold();
      this._stopPlaceholder();
    },

    // ---- the placeholder ----

    // the default text shows first and stays a moment, then the examples take
    // turns. nothing runs while the window is closed, and someone who asks the
    // browser for less motion gets the default text and no animation
    _startPlaceholder() {
      if (this._typerTimer !== null) return;
      if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
      this._typer = startTyper();
      this.placeholder = visibleText(this._typer);
      this._schedulePlaceholderStep(HOLD_MS);
    },

    _schedulePlaceholderStep(delay: number) {
      this._typerTimer = window.setTimeout(() => {
        if (!this._typer) return;
        const next = advance(this._typer, (previous) => pickNext(previous));
        this._typer = next.typer;
        this.placeholder = visibleText(next.typer);
        this._schedulePlaceholderStep(next.delay);
      }, delay);
    },

    _stopPlaceholder() {
      if (this._typerTimer !== null) window.clearTimeout(this._typerTimer);
      this._typerTimer = null;
      this._typer = null;
      this.placeholder = DEFAULT_PLACEHOLDER;
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
      if (from) {
        from.draft = this.input;
        // where its list is now, which it gets back when it is shown again. every
        // chat is shown in the same list, so nothing else would keep it
        const list = (this as unknown as AlpineMagics).$refs["messages"];
        if (list) from.scrollTop = this._holdPlace ?? list.scrollTop;
      }
      this.renamingId = null;
      this.activeId = id;
      this._showActiveTab();
    },

    // what changes when another chat comes to the front: its unsent text goes
    // in the box, it is no longer unread, its messages are laid out afresh, and
    // the list is put back where that chat left it. it does not scroll to
    // anything of its own accord: a chat is where it was left
    _showActiveTab() {
      // the old chat's hold goes at once: its contents are about to be replaced, and it
      // would put the list back at the old place against the new ones
      this._stopHold();
      const tab = this.activeTab;
      this.input = tab?.draft ?? "";
      if (tab) tab.unread = false;
      this.atBottom = true;
      this.hasNewResponse = false;
      this._saveTabs();
      const magics = this as unknown as AlpineMagics;
      void magics.$nextTick(() => {
        window.dispatchEvent(new CustomEvent("sensai-remeasure"));
        // after the messages have laid themselves out, which changes the height of the list
        void magics.$nextTick(() => this._restoreScroll());
      });
    },

    // puts the list where the open chat left it (the top for one that was never
    // scrolled), and keeps it there while the chat's contents take their final height
    _restoreScroll() {
      const list = (this as unknown as AlpineMagics).$refs["messages"];
      if (!list) return;
      const place = rememberedScroll(this.activeTab);
      this._putListAt(list, place);
      this._holdListAt(list, place);
    },

    // moves the list to `place` and says whether that is the bottom, which the scroll
    // button goes by
    _putListAt(list: HTMLElement, place: number) {
      list.scrollTop = place;
      this.atBottom = isAtBottom(list.scrollHeight, list.scrollTop, list.clientHeight);
    },

    // a chat's contents are made when it is shown and go on taking their final height for a
    // moment (code editors correct their estimate of themselves a frame later, math is
    // typeset once KaTeX has loaded), and every change above `place` moves what it points
    // at, so the list is put back at `place` whenever the contents change size. it is let
    // go when the user takes hold of it, when something else scrolls it, or after
    // SCROLL_HOLD_MS, whichever is first
    _holdListAt(list: HTMLElement, place: number) {
      if (typeof ResizeObserver === "undefined") return;
      const observer = new ResizeObserver(() => {
        if (this._holdStop !== null && list.scrollTop !== place) this._putListAt(list, place);
      });
      for (const child of Array.from(list.children)) observer.observe(child);
      this._holdPlace = place;
      const release = () => this._stopHold();
      // the ways a person scrolls: the wheel, a finger, the scroll bar, and the keys (which reach the
      // list from whatever inside it has focus)
      const userEvents = ["wheel", "touchstart", "pointerdown", "keydown"] as const;
      for (const name of userEvents) list.addEventListener(name, release, { passive: true });
      const timer = window.setTimeout(release, SCROLL_HOLD_MS);
      this._holdStop = () => {
        observer.disconnect();
        for (const name of userEvents) list.removeEventListener(name, release);
        window.clearTimeout(timer);
        this._holdStop = null;
        this._holdPlace = null;
      };
    },

    _stopHold() {
      this._holdStop?.();
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
      this._scrollToLastPrompt();
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
      if (tab.id === this.activeId) this._scrollToLastPrompt();

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
      // a chat that has just been shown is held at its own place, which this must not undo: a different
      // draft in the box than the chat before had is what brings it here
      if (wasAtBottom && msgEl && this._holdStop === null) {
        msgEl.scrollTop = msgEl.scrollHeight;
      }
    },

    onScroll(el: HTMLElement) {
      this.atBottom = isAtBottom(el.scrollHeight, el.scrollTop, el.clientHeight);
      if (this.atBottom) this.hasNewResponse = false;
    },

    scrollToBottom() {
      this._stopHold();
      const el = (this as unknown as AlpineMagics).$refs["messages"];
      if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      this.atBottom = true;
      this.hasNewResponse = false;
    },

    _saveTabs() {
      saveSensAITabs(this.tabs, this.activeId);
    },

    // where the window scrolls by itself (a message sent, a reply arriving, a
    // chat shown): the last prompt goes to the top of the list with the reply
    // below it, so an answer is read from its start. the browser stops at the
    // end of the list, so a short reply leaves the prompt lower down; the
    // button still goes to the very end (scrollToBottom)
    _scrollToLastPrompt() {
      void (this as unknown as AlpineMagics).$nextTick(() => {
        const el = (this as unknown as AlpineMagics).$refs["messages"];
        if (!el) return;
        const prompts = el.querySelectorAll<HTMLElement>('[data-role="user"]');
        this._scrollListTo(el, prompts[prompts.length - 1]);
      });
    },

    // what clicking a question does besides opening it: takes the list up to where
    // its exchange begins, which is the point when it is pinned at the top and the
    // list is far down its answer. a click that ends a selection of its text is
    // left alone
    showExchange(from: HTMLElement) {
      const list = (this as unknown as AlpineMagics).$refs["messages"];
      const exchange = from.closest<HTMLElement>(".sensai-exchange");
      if (!list || !exchange || window.getSelection()?.toString()) return;
      this._scrollListTo(list, exchange);
    },

    // scrolls the list so `prompt` is at its top (or to the end of the list when
    // there is none). a question pinned at the top is not where it began, so the
    // top of the exchange it is in is used when there is one
    _scrollListTo(list: HTMLElement, prompt: HTMLElement | undefined) {
      this._stopHold();
      const exchange = prompt?.closest<HTMLElement>(".sensai-exchange") ?? null;
      const where = exchange ?? prompt;
      // the list has no padding of its own above (a question that sticks to the top
      // has to be flush with it), so the space above a question is its exchange's.
      // the question is put at the very top, which is also where it sticks, so it
      // does not move when it goes from scrolling to stuck
      const lead = exchange ? parseFloat(getComputedStyle(exchange).paddingTop) || 0 : 0;
      const top = where
        ? promptScrollTop(list.getBoundingClientRect().top, list.scrollTop, where.getBoundingClientRect().top) + lead
        : list.scrollHeight;
      list.scrollTo({ top, behavior: "smooth" });
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
        if (this.open && this.atBottom) this._scrollToLastPrompt();
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
      const language = codeLanguage(lang);
      if (language) extensions.unshift(language);
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
window.initSensAIMath = renderMath;

// ---------------------------------------------------------------------------
// per-message collapse/expand state
// ---------------------------------------------------------------------------

interface SensAIMsgState {
  open: boolean;
  single: boolean;
  settled: boolean;
  fullHeight: number;
  _role: string;
}

// how long the copy button shows its check mark
const COPIED_MS = 1500;

function sensaiMsgData(role: string, isLastUser = false) {
  return {
    open: role !== "user" || isLastUser,
    single: false,
    // opening and closing animate between pixel heights (see bubbleStyle in
    // lib/sensai.ts): the height the bubble opens to, and whether the change is over
    settled: true,
    fullHeight: 0,
    copied: false,
    _role: role,
    get bubbleStyle(): string {
      return bubbleStyle({
        single: this.single,
        open: this.open,
        settled: this.settled,
        fullHeight: this.fullHeight,
      });
    },
    // the header's button: opens a closed bubble and closes an open one
    toggle() {
      if (!this.single) this.setOpen(!this.open);
    },
    // clicking a closed bubble opens it; an open one is left as it is (setOpen
    // does nothing when the bubble is already as asked)
    expand() {
      if (!this.single) this.setOpen(true);
    },
    // opens or closes the bubble, animating the change
    setOpen(next: boolean) {
      const self = this as unknown as SensAIMsgState & AlpineMagics;
      if (next === self.open) return;
      const bubble = self.$refs["bubble"];
      if (next) {
        self.fullHeight = bubble ? fullBubbleHeight(bubble) : 0;
        self.settled = false;
        self.open = true;
        // once it has opened it has no height limit, so what it holds can grow
        window.setTimeout(() => {
          if (self.open) self.settled = true;
        }, BUBBLE_SETTLE_MS);
      } else {
        // an open bubble has no height limit, which cannot be animated from: give
        // it its height in pixels and let the browser see that, then close it
        if (bubble && self.settled) {
          bubble.style.maxHeight = `${fullBubbleHeight(bubble)}px`;
          void bubble.offsetHeight;
        }
        self.settled = false;
        self.open = false;
      }
    },
    // what is done to a message once it is on the page: its code blocks become
    // editors, it is measured, and its math is typeset (which waits for KaTeX the
    // first time), after which it is measured again since math is taller than its
    // source
    hydrate(isLastUser = false) {
      const self = this as unknown as SensAIMsgState & AlpineMagics & { measure(last: boolean): void };
      initSensAICodeBlocks(self.$el);
      self.measure(isLastUser);
      void renderMath(self.$el).then((typeset) => {
        if (typeset) self.measure(isLastUser);
      });
    },
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
      self.settled = true;
    },
  };
}

window.sensaiMsgData = sensaiMsgData;
