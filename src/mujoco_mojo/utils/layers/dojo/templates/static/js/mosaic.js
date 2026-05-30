"use strict";
(() => {
  // src/mosaic.ts
  function mosaic() {
    return {
      trials: [],
      loading: true,
      async init() {
        try {
          const statusResp = await fetch("/monitor/api/status/job");
          const statusData = await statusResp.json();
          if (statusData && !statusData.error) {
            Alpine.store("dojo").updateSync(Date.now(), statusData.is_complete);
          }
        } catch (e) {
          console.warn("Global bootstrap failed for Mosaic.", e);
        }
        await this.refreshTiles();
        Alpine.store("dojo").startGlobalSync();
        window.addEventListener("mojo-data-updated", () => {
          void this.refreshTiles(false);
        });
        this.loading = false;
        Alpine.store("dojo").setPageReady(true);
      },
      async refreshTiles(showLoading = true) {
        if (showLoading) this.loading = true;
        try {
          const resp = await fetch("/mosaic/api/trials");
          const data = await resp.json();
          this.trials = data.trials ?? [];
        } catch (e) {
          console.error("Mosaic refresh failed:", e);
        } finally {
          if (showLoading) this.loading = false;
        }
      }
    };
  }
  window.mosaic = mosaic;
})();
//# sourceMappingURL=mosaic.js.map
