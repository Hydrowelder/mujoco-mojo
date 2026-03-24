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
        gridMode: 'all', // none, major, all
        markerMode: 'lines', // lines, markers, lines+markers
        lineInterpolation: 'linear', // linear, spline, vh, hv
        hoverMode: 'x unified', // x, y, closest, x unified

        async init() {
            const currentNum = parseInt(this.trialId.split('_').pop());
            this.warpId = isNaN(currentNum) ? null : currentNum;

            // 1. Listen for Theme Changes (Auto-Redraw)
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.attributeName === 'class' && this.data && this.selectedY.length > 0) {
                        this.renderPlot();
                    }
                });
            });
            observer.observe(document.documentElement, { attributes: true });

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

                    // Prioritize 'time' column for initial load
                    this.loadConfig();

                    this.$nextTick(() => {
                        this.renderPlot();
                        setTimeout(() => {
                            const el = document.getElementById('plot-area');
                            if (el && el.offsetParent !== null) {
                                Plotly.Plots.resize(el);
                            }
                        }, 100);
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

            // Force X to 'time' if it exists and no preference is saved
            const hasTime = this.columns.includes('time');
            this.selectedX = (savedX && this.columns.includes(savedX)) ? savedX : (hasTime ? 'time' : this.columns[0]);

            if (savedY) {
                this.selectedY = JSON.parse(savedY).filter(col => this.columns.includes(col));
            }

            // Load Plot Settings
            this.gridMode = localStorage.getItem('mojo_grid') || 'all';
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

            // Also guard resize here in case signals were added to an empty plot
            this.$nextTick(() => {
                const el = document.getElementById('plot-area');
                if (el && el.offsetParent !== null) {
                    Plotly.Plots.resize(el);
                }
            });
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

            // Theme Contrast Corrections
            const textColor = isDark ? '#94a3b8' : '#475569';
            const majorGrid = isDark ? '#334155' : '#f1f5f9';
            const minorGrid = isDark ? '#1e293b' : '#f8fafc';
            const tooltipBg = isDark ? '#0f172a' : '#ffffff';
            const tooltipBorder = isDark ? '#06b6d4' : '#06b6d4';

            // Fix: Spike needs to be bright in dark mode to be visible
            const spikeColor = isDark ? '#06b6d4' : '#94a3b8';

            const traces = this.selectedY.map((key, i) => ({
                x: this.data[this.selectedX],
                y: this.data[key],
                name: key,
                mode: this.markerMode,
                type: 'scatter',
                line: { width: 2, color: colors[i % colors.length], shape: this.lineInterpolation },
                marker: { size: 6 },
                namelength: -1,
                // --- FIX: Force uniform background color per trace ---
                hoverlabel: {
                    bgcolor: tooltipBg,
                    bordercolor: tooltipBorder,
                    font: { family: 'monospace', size: 12, color: isDark ? '#f8fafc' : '#0f172a' }
                }
            }));

            const layout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { t: 20, r: 20, b: 40, l: 60 },
                hovermode: this.hoverMode,
                // Global hoverlabel settings for the X-axis part
                hoverlabel: {
                    bgcolor: tooltipBg,
                    bordercolor: tooltipBorder,
                    font: { family: 'monospace', size: 12, color: isDark ? '#f8fafc' : '#0f172a' },
                    align: 'left'
                },
                showlegend: true,
                legend: { font: { size: 10, color: textColor }, orientation: 'h', y: -0.2 },
                xaxis: {
                    gridcolor: majorGrid,
                    showgrid: this.gridMode !== 'none',
                    minor: { showgrid: this.gridMode === 'all', gridcolor: minorGrid },
                    zeroline: false,
                    tickfont: { color: textColor },
                    title: { text: this.selectedX, font: { size: 10, color: textColor, family: 'monospace' } },

                    // --- Spike & Unified Hover Label Styling ---
                    showspikes: true,
                    spikemode: 'across',
                    spikesnap: 'cursor',
                    spikelinecolor: spikeColor,
                    spikethickness: 1,
                    spikedash: 'solid',
                    // Specifically style the x-axis label background
                    hoverlabel: {
                        bgcolor: tooltipBg,
                        font: { color: isDark ? '#f8fafc' : '#0f172a' }
                    }
                },
                yaxis: {
                    gridcolor: majorGrid,
                    showgrid: this.gridMode !== 'none',
                    minor: { showgrid: this.gridMode === 'all', gridcolor: minorGrid },
                    zeroline: false,
                    tickfont: { color: textColor }
                }
            };

            Plotly.newPlot('plot-area', traces, layout, {
                responsive: true,
                displayModeBar: true,
                modeBarButtonsToRemove: ['lasso2d', 'select2d']
            });
        }
    }
}
