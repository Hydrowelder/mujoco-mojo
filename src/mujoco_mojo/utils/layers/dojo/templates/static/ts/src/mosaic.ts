import type { DojoStore, JobStatus, TrialManifest } from './models';

function mosaic() {
  return {
    trials: [] as string[],
    loading: true,

    async init() {
      try {
        const statusResp = await fetch('/monitor/api/status/job');
        const statusData = (await statusResp.json()) as JobStatus;
        if (statusData && !statusData.error) {
          const store = Alpine.store('dojo') as DojoStore;
          store.updateSync(Date.now(), statusData.is_complete);
          store.applyJobOutcomes(statusData);
        }
      } catch (e) {
        console.warn('Global bootstrap failed for Mosaic.', e);
      }

      await this.refreshTiles();
      (Alpine.store('dojo') as DojoStore).startGlobalSync();

      // $store.dojo's own SSE handler already applies trial outcomes for
      // this event -- see startGlobalSync() in store.ts
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

    // same "primary button" base every tile gets, with the border swapped
    // same badge-success/-failure/-error classes monitor.html's own
    // success/failed/error trial grids use (a translucent tinted
    // background + colored border/text, not a solid fill) -- this grid is
    // effectively those three sections merged into one, so it should look
    // identical rather than inventing its own similar-but-different style.
    // Reads trial outcomes from $store.dojo rather than keeping its own
    // copy (see applyJobOutcomes() in store.ts).
    tileClass(trial: string): string {
      const tn = Number(trial.split('_').pop() ?? '0');
      const store = Alpine.store('dojo') as DojoStore;
      if (store.errorTrialNums.includes(tn)) return 'badge-error';
      if (store.failureTrialNums.includes(tn)) return 'badge-failure';
      return 'badge-success';
    },
  };
}

window.mosaic = mosaic;
