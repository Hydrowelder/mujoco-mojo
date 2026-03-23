function monitor() {
    return {
        status: {
            n_done: 0, n_success: 0, n_failed: 0,
            success_tns: [], failure_tns: [], progress: 0,
        },
        stats: [],
        timer: null,
        source: null,
        isSyncing: false,
        hasInitialData: false,
        chimePlayed: false,

        async init() {
            // Listen for global toggle events from the header
            window.addEventListener('auto-refresh-toggled', (e) => {
                if (e.detail) this.startPolling();
                else this.stopPolling();
            });

            try {
                const resp = await fetch("/monitor/api/status");
                const data = await resp.json();

                if (data && !data.error) {
                    this.status = data;
                    this.hasInitialData = true;
                    this.refreshStats();

                    // Notify Global Store: We have data, and tell it if the job is done
                    Alpine.store('dojo').updateSync(Date.now(), this.status.is_complete);

                    if (this.status.is_complete) {
                        this.handleCompletion();
                    }
                }
            } catch (e) {
                console.warn("Initial bootstrap failed.", e);
                Alpine.store('dojo').setPageReady(true);
            }

            // Start the persistent live stream if needed
            if (!this.status.is_complete && Alpine.store('dojo').isAutoRefresh) {
                this.startStreaming();
            }
        },

        startStreaming() {
            this.stopStreaming(); // Close any existing connection first

            this.source = new EventSource("/monitor/api/status/stream");
            this.isSyncing = true;

            this.source.onmessage = (event) => {
                const data = JSON.parse(event.data);

                // Start the 'Laser Beam' in the global store
                if (data.type === "start") {
                    Alpine.store('dojo').startSync();
                }

                // Update the 'Laser Beam' progress
                if (data.type === "progress") {
                    Alpine.store('dojo').setSyncProgress(data.value);
                }

                // Data has arrived!
                if (data.type === "final") {
                    this.status = data.status;
                    this.hasInitialData = true;

                    // Finish the 'Laser Beam' animation and update footer
                    Alpine.store('dojo').endSync(Date.now(), this.status.is_complete);

                    if (this.status.is_complete) {
                        this.stopStreaming();
                        this.handleCompletion();
                    }

                    this.$nextTick(() => {
                        this.refreshStats();
                    });
                }
            };

            this.source.onerror = () => {
                this.isSyncing = false;
                Alpine.store('dojo').isSyncing = false;
                // The browser will automatically try to reconnect here
            };
        },

        stopStreaming() {
            if (this.source) {
                this.source.close();
                this.source = null;
                this.isSyncing = false;
            }
        },

        refreshStats() {
            const totalDone = this.status.n_done || 0;
            const n_trial = this.status.n_trial || 1;
            const progress = ((totalDone / n_trial) * 100).toFixed(1);
            document.title = `${this.status.is_complete ? '✓' : '(' + progress + '%)'} Monitor | MuJoCo Mojo`;

            const successPerc =
                totalDone > 0
                    ? ((this.status.n_success / totalDone) * 100).toFixed(1)
                    : 0;
            const failurePerc =
                totalDone > 0
                    ? ((this.status.n_failed / totalDone) * 100).toFixed(1)
                    : 0;
            const donePerc = ((totalDone / n_trial) * 100).toFixed(1);
            const lastSuccess =
                this.status.success_tns.length > 0
                    ? this.status.success_tns[this.status.success_tns.length - 1]
                    : "None";
            const lastFailure =
                this.status.failure_tns.length > 0
                    ? this.status.failure_tns[this.status.failure_tns.length - 1]
                    : "None";

            const finalETA = this.status.is_complete
                ? "Job Complete"
                : `ETA: ${this.status.end_time}`;
            const remainingVal = this.status.is_complete
                ? "00:00:00"
                : this.status.time_remaining;

            this.stats = [
                {
                    label: "Successes",
                    value: `${this.status.n_success} (${successPerc}%)`,
                    color: "text-emerald-500",
                    subValue: `Last Success: Trial ${lastSuccess}`,
                },
                {
                    label: "Failures",
                    value: `${this.status.n_failed} (${failurePerc}%)`,
                    color: "text-rose-500",
                    subValue: `Last Failure: Trial ${lastFailure}`,
                },
                {
                    label: "Remaining",
                    value: `${this.status.n_remaining} (${(100 - donePerc).toFixed(1)}%)`,
                    color: "text-amber-500",
                    subValue: `${this.status.throughput} trials/min (${this.status.avg_duration} per trial)`,
                },
                {
                    label: "Time Elapsed",
                    value: this.status.elapsed,
                    color: "text-slate-500",
                    subValue: `Started: ${this.status.start_time}`,
                },
                {
                    label: "Total Done",
                    value: `${totalDone}`,
                    color: "text-cyan-500",
                    subValue: `Target: ${n_trial} trials`,
                },
                {
                    label: this.status.is_complete ? "Finished" : "Est. Remaining",
                    value: remainingVal,
                    color: "text-slate-500",
                    subValue: finalETA,
                },
            ];
        },

        handleCompletion() {
            const celebrationKey = `mojo_celebrated_${this.status.n_done}`;
            if (sessionStorage.getItem(celebrationKey)) return;

            if (!Alpine.store('dojo').isMuted) {
                const audio = document.getElementById("chime");
                if (audio) audio.play().catch(() => { });
            }

            this.fireConfetti();

            sessionStorage.setItem(celebrationKey, "true");
        },

        fireConfetti() {
            const duration = 3 * 1000;
            const animationEnd = Date.now() + duration;
            const defaults = {
                startVelocity: 30,
                spread: 360,
                ticks: 60,
                zIndex: 1000,
            };
            const randomInRange = (min, max) => Math.random() * (max - min) + min;

            const interval = setInterval(function () {
                const timeLeft = animationEnd - Date.now();
                if (timeLeft <= 0) return clearInterval(interval);
                const particleCount = 50 * (timeLeft / duration);
                confetti({
                    ...defaults,
                    particleCount,
                    origin: { x: randomInRange(0.1, 0.3), y: Math.random() - 0.2 },
                    colors: ["#06b6d4", "#3b82f6", "#22c55e"],
                });
                confetti({
                    ...defaults,
                    particleCount,
                    origin: { x: randomInRange(0.7, 0.9), y: Math.random() - 0.2 },
                    colors: ["#06b6d4", "#3b82f6", "#22c55e"],
                });
            }, 250);
        },
    };
}
