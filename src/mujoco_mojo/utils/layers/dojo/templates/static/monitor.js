function monitor() {
    return {
        status: {
            n_done: 0, n_success: 0, n_failed: 0,
            success_tns: [], failure_tns: [], progress: 0,
            padding_style: "02d" // fallback
        },
        stats: [],
        hasInitialData: false,

        async init() {
            // listen for data updates from the global store
            window.addEventListener('mojo-data-updated', (e) => {
                this.handleDataUpdate(e.detail);
            });

            // 1. Initial bootstrap
            try {
                const resp = await fetch("/monitor/api/status");
                const data = await resp.json();

                if (data && !data.error) {
                    this.handleDataUpdate(data);
                    // update global store with the initial pulse
                    Alpine.store('dojo').updateSync(Date.now(), data.is_complete);
                }
            } catch (e) {
                console.warn("Monitor bootstrap failed.", e);
            } finally {
                // tell the global store to start the live pulse if needed
                Alpine.store('dojo').startGlobalSync();
                Alpine.store('dojo').setPageReady(true);
            }
        },

        handleDataUpdate(data) {
            this.status = data;
            this.hasInitialData = true;
            this.refreshStats();

            if (this.status.is_complete) {
                this.handleCompletion();
            }
        },

        refreshStats() {
            const totalDone = this.status.n_done || 0;
            const n_trial = this.status.n_trial || 1;
            const progress = ((totalDone / n_trial) * 100).toFixed(1);

            // update tab title with progress
            document.title = `${this.status.is_complete ? '✓' : '(' + progress + '%)'} Monitor | MuJoCo Mojo`;

            const successPerc = totalDone > 0 ? ((this.status.n_success / totalDone) * 100).toFixed(1) : 0;
            const failurePerc = totalDone > 0 ? ((this.status.n_failed / totalDone) * 100).toFixed(1) : 0;

            const lastSuccess = this.status.success_tns.length > 0 ? this.status.success_tns.slice(-1)[0] : "None";
            const lastFailure = this.status.failure_tns.length > 0 ? this.status.failure_tns.slice(-1)[0] : "None";

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
                    value: `${this.status.n_remaining} (${(100 - progress).toFixed(1)}%)`,
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
                    value: this.status.is_complete ? "00:00:00" : this.status.time_remaining,
                    color: "text-slate-500",
                    subValue: this.status.is_complete ? "Job Complete" : `ETA: ${this.status.end_time}`,
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
            const defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 1000 };
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
