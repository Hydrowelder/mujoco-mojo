import type { DojoStore, JobStatus, TrialManifest } from './models';

function mosaic() {
  return {
    trials: [] as string[],
    loading: true,

    async init() {
      try {
        const statusResp = await fetch('/monitor/api/status');
        const statusData = (await statusResp.json()) as JobStatus;
        if (statusData && !statusData.error) {
          (Alpine.store('dojo') as DojoStore).updateSync(Date.now(), statusData.is_complete);
        }
      } catch (e) {
        console.warn('Global bootstrap failed for Mosaic.', e);
      }

      await this.refreshTiles();
      (Alpine.store('dojo') as DojoStore).startGlobalSync();

      window.addEventListener('mojo-data-updated', () => {
        void this.refreshTiles(false);
      });

      this.loading = false;
      (Alpine.store('dojo') as DojoStore).setPageReady(true);
    },

    async refreshTiles(showLoading = true) {
      if (showLoading) this.loading = true;
      try {
        const resp = await fetch('/mosaic/api/trials');
        const data = (await resp.json()) as TrialManifest;
        this.trials = data.trials ?? [];
      } catch (e) {
        console.error('Mosaic refresh failed:', e);
      } finally {
        if (showLoading) this.loading = false;
      }
    },
  };
}

window.mosaic = mosaic;
