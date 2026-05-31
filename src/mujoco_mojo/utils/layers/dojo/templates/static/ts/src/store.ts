import { formatTimeAgo, notifTimeAgo } from "./lib/format";
import type { DojoStore, NotificationEntry } from "./models";

// Expose time helpers as globals - HTML templates call them in x-text expressions.
window.formatTimeAgo = formatTimeAgo;
window.notifTimeAgo = notifTimeAgo;

document.addEventListener("alpine:init", () => {
  Alpine.store("dojo", {
    isPageReady: false,
    isFullscreen: localStorage.getItem("mojo_fullscreen") === "true",
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
    },

    toast(message: string, type: "success" | "error" | "info" = "info") {
      this.globalToast = { show: true, message, type };
      setTimeout(() => {
        this.globalToast = { ...this.globalToast, show: false };
      }, 3500);
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
        if (!response.ok && this.source) this.stopGlobalSync();
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
            status?: { is_complete: boolean };
          };
          if (data.type === "start") this.startSync();
          if (data.type === "progress" && data.value !== undefined)
            this.setSyncProgress(data.value);
          if (data.type === "final") {
            this.endSync(Date.now(), data.status?.is_complete ?? false);
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

    // ── Generic confirm dialog ─────────────────────────────────────────────
    dialog: {
      show: false,
      title: "",
      message: "",
      confirmLabel: "Confirm",
      cancelLabel: "Cancel",
      variant: "info" as "danger" | "warning" | "info",
      _resolve: null as ((v: boolean) => void) | null,

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
        this.show = true;
        return new Promise<boolean>((resolve) => {
          this._resolve = resolve;
        });
      },

      confirm() {
        this.show = false;
        this._resolve?.(true);
        this._resolve = null;
      },

      cancel() {
        this.show = false;
        this._resolve?.(false);
        this._resolve = null;
      },
    },
  });

  // expose as a drop-in async alternative to the native confirm() dialog
  window.mojoConfirm = (opts) =>
    (
      Alpine.store("dojo") as DojoStore & {
        dialog: { open(opts: object): Promise<boolean> };
      }
    ).dialog.open(opts);

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
