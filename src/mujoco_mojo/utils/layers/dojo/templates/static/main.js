// Global Helpers
const formatTimeAgo = (seconds) => {
  if (!seconds || seconds < 60) return `${seconds || 0}s ago`;
  const mins = Math.floor(seconds / 60);
  return mins < 60 ? `${mins}m ago` : `${Math.floor(mins / 60)}h ago`;
};

// Global Alpine Initialization
document.addEventListener("alpine:init", () => {
  Alpine.store("dojo", {
    isPageReady: false,
    loadStartTime: Date.now(),
    isComplete: false,
    isMuted: localStorage.getItem("mojo_muted") !== "false",
    isAutoRefresh: localStorage.getItem("mojo_auto") !== "false",

    // streaming state
    isConnected: false,
    isSyncing: false,
    syncProgress: 0,
    secondsSinceUpdate: 0,
    lastUpdate: null,
    source: null,

    // loading messages
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
      "Adjusting the differential girdlespring tension...",
    ],

    init() {
      // 1. Immediate check on load
      this.checkServerHealth();

      // 2. Periodic heartbeat (every 1 seconds)
      setInterval(() => {
        this.checkServerHealth();
      }, 10000);

      // 3. Start the SSE sync if appropriate
      this.startGlobalSync();
    },

    async checkServerHealth() {
      // Create a timeout so the fetch doesn't hang for 30 seconds
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);

      try {
        const response = await fetch("/monitor/api/status", {
          method: "GET",
          cache: "no-store", // CRITICAL: Stop the browser from lying to us
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        // Explicitly check for 200 OK
        this.isConnected = response.ok;
      } catch (err) {
        // If the server is down, fetch throws a TypeError or AbortError
        this.isConnected = false;

        // If we were syncing, stop it now
        if (this.source) {
          this.stopGlobalSync();
        }
      }
    },

    setPageReady(val, force = false) {
      if (val) {
        // If we're forcing it (e.g., job is done), duration is 0.
        // Otherwise, keep the 2-second technobabble for "immersion."
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

      // 1. Initial random seed
      this.loadingIndex = Math.floor(
        Math.random() * this.loadingPhrases.length,
      );
      this.showPhrase = true;

      this.loadingInterval = setInterval(() => {
        // 2. Start the exit transition
        this.showPhrase = false;

        setTimeout(() => {
          // 3. Pick a new random index that ISN'T the current one
          let nextIndex;
          do {
            nextIndex = Math.floor(Math.random() * this.loadingPhrases.length);
          } while (nextIndex === this.loadingIndex);

          this.loadingIndex = nextIndex;

          // 4. Trigger the entry transition
          this.showPhrase = true;
        }, 300); // 300ms matches the x-transition duration
      }, 4000);
    },

    stopLoadingMessages() {
      clearInterval(this.loadingInterval);
      this.loadingInterval = null;
    },

    toggleMute() {
      this.isMuted = !this.isMuted;
      localStorage.setItem("mojo_muted", this.isMuted.toString());
    },

    toggleAuto() {
      this.isAutoRefresh = !this.isAutoRefresh;
      localStorage.setItem("mojo_auto", this.isAutoRefresh);

      if (this.isAutoRefresh) {
        this.startGlobalSync();
      } else {
        this.stopGlobalSync();
      }
    },

    // global sse management
    startGlobalSync() {
      if (this.source || !this.isAutoRefresh || this.isComplete) return;

      this.source = new EventSource("/monitor/api/status/stream");

      this.source.onmessage = (event) => {
        // 1. SILENT GUARD: Skip empty keep-alive pings from the server
        if (!event.data || !event.data.trim()) return;

        try {
          // 2. PROTECTIVE PARSE: Don't let a bad payload kill the app
          const data = JSON.parse(event.data);

          // 3. LOGICAL DISPATCH
          if (data.type === "start") this.startSync();

          if (data.type === "progress") this.setSyncProgress(data.value);

          if (data.type === "final") {
            this.endSync(Date.now(), data.status?.is_complete);

            // Broadcast the update to other components (Mosaic/Monitor)
            window.dispatchEvent(
              new CustomEvent("mojo-data-updated", { detail: data.status }),
            );
          }
        } catch (err) {
          // 4. THE SAFETY NET: Handle non-JSON strings or HTML error pages
          console.warn(
            "[Mojo Sync] Received invalid payload. Stream may be idle or server errored.",
            {
              raw: event.data,
              error: err.message,
            },
          );
        }
      };

      this.source.onerror = (err) => {
        console.error("[Mojo Sync] Connection lost. Attempting recovery...");
        this.isSyncing = false;
        this.stopGlobalSync();

        // Attempt reconnection in 5s
        setTimeout(() => this.startGlobalSync(), 5000);
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

    // animation helpers for the 'laser beam'
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

      // job is done and auto refresh should turn itself off
      if (isComplete) {
        this.stopGlobalSync();
      }

      setTimeout(() => {
        this.syncProgress = 0;
      }, 700);
    },

    updateSync(timestamp, isComplete = false) {
      this.lastUpdate = timestamp;
      this.secondsSinceUpdate = 0;
      this.isComplete = isComplete;

      if (isComplete) {
        this.stopGlobalSync();
      }
    },
  });

  const store = Alpine.store("dojo");

  // Global Timer
  setInterval(() => {
    if (store.lastUpdate) {
      store.secondsSinceUpdate = Math.floor(
        (Date.now() - store.lastUpdate) / 1000,
      );
    }
  }, 1000);

  if (!store.isPageReady) {
    store.loadStartTime = Date.now(); // Record the exact start time of the app
    store.startLoadingMessages();
  }
});
