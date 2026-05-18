"use strict";
(() => {
  // src/lib/format.ts
  function formatTimeAgo(seconds) {
    if (!seconds || seconds < 60) return `${seconds || 0}s ago`;
    const mins = Math.floor(seconds / 60);
    return mins < 60 ? `${mins}m ago` : `${Math.floor(mins / 60)}h ago`;
  }

  // src/store.ts
  window.formatTimeAgo = formatTimeAgo;
  document.addEventListener("alpine:init", () => {
    Alpine.store("dojo", {
      isPageReady: false,
      isFullscreen: false,
      loadStartTime: Date.now(),
      isComplete: false,
      isMuted: localStorage.getItem("mojo_muted") !== "false",
      isAutoRefresh: localStorage.getItem("mojo_auto") !== "false",
      isConnected: false,
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
        this.checkServerHealth();
        setInterval(() => this.checkServerHealth(), 1e4);
        this.startGlobalSync();
      },
      async checkServerHealth() {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2e3);
        try {
          const response = await fetch("/monitor/api/status", {
            method: "GET",
            cache: "no-store",
            signal: controller.signal
          });
          clearTimeout(timeoutId);
          this.isConnected = response.ok;
        } catch {
          this.isConnected = false;
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
        this.loadingIndex = Math.floor(Math.random() * this.loadingPhrases.length);
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
        this.source.onmessage = (event) => {
          if (!event.data || !event.data.trim()) return;
          try {
            const data = JSON.parse(event.data);
            if (data.type === "start") this.startSync();
            if (data.type === "progress" && data.value !== void 0) this.setSyncProgress(data.value);
            if (data.type === "final") {
              this.endSync(Date.now(), data.status?.is_complete ?? false);
              window.dispatchEvent(
                new CustomEvent("mojo-data-updated", { detail: data.status })
              );
            }
          } catch (err) {
            console.warn("[Mojo Sync] Received invalid payload.", { raw: event.data, error: err });
          }
        };
        this.source.onerror = () => {
          console.error("[Mojo Sync] Connection lost. Attempting recovery...");
          this.isSyncing = false;
          this.stopGlobalSync();
          setTimeout(() => this.startGlobalSync(), 5e3);
        };
      },
      stopGlobalSync() {
        if (this.source) {
          this.source.close();
          this.source = null;
          this.isConnected = false;
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
      }
    });
    const store = Alpine.store("dojo");
    setInterval(() => {
      if (store.lastUpdate) {
        store.secondsSinceUpdate = Math.floor((Date.now() - store.lastUpdate) / 1e3);
      }
    }, 1e3);
    if (!store.isPageReady) {
      store.loadStartTime = Date.now();
      store.startLoadingMessages();
    }
  });
})();
//# sourceMappingURL=main.js.map
