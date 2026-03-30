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
    isComplete: false,
    isMuted: localStorage.getItem("mojo_muted") !== "false",
    isAutoRefresh: localStorage.getItem("mojo_auto") !== "false",

    // streaming state
    isSyncing: false,
    syncProgress: 0,
    secondsSinceUpdate: 0,
    lastUpdate: null,
    source: null,

    setPageReady(val) {
      this.isPageReady = val;
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
        const data = JSON.parse(event.data);

        if (data.type === "start") this.startSync();
        if (data.type === "progress") this.setSyncProgress(data.value);

        if (data.type === "final") {
          this.endSync(Date.now(), data.status.is_complete);
          // tell the specific page (Monitor/Mosaic) that new data is here
          window.dispatchEvent(
            new CustomEvent("mojo-data-updated", { detail: data.status }),
          );
        }
      };

      this.source.onerror = () => {
        this.isSyncing = false;
        this.stopGlobalSync();
        // try to reconnect in 5s
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

      if (isComplete) this.stopGlobalSync();

      setTimeout(() => {
        this.syncProgress = 0;
      }, 700);
    },

    updateSync(timestamp, isComplete = false) {
      this.lastUpdate = timestamp;
      this.secondsSinceUpdate = 0;
      this.isComplete = isComplete;
    },
  });

  // Global Timer
  setInterval(() => {
    const store = Alpine.store("dojo");
    if (store.lastUpdate) {
      store.secondsSinceUpdate = Math.floor(
        (Date.now() - store.lastUpdate) / 1000,
      );
    }
  }, 1000);
});
