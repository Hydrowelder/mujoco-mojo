// static/mosaic.js
function mosaic() {
    return {
        trials: [],
        loading: true,

        async init() {
            // 1. Bootstrap the global state (The Pulse Check)
            try {
                const statusResp = await fetch("/monitor/api/status");
                const statusData = await statusResp.json();
                if (statusData && !statusData.error) {
                    Alpine.store('dojo').updateSync(Date.now(), statusData.is_complete);
                }
            } catch (e) {
                console.warn("Global bootstrap failed for Mosaic.", e);
            }

            // 2. Load the actual tiles
            await this.refreshTiles();

            // 3. Start the live pulse for the footer and auto-refresh
            Alpine.store('dojo').startGlobalSync();

            // 4. Listen for new data to refresh the grid live
            window.addEventListener('mojo-data-updated', () => {
                this.refreshTiles(false); // refresh without showing the big loading blur
            });

            this.loading = false;
            Alpine.store('dojo').setPageReady(true);
        },

        async refreshTiles(showLoading = true) {
            if (showLoading) this.loading = true;
            try {
                const resp = await fetch("/mosaic/api/trials");
                const data = await resp.json();
                this.trials = data.trials || [];
            } catch (e) {
                console.error("Mosaic refresh failed:", e);
            } finally {
                if (showLoading) this.loading = false;
            }
        }
    }
}
