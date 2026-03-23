function trialViewer(trialId) {
    return {
        trialId: trialId,
        jumpId: '',      // Bound to the text box
        paddingLen: 2,   // Fallback padding
        loading: true,

        async init() {
            // 1. Bootstrap pulse + grab padding length
            try {
                const statusResp = await fetch("/monitor/api/status");
                const statusData = await statusResp.json();
                if (statusData && !statusData.error) {
                    Alpine.store('dojo').updateSync(Date.now(), statusData.is_complete);

                    // Parse '03d' -> 3
                    const match = statusData.padding_style.match(/\d+/);
                    this.paddingLen = match ? parseInt(match[0]) : 2;
                }
            } catch (e) { console.warn("Bootstrap failed", e); }

            // 2. Fetch the Plotly data
            try {
                const resp = await fetch(`/mosaic/${this.trialId}/data`);
                if (!resp.ok) throw new Error("Data fetch failed");
                this.data = await resp.json();
                this.renderPlot();
            } catch (e) {
                console.error(e);
            } finally {
                this.loading = false;

                // 3. Start the footer pulse and reveal page
                Alpine.store('dojo').startGlobalSync();
                Alpine.store('dojo').setPageReady(true);
            }

            // 4. Keyboard Navigation
            window.addEventListener('keydown', (e) => {
                if (e.repeat) return;

                // 1. ESCAPE: If typing, blur the input to return to global navigation
                if (e.key === 'Escape') {
                    if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
                        e.target.blur();
                        // Optional: this.jumpId = ''; // Clear the box on escape?
                        return;
                    }
                }

                // 2. BLOCK: Prevent Arrow Keys from triggering navigation while typing
                if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
                    return;
                }

                // 3. NAVIGATE: Standard Arrow Key logic
                if (e.key === 'ArrowLeft') {
                    const prevBtn = document.getElementById('nav-prev');
                    if (prevBtn) prevBtn.click();
                }

                if (e.key === 'ArrowRight') {
                    const nextBtn = document.getElementById('nav-next');
                    if (nextBtn) nextBtn.click();
                }
            });
        },

        jumpToTrial() {
            if (!this.jumpId) return;

            // Reconstruct the folder name: trial_ + 0-padded number
            const paddedNum = String(this.jumpId).padStart(this.paddingLen, '0');
            const targetUrl = `/mosaic/trial_${paddedNum}`;

            // Navigate!
            window.location.href = targetUrl;
        },

        renderPlot() {
            const time = this.data.time || this.data.timestamp || [];
            const traces = [];

            // Automatically create a trace for every column that isn't 'time'
            Object.keys(this.data).forEach(key => {
                if (key === 'time' || key === 'timestamp') return;

                traces.push({
                    x: time,
                    y: this.data[key],
                    name: key,
                    type: 'scatter',
                    mode: 'lines',
                    line: { width: 2 }
                });
            });

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
