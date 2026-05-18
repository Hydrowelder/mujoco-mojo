"use strict";
(() => {
  // src/monitor.ts
  function monitor() {
    return {
      status: {
        n_done: 0,
        n_success: 0,
        n_failed: 0,
        success_tns: [],
        failure_tns: [],
        progress: 0,
        padding_style: "02d"
      },
      stats: [],
      hasInitialData: false,
      hasCelebrated: false,
      async init() {
        window.addEventListener("mojo-data-updated", (e) => {
          this.handleDataUpdate(e.detail);
        });
        try {
          const resp = await fetch("/monitor/api/status");
          const data = await resp.json();
          if (data && !data.error) {
            Alpine.store("dojo").updateSync(Date.now(), data.is_complete);
            this.handleDataUpdate(data);
          }
        } catch (e) {
          console.warn("Monitor bootstrap failed.", e);
        } finally {
          const store = Alpine.store("dojo");
          store.startGlobalSync();
          store.setPageReady(true, this.status.is_complete);
        }
      },
      handleDataUpdate(data) {
        this.status = data;
        this.hasInitialData = true;
        this.refreshStats();
        if (this.status.is_complete) this.handleCompletion();
      },
      refreshStats() {
        const totalDone = this.status.n_done || 0;
        const n_trial = this.status.n_trial || 1;
        const progress = (totalDone / n_trial * 100).toFixed(1);
        document.title = `${this.status.is_complete ? "\u2713" : `(${progress}%)`} Monitor | MuJoCo Mojo`;
        const successPerc = totalDone > 0 ? (this.status.n_success / totalDone * 100).toFixed(1) : 0;
        const failurePerc = totalDone > 0 ? (this.status.n_failed / totalDone * 100).toFixed(1) : 0;
        const lastSuccess = this.status.success_tns.length > 0 ? this.status.success_tns.slice(-1)[0] : "None";
        const lastFailure = this.status.failure_tns.length > 0 ? this.status.failure_tns.slice(-1)[0] : "None";
        this.stats = [
          {
            label: "Successes",
            value: `${this.status.n_success} (${successPerc}%)`,
            color: "text-emerald-500",
            subValue: `Last Success: Trial ${lastSuccess}`
          },
          {
            label: "Failures",
            value: `${this.status.n_failed} (${failurePerc}%)`,
            color: "text-rose-500",
            subValue: `Last Failure: Trial ${lastFailure}`
          },
          {
            label: "Remaining",
            value: `${this.status.n_remaining} (${(100 - Number(progress)).toFixed(1)}%)`,
            color: "text-amber-500",
            subValue: `${this.status.throughput} trials/min (${this.status.avg_duration} per trial)`
          },
          {
            label: "Time Elapsed",
            value: this.status.elapsed,
            color: "text-slate-500",
            subValue: `Started: ${this.status.start_time}`
          },
          {
            label: "Total Done",
            value: `${totalDone}`,
            color: "text-cyan-500",
            subValue: `Target: ${n_trial} trials`
          },
          {
            label: this.status.is_complete ? "Finished" : "Est. Remaining",
            value: this.status.is_complete ? "00:00:00" : this.status.time_remaining,
            color: "text-slate-500",
            subValue: this.status.is_complete ? "Job Complete" : `ETA: ${this.status.end_time}`
          }
        ];
      },
      handleCompletion() {
        if (this.hasCelebrated) return;
        const theme = this.getHolidayTheme();
        const chime = document.getElementById("chime");
        if (!Alpine.store("dojo").isMuted) {
          if (theme.audioUrl) {
            const holidaySound = new Audio(theme.audioUrl);
            holidaySound.play().catch(() => chime?.play().catch(() => {
            }));
          } else {
            chime?.play().catch(() => {
            });
          }
        }
        setTimeout(() => this.fireConfetti(theme), 300);
        this.hasCelebrated = true;
      },
      getHolidayTheme() {
        const now = /* @__PURE__ */ new Date();
        const m = now.getMonth();
        const d = now.getDate();
        if (m === 11 && d === 31 || m === 0 && d <= 2) {
          return { name: "New Year", emojis: ["\u{1F386}", "\u2728", "\u{1F942}"], colors: ["#ffcc00", "#ffffff"] };
        }
        if (m === 2 && d === 14) {
          return { name: "Pi Day", emojis: ["\u03C0", "\u{1F967}"], colors: ["#ff9900"] };
        }
        if (m === 2 && d === 17) {
          return { name: "St. Patrick's Day", emojis: ["\u{1F340}", "\u{1F308}"], colors: ["#22c55e", "#166534"] };
        }
        if (m === 4 && d === 4) {
          return { name: "May the 4th", emojis: ["\u2694\uFE0F", "\u{1F30C}", "\u2728"], colors: ["#FFE81F", "#2dd4bf"] };
        }
        if (m === 9 && d >= 25 || m === 10 && d === 1) {
          return { name: "Halloween", emojis: ["\u{1F383}", "\u{1F47B}", "\u{1F987}"], colors: ["#ff6600", "#9437ff"] };
        }
        if (m === 11 || m === 0 && d <= 15) {
          return { name: "Winter Snow", emojis: ["\u2744\uFE0F", "\u26C4", "\u{1F328}\uFE0F"], isSnow: true };
        }
        return { name: "Standard Mojo", colors: ["#06b6d4", "#3b82f6", "#22c55e"] };
      },
      fireConfetti(theme = { name: "Standard Mojo" }) {
        const themeName = theme.name ?? "Standard Mojo";
        const isSpecial = !!theme.emojis;
        const isSnow = theme.isSnow ?? false;
        console.log(
          `%c \u{1F38A} Mojo Celebration: ${themeName} `,
          "background: #06b6d4; color: #fff; font-weight: bold; padding: 2px 4px; border-radius: 4px;"
        );
        const duration = 3e3;
        const animationEnd = Date.now() + duration;
        const colors = theme.colors ?? ["#06b6d4", "#3b82f6", "#22c55e"];
        let shapes = ["circle", "square"];
        if (theme.emojis) {
          shapes = theme.emojis.map(
            (emoji) => confetti.shapeFromText({ text: emoji, scalar: 5, color: colors[0] })
          );
        }
        const defaults = {
          zIndex: 1e3,
          shapes,
          colors,
          ticks: isSpecial ? 200 : 100,
          scalar: isSpecial ? 5 : 1,
          gravity: isSnow ? 0.4 : isSpecial ? 0.4 : 1.2
        };
        const interval = setInterval(() => {
          const timeLeft = animationEnd - Date.now();
          if (timeLeft <= 0) {
            clearInterval(interval);
            return;
          }
          if (isSnow) {
            confetti({ ...defaults, particleCount: 1, startVelocity: 0, drift: (Math.random() - 0.5) * 1.5, origin: { x: Math.random(), y: -0.2 } });
          } else {
            const countMultiplier = isSpecial ? 40 : 150;
            const particleCount = countMultiplier * (timeLeft / duration);
            for (let i = 0; i < 3; i++) {
              confetti({ ...defaults, particleCount: Math.ceil(particleCount / 3), spread: isSpecial ? 90 : 360, startVelocity: isSpecial ? 15 : 45, origin: { x: Math.random(), y: Math.random() - 0.2 } });
            }
          }
        }, isSpecial ? 400 : 250);
      }
    };
  }
  window.monitor = monitor;
})();
//# sourceMappingURL=monitor.js.map
