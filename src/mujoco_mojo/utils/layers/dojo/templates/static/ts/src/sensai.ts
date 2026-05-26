import { marked, type Tokens } from 'marked';
import type { AlpineMagics } from "./types/global";

interface SensAIMessage {
  role: "user" | "assistant";
  content: string;
  error?: boolean;
  plot_config_update?: object | null;
  ts: number;
}

interface SensAIConfig {
  enabled: boolean;
}

interface SensAIResultPayload {
  message?: string;
  plot_config_update?: object | null;
  detail?: string;
}

const STORAGE_KEY = "sensai-messages";

function sensai() {
  return {
    open: false,
    loading: false,
    streaming: false,
    streamingContent: "",
    enabled: null as boolean | null,
    messages: [] as SensAIMessage[],
    input: "",
    atBottom: true,
    hasNewResponse: false,

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
    },

    toggle() {
      this.open = !this.open;
      if (this.open) {
        this.hasNewResponse = false;
        this._scrollToBottom();
        // dispatch after next tick so the panel is back in layout flow and scrollHeights are valid
        (this as unknown as AlpineMagics).$nextTick(() => {
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
      await (this as unknown as AlpineMagics).$nextTick();
      this._scrollToBottom();

      try {
        const history = this.messages
          .slice(0, -1)   // exclude the just-pushed user message
          .slice(-20)
          .map(m => ({ role: m.role, content: m.content }));

        const currentPlotConfigJson = localStorage.getItem("mojo_mosaic_config");

        const response = await fetch("/sensai/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            message_history: history,
            all_columns: [],
            rotatable_vectors: [],
            available_quats: [],
            current_plot_config_json: currentPlotConfigJson,
          }),
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
        window.dispatchEvent(new CustomEvent("sensai-remeasure"));
        if (!this.open || !this.atBottom) {
          this.hasNewResponse = true;
        }
      }
    },

    async _streamSse(body: ReadableStream<Uint8Array>) {
      const reader = body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let eventType = "";

      const handleLine = async (line: string) => {
        const trimmed = line.trimEnd();
        if (trimmed.startsWith("event: ")) {
          eventType = trimmed.slice(7);
        } else if (trimmed.startsWith("data: ")) {
          try {
            const payload = JSON.parse(trimmed.slice(6)) as SensAIResultPayload & { delta?: string };
            if (eventType === "text_delta" && typeof payload.delta === "string") {
              if (!this.streaming) {
                this.streaming = true;
              }
              this.streamingContent += payload.delta;
              if (this.open && this.atBottom) this._scrollToBottom();
              await new Promise<void>(resolve => setTimeout(resolve, 25));
            } else if (eventType === "result") {
              const content = typeof payload.message === "string"
                ? payload.message || this.streamingContent || "(no response)"
                : this.streamingContent || "(no response)";
              this.messages.push({
                role: "assistant",
                content,
                plot_config_update: payload.plot_config_update ?? null,
                ts: Date.now(),
              });
              if (payload.plot_config_update) {
                window.dispatchEvent(new CustomEvent("mojo-sensai-plot-config", {
                  detail: payload.plot_config_update,
                }));
              }
              this.streaming = false;
              this.streamingContent = "";
            } else if (eventType === "error") {
              this.messages.push({
                role: "assistant",
                content: payload.detail ?? "An error occurred.",
                error: true,
                ts: Date.now(),
              });
              this.streaming = false;
              this.streamingContent = "";
            }
          } catch { /* ignore malformed SSE lines */ }
        } else if (trimmed === "") {
          eventType = "";
        }
      };

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let newline: number;
          while ((newline = buffer.indexOf("\n")) !== -1) {
            await handleLine(buffer.slice(0, newline));
            buffer = buffer.slice(newline + 1);
          }
        }
        // flush any remaining content in the buffer
        if (buffer) await handleLine(buffer);
      } finally {
        reader.releaseLock();
      }
    },

    resize(el: HTMLElement) {
      const msgEl = (this as unknown as AlpineMagics).$refs["messages"] as HTMLElement | undefined;
      const wasAtBottom = this.atBottom;
      el.style.height = "auto";
      el.style.overflowY = "hidden";
      const lineHeight = parseInt(getComputedStyle(el).lineHeight, 10) || 20;
      const maxHeight = lineHeight * 6;
      if (el.scrollHeight > maxHeight) {
        el.style.height = maxHeight + "px";
        el.style.overflowY = "auto";
      } else {
        el.style.height = el.scrollHeight + "px";
      }
      if (wasAtBottom && msgEl) {
        msgEl.scrollTop = msgEl.scrollHeight;
      }
    },

    onScroll(el: HTMLElement) {
      this.atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
      if (this.atBottom) this.hasNewResponse = false;
    },

    scrollToBottom() {
      const el = (this as unknown as AlpineMagics).$refs["messages"] as HTMLElement | undefined;
      if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      this.atBottom = true;
      this.hasNewResponse = false;
    },

    _loadMessages() {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
          const parsed = JSON.parse(stored) as SensAIMessage[];
          this.messages = parsed.map(m => ({ ...m, ts: m.ts ?? Date.now() }));
        }
      } catch { /* ignore */ }
    },

    _saveMessages() {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.messages));
      } catch { /* ignore */ }
    },

    _scrollToBottom() {
      (this as unknown as AlpineMagics).$nextTick(() => {
        const el = (this as unknown as AlpineMagics).$refs["messages"];
        if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      });
    },

    clear() {
      this.messages = [];
      this._saveMessages();
    },
  };
}

window.sensai = sensai;

function downloadSensAIHistory(): void {
  const stored = localStorage.getItem(STORAGE_KEY);
  let messages: SensAIMessage[] = [];
  try {
    if (stored) messages = JSON.parse(stored) as SensAIMessage[];
  } catch { /* ignore */ }

  const now = new Date();
  const payload = {
    exported_at: now.toISOString(),
    messages: messages.map(m => {
      const entry: Record<string, unknown> = {
        timestamp: new Date(m.ts).toISOString(),
        sender: m.role === "user" ? "user" : "sensai",
        message: m.content,
      };
      if (m.error) entry["error"] = true;
      if (m.plot_config_update !== undefined) entry["plot_config_update"] = m.plot_config_update;
      return entry;
    }),
  };

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `sensai-chat-${now.toISOString().slice(0, 10)}.json`;
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

marked.use({
  renderer: {
    code({ text, lang }: Tokens.Code): string {
      const encoded = encodeURIComponent(text);
      const langAttr = lang ? ` data-lang="${encodeURIComponent(lang)}"` : "";
      return `<div class="sensai-cm-block" data-code="${encoded}"${langAttr}></div>`;
    },
    codespan({ text }: Tokens.Codespan): string {
      return `<code class="bg-slate-100 dark:bg-slate-800 rounded px-1 font-mono text-cyan-600 dark:text-cyan-400 text-[0.85em]">${text}</code>`;
    },
  },
});

function renderMarkdown(text: string): string {
  return marked.parse(text) as string;
}

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
        CM.EditorView.editable.of(false),
        CM.EditorState.readOnly.of(true),
        CM.syntaxHighlighting(CM.defaultHighlightStyle),
      ];
      if (lang === "json") extensions.unshift(CM.json());
      new CM.EditorView({
        state: CM.EditorState.create({ doc: code, extensions }),
        parent: el,
      });
    });
  } catch { /* CM not yet loaded or no blocks present */ }
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
      ) as HTMLElement | null;
      if (!content || content.scrollHeight === 0) return;
      const lh = parseFloat(getComputedStyle(content).lineHeight) || 22;
      self.single = content.scrollHeight <= Math.ceil(lh * 2.5);
      self.open = self.single || self._role !== "user";
    },
  };
}

window.sensaiMsgData = sensaiMsgData;
