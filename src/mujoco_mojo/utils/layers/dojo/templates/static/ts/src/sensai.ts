import type { AlpineMagics } from "./types/global";
import {
  EditorView,
  EditorState,
  json,
  syntaxHighlighting,
  defaultHighlightStyle,
} from "./lib/codemirror";
import { renderMarkdown } from "./lib/markdown";
import {
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
} from "./lib/sensai";

interface SensAIConfig {
  enabled: boolean;
}

function sensai() {
  return {
    open: false,
    loading: false,
    streaming: false,
    streamingContent: "",
    thinkingLabel: null as string | null,
    enabled: null as boolean | null,
    messages: [] as SensAIMessage[],
    input: "",
    atBottom: true,
    hasNewResponse: false,
    _revealQueue: "",
    _revealTimer: null as number | null,

    async init() {
      this._loadMessages();
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

    async send() {
      const message = this.input.trim();
      if (!message || this.loading) return;

      this.messages.push({ role: "user", content: message, ts: Date.now() });
      this._saveMessages();
      this.input = "";
      this.loading = true;
      this.streaming = false;
      this.streamingContent = "";
      this.thinkingLabel = null;
      await (this as unknown as AlpineMagics).$nextTick();
      this._scrollToBottom();

      try {
        const currentPlotConfigJson = localStorage.getItem("mojo_mosaic_config");

        const response = await fetch("/sensai/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            chatRequestBody(message, this.messages, currentPlotConfigJson),
          ),
        });

        if (!response.ok || !response.body) {
          let detail = "Request failed.";
          try {
            const err = (await response.json()) as { detail?: string };
            if (err.detail) detail = err.detail;
          } catch { /* ignore */ }
          this.messages.push({ role: "assistant", content: detail, error: true, ts: Date.now() });
          return;
        }

        await this._streamSse(response.body);
      } catch {
        this.messages.push({
          role: "assistant",
          content: "Network error. Please try again.",
          error: true,
          ts: Date.now(),
        });
      } finally {
        this._saveMessages();
        this.loading = false;
        this.streaming = false;
        this.streamingContent = "";
        this.thinkingLabel = null;
        this._flushReveal();
        window.dispatchEvent(new CustomEvent("sensai-remeasure"));
        if (!this.open || !this.atBottom) {
          this.hasNewResponse = true;
        }
      }
    },

    // applies one event from the server's stream; a throw while applying it
    // is ignored, like a malformed line
    _handleSseEvent({ type: eventType, payload }: SseEvent) {
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
          this.messages.push({
            role: "assistant",
            content,
            plot_config_update: payload.plot_config_update ?? null,
            routed_to: payload.routed_to,
            ts: Date.now(),
          });
          if (payload.plot_config_update) {
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
          this.messages.push({
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

    async _streamSse(body: ReadableStream<Uint8Array>) {
      const reader = body.getReader();
      const decoder = new TextDecoder();
      const parser = createSseParser();

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          for (const event of parser.feed(decoder.decode(value, { stream: true }))) {
            this._handleSseEvent(event);
          }
        }
        for (const event of parser.end()) this._handleSseEvent(event);
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

    _loadMessages() {
      const loaded = loadMessages();
      if (loaded) this.messages = loaded;
    },

    _saveMessages() {
      saveMessages(this.messages);
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

    clear() {
      this.messages = [];
      this._saveMessages();
    },
  };
}

window.sensai = sensai;

function downloadSensAIHistory(): void {
  const now = new Date();
  const payload = historyExport(storedMessages(), now);

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
        syntaxHighlighting(defaultHighlightStyle),
      ];
      if (lang === "json") extensions.unshift(json());
      new EditorView({
        state: EditorState.create({ doc: code, extensions }),
        parent: el,
      });
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

function sensaiMsgData(role: string) {
  return {
    open: role !== "user",
    single: false,
    _role: role,
    measure() {
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
      );
      self.single = layout.single;
      self.open = layout.open;
    },
  };
}

window.sensaiMsgData = sensaiMsgData;
