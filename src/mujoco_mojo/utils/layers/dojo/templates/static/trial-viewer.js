function trialViewer(trialId) {
    return {
        trialId: trialId,
        warpId: null,
        paddingLen: 2,
        loading: true,
        data: null,
        errorState: null,

        // Menu States
        yMenuOpen: false,
        settingsOpen: false,
        ySearch: '',

        // Axis & Signal State
        columns: [],
        selectedX: 'time',
        selectedY: [],

        // Plot Customization State
        gridMode: 'major', // none, major, all
        markerMode: 'lines', // lines, markers, lines+markers
        lineInterpolation: 'linear', // linear, spline, vh, hv
        hoverMode: 'x unified', // x, y, closest, x unified

        async init() {
            const currentNum = parseInt(this.trialId.split('_').pop());
            this.warpId = isNaN(currentNum) ? null : currentNum;

            try {
                const statusResp = await fetch("/monitor/api/status");
                const statusData = await statusResp.json();
                if (statusData && !statusData.error) {
                    Alpine.store('dojo').updateSync(Date.now(), statusData.is_complete);
                    const match = statusData.padding_style.match(/\d+/);
                    this.paddingLen = match ? parseInt(match[0]) : 2;
                }
            } catch (e) { console.warn("Dojo offline", e); }

            try {
                const resp = await fetch(`/mosaic/${this.trialId}/data`);
                if (resp.status === 404) { this.errorState = 'not_found'; throw new Error(); }

                const json = await resp.json();
                if (json && Object.keys(json).length > 0) {
                    this.data = json;
                    this.columns = Object.keys(json).sort();
                    this.loadConfig();

                    this.$nextTick(() => {
                        this.renderPlot();
                        setTimeout(() => Plotly.Plots.resize('plot-area'), 100);
                    });
                } else { this.errorState = 'empty'; }
            } catch (e) { this.data = null; } finally {
                this.loading = false;
                Alpine.store('dojo').startGlobalSync();
                Alpine.store('dojo').setPageReady(true);
            }

            window.addEventListener('keydown', (e) => {
                if (e.repeat) return;
                if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
                    e.preventDefault();
                    document.querySelector('input[type="number"]')?.focus();
                }
                if (e.key === 'Escape') {
                    this.yMenuOpen = false;
                    this.settingsOpen = false;
                    if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) e.target.blur();
                }
                if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;
                if (e.key === 'ArrowLeft') document.getElementById('nav-prev')?.click();
                if (e.key === 'ArrowRight') document.getElementById('nav-next')?.click();
            });
        },

        get filteredCols() {
            return !this.ySearch ? this.columns : this.columns.filter(c => c.toLowerCase().includes(this.ySearch.toLowerCase()));
        },

        loadConfig() {
            const savedX = localStorage.getItem('mojo_viewer_x');
            const savedY = localStorage.getItem('mojo_viewer_y');
            this.selectedX = (savedX && this.columns.includes(savedX)) ? savedX : (this.columns.includes('time') ? 'time' : this.columns[0]);
            if (savedY) {
                this.selectedY = JSON.parse(savedY).filter(col => this.columns.includes(col));
            }

            // Load Plot Settings
            this.gridMode = localStorage.getItem('mojo_grid') || 'major';
            this.markerMode = localStorage.getItem('mojo_markers') || 'lines';
            this.lineInterpolation = localStorage.getItem('mojo_interp') || 'linear';
            this.hoverMode = localStorage.getItem('mojo_hover') || 'x unified';
        },

        saveAndRender() {
            localStorage.setItem('mojo_viewer_x', this.selectedX);
            localStorage.setItem('mojo_viewer_y', JSON.stringify(this.selectedY));
            localStorage.setItem('mojo_grid', this.gridMode);
            localStorage.setItem('mojo_markers', this.markerMode);
            localStorage.setItem('mojo_interp', this.lineInterpolation);
            localStorage.setItem('mojo_hover', this.hoverMode);
            this.renderPlot();
        },

        toggleY(col) {
            this.selectedY = this.selectedY.includes(col) ? this.selectedY.filter(c => c !== col) : [...this.selectedY, col];
            this.saveAndRender();
        },

        warpToTrial() {
            if (this.warpId === null) return;
            const paddedNum = String(this.warpId).padStart(this.paddingLen, '0');
            window.location.href = `/mosaic/trial_${paddedNum}`;
        },

        renderPlot() {
            if (!this.data || this.selectedY.length === 0) return;

            const isDark = document.documentElement.classList.contains('dark');
            const colors = ['#06b6d4', '#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444'];
            const textColor = isDark ? '#94a3b8' : '#475569';
            const gridColor = isDark ? '#334155' : '#e2e8f0';

            const traces = this.selectedY.map((key, i) => ({
                x: this.data[this.selectedX],
                y: this.data[key],
                name: key,
                mode: this.markerMode,
                type: 'scatter',
                line: {
                    width: 2,
                    color: colors[i % colors.length],
                    shape: this.lineInterpolation
                },
                marker: { size: 6 }
            }));

            const layout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { t: 20, r: 20, b: 40, l: 60 },
                hovermode: this.hoverMode,
                hoverlabel: {
                    bgcolor: isDark ? '#1e293b' : '#ffffff',
                    font: { family: 'monospace', color: isDark ? '#f8fafc' : '#0f172a' }
                },
                showlegend: true,
                legend: { font: { size: 10, color: textColor }, orientation: 'h', y: -0.2 },
                xaxis: {
                    gridcolor: gridColor,
                    showgrid: this.gridMode !== 'none',
                    minor: { showgrid: this.gridMode === 'all', gridcolor: isDark ? '#1e293b' : '#f1f5f9' },
                    zeroline: false,
                    title: { text: this.selectedX, font: { size: 10, color: textColor } }
                },
                yaxis: {
                    gridcolor: gridColor,
                    showgrid: this.gridMode !== 'none',
                    minor: { showgrid: this.gridMode === 'all', gridcolor: isDark ? '#1e293b' : '#f1f5f9' },
                    zeroline: false
                }
            };

            // DisplayModeBar set to true to restore download/resize tools
            Plotly.newPlot('plot-area', traces, layout, { responsive: true, displayModeBar: true });
        }
    }
}
