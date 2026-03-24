function trialViewer(trialId) {
    return {
        trialId: trialId,
        warpId: '',      // Bound to the text box
        paddingLen: 2,   // Fallback padding
        loading: true,
        data: null,

        async init() {
            // preconfigure trial number into warp box
            const currentNum = parseInt(this.trialId.split('_').pop());
            this.warpId = isNaN(currentNum) ? null : currentNum;

            // 1. Bootstrap pulse + grab padding length
            try {
                const statusResp = await fetch("/monitor/api/status");
                const statusData = await statusResp.json();
                if (statusData && !statusData.error) {
                    Alpine.store('dojo').updateSync(Date.now(), statusData.is_complete);
                    const match = statusData.padding_style.match(/\d+/);
                    this.paddingLen = match ? parseInt(match[0]) : 2;
                }
            } catch (e) { console.warn("Bootstrap failed", e); }

            // 2. Fetch the Plotly data
            try {
                const resp = await fetch(`/mosaic/${this.trialId}/data`);
                if (!resp.ok) throw new Error("Data fetch failed");
                const json = await resp.json();

                // Check if the data is actually populated
                if (json && Object.keys(json).length > 0) {
                    this.data = json;
                    this.renderPlot();
                } else {
                    this.data = null;
                }
            } catch (e) {
                console.error(e);
                this.data = null;
            } finally {
                this.loading = false;
                Alpine.store('dojo').startGlobalSync();
                Alpine.store('dojo').setPageReady(true);
            }

            // 4. Keyboard Navigation
            window.addEventListener('keydown', (e) => {
                if (e.repeat) return;

                // Handle '/' to focus warp box
                if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
                    e.preventDefault();
                    const input = document.querySelector('input[type="number"]');
                    if (input) input.focus();
                }

                // Handle ESC to blur
                if (e.key === 'Escape' && ['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
                    e.target.blur();
                }

                // Block nav if typing
                if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;

                // Nav logic
                if (e.key === 'ArrowLeft') document.getElementById('nav-prev')?.click();
                if (e.key === 'ArrowRight') document.getElementById('nav-next')?.click();
            });
        },

        warpToTrial() {
            if (this.warpId === null) return;
            const paddedNum = String(this.warpId).padStart(this.paddingLen, '0');
            window.location.href = `/mosaic/trial_${paddedNum}`;
        },

        renderPlot() {
            if (!this.data) return;
            const time = this.data.time || this.data.timestamp || [];
            const traces = Object.keys(this.data)
                .filter(key => key !== 'time' && key !== 'timestamp')
                .map(key => ({
                    x: time, y: this.data[key], name: key,
                    type: 'scatter', mode: 'lines', line: { width: 2 }
                }));

            const layout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { t: 40, r: 20, b: 40, l: 60 },
                hovermode: 'closest',
                showlegend: true,
                font: {
                    family: 'monospace',
                    color: document.documentElement.classList.contains('dark') ? '#94a3b8' : '#475569'
                },
                xaxis: { gridcolor: '#334155', zeroline: false },
                yaxis: { gridcolor: '#334155', zeroline: false }
            };

            Plotly.newPlot('plot-area', traces, layout, { responsive: true });
        }
    }
}
