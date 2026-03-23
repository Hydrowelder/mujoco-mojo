function mosaic() {
    return {
        trials: [],
        loading: true,

        async init() {
            try {
                const resp = await fetch("/mosaic/api/trials");
                const data = await resp.json();
                this.trials = data.trials || [];
            } catch (e) {
                console.error("Mosaic load failed:", e);
            } finally {
                this.loading = false;
                Alpine.store('dojo').setPageReady(true);
            }
        }
    }
}
