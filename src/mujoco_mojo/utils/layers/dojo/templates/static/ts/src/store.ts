import Alpine from "alpinejs";
import { formatTimeAgo, notifTimeAgo } from "./lib/format";
import { fetchWithTimeout } from "./lib/fetch-timeout";
import {
  nearestColorName,
  resolveColorHex,
  isHexColor,
  collapseColorAlias,
  createSettingsPanelState,
} from "./lib/settings-panel";
import { themeColor } from "./lib/theme-colors";
import type {
  ChangelogResponse,
  DojoStore,
  JobStatus,
  NotificationEntry,
} from "./models";
// window.mojoCreateColorPicker (used by both _settings_panel.html below and
// _macros.html's color_picker macro) was only ever registered as a side
// effect of trial-viewer.ts importing this module - fine for the Plot
// Editor's color pickers, which only ever render on the trial-viewer page
// anyway, but the Settings panel is a global, every-page feature (opened
// from base.html's gear icon), so its color-widget wheel silently never
// rendered at all on any page that doesn't also load trial-viewer.js (e.g.
// Monitor, Mosaic). Importing it here too - main.js loads on every page -
// fixes that; ES modules are idempotent, so trial-viewer.ts keeping its own
// import as well is harmless, not a double-registration.
import "./lib/color-picker";

// the npm/module build doesn't auto-start itself the way the old vendored
// CDN script did, so this is now the one place that does it explicitly --
// see types/global.d.ts for why every other entry bundle keeps referencing
// the bare `Alpine` global instead of importing its own separate copy.
window.Alpine = Alpine;

// Expose time helpers as globals - HTML templates call them in x-text expressions.
window.formatTimeAgo = formatTimeAgo;
window.notifTimeAgo = notifTimeAgo;

// _macros.html's color_picker x-init isn't bundled TS, so it needs the same
// hex-normalizing themeColor() every TS caller uses (see lib/theme-colors.ts)
// rather than its own raw getComputedStyle() read, which would resolve
// Tailwind's default palette to a lab() string in modern browsers -- a
// format iro.js can't parse.
window.themeColor = themeColor;

// _settings_panel.html's color-picker wiring isn't bundled TS either (it's
// built per-field at runtime from the schema, unlike _macros.html's
// compile-time color_picker macro), so it needs these exposed the same way.
window.mojoNearestColorName = nearestColorName;
window.mojoResolveColorHex = resolveColorHex;
window.mojoIsHexColor = isHexColor;
window.mojoCollapseColorAlias = collapseColorAlias;

document.addEventListener("alpine:init", () => {
  const dojoStore: DojoStore = {
    ...createSettingsPanelState(),

    changelogOpen: false,
    changelogLoading: false,
    changelogError: "",
    changelogEntries: [],
    changelogInstalledVersion: "",
    changelogLatestVersion: null,
    changelogUpdateAvailable: false,
    changelogShowWhatsChanged: true,

    isPageReady: false,
    // Falls back to dojo.default_to_fullscreen (settings.py, seeded onto
    // window by base.html's own blocking <head> script) only when the user
    // has never actually touched fullscreen in this browser - once they
    // have (mojo_fullscreen exists in localStorage either way), that choice
    // always wins over the server default, same as today.
    isFullscreen:
      localStorage.getItem("mojo_fullscreen") === null
        ? !!window.__mojoDefaultToFullscreen
        : localStorage.getItem("mojo_fullscreen") === "true",
    overlayCount: 0,
    loadStartTime: Date.now(),
    isComplete: false,
    isMuted: localStorage.getItem("mojo_muted") !== "false",
    isAutoRefresh: localStorage.getItem("mojo_auto") !== "false",

    isConnected: false,
    _wasConnected: null as boolean | null,
    globalToast: {
      show: false,
      message: "",
      type: "info" as "success" | "error" | "info",
    },
    isSyncing: false,
    syncProgress: 0,
    secondsSinceUpdate: 0,
    lastUpdate: null as number | null,
    source: null as EventSource | null,

    showPhrase: true,
    loadingIndex: 0,
    loadingInterval: null as ReturnType<typeof setInterval> | null,
    loadingPhrases: [
      "Eliminating side fumbling in the kinematic tree...",
      "Cooling off the physics engine...",
      "Lubricating spurving bearings with phenylhydrobenzamine...",
      "Was it (x, y, z, w) or (w, x, y, z)...?",
      "Synchronizing cardinal grammeters with the warm-start...",
      "Fromaging the bituminous spandrels for stability...",
      "Reducing sinusoidal depleneration in the dingle arm...",
      "Checking the prefabulated amulite for micro-cracks...",
      "Recalculating Chomondeley's annual grillage coefficient...",
      "Polishing the hydrocoptic marzelvanes...",
      "Resolving contact constraints (it's complicated)...",
      "Nubbing the regurgitative purwell to the wennel-sprocket...",
      "Ensuring nofer trunnions are within tolerance...",
      "Consulting the transcendental hopper dadoscope...",
      "Minimizing side-fumbling in the ambifacient vaneshaft...",
      "Aligning the lotus-o-delta stator windings...",
      "Preparing for the inevitable...",
      "Correcting the Lotus-o-delta offset in the kinematic tree...",
      "Tightening the roffit bars on the spamshaft...",
      "Re-aligning the hydrocoptic marzelvanes...",
      "Calibrating the metapolar pilfrometer...",
      "Evaluating the diathecial evolute of retrograde temperature...",
      "De-nubbing the superaminative wennel-sprocket...",
      "Buffering the anhydrous nagling pins...",
      "Shimming the kyptonastic boiling tank...",
      "Analyzing quasi-pietic stresses in the gremlin studs...",
      "Applying drammock oil to the nivelsheave...",
      "Synchronizing the barescent skor motion...",
      "Filtering out reminative tetraiodohexamine...",
      "Stabilizing the modial interaction of magneto-reluctance...",
      "Compensating for capacitive directance...",
      "Scrubbing the manestically placed grouting brushes...",
      "Zeroing out the transcendental hopper dadoscope...",
      "Wrangling the inertia tensor...",
      "Converting Euler angles (and regretting it)...",
      "Refining the convex hull of the collision geometry...",
      "Validating the mass-proportional damping coefficients...",
      "Buffering the unilateral phase detectors...",
      "Extending the drawn reciprocating dingle arm...",
      "Optimizing the panendermic semiboloid slots...",
      "Bleeding air from the non-reversible tremie pipe...",
      "Adjusting the differential girdlespring tension...",
    ],

    init() {
      // Restore notification history persisted from a previous page/tab
      try {
        const raw = localStorage.getItem("mojo_notif");
        if (raw) {
          const saved = JSON.parse(raw) as {
            n: NotificationEntry[];
            u: number;
          };
          this.notifications = saved.n ?? [];
          this.unreadCount = saved.u ?? 0;
        }
      } catch {
        /* ignore corrupt data */
      }

      this.checkServerHealth();
      setInterval(() => this.checkServerHealth(), 5000);
      this.startGlobalSync();
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden) this.checkServerHealth();
      });
      this._installPlotlyLogCapture();
      this.fetchChangelog();
    },

    async fetchChangelog() {
      this.changelogLoading = true;
      this.changelogError = "";
      try {
        const resp = await fetchWithTimeout("/changelog/data", {}, 8000);
        if (!resp.ok) throw new Error(`Request failed (${resp.status})`);
        const data = (await resp.json()) as ChangelogResponse;
        this.changelogEntries = data.entries;
        this.changelogInstalledVersion = data.installed_version;
        this.changelogLatestVersion = data.latest_version;
        this.changelogUpdateAvailable = data.update_available;
        this.changelogShowWhatsChanged = data.show_whats_changed;
        // shared with the Settings panel's own fields - same underlying
        // fact about this request, whichever endpoint happens to load
        // first this session should seed it, not just /settings's own
        if (data.is_localhost) this.settingsIsLocalhost = true;
        if (data.error) this.changelogError = data.error;
        // is_new is read fresh from the server's own persisted "last seen
        // version" file (utils/changelog.py), updated the moment
        // closeChangelog() marks a version seen - so this alone correctly
        // stays quiet on a later page load in the same session AND across
        // a full Dojo restart, with no separate client-side bookkeeping.
        else if (
          data.show_whats_changed &&
          !this.settingsOpen &&
          data.entries.some((e) => e.is_new)
        ) {
          this.openChangelog();
        }
      } catch (err) {
        this.changelogError =
          err instanceof Error ? err.message : "Failed to load changelog";
      } finally {
        this.changelogLoading = false;
      }
    },

    openChangelog() {
      if (this.settingsOpen) this.closeSettings();
      this.changelogOpen = true;
      document.body.style.overflow = "hidden";
    },

    jumpToChangelogVersion(version: string) {
      document
        .getElementById(`changelog-v-${version}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    },

    async closeChangelog() {
      this.changelogOpen = false;
      document.body.style.overflow = "";
      // only acknowledge when there was actually something new - no point
      // writing (and no point clearing the "New" tags) on a plain re-read
      // of an already-seen changelog
      if (this.changelogLatestVersion && this.changelogEntries.some((e) => e.is_new)) {
        try {
          await fetch("/changelog/mark-seen", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ version: this.changelogLatestVersion }),
          });
          this.changelogEntries = this.changelogEntries.map((e) => ({
            ...e,
            is_new: false,
          }));
        } catch {
          // best-effort - a failed mark-seen just means the "New" tags and
          // auto-open may reappear on a later refresh
        }
      }
    },

    async setShowWhatsChanged(value: boolean) {
      const previous = this.changelogShowWhatsChanged;
      this.changelogShowWhatsChanged = value;
      try {
        const resp = await fetch("/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dojo: { show_whats_changed: value } }),
        });
        if (!resp.ok) throw new Error(`Request failed (${resp.status})`);
      } catch (err) {
        this.changelogShowWhatsChanged = previous;
        this.toast(
          err instanceof Error ? err.message : "Failed to update setting",
          "error",
        );
      }
    },

    // plotly.js routes all its logging through loggers that prepend "WARN:"
    // or "ERROR:" as the first console argument, so wrapping the console
    // methods it uses lets us surface its complaints as toasts without
    // touching any other console traffic
    _installPlotlyLogCapture() {
      const w = window as unknown as { _mojoPlotlyLogsHooked?: boolean };
      if (w._mojoPlotlyLogsHooked) return;
      w._mojoPlotlyLogsHooked = true;

      const recent = new Map<string, number>();
      const forward = (prefix: string, args: unknown[]) => {
        const msg = args.map(String).join(" ").slice(0, 160);
        const now = Date.now();
        // rate-limit: plotly repeats the same warning on every re-render
        if (now - (recent.get(msg) ?? 0) < 10_000) return;
        recent.set(msg, now);
        const type = prefix === "ERROR:" ? "error" : "info";
        this.toast(`${msg}`, type);
        this.addNotification(`${msg}`, type);
      };

      // warns go through console.trace (falling back to console.log),
      // errors through console.error
      (["trace", "log", "error"] as const).forEach((level) => {
        const orig = console[level].bind(console);
        console[level] = (...args: unknown[]) => {
          orig(...args);
          const first = String(args[0] ?? "");
          if (first === "WARN:" || first === "ERROR:") {
            forward(first, args.slice(1));
          }
        };
      });

      // plotly's on-page notifier boxes ("Double-click to zoom back out",
      // "Taking snapshot...", ...) never touch the console: plotly appends
      // .plotly-notifier/.notifier-note divs straight to <body>. watch for
      // them, re-surface the text as a toast, and let CSS hide the originals
      // (see base.html)
      const notifierObserver = new MutationObserver((mutations) => {
        for (const m of mutations) {
          for (const node of m.addedNodes) {
            if (!(node instanceof HTMLElement)) continue;
            const notes = node.classList.contains("notifier-note")
              ? [node]
              : Array.from(node.querySelectorAll(".notifier-note"));
            for (const note of notes) {
              const msg = (note.textContent ?? "").replace(/^\s*×/, "").trim();
              if (msg) this.toast(`${msg}`, "info");
            }
          }
        }
      });
      notifierObserver.observe(document.body, {
        childList: true,
        subtree: true,
      });
    },

    toast(message: string, type: "success" | "error" | "info" = "info") {
      this.globalToast = { show: true, message, type };
      setTimeout(() => {
        this.globalToast = { ...this.globalToast, show: false };
      }, 3500);
    },

    async copyText(text: string, successMsg = "Copied to clipboard") {
      if (navigator.clipboard && window.isSecureContext) {
        try {
          await navigator.clipboard.writeText(text);
          this.toast(successMsg, "success");
          return;
        } catch (err) {
          console.warn("Modern clipboard failed, falling back...", err);
        }
      }
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.cssText = "position:fixed;left:-9999px;top:0";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        if (document.execCommand("copy")) {
          this.toast(successMsg, "success");
        } else throw new Error("execCommand returned false");
      } catch {
        this.toast("Failed to copy to clipboard", "error");
      }
      document.body.removeChild(textArea);
    },

    _setConnected(connected: boolean) {
      this.isConnected = connected;
      if (this._wasConnected === null) {
        // Initial connection - set baseline without notifying.
        if (connected) this._wasConnected = true;
        return;
      }
      if (connected === this._wasConnected) return;
      this._wasConnected = connected;
      const message = connected
        ? "Server connection restored"
        : "Server connection lost";
      const type = connected ? "success" : "error";
      this.toast(message, type);
      this.addNotification(message, type);
    },

    async checkServerHealth() {
      if (document.hidden) return;
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);
      try {
        const response = await fetch("/monitor/api/status/job", {
          method: "GET",
          cache: "no-store",
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        this._setConnected(response.ok);
        if (!response.ok && this.source) {
          this.stopGlobalSync();
          return;
        }
        if (response.ok) {
          const status = (await response.json()) as { is_complete?: boolean };
          // a new run started while we were idle after a completed job
          if (this.isComplete && status.is_complete === false) {
            this.isComplete = false;
            this.toast("New run detected", "info");
            this.addNotification("New run detected", "info");
            this.startGlobalSync();
          }
        }
      } catch {
        this._setConnected(false);
        if (this.source) this.stopGlobalSync();
      }
    },

    setPageReady(val: boolean, force = false) {
      if (val) {
        const minDuration = force ? 0 : 2000;
        const elapsed = Date.now() - this.loadStartTime;
        const remaining = Math.max(0, minDuration - elapsed);
        setTimeout(() => {
          this.isPageReady = true;
          this.stopLoadingMessages();
        }, remaining);
      } else {
        this.loadStartTime = Date.now();
        this.isPageReady = false;
        this.startLoadingMessages();
      }
    },

    startLoadingMessages() {
      if (this.loadingInterval) return;
      this.loadingIndex = Math.floor(
        Math.random() * this.loadingPhrases.length,
      );
      this.showPhrase = true;
      this.loadingInterval = setInterval(() => {
        this.showPhrase = false;
        setTimeout(() => {
          let nextIndex: number;
          do {
            nextIndex = Math.floor(Math.random() * this.loadingPhrases.length);
          } while (nextIndex === this.loadingIndex);
          this.loadingIndex = nextIndex;
          this.showPhrase = true;
        }, 300);
      }, 4000);
    },

    stopLoadingMessages() {
      if (this.loadingInterval) {
        clearInterval(this.loadingInterval);
        this.loadingInterval = null;
      }
    },

    toggleFullscreen() {
      this.isFullscreen = !this.isFullscreen;
      localStorage.setItem("mojo_fullscreen", String(this.isFullscreen));
    },
    exitFullscreen() {
      this.isFullscreen = false;
      localStorage.setItem("mojo_fullscreen", "false");
    },
    toggleMute() {
      this.isMuted = !this.isMuted;
      localStorage.setItem("mojo_muted", this.isMuted.toString());
    },

    toggleAuto() {
      this.isAutoRefresh = !this.isAutoRefresh;
      localStorage.setItem("mojo_auto", String(this.isAutoRefresh));
      if (this.isAutoRefresh) this.startGlobalSync();
      else this.stopGlobalSync();
    },

    startGlobalSync() {
      if (this.source || !this.isAutoRefresh || this.isComplete) return;
      this.source = new EventSource("/monitor/api/status/stream");

      this.source.onopen = () => {
        this._setConnected(true);
      };

      this.source.onmessage = (event: MessageEvent) => {
        if (!event.data || !event.data.trim()) return;
        try {
          const data = JSON.parse(event.data as string) as {
            type: string;
            value?: number;
            status?: JobStatus;
          };
          if (data.type === "start") this.startSync();
          if (data.type === "progress" && data.value !== undefined)
            this.setSyncProgress(data.value);
          if (data.type === "final") {
            this.endSync(Date.now(), data.status?.is_complete ?? false);
            this.applyJobOutcomes(data.status);
            window.dispatchEvent(
              new CustomEvent("mojo-data-updated", { detail: data.status }),
            );
          }
        } catch (err) {
          console.warn("[Mojo Sync] Received invalid payload.", {
            raw: event.data,
            error: err,
          });
        }
      };

      this.source.onerror = () => {
        console.error("[Mojo Sync] Connection lost. Attempting recovery...");
        this.isSyncing = false;
        this.stopGlobalSync();
        this.checkServerHealth();
        setTimeout(() => this.startGlobalSync(), 5000);
      };
    },

    stopGlobalSync() {
      if (this.source) {
        this.source.close();
        this.source = null;
        this.isSyncing = false;
      }
    },

    startSync() {
      this.isSyncing = true;
      this.syncProgress = 0;
    },

    setSyncProgress(val: number) {
      this.syncProgress = val;
    },

    endSync(timestamp: number, isComplete: boolean) {
      this.syncProgress = 100;
      this.lastUpdate = timestamp;
      this.secondsSinceUpdate = 0;
      this.isComplete = isComplete;
      this.isSyncing = false;
      if (isComplete) this.stopGlobalSync();
      setTimeout(() => {
        this.syncProgress = 0;
      }, 700);
    },

    updateSync(timestamp: number, isComplete = false) {
      this.lastUpdate = timestamp;
      this.secondsSinceUpdate = 0;
      this.isComplete = isComplete;
      if (isComplete) this.stopGlobalSync();
    },

    // ── Trial outcome tracking ──────────────────────────────────────────────
    // shared across every page that colors something by trial status
    // (mosaic tiles, the trial-viewer versus-selector chips), so each page
    // doesn't fetch/derive its own copy independently.
    failureTrialNums: [] as number[],
    errorTrialNums: [] as number[],

    applyJobOutcomes(data: JobStatus | undefined) {
      if (!data) return;
      this.failureTrialNums = (data.failure_tns ?? []).map(Number);
      this.errorTrialNums = (data.error_tns ?? []).map(Number);
    },

    // ── Notification history ───────────────────────────────────────────────
    notifications: [] as NotificationEntry[],
    unreadCount: 0,
    notifOpen: false,
    notifTick: Date.now(),

    _saveNotifications() {
      try {
        localStorage.setItem(
          "mojo_notif",
          JSON.stringify({
            n: this.notifications,
            u: this.unreadCount,
          }),
        );
      } catch {
        /* quota exceeded - ignore */
      }
    },

    addNotification(message: string, type: string) {
      (this.notifications as NotificationEntry[]).unshift({
        id: Date.now() + Math.random(),
        message,
        type: type as "success" | "error" | "info",
        timestamp: Date.now(),
        read: !!(this.notifOpen as boolean),
      });
      if ((this.notifications as NotificationEntry[]).length > 100) {
        (this.notifications as NotificationEntry[]).length = 100;
      }
      if (!(this.notifOpen as boolean)) (this.unreadCount as number)++;
      this._saveNotifications();
    },

    openNotifications() {
      this.notifOpen = !this.notifOpen;
      if (this.notifOpen) {
        (this.notifications as NotificationEntry[]).forEach((n) => {
          n.read = true;
        });
        this.unreadCount = 0;
        this._saveNotifications();
      }
    },

    clearNotifications() {
      this.notifications = [] as NotificationEntry[];
      this.unreadCount = 0;
      this._saveNotifications();
    },

    // ── Generic confirm / prompt dialog ────────────────────────────────────
    // Doubles as a text-input prompt when `showInput` is set: confirm()
    // resolves with the trimmed input string (or null if blank), cancel()
    // resolves with null. Plain confirm dialogs resolve with booleans.
    dialog: {
      show: false,
      title: "",
      message: "",
      confirmLabel: "Confirm",
      cancelLabel: "Cancel",
      variant: "info" as "danger" | "warning" | "info",
      showInput: false,
      inputValue: "",
      inputPlaceholder: "",
      _resolve: null as ((v: unknown) => void) | null,

      open(opts: {
        title: string;
        message: string;
        confirmLabel?: string;
        cancelLabel?: string;
        variant?: "danger" | "warning" | "info";
      }): Promise<boolean> {
        this.title = opts.title;
        this.message = opts.message;
        this.confirmLabel = opts.confirmLabel ?? "Confirm";
        this.cancelLabel = opts.cancelLabel ?? "Cancel";
        this.variant = opts.variant ?? "info";
        this.showInput = false;
        this.show = true;
        return new Promise<boolean>((resolve) => {
          this._resolve = resolve as (v: unknown) => void;
        });
      },

      prompt(opts: {
        title: string;
        message?: string;
        confirmLabel?: string;
        cancelLabel?: string;
        variant?: "danger" | "warning" | "info";
        placeholder?: string;
        value?: string;
      }): Promise<string | null> {
        this.title = opts.title;
        this.message = opts.message ?? "";
        this.confirmLabel = opts.confirmLabel ?? "Save";
        this.cancelLabel = opts.cancelLabel ?? "Cancel";
        this.variant = opts.variant ?? "info";
        this.showInput = true;
        this.inputValue = opts.value ?? "";
        this.inputPlaceholder = opts.placeholder ?? "";
        this.show = true;
        return new Promise<string | null>((resolve) => {
          this._resolve = resolve as (v: unknown) => void;
        });
      },

      confirm() {
        this.show = false;
        const result: unknown = this.showInput
          ? this.inputValue.trim() || null
          : true;
        this.showInput = false;
        this._resolve?.(result);
        this._resolve = null;
      },

      cancel() {
        this.show = false;
        const result: unknown = this.showInput ? null : false;
        this.showInput = false;
        this._resolve?.(result);
        this._resolve = null;
      },
    },
  };
  Alpine.store("dojo", dojoStore);

  // expose as a drop-in async alternative to the native confirm() dialog
  window.mojoConfirm = (opts) =>
    (
      Alpine.store("dojo") as DojoStore & {
        dialog: { open(opts: object): Promise<boolean> };
      }
    ).dialog.open(opts);

  // expose as a drop-in async alternative to the native prompt() dialog
  window.mojoPrompt = (opts) =>
    (
      Alpine.store("dojo") as DojoStore & {
        dialog: { prompt(opts: object): Promise<string | null> };
      }
    ).dialog.prompt(opts);

  const store = Alpine.store("dojo") as DojoStore & {
    lastUpdate: number | null;
    secondsSinceUpdate: number;
    loadStartTime: number;
    startLoadingMessages(): void;
    isPageReady: boolean;
  };

  setInterval(() => {
    if (store.lastUpdate) {
      store.secondsSinceUpdate = Math.floor(
        (Date.now() - store.lastUpdate) / 1000,
      );
    }
  }, 1000);

  // Tick every 30 s so notifTimeAgo expressions re-evaluate ("Just now" → "1m ago" etc.)
  setInterval(() => {
    store.notifTick = Date.now();
  }, 30_000);

  if (!store.isPageReady) {
    store.loadStartTime = Date.now();
    store.startLoadingMessages();
  }
});

// the vendored CDN build called this itself once loaded; the npm build
// requires an explicit call. This bundle (main.js) loads in <head>, ahead of
// the page-specific bundle (monitor.js/mosaic.js/trial-viewer.js/sensai.js)
// which is declared at the bottom of the body and sets window.<name> for the
// page's own x-data component -- so starting Alpine here immediately would
// scan the DOM and evaluate e.g. x-data="monitor()" before that global
// exists. Waiting for DOMContentLoaded defers the start until every deferred
// <script type="module"> on the page (main.js included) has finished
// executing, guaranteeing those globals are already in place.
document.addEventListener("DOMContentLoaded", () => Alpine.start());
