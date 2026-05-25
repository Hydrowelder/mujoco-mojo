import type { AlpineMagics } from "./types/global";

interface SensAIMessage {
  role: "user" | "assistant";
  content: string;
  error?: boolean;
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
    enabled: null as boolean | null,
    messages: [] as SensAIMessage[],
    input: "",

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
    },

    close() {
      this.open = false;
    },

    async send() {
      const message = this.input.trim();
      if (!message || this.loading) return;

      this.messages.push({ role: "user", content: message });
      this._saveMessages();
      this.input = "";
      this.loading = true;
      this._scrollToBottom();

      try {
        const response = await fetch("/sensai/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            available_columns: [],
            current_plot_config_json: null,
          }),
        });

        if (!response.ok) {
          let detail = "Request failed.";
          try {
            const err = (await response.json()) as { detail?: string };
            if (err.detail) detail = err.detail;
          } catch { /* ignore */ }
          this.messages.push({ role: "assistant", content: detail, error: true });
          return;
        }

        const text = await response.text();
        this._parseSse(text);
      } catch {
        this.messages.push({
          role: "assistant",
          content: "Network error. Please try again.",
          error: true,
        });
      } finally {
        this._saveMessages();
        this.loading = false;
        this._scrollToBottom();
      }
    },

    _parseSse(text: string) {
      let eventType = "";
      for (const line of text.split("\n")) {
        const trimmed = line.trimEnd();
        if (trimmed.startsWith("event: ")) {
          eventType = trimmed.slice(7);
        } else if (trimmed.startsWith("data: ")) {
          try {
            const payload = JSON.parse(trimmed.slice(6)) as SensAIResultPayload;
            if (eventType === "result") {
              if (payload.message) {
                this.messages.push({ role: "assistant", content: payload.message });
              }
              if (payload.plot_config_update) {
                window.dispatchEvent(
                  new CustomEvent("mojo-sensai-plot-config", {
                    detail: payload.plot_config_update,
                  }),
                );
              }
            } else if (eventType === "error") {
              this.messages.push({
                role: "assistant",
                content: payload.detail ?? "An error occurred.",
                error: true,
              });
            }
          } catch { /* ignore malformed lines */ }
        } else if (trimmed === "") {
          eventType = "";
        }
      }
    },

    resize(el: HTMLElement) {
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
    },

    _loadMessages() {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) this.messages = JSON.parse(stored) as SensAIMessage[];
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
        if (el) el.scrollTop = el.scrollHeight;
      });
    },

    clear() {
      this.messages = [];
      this._saveMessages();
    },
  };
}

window.sensai = sensai;
