"use strict";
(() => {
  // src/lib/format.ts
  function formatTimeAgo(seconds) {
    if (!seconds || seconds < 60) return `${seconds || 0}s ago`;
    const mins = Math.floor(seconds / 60);
    return mins < 60 ? `${mins}m ago` : `${Math.floor(mins / 60)}h ago`;
  }
  function notifTimeAgo(timestamp, _tick) {
    const diff = Math.floor((Date.now() - timestamp) / 1e3);
    if (diff < 60) return "Just now";
    const mins = Math.floor(diff / 60);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  // src/store.ts
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
      _wasConnected: null,
      globalToast: {
        show: false,
        message: "",
        type: "info"
      },
      isSyncing: false,
      syncProgress: 0,
      secondsSinceUpdate: 0,
      lastUpdate: null,
      source: null,
      showPhrase: true,
      loadingIndex: 0,
      loadingInterval: null,
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
        "Adjusting the differential girdlespring tension..."
      ],
      init() {
        try {
          const raw = localStorage.getItem("mojo_notif");
          if (raw) {
            const saved = JSON.parse(raw);
            this.notifications = saved.n ?? [];
            this.unreadCount = saved.u ?? 0;
          }
        } catch {
        }
        this.checkServerHealth();
        setInterval(() => this.checkServerHealth(), 5e3);
        this.startGlobalSync();
        document.addEventListener("visibilitychange", () => {
          if (!document.hidden) this.checkServerHealth();
        });
      },
      toast(message, type = "info") {
        this.globalToast = { show: true, message, type };
        setTimeout(() => {
          this.globalToast = { ...this.globalToast, show: false };
        }, 3500);
      },
      _setConnected(connected) {
        this.isConnected = connected;
        if (this._wasConnected === null) {
          if (connected) this._wasConnected = true;
          return;
        }
        if (connected === this._wasConnected) return;
        this._wasConnected = connected;
        const message = connected ? "Server connection restored" : "Server connection lost";
        const type = connected ? "success" : "error";
        this.toast(message, type);
        this.addNotification(message, type);
      },
      async checkServerHealth() {
        if (document.hidden) return;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2e3);
        try {
          const response = await fetch("/monitor/api/status/job", {
            method: "GET",
            cache: "no-store",
            signal: controller.signal
          });
          clearTimeout(timeoutId);
          this._setConnected(response.ok);
          if (!response.ok && this.source) {
            this.stopGlobalSync();
            return;
          }
          if (response.ok) {
            const status = await response.json();
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
      setPageReady(val, force = false) {
        if (val) {
          const minDuration = force ? 0 : 2e3;
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
          Math.random() * this.loadingPhrases.length
        );
        this.showPhrase = true;
        this.loadingInterval = setInterval(() => {
          this.showPhrase = false;
          setTimeout(() => {
            let nextIndex;
            do {
              nextIndex = Math.floor(Math.random() * this.loadingPhrases.length);
            } while (nextIndex === this.loadingIndex);
            this.loadingIndex = nextIndex;
            this.showPhrase = true;
          }, 300);
        }, 4e3);
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
        this.source.onmessage = (event) => {
          if (!event.data || !event.data.trim()) return;
          try {
            const data = JSON.parse(event.data);
            if (data.type === "start") this.startSync();
            if (data.type === "progress" && data.value !== void 0)
              this.setSyncProgress(data.value);
            if (data.type === "final") {
              this.endSync(Date.now(), data.status?.is_complete ?? false);
              window.dispatchEvent(
                new CustomEvent("mojo-data-updated", { detail: data.status })
              );
            }
          } catch (err) {
            console.warn("[Mojo Sync] Received invalid payload.", {
              raw: event.data,
              error: err
            });
          }
        };
        this.source.onerror = () => {
          console.error("[Mojo Sync] Connection lost. Attempting recovery...");
          this.isSyncing = false;
          this.stopGlobalSync();
          this.checkServerHealth();
          setTimeout(() => this.startGlobalSync(), 5e3);
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
      setSyncProgress(val) {
        this.syncProgress = val;
      },
      endSync(timestamp, isComplete) {
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
      updateSync(timestamp, isComplete = false) {
        this.lastUpdate = timestamp;
        this.secondsSinceUpdate = 0;
        this.isComplete = isComplete;
        if (isComplete) this.stopGlobalSync();
      },
      // ── Notification history ───────────────────────────────────────────────
      notifications: [],
      unreadCount: 0,
      notifOpen: false,
      notifTick: Date.now(),
      _saveNotifications() {
        try {
          localStorage.setItem(
            "mojo_notif",
            JSON.stringify({
              n: this.notifications,
              u: this.unreadCount
            })
          );
        } catch {
        }
      },
      addNotification(message, type) {
        this.notifications.unshift({
          id: Date.now() + Math.random(),
          message,
          type,
          timestamp: Date.now(),
          read: !!this.notifOpen
        });
        if (this.notifications.length > 100) {
          this.notifications.length = 100;
        }
        if (!this.notifOpen) this.unreadCount++;
        this._saveNotifications();
      },
      openNotifications() {
        this.notifOpen = !this.notifOpen;
        if (this.notifOpen) {
          this.notifications.forEach((n) => {
            n.read = true;
          });
          this.unreadCount = 0;
          this._saveNotifications();
        }
      },
      clearNotifications() {
        this.notifications = [];
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
        variant: "info",
        showInput: false,
        inputValue: "",
        inputPlaceholder: "",
        _resolve: null,
        open(opts) {
          this.title = opts.title;
          this.message = opts.message;
          this.confirmLabel = opts.confirmLabel ?? "Confirm";
          this.cancelLabel = opts.cancelLabel ?? "Cancel";
          this.variant = opts.variant ?? "info";
          this.showInput = false;
          this.show = true;
          return new Promise((resolve) => {
            this._resolve = resolve;
          });
        },
        prompt(opts) {
          this.title = opts.title;
          this.message = opts.message ?? "";
          this.confirmLabel = opts.confirmLabel ?? "Save";
          this.cancelLabel = opts.cancelLabel ?? "Cancel";
          this.variant = opts.variant ?? "info";
          this.showInput = true;
          this.inputValue = opts.value ?? "";
          this.inputPlaceholder = opts.placeholder ?? "";
          this.show = true;
          return new Promise((resolve) => {
            this._resolve = resolve;
          });
        },
        confirm() {
          this.show = false;
          const result = this.showInput ? this.inputValue.trim() || null : true;
          this.showInput = false;
          this._resolve?.(result);
          this._resolve = null;
        },
        cancel() {
          this.show = false;
          const result = this.showInput ? null : false;
          this.showInput = false;
          this._resolve?.(result);
          this._resolve = null;
        }
      }
    });
    window.mojoConfirm = (opts) => Alpine.store("dojo").dialog.open(opts);
    window.mojoPrompt = (opts) => Alpine.store("dojo").dialog.prompt(opts);
    const store = Alpine.store("dojo");
    setInterval(() => {
      if (store.lastUpdate) {
        store.secondsSinceUpdate = Math.floor(
          (Date.now() - store.lastUpdate) / 1e3
        );
      }
    }, 1e3);
    setInterval(() => {
      store.notifTick = Date.now();
    }, 3e4);
    if (!store.isPageReady) {
      store.loadStartTime = Date.now();
      store.startLoadingMessages();
    }
  });
})();
//# sourceMappingURL=main.js.map
