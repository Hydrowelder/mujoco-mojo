import type { DojoStore, JobStatus, TimelineBin } from "./models";
import { themeColor } from "./lib/theme-colors";
import Plotly from "./lib/plotly";
import confetti from "canvas-confetti";
import { fetchWithRetry } from "./lib/fetch-timeout";
import { confettiPlan, confettiShots } from "./lib/confetti";
import {
  isNarrowTimeline,
  timelineLayout,
  timelineTraces,
  type TimelineColors,
} from "./lib/timeline";
import {
  celebrationKey,
  chimeChoice,
  completionNotification,
  holidayTheme,
  outcomeGradient,
  progressTitle,
  statCards,
  trialNotification,
  type HolidayTheme,
  type StatCard,
} from "./lib/monitor-stats";

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
        const resp = await fetchWithRetry("/monitor/api/status/job");
        const data = (await resp.json()) as JobStatus;
        if (data && !data.error) {
          const store = Alpine.store("dojo") as DojoStore;
          store.updateSync(Date.now(), data.is_complete);
          store.applyJobOutcomes(data);
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
        const note = trialNotification(prev, data);
        if (note) (Alpine.store("dojo") as DojoStore).addNotification(note.message, note.type);
      }
    },

    refreshStats() {
      document.title = progressTitle(this.status);
      this.stats = statCards(this.status);
    },

    // builds a single left-to-right gradient across the filled bar: solid
    // color in the middle of each outcome's share, soft blends at boundaries
    progressGradient(): string {
      return outcomeGradient([
        { color: themeColor("success"), n: this.status.n_success },
        { color: themeColor("danger"), n: this.status.n_failed },
        { color: themeColor("warning"), n: this.status.n_error },
      ]);
    },

    renderTimeline() {
      const bins: TimelineBin[] = this.status.timeline ?? [];
      const el = document.getElementById("timeline-chart");
      if (!el || bins.length === 0) return;

      // same tokens trial-viewer.ts's renderPlot() uses, so this chart's
      // chrome matches every other Plotly chart in the app instead of
      // improvising its own: --color-ink-muted at 15% alpha (the previous
      // approach here) is a light-to-medium gray in both themes, so blended
      // at low alpha over a dark chart it read as a pale, washed-out grid --
      // the opposite of --color-chart-grid-major/-minor's dedicated dark
      // values, which are deliberately darker than the surface so gridlines
      // sit recessed rather than glowing.
      const colors: TimelineColors = {
        font: themeColor("chart-text"),
        grid: themeColor("chart-grid-major"),
        success: themeColor("success"),
        danger: themeColor("danger"),
        warning: themeColor("warning"),
        info: themeColor("info"),
        accent: themeColor("accent-500"),
        tooltipBg: themeColor("chart-tooltip-bg"),
        tooltipFont: themeColor("chart-tooltip-font"),
      };
      const traces = timelineTraces(bins, colors);
      // on narrow screens the horizontal legend doesn't fit above the plot,
      // so move it below the x-axis where it can wrap freely
      const layout = timelineLayout(isNarrowTimeline(el.offsetWidth), colors);

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
      const celebKey = celebrationKey(this.status.start_time);
      if (localStorage.getItem(celebKey)) {
        this.hasCelebrated = true; // sync in-memory flag so future calls within this session are fast
        return;
      }
      localStorage.setItem(celebKey, "1");
      this.hasCelebrated = true;

      const store = Alpine.store("dojo") as DojoStore;
      const done = completionNotification(this.status);
      store.addNotification(done.message, done.type);
      const theme = this.getHolidayTheme();
      const chime = document.getElementById("chime") as HTMLAudioElement | null;
      // dojo.chime (settings.py) - a global, server-side enable/disable
      // distinct from isMuted's per-browser toggle below. Gates the
      // holiday sound too, not just the plain chime: from a user's
      // perspective "disable the chime" means no completion sound at all,
      // not "keep seasonal sounds but drop the default one."
      const chimeEnabled = chime?.dataset.chimeEnabled !== "false";

      const sound = chimeChoice(
        chimeEnabled,
        (Alpine.store("dojo") as DojoStore).isMuted,
        theme.audioUrl,
      );
      if (sound === "holiday") {
        const holidaySound = new Audio(theme.audioUrl);
        holidaySound.play().catch(() => chime?.play().catch(() => {}));
      } else if (sound === "default") {
        chime?.play().catch(() => {});
      }

      setTimeout(() => this.fireConfetti(theme), 300);
      this.hasCelebrated = true;
    },

    getHolidayTheme(): HolidayTheme {
      return holidayTheme(new Date());
    },

    fireConfetti(theme: HolidayTheme = { name: "Standard Mojo" }) {
      const plan = confettiPlan(theme);

      console.log(
        `%c 🎊 Mojo Celebration: ${plan.themeName} `,
        "background: #06b6d4; color: #fff; font-weight: bold; padding: 2px 4px; border-radius: 4px;",
      );

      const animationEnd = Date.now() + plan.duration;
      const colors = plan.colors;

      let shapes: confetti.Shape[] = ["circle", "square"];
      if (theme.emojis) {
        shapes = theme.emojis.map((emoji) =>
          confetti.shapeFromText({ text: emoji, scalar: 5, color: colors[0] }),
        );
      }

      const defaults = {
        zIndex: 1000,
        shapes,
        colors,
        ticks: plan.ticks,
        scalar: plan.scalar,
        gravity: plan.gravity,
      };

      const interval = setInterval(() => {
        const timeLeft = animationEnd - Date.now();
        if (timeLeft <= 0) {
          clearInterval(interval);
          return;
        }
        for (const shot of confettiShots(plan, timeLeft, Math.random)) {
          confetti({ ...defaults, ...shot });
        }
      }, plan.intervalMs);
    },
  };
}

window.monitor = monitor;
