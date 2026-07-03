import type { DojoStore, JobStatus, TimelineBin } from "./models";

interface StatCard {
  label: string;
  value: string;
  color: string;
  subValue: string;
  tooltip: string;
}

interface HolidayTheme {
  name: string;
  emojis?: string[];
  colors?: string[];
  isSnow?: boolean;
  audioUrl?: string;
}

function monitor() {
  return {
    status: {
      n_done: 0,
      n_success: 0,
      n_failed: 0,
      n_error: 0,
      success_tns: [] as string[],
      failure_tns: [] as string[],
      error_tns: [] as string[],
      failure_tns_with_db: [] as string[],
      error_tns_with_db: [] as string[],
      progress: 0,
      padding_style: "02d",
    } as JobStatus,
    prevStatus: { n_done: 0, n_success: 0, n_failed: 0, n_error: 0 },
    stats: [] as StatCard[],
    hasInitialData: false,
    hasCelebrated: false,

    async init() {
      window.addEventListener("mojo-data-updated", (e) => {
        this.handleDataUpdate((e as CustomEvent<JobStatus>).detail);
      });

      // re-render the timeline with the new palette when dark mode toggles,
      // instead of waiting for the next data tick
      const themeObserver = new MutationObserver((mutations) => {
        if (mutations.some((m) => m.attributeName === "class")) {
          this.renderTimeline();
        }
      });
      themeObserver.observe(document.documentElement, { attributes: true });

      // re-render on resize so the legend placement can switch between the
      // wide and narrow layouts (plotly's responsive flag only rescales)
      let resizeTimer: ReturnType<typeof setTimeout> | null = null;
      window.addEventListener("resize", () => {
        if (resizeTimer) clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => this.renderTimeline(), 200);
      });

      try {
        const resp = await fetch("/monitor/api/status/job");
        const data = (await resp.json()) as JobStatus;
        if (data && !data.error) {
          (Alpine.store("dojo") as DojoStore).updateSync(
            Date.now(),
            data.is_complete,
          );
          this.handleDataUpdate(data);
        }
      } catch (e) {
        console.warn("Monitor bootstrap failed.", e);
      } finally {
        const store = Alpine.store("dojo") as DojoStore;
        store.startGlobalSync();
        store.setPageReady(
          true,
          (this.status as JobStatus & { is_complete?: boolean }).is_complete,
        );
      }
    },

    handleDataUpdate(data: JobStatus) {
      const wasInit = this.hasInitialData;
      const prev = { ...this.prevStatus } as {
        n_done: number;
        n_success: number;
        n_failed: number;
        n_error: number;
      };
      this.prevStatus = {
        n_done: data.n_done,
        n_success: data.n_success,
        n_failed: data.n_failed,
        n_error: data.n_error,
      };
      this.status = data;
      this.hasInitialData = true;
      this.refreshStats();
      this.renderTimeline();

      if (this.status.is_complete) {
        this.handleCompletion();
      } else if (wasInit) {
        const newDone = data.n_done - prev.n_done;
        if (newDone > 0) {
          const newFailed = data.n_failed - prev.n_failed;
          const newError = data.n_error - prev.n_error;
          const store = Alpine.store("dojo") as DojoStore;
          if (newDone === 1) {
            let verb = "succeeded";
            let trialId = data.success_tns.at(-1);
            if (newError === 1) {
              verb = "errored";
              trialId = data.error_tns.at(-1);
            } else if (newFailed === 1) {
              verb = "failed requirements";
              trialId = data.failure_tns.at(-1);
            }
            store.addNotification(
              `Trial ${trialId} ${verb}`,
              verb === "succeeded" ? "success" : "error",
            );
          } else {
            const newOk = newDone - newFailed - newError;
            store.addNotification(
              `${newDone} trials done - ${newOk} ok, ${newFailed} failed, ${newError} errored`,
              newFailed + newError > 0 ? "error" : "success",
            );
          }
        }
      }
    },

    refreshStats() {
      const totalDone = this.status.n_done || 0;
      const n_trial = this.status.n_trial || 1;
      const progress = ((totalDone / n_trial) * 100).toFixed(1);

      document.title = `${this.status.is_complete ? "✓" : `(${progress}%)`} Monitor | MuJoCo Mojo`;

      const pctOfTotal = (n: number) => ((n / n_trial) * 100).toFixed(1);

      const lastSuccess = this.status.last_success_tn ?? "None";
      const lastFailure = this.status.last_failure_tn ?? "None";
      const lastError = this.status.last_error_tn ?? "None";

      this.stats = [
        {
          label: "Successes",
          value: `${this.status.n_success} (${pctOfTotal(this.status.n_success)}%)`,
          color: "text-emerald-500",
          subValue: `Last Success: Trial ${lastSuccess}`,
          tooltip: `Trials that completed and passed every registered requirement (or had none). Percentage is of all ${n_trial} trials.`,
        },
        {
          label: "Failures",
          value: `${this.status.n_failed} (${pctOfTotal(this.status.n_failed)}%)`,
          color: "text-rose-500",
          subValue: `Last Failure: Trial ${lastFailure}`,
          tooltip:
            "Trials that ran but failed one or more requirement checks, including early terminations triggered by a failing requirement. Not runtime errors.",
        },
        {
          label: "Errors",
          value: `${this.status.n_error} (${pctOfTotal(this.status.n_error)}%)`,
          color: "text-amber-500",
          subValue: `Last Error: Trial ${lastError}`,
          tooltip:
            "Trials that raised an unhandled runtime error while being processed. These runs broke; they were never judged against requirements.",
        },
        {
          label: "Time Elapsed",
          value: this.status.elapsed,
          color: "text-slate-500",
          subValue: `Started: ${this.status.start_time}`,
          tooltip: "Wall-clock time since the job started.",
        },
        {
          label: "Remaining",
          value: `${this.status.n_remaining} (${pctOfTotal(this.status.n_remaining)}%)`,
          color: "text-cyan-500",
          subValue: `${this.status.throughput} trials/min - ${n_trial} trials total`,
          tooltip:
            "Trials that have not finished yet. Throughput is derived from the average duration of completed trials (successes and failures; errors excluded) and the number of processors.",
        },
        {
          label: this.status.is_complete ? "Finished" : "Est. Remaining",
          value: this.status.is_complete
            ? "00:00:00"
            : this.status.time_remaining,
          color: "text-slate-500",
          subValue: this.status.is_complete
            ? `Finished: ${this.status.end_time}`
            : `ETA: ${this.status.end_time}`,
          tooltip: this.status.is_complete
            ? "The job has finished. Shows the local time at which the job completed."
            : "Estimated wall-clock time until all trials finish, based on the average completed-trial duration (errors excluded). ETA is the projected local completion time.",
        },
      ];
    },

    // builds a single left-to-right gradient across the filled bar: solid
    // color in the middle of each outcome's share, soft blends at boundaries
    progressGradient(): string {
      const segs = [
        { color: "#10b981", n: this.status.n_success }, // emerald-500
        { color: "#f43f5e", n: this.status.n_failed }, // rose-500
        { color: "#f59e0b", n: this.status.n_error }, // amber-500
      ].filter((seg) => seg.n > 0);
      if (segs.length === 0) return "transparent";
      if (segs.length === 1) return segs[0].color;

      const total = segs.reduce((sum, seg) => sum + seg.n, 0);
      const blend = 5; // half-width of each blend zone, in % of the filled bar
      const stops: string[] = [];
      let acc = 0;
      segs.forEach((seg, i) => {
        const start = (acc / total) * 100;
        acc += seg.n;
        const end = (acc / total) * 100;
        const mid = (start + end) / 2;
        const lo = i === 0 ? 0 : Math.min(start + blend, mid);
        const hi = i === segs.length - 1 ? 100 : Math.max(end - blend, mid);
        stops.push(`${seg.color} ${lo.toFixed(2)}%`, `${seg.color} ${hi.toFixed(2)}%`);
      });
      return `linear-gradient(to right, ${stops.join(", ")})`;
    },

    renderTimeline() {
      const bins: TimelineBin[] = this.status.timeline ?? [];
      const el = document.getElementById("timeline-chart");
      if (!el || bins.length === 0) return;

      const x = bins.map((b) => b.label);
      const dark = document.documentElement.classList.contains("dark");
      const fontColor = dark ? "#94a3b8" : "#64748b"; // slate-400 / slate-500
      const gridColor = dark
        ? "rgba(148, 163, 184, 0.15)"
        : "rgba(100, 116, 139, 0.15)";

      const traces = [
        {
          name: "Success",
          x,
          y: bins.map((b) => b.n_success),
          type: "bar",
          marker: { color: "#10b981" },
        },
        {
          name: "Failure",
          x,
          y: bins.map((b) => b.n_failed),
          type: "bar",
          marker: { color: "#f43f5e" },
        },
        {
          name: "Error",
          x,
          y: bins.map((b) => b.n_error),
          type: "bar",
          marker: { color: "#f59e0b" },
        },
        {
          name: "Running",
          x,
          y: bins.map((b) => b.n_running),
          type: "bar",
          marker: { color: "#6366f1" }, // indigo-500
        },
        {
          name: "Pending",
          x,
          y: bins.map((b) => b.n_pending),
          type: "bar",
          marker: { color: "#06b6d4" }, // cyan-500
        },
      ];

      // on narrow screens the horizontal legend doesn't fit above the plot,
      // so move it below the x-axis where it can wrap freely
      const narrow = el.offsetWidth > 0 && el.offsetWidth < 560;

      const layout = {
        autosize: true,
        barmode: "stack",
        bargap: 0.15,
        margin: { l: 45, r: 10, t: 10, b: narrow ? 110 : 55 },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: fontColor, family: "monospace", size: 11 },
        xaxis: {
          // bin labels carry microsecond precision so distinct bins never
          // collide onto the same x position; force a real date axis (rather
          // than letting plotly infer a categorical string axis) and control
          // the tick format so it still reads as a plain clock time
          type: "date",
          tickformat: "%H:%M:%S",
          gridcolor: gridColor,
          tickangle: -45,
          nticks: 8,
          showspikes: true,
          spikemode: "across",
          spikelinecolor: "#06b6d4", // cyan-500, same as the trial viewer
          spikethickness: -2,
        },
        yaxis: { gridcolor: gridColor, title: { text: "trials" } },
        legend: narrow
          ? { orientation: "h", x: 0.5, xanchor: "center", y: -0.45, yanchor: "top", font: { size: 10 } }
          : { orientation: "h", y: 1.15, x: 0 },
        hovermode: "x unified",
        hoverlabel: {
          bgcolor: dark ? "#0f172a" : "#ffffff", // slate-900 / white
          bordercolor: "#06b6d4", // cyan-500
          font: {
            color: dark ? "#f8fafc" : "#0f172a", // slate-50 / slate-900
            family: "monospace",
            size: 12,
          },
          align: "left",
        },
        showlegend: true,
      };

      // defer one frame so the x-show'd container has a real width before
      // plotly measures it, then force a resize in case it was still hidden
      // (plotly falls back to a fixed 700px width when it measures 0)
      requestAnimationFrame(() => {
        void Plotly.react(el, traces, layout, {
          displayModeBar: false,
          responsive: true,
        }).then(() => {
          if (el.offsetWidth > 0) Plotly.Plots.resize(el);
        });
      });
    },

    handleCompletion() {
      if (this.hasCelebrated) return;

      // Use localStorage so the notification only fires once per job across all page navigations.
      // The key is the job's start_time - unique per job run.
      const celebKey = `mojo_celebrated_${this.status.start_time}`;
      if (localStorage.getItem(celebKey)) {
        this.hasCelebrated = true; // sync in-memory flag so future calls within this session are fast
        return;
      }
      localStorage.setItem(celebKey, "1");
      this.hasCelebrated = true;

      const store = Alpine.store("dojo") as DojoStore;
      store.addNotification(
        `Job complete in ${this.status.elapsed} - ${this.status.n_success} succeeded, ${this.status.n_failed} failed, ${this.status.n_error} errored`,
        this.status.n_failed + this.status.n_error > 0 ? "error" : "success",
      );
      const theme = this.getHolidayTheme();
      const chime = document.getElementById("chime") as HTMLAudioElement | null;

      if (!(Alpine.store("dojo") as DojoStore).isMuted) {
        if (theme.audioUrl) {
          const holidaySound = new Audio(theme.audioUrl);
          holidaySound.play().catch(() => chime?.play().catch(() => {}));
        } else {
          chime?.play().catch(() => {});
        }
      }

      setTimeout(() => this.fireConfetti(theme), 300);
      this.hasCelebrated = true;
    },

    getHolidayTheme(): HolidayTheme {
      const now = new Date();
      const m = now.getMonth();
      const d = now.getDate();

      if ((m === 11 && d === 31) || (m === 0 && d <= 2)) {
        return {
          name: "New Year",
          emojis: ["🎆", "✨", "🥂"],
          colors: ["#ffcc00", "#ffffff"],
        };
      }
      if (m === 2 && d === 14) {
        return { name: "Pi Day", emojis: ["π", "🥧"], colors: ["#ff9900"] };
      }
      if (m === 2 && d === 17) {
        return {
          name: "St. Patrick's Day",
          emojis: ["🍀", "🌈"],
          colors: ["#22c55e", "#166534"],
        };
      }
      if (m === 4 && d === 4) {
        return {
          name: "May the 4th",
          emojis: ["⚔️", "🌌", "✨"],
          colors: ["#FFE81F", "#2dd4bf"],
        };
      }
      if ((m === 9 && d >= 25) || (m === 10 && d === 1)) {
        return {
          name: "Halloween",
          emojis: ["🎃", "👻", "🦇"],
          colors: ["#ff6600", "#9437ff"],
        };
      }
      if (m === 11 || (m === 0 && d <= 15)) {
        return {
          name: "Winter Snow",
          emojis: ["❄️", "⛄", "🌨️"],
          isSnow: true,
        };
      }
      return {
        name: "Standard Mojo",
        colors: ["#06b6d4", "#3b82f6", "#22c55e"],
      };
    },

    fireConfetti(theme: HolidayTheme = { name: "Standard Mojo" }) {
      const themeName = theme.name ?? "Standard Mojo";
      const isSpecial = !!theme.emojis;
      const isSnow = theme.isSnow ?? false;

      console.log(
        `%c 🎊 Mojo Celebration: ${themeName} `,
        "background: #06b6d4; color: #fff; font-weight: bold; padding: 2px 4px; border-radius: 4px;",
      );

      const duration = 3000;
      const animationEnd = Date.now() + duration;
      const colors = theme.colors ?? ["#06b6d4", "#3b82f6", "#22c55e"];

      let shapes: unknown[] = ["circle", "square"];
      if (theme.emojis) {
        shapes = theme.emojis.map((emoji) =>
          confetti.shapeFromText({ text: emoji, scalar: 5, color: colors[0] }),
        );
      }

      const defaults = {
        zIndex: 1000,
        shapes,
        colors,
        ticks: isSpecial ? 200 : 100,
        scalar: isSpecial ? 5 : 1,
        gravity: isSnow ? 0.4 : isSpecial ? 0.4 : 1.2,
      };

      const interval = setInterval(
        () => {
          const timeLeft = animationEnd - Date.now();
          if (timeLeft <= 0) {
            clearInterval(interval);
            return;
          }

          if (isSnow) {
            confetti({
              ...defaults,
              particleCount: 1,
              startVelocity: 0,
              drift: (Math.random() - 0.5) * 1.5,
              origin: { x: Math.random(), y: -0.2 },
            });
          } else {
            const countMultiplier = isSpecial ? 40 : 150;
            const particleCount = countMultiplier * (timeLeft / duration);
            for (let i = 0; i < 3; i++) {
              confetti({
                ...defaults,
                particleCount: Math.ceil(particleCount / 3),
                spread: isSpecial ? 90 : 360,
                startVelocity: isSpecial ? 15 : 45,
                origin: { x: Math.random(), y: Math.random() - 0.2 },
              });
            }
          }
        },
        isSpecial ? 400 : 250,
      );
    },
  };
}

window.monitor = monitor;
