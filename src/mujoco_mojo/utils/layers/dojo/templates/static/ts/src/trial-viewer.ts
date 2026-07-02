import { breakableLabel, formatNum } from "./lib/format";
import { OPTIONS } from "./lib/options";
import { DASH_STYLE_VALUES, PLOT_CONFIG_SCHEMA } from "./lib/plot-config.generated";
import { attachVerticalResizeHandle, restorePersistedHeight } from "./lib/resize";
import { validateAgainstSchema } from "./lib/schema-validate";
import { createToastMixin } from "./lib/toast";
import type { AlpineMagics } from "./types/global";
import type {
  Annotation,
  DashStyle,
  DistEntry,
  DistsResponse,
  DojoStore,
  FilterEntry,
  FilterSchema,
  LogEntry,
  PlotConfig,
  Shape,
  TrialDataResponse,
  TrialLogsResponse,
  TrialManifest,
  TrialMediaFile,
  TrialMediaResponse,
  TrialStatus,
  UnitGroup,
  YAxisConfig,
} from "./models";

// ---------------------------------------------------------------------------
// Tailwind offline palette - hex values matching Tailwind CSS defaults
// ---------------------------------------------------------------------------
const tw = {
  slate: {
    50: "#f8fafc",
    100: "#f1f5f9",
    200: "#e2e8f0",
    300: "#cbd5e1",
    400: "#94a3b8",
    500: "#64748b",
    600: "#475569",
    700: "#334155",
    800: "#1e293b",
    900: "#0f172a",
    950: "#020617",
  },
  cyan: { 400: "#22d3ee", 500: "#06b6d4", 600: "#0891b2" },
  emerald: { 500: "#10b981" },
  blue: { 500: "#3b82f6" },
  violet: { 500: "#8b5cf6" },
  amber: { 500: "#f59e0b" },
  rose: { 500: "#ef4444" },
} as const;

// matches Python's logging severity ordering
const LOG_LEVEL_SEVERITY: Record<string, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40,
  CRITICAL: 50,
};

const DEFAULT_CONFIG: PlotConfig = {
  xAxis: { col: "time", filters: [] },
  yAxes: {},
  refFrame: null,
  grid: "all",
  lineMode: "lines+markers",
  interp: "linear",
  hover: "closest",
  title: "",
  xAxisTitle: "",
  yAxisTitle: "",
  showSpike: true,
  legendPos: "bottom",
  rangeX: null,
  rangeY: null,
  xScale: "linear",
  yScale: "linear",
  plotType: "cartesian",
  vsEnabled: false,
  vsRange: [0, 10],
  vsPinned: [],
  annotations: [],
  shapes: [],
  maxPoints: null,
};

// ---------------------------------------------------------------------------
// CodeMirror editor state (kept outside Alpine to avoid proxy issues)
// ---------------------------------------------------------------------------
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _cm: {
  editor: any;
  updating: boolean;
  debounce: ReturnType<typeof setTimeout> | null;
} = {
  editor: null,
  updating: false,
  debounce: null,
};

// miniplayer RAF state - kept outside Alpine to avoid proxy overhead
const _mini: { rafId: number | null } = { rafId: null };

// ---------------------------------------------------------------------------
// Lab tab state
// ---------------------------------------------------------------------------
interface LabTab {
  id: string;
  name: string;
  graph: object | null;
  savedState: string | null; // JSON of the graph at last save/load; null = never saved
  dirty: boolean;
  viewport: { scale: number; offset: [number, number] } | null; // remembered pan/zoom
}

// ---------------------------------------------------------------------------
// Component factory
// ---------------------------------------------------------------------------
function trialViewer(trialId: string, externalUrl: string) {
  const self = {
    // Alpine magic (injected at runtime - declared here for TS)
    ...(null as unknown as AlpineMagics),

    // --- BASE STATE ---
    trialId,
    externalUrl,
    warpId: null as number | null,
    paddingLen: 2,
    loading: true,
    isMac: /Mac|iPhone|iPod|iPad/.test(navigator.platform),
    data: null as Record<string, number[]> | null,
    errorState: null as string | null,
    _renderedPlotType: null as string | null,

    // --- UI / MENU STATES ---
    theme: "dark",
    xMenuOpen: false,
    xSearch: "",
    yMenuOpen: false,
    ySearch: "",
    refFrameMenuOpen: false,
    settingsOpen: false,
    downloadOpen: false,
    activeFrame: null as string | null,
    dragCounter: 0,
    editorOpen: false,
    columns: [] as string[],
    rotateableVectors: [] as string[],
    columnMetadata: {} as Record<string, Record<string, string>>,
    discoveryId: 0,
    plotColors: [
      tw.cyan[500],
      tw.emerald[500],
      tw.blue[500],
      tw.violet[500],
      tw.amber[500],
      tw.rose[500],
    ],
    dashStyles: DASH_STYLE_VALUES,

    // Toast (shared mixin)
    ...createToastMixin(),

    // Options - exposed so templates can use opts.lineMode, opts.interpLabel(...), etc.
    opts: OPTIONS,

    // --- PLOT CONFIGURATION ---
    config: JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as PlotConfig,

    // --- JSON EDITOR STATE ---
    configRaw: "",
    isValidJson: true,
    isValidConfig: true,
    configErrors: [] as string[],
    isEditingRaw: false,

    // --- PROFILES ---
    profiles: [] as Array<{ name: string; modified: number }>,
    profileWarnings: {} as Record<string, string[]>,
    profileSearch: localStorage.getItem("mojo:profile:search") ?? "",
    profilesOpen: false,
    profileNameDraft: "",

    // --- FILTER SCHEMAS (loaded from /mosaic/api/filter-schema on init) ---
    filterSchemas: [] as FilterSchema[],
    // tracks the last filter fingerprint that was fetched for each col; used to detect
    // real filter changes without relying on Alpine.js's (unreliable) oldValue deep clone
    filterFingerprints: {} as Record<string, string>,
    xAxisFilterFingerprint: "[]" as string,
    // deduplicates filter error toasts so VS mode (N parallel fetches) shows each error once
    _shownFilterErrors: new Set<string>(),
    // in-progress signal editor edits that survive closing/reopening the panel
    signalDrafts: {} as Record<
      string,
      { draft: YAxisConfig; baseSnapshot: string }
    >,

    // --- MATCHUP STATE ---
    vsDatasets: {} as Record<string, Record<string, number[]>>,
    allTrials: [] as string[],
    vsMenuOpen: false,
    vsLoading: false,
    vsDraft: { enabled: false, range: [0, 0] as [number, number], pinned: [] as number[] },
    discoveryTimeout: null as ReturnType<typeof setTimeout> | null,

    // --- HISTORY STATE ---
    historyStack: [] as string[],
    historyIndex: -1,
    isUndoing: false,
    maxHistory: 50,

    // --- ANNOTATIONS ---
    annotationsOpen: false,
    annDraft: null as Annotation | null,
    annEditIndex: null as number | null,

    // --- FILTER LAB ---
    labOpen: localStorage.getItem("mojo:lab:open") === "1",
    labGraph: null as object | null,
    labName: "" as string,
    labTabs: [] as LabTab[],
    labActiveTabId: null as string | null,
    nodePickingColumn: null as number | null,
    nodeColSearch: "" as string,
    nodePickingQuat: null as number | null,
    nodeQuatSearch: "" as string,
    nodePickingTemplate: null as number | null,
    labSchemas: [] as Array<{
      name: string;
      signal_in_columns: string[];
      outputs: string[];
      modified: number;
      valid: boolean;
      missing: string[];
      is_template: boolean;
      template_inputs: string[];
      template_outputs: string[];
    }>,

    // --- SHAPES ---
    shapesOpen: false,
    placementMode: null as "vline" | "hline" | "rect" | null,
    rectStart: null as { x: number; y: number } | null,
    shapeDraft: null as Shape | null,
    shapeEditIndex: null as number | null,

    // --- TRIAL STATUS ---
    trialStatus: null as TrialStatus | null,
    _trialStatusPoll: null as ReturnType<typeof setTimeout> | null,

    // --- DISTRIBUTIONS ---
    dists: [] as DistEntry[],
    _distTooltipEntry: null as DistEntry | null,
    distFilterName: ((): string => {
      try { return localStorage.getItem("mojo:dists:filter-name") ?? ""; } catch { return ""; }
    })(),
    // null = no filter applied (all pass); a (possibly empty) array is an
    // explicit selection, so deselecting every item shows zero rows instead
    // of silently falling back to "all"
    distFilterCategories: ((): string[] | null => {
      try {
        const v = localStorage.getItem("mojo:dists:filter-categories");
        return v === null ? null : (JSON.parse(v) as string[] | null);
      } catch { return null; }
    })(),
    distFilterTypes: ((): string[] | null => {
      try {
        const v = localStorage.getItem("mojo:dists:filter-types");
        return v === null ? null : (JSON.parse(v) as string[] | null);
      } catch { return null; }
    })(),
    distFilterUnits: ((): string[] | null => {
      try {
        const v = localStorage.getItem("mojo:dists:filter-units");
        return v === null ? null : (JSON.parse(v) as string[] | null);
      } catch { return null; }
    })(),
    distSortKey: "name" as
      | "name"
      | "category"
      | "dist_type"
      | "nominal"
      | "sampled_value"
      | "stat",
    distSortAsc: true,
    distColWidths: ((): Record<
      "name" | "category" | "dist_type" | "units" | "nominal" | "sampled",
      number
    > => {
      try {
        const saved = localStorage.getItem("mojo:dists:col-widths");
        if (saved) return JSON.parse(saved);
      } catch {
        // ignore malformed storage
      }
      return {
        name: 180,
        category: 100,
        dist_type: 148,
        units: 70,
        nominal: 88,
        sampled: 88,
      };
    })(),

    // --- TRIAL LOGS ---
    logFilename: null as string | null,
    logEntries: [] as LogEntry[],
    logSortKey: "timestamp" as "timestamp" | "level",
    logSortAsc: true,
    logFilterLevels: [] as string[], // empty = all levels
    logLevelMenuOpen: false,
    logFilterMessage: "" as string,
    logFilterRegex: false,
    logColWidths: ((): Record<"time" | "level" | "source", number> => {
      try {
        const saved = localStorage.getItem("mojo:trial-logs:col-widths");
        if (saved) return JSON.parse(saved);
      } catch {
        // ignore malformed storage
      }
      return { time: 176, level: 96, source: 160 };
    })(),
    _logColResize: null as { col: "time" | "level" | "source" } | null,
    _logMeasureCanvas: null as HTMLCanvasElement | null,

    // --- MEDIA PLAYER ---
    mediaFiles: [] as string[],
    selectedMedia: null as string | null,
    mediaScrubMode: (localStorage.getItem("mojo:media:mode") ?? "play") as
      | "play"
      | "scrub",
    mediaShowLine: localStorage.getItem("mojo:media:show-line") === "1",
    mediaShowFrames: localStorage.getItem("mojo:media:show-frames") === "1",
    mediaPlaybackRate: Number(localStorage.getItem("mojo:media:rate")) || 1,
    mediaSpeedPresets: [0.2, 0.5, 1.0, 2.0, 4.0] as number[],
    mediaMiniplayerOpen: localStorage.getItem("mojo:media:mini") === "1",
    mediaIsScrubbable: false,
    _gifConvertStatus: "none" as "none" | "loading" | "ready" | "failed",
    _mediaRafId: null as number | null,
    _mediaFpsMap: {} as Record<string, number | null>,
    _mediaMtimeMap: {} as Record<string, number>,
    _mediaFrameInterval: null as number | null,

    // -----------------------------------------------------------------------
    // History
    // -----------------------------------------------------------------------
    pushHistory() {
      if (this.isUndoing) return;
      const snapshot = JSON.stringify(this.config);
      if (this.historyStack[this.historyIndex] === snapshot) return;
      this.historyStack = this.historyStack.slice(0, this.historyIndex + 1);
      this.historyStack.push(snapshot);
      if (this.historyStack.length > this.maxHistory) this.historyStack.shift();
      this.historyIndex = this.historyStack.length - 1;
      this.persistHistory();
    },

    undo() {
      if (this.historyIndex > 0) {
        this.isUndoing = true;
        this.historyIndex--;
        this.config = JSON.parse(
          this.historyStack[this.historyIndex] ?? "{}",
        ) as PlotConfig;
        this.persistHistory();
        void this.$nextTick(() => {
          this.isUndoing = false;
        });
        this.notify("Undo", "info");
      }
    },

    redo() {
      if (this.historyIndex < this.historyStack.length - 1) {
        this.isUndoing = true;
        this.historyIndex++;
        this.config = JSON.parse(
          this.historyStack[this.historyIndex] ?? "{}",
        ) as PlotConfig;
        this.persistHistory();
        void this.$nextTick(() => {
          this.isUndoing = false;
        });
        this.notify("Redo", "info");
      }
    },

    persistHistory() {
      localStorage.setItem(
        "mojo_mosaic_history",
        JSON.stringify({ stack: this.historyStack, index: this.historyIndex }),
      );
    },

    shiftY(index: number, direction: number, isWarp = false) {
      const keys = Object.keys(this.config.yAxes);
      if (keys.length < 2) return;
      const newKeys = [...keys];
      const movedKey = newKeys.splice(index, 1)[0]!;
      if (isWarp) {
        direction === -1 ? newKeys.unshift(movedKey) : newKeys.push(movedKey);
      } else {
        newKeys.splice(index + direction, 0, movedKey);
      }
      const newYAxes: Record<string, YAxisConfig> = {};
      newKeys.forEach((k) => {
        newYAxes[k] = this.config.yAxes[k]!;
      });
      this.config.yAxes = newYAxes;
      this.saveAndRender();
    },

    // -----------------------------------------------------------------------
    // Data fetching
    // -----------------------------------------------------------------------
    async fetchTrialData(
      id: string,
      requiredCols: string[] = [],
    ): Promise<TrialDataResponse> {
      let url = `/mosaic/${id}/data`;
      const colParams = new URLSearchParams();
      if (requiredCols.length > 0)
        colParams.append("cols", requiredCols.join(","));

      // include active filter stacks for requested columns (x-axis and y-axes)
      const filtersPayload: Record<string, object[]> = {};
      const toActiveFilters = (
        filters: { enabled?: boolean; [k: string]: unknown }[],
      ) =>
        filters
          .filter((f) => f.enabled !== false)
          .map((f) =>
            Object.fromEntries(
              Object.entries(f).filter(([k]) => k !== "enabled"),
            ),
          );
      for (const col of requiredCols) {
        const yConfig = this.config.yAxes[col];
        if (yConfig?.filters && yConfig.filters.length > 0) {
          const active = toActiveFilters(yConfig.filters);
          if (active.length > 0) filtersPayload[col] = active;
        }
        if (col === this.config.xAxis!.col!) {
          const xFilters = this.config.xAxis?.filters ?? [];
          if (xFilters.length > 0) {
            const active = toActiveFilters(xFilters);
            if (active.length > 0) filtersPayload[col] = active;
          }
        }
      }
      if (Object.keys(filtersPayload).length > 0) {
        colParams.append("filters", JSON.stringify(filtersPayload));
      }
      if (this.config.displayUnitSystem) {
        colParams.append("display_unit_system", this.config.displayUnitSystem);
      }
      if (this.config.maxPoints != null) {
        colParams.append("max_points", String(this.config.maxPoints));
      }

      const queryStr = colParams.toString();
      if (queryStr) url += `?${queryStr}`;
      // lab-virtual columns can change value for the same URL after an
      // in-place edit + save, so always bypass the browser HTTP cache
      const resp = await fetch(url, { cache: "no-store" });
      if (!resp.ok) throw new Error(`Trial ${id} failed`);
      const result = (await resp.json()) as TrialDataResponse;
      if (result.filter_errors && result.filter_errors.length > 0) {
        result.filter_errors.forEach((msg) => {
          if (!(this._shownFilterErrors as Set<string>).has(msg)) {
            (this._shownFilterErrors as Set<string>).add(msg);
            this.notify(msg, "error");
            // clear after 5 s so the same error can resurface if the user tries again
            setTimeout(
              () => (this._shownFilterErrors as Set<string>).delete(msg),
              5000,
            );
          }
        });
      }
      return result;
    },

    async trickleFetch(
      id: string,
      columnList: string[],
      label: string,
      isVsDataset: boolean,
      loopId: number,
    ) {
      const CHUNK_SIZE = 10;
      for (let i = 0; i < columnList.length; i += CHUNK_SIZE) {
        if (loopId !== this.discoveryId) return;
        await new Promise((r) => setTimeout(r, 50));
        const chunk = columnList.slice(i, i + CHUNK_SIZE);
        try {
          const resp = await this.fetchTrialData(id, chunk);
          if (isVsDataset) {
            this.vsDatasets[id] = {
              ...(this.vsDatasets[id] ?? {}),
              ...resp.data,
            };
            this.vsDatasets = { ...this.vsDatasets };
          } else {
            this.data = { ...(this.data ?? {}), ...resp.data };
          }
          if (Object.keys(this.config.yAxes).some((y) => chunk.includes(y)))
            this.renderPlot();
          console.debug(
            `Dojo Hydration [${label}]: ${i + chunk.length}/${columnList.length}`,
          );
        } catch (e) {
          console.warn(`Hydration failed for ${id}`, e);
        }
      }
    },

    async fetchTrialStatus() {
      if (this.warpId === null) return;
      try {
        const resp = await fetch(`/monitor/api/status/trial/${this.warpId}`);
        if (!resp.ok) return;
        this.trialStatus = (await resp.json()) as TrialStatus;
      } catch {
        // dojo offline - leave existing status in place
      }
      if (this.trialStatus && this.trialStatus.completion === "incomplete") {
        if (this._trialStatusPoll === null) {
          this._trialStatusPoll = setInterval(() => {
            void this.fetchTrialStatus();
            void this.fetchTrialLogs();
          }, 3000);
        }
      } else {
        if (this._trialStatusPoll !== null) {
          clearInterval(this._trialStatusPoll);
          this._trialStatusPoll = null;
        }
      }
    },

    async fetchTrialLogs() {
      try {
        const resp = await fetch(`/mosaic/${this.trialId}/logs`, {
          cache: "no-store",
        });
        if (!resp.ok) return;
        const result = (await resp.json()) as TrialLogsResponse;
        this.logFilename = result.filename;
        this.logEntries = result.entries;
      } catch {
        // dojo offline - leave existing logs in place
      }
    },

    // -----------------------------------------------------------------------
    // Distributions
    // -----------------------------------------------------------------------
    async fetchDists() {
      try {
        const resp = await fetch(`/mosaic/${this.trialId}/dists`, {
          cache: "no-store",
        });
        if (!resp.ok) return;
        const result = (await resp.json()) as DistsResponse;
        this.dists = result.entries;
      } catch {
        // stochas tables not written yet - silently skip
      }
    },

    showDistTooltip(event: MouseEvent, entry: DistEntry) {
      const hasChart =
        entry.pdf_x.length > 0 || entry.cat_labels.length > 0;
      const hasParams = Object.keys(entry.params).length > 0;
      if (!hasChart && !hasParams) return;
      this._distTooltipEntry = entry;
      const tooltip = document.getElementById(
        "dist-pdf-tooltip",
      ) as HTMLElement | null;
      if (!tooltip) return;
      // widen tooltip for categorical with many choices so bars have room
      const minW =
        entry.chart_type === "categorical"
          ? Math.min(560, Math.max(340, entry.cat_labels.length * 52))
          : 340;
      tooltip.style.minWidth = `${minW}px`;
      const x = event.clientX + 18;
      const y = event.clientY - 110;
      // flip to the left of the cursor when too close to the right edge so the
      // cursor never lands inside the tooltip (Plotly SVG overrides pointer-events
      // on child elements, causing mouseleave/mouseenter flicker if the cursor
      // enters the tooltip bounds)
      const fitsRight = x + minW + 20 <= window.innerWidth;
      tooltip.style.left = `${fitsRight ? x : Math.max(8, event.clientX - minW - 18)}px`;
      tooltip.style.top = `${Math.max(8, y)}px`;
      tooltip.style.display = "block";
      void this._renderDistTooltipPlot(entry);
    },

    hideDistTooltip() {
      this._distTooltipEntry = null;
      const tooltip = document.getElementById("dist-pdf-tooltip");
      if (tooltip) tooltip.style.display = "none";
    },

    async _renderDistTooltipPlot(entry: DistEntry) {
      const chartEl = document.getElementById(
        "dist-pdf-chart",
      ) as HTMLElement | null;
      const paramsEl = document.getElementById("dist-pdf-params");
      if (!chartEl) return;

      const isDark = this.theme === "dark";
      const bg = isDark ? "#1e293b" : "#ffffff";
      const textColor = isDark ? "#94a3b8" : "#64748b";
      const curveColor = isDark ? "#06b6d4" : "#0891b2";
      const cdfColor = isDark ? "#a78bfa" : "#7c3aed";
      const fillColor = isDark
        ? "rgba(6,182,212,0.12)"
        : "rgba(8,145,178,0.10)";
      const sampledColor = "#ef4444";

      const chartType = entry.chart_type;

      if (chartType === "permutation" || chartType === "none") {
        // no chart — hide the chart element so the tooltip is params-only
        chartEl.style.display = "none";
      } else {
        chartEl.style.display = "";

        let traces: object[];
        let layout: object;

        if (chartType === "categorical") {
          const barColors = entry.cat_labels.map((lbl) =>
            entry.sampled_labels?.includes(lbl) ? sampledColor : curveColor,
          );
          traces = [
            {
              x: entry.cat_labels,
              y: entry.cat_probs,
              type: "bar",
              marker: { color: barColors, opacity: 0.85 },
              hoverinfo: "x+y",
            },
          ];
          const maxProb = Math.max(...entry.cat_probs.map((p) => p ?? 0), 0);
          const annotations = entry.cat_labels.map((lbl, i) => ({
            x: lbl,
            y: entry.cat_probs[i] ?? 0,
            text: `${(((entry.cat_probs[i] ?? 0) * 100)).toFixed(1)}%`,
            showarrow: false,
            yanchor: "bottom",
            yshift: 2,
            font: { size: 9, color: textColor },
          }));
          layout = {
            paper_bgcolor: bg,
            plot_bgcolor: bg,
            margin: { t: 22, r: 10, b: 52, l: 52 },
            xaxis: {
              color: textColor,
              showgrid: false,
              tickfont: { size: 10 },
              tickangle: entry.cat_labels.length > 5 ? -30 : 0,
            },
            yaxis: {
              color: textColor,
              showgrid: false,
              tickfont: { size: 11 },
              title: {
                text: "Probability",
                font: { size: 13 },
                standoff: 4,
              },
              // extend range above max bar so annotations have room
              range: [0, maxProb * 1.2],
            },
            annotations,
            showlegend: false,
            font: { size: 11, color: textColor },
          };
        } else {
          // continuous or discrete: PDF/PMF + CDF on secondary y-axis
          const unitsLabel =
            entry.units !== "unset" && entry.units !== "" ? entry.units : "";

          const shapes: object[] = [];
          if (entry.nominal !== null && typeof entry.nominal === "number") {
            shapes.push({
              type: "line",
              x0: entry.nominal,
              x1: entry.nominal,
              y0: 0,
              y1: 1,
              yref: "paper",
              line: { color: "#94a3b8", width: 1.5, dash: "dot" },
            });
          }
          for (const sampledValue of entry.sampled_values ?? []) {
            shapes.push({
              type: "line",
              x0: sampledValue,
              x1: sampledValue,
              y0: 0,
              y1: 1,
              yref: "paper",
              line: { color: sampledColor, width: 2, dash: "solid" },
            });
          }

          const pdfTrace: object =
            chartType === "discrete"
              ? {
                  x: entry.pdf_x,
                  y: entry.pdf_y,
                  type: "bar",
                  marker: { color: curveColor, opacity: 0.75 },
                  name: "P(x)",
                  hoverinfo: "x+y",
                }
              : {
                  x: entry.pdf_x,
                  y: entry.pdf_y,
                  type: "scatter",
                  mode: "lines",
                  fill: "tozeroy",
                  line: { color: curveColor, width: 1.5 },
                  fillcolor: fillColor,
                  name: "PDF",
                  hoverinfo: "x+y",
                };

          const cdfTrace: object = {
            x: entry.cdf_x,
            y: entry.cdf_y,
            type: "scatter",
            mode: "lines",
            line: {
              color: cdfColor,
              width: 1.5,
              shape: chartType === "discrete" ? "hv" : "linear",
            },
            name: "CDF",
            yaxis: "y2",
            hoverinfo: "x+y",
          };

          traces = [pdfTrace, cdfTrace];
          layout = {
            paper_bgcolor: bg,
            plot_bgcolor: bg,
            // only reserve bottom space for x-axis title when units are present
            margin: { t: 14, r: 48, b: unitsLabel ? 46 : 32, l: 64 },
            xaxis: {
              color: textColor,
              showgrid: false,
              tickfont: { size: 11 },
              ...(unitsLabel
                ? { title: { text: unitsLabel, font: { size: 13 }, standoff: 4 } }
                : {}),
            },
            yaxis: {
              color: curveColor,
              showgrid: false,
              tickfont: { size: 11 },
              title: {
                text:
                  chartType === "discrete"
                    ? "Probability"
                    : "Probability Density",
                font: { size: 13 },
                standoff: 4,
              },
            },
            // avoid setting `color` on yaxis2 — it bleeds into the x-axis ticks;
            // use per-property colors on tickfont and title.font instead
            yaxis2: {
              overlaying: "y",
              side: "right",
              range: [0, 1],
              showgrid: false,
              tickfont: { size: 10, color: cdfColor },
              title: {
                text: "CDF",
                font: { size: 12, color: cdfColor },
                standoff: 2,
              },
              tickformat: ".1f",
            },
            showlegend: false,
            shapes,
            font: { size: 11, color: textColor },
          };
        }

        await Plotly.react(chartEl, traces, layout, {
          displayModeBar: false,
          responsive: true,
        });
      }

      if (paramsEl) {
        // categorical: probabilities are shown as bar annotations; skip the
        // redundant params listing below the chart
        if (chartType === "categorical") {
          paramsEl.innerHTML = "";
        } else {
          const fmt = (v: string | number | boolean): string => {
            if (typeof v === "number") {
              return Math.abs(v) >= 1000 || (Math.abs(v) < 0.01 && v !== 0)
                ? v.toExponential(3)
                : v.toPrecision(4).replace(/\.?0+$/, "");
            }
            return String(v);
          };
          paramsEl.innerHTML = Object.entries(entry.params)
            .map(
              ([k, v]) =>
                `<span><span class="text-slate-400 dark:text-slate-500">${k}:</span> ${fmt(v)}</span>`,
            )
            .join("");
        }
      }
    },

    get dataLength(): number {
      if (!this.data) return 0;
      const xCol = this.config.xAxis?.col;
      if (xCol && this.data[xCol]) return this.data[xCol].length;
      const first = Object.values(this.data).find((arr) => arr.length > 0);
      return first?.length ?? 0;
    },

    // -----------------------------------------------------------------------
    // Distributions: sorting, filtering & column resize
    // -----------------------------------------------------------------------
    get distCategories(): string[] {
      return Array.from(new Set(this.dists.map((d) => d.category))).sort();
    },

    get distTypes(): string[] {
      return Array.from(new Set(this.dists.map((d) => d.dist_type))).sort();
    },

    get distUnits(): string[] {
      return Array.from(new Set(this.dists.map((d) => d.units))).sort();
    },

    // signal counts per dropdown option, shown right-justified next to each
    // checkbox so users can see how many rows a filter choice covers
    get distCategoryCounts(): Record<string, number> {
      const counts: Record<string, number> = {};
      for (const d of this.dists) counts[d.category] = (counts[d.category] ?? 0) + 1;
      return counts;
    },

    get distTypeCounts(): Record<string, number> {
      const counts: Record<string, number> = {};
      for (const d of this.dists) counts[d.dist_type] = (counts[d.dist_type] ?? 0) + 1;
      return counts;
    },

    get distUnitCounts(): Record<string, number> {
      const counts: Record<string, number> = {};
      for (const d of this.dists) counts[d.units] = (counts[d.units] ?? 0) + 1;
      return counts;
    },

    // null = all selected; toggling derives the explicit set from the
    // current selection (defaulting to "all" the first time) and only
    // collapses back to null once it matches the full set again - it never
    // re-expands to "all" just because the set happens to become empty
    toggleDistCategoryFilter(cat: string) {
      const all = this.distCategories;
      const current = this.distFilterCategories ?? all;
      const next = current.includes(cat)
        ? current.filter((c) => c !== cat)
        : [...current, cat];
      this.distFilterCategories = next.length === all.length ? null : next;
    },

    selectAllDistCategories() {
      this.distFilterCategories = null;
    },

    deselectAllDistCategories() {
      this.distFilterCategories = [];
    },

    toggleDistTypeFilter(type: string) {
      const all = this.distTypes;
      const current = this.distFilterTypes ?? all;
      const next = current.includes(type)
        ? current.filter((t) => t !== type)
        : [...current, type];
      this.distFilterTypes = next.length === all.length ? null : next;
    },

    selectAllDistTypes() {
      this.distFilterTypes = null;
    },

    deselectAllDistTypes() {
      this.distFilterTypes = [];
    },

    toggleDistUnitFilter(unit: string) {
      const all = this.distUnits;
      const current = this.distFilterUnits ?? all;
      const next = current.includes(unit)
        ? current.filter((u) => u !== unit)
        : [...current, unit];
      this.distFilterUnits = next.length === all.length ? null : next;
    },

    selectAllDistUnits() {
      this.distFilterUnits = null;
    },

    deselectAllDistUnits() {
      this.distFilterUnits = [];
    },

    get filteredDists(): DistEntry[] {
      const name = this.distFilterName.trim().toLowerCase();
      const filtered = this.dists.filter((d) => {
        if (name && !d.name.toLowerCase().includes(name)) return false;
        if (
          this.distFilterCategories !== null &&
          !this.distFilterCategories.includes(d.category)
        )
          return false;
        if (
          this.distFilterTypes !== null &&
          !this.distFilterTypes.includes(d.dist_type)
        )
          return false;
        if (
          this.distFilterUnits !== null &&
          !this.distFilterUnits.includes(d.units)
        )
          return false;
        return true;
      });
      const dir = this.distSortAsc ? 1 : -1;
      return filtered.slice().sort((a, b) => {
        switch (this.distSortKey) {
          case "name":
            return dir * a.name.localeCompare(b.name);
          case "category":
            return dir * a.category.localeCompare(b.category);
          case "dist_type":
            return dir * a.dist_type.localeCompare(b.dist_type);
          case "nominal": {
            const av = a.nominal ?? -Infinity;
            const bv = b.nominal ?? -Infinity;
            return dir * (av - bv);
          }
          case "sampled_value": {
            const av = a.sampled_value ?? -Infinity;
            const bv = b.sampled_value ?? -Infinity;
            return dir * (av - bv);
          }
          case "stat": {
            const av =
              a.z_score ?? (a.percentile != null ? a.percentile / 100 : -Infinity);
            const bv =
              b.z_score ?? (b.percentile != null ? b.percentile / 100 : -Infinity);
            return dir * (av - bv);
          }
        }
      });
    },

    toggleDistSort(
      key: "name" | "category" | "dist_type" | "nominal" | "sampled_value" | "stat",
    ) {
      if (this.distSortKey === key) {
        this.distSortAsc = !this.distSortAsc;
      } else {
        this.distSortKey = key;
        this.distSortAsc = true;
      }
    },

    _persistDistColWidths() {
      try {
        localStorage.setItem(
          "mojo:dists:col-widths",
          JSON.stringify(this.distColWidths),
        );
      } catch {
        // ignore storage errors
      }
    },

    startDistColResize(
      e: MouseEvent,
      col: "name" | "category" | "dist_type" | "units" | "nominal" | "sampled",
    ) {
      e.preventDefault();
      const startX = e.clientX;
      const startWidth = this.distColWidths[col];
      const MIN: Record<typeof col, number> = {
        name: 80,
        category: 68,
        dist_type: 96,
        units: 48,
        nominal: 64,
        sampled: 64,
      };
      const onMove = (ev: MouseEvent) => {
        this.distColWidths[col] = Math.max(
          MIN[col],
          startWidth + (ev.clientX - startX),
        );
      };
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        this._persistDistColWidths();
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },

    autoFitDistColumn(
      col: "name" | "category" | "dist_type" | "units" | "nominal" | "sampled",
    ) {
      const container = this.$refs.distTable as HTMLElement | undefined;
      if (!container) return;
      const headerEl = container.querySelector<HTMLElement>(
        `[data-distcol-header="${col}"]`,
      );
      if (!headerEl) return;
      // header: canvas-measure the label text + room for the sort chevron
      let width =
        this._measureTextWidth(headerEl.textContent?.trim() ?? "", headerEl) +
        20;
      // per-column total horizontal padding: outer cell px-3 = 24px;
      // dist_type badge adds its own px-1.5 (12px) on top, so 36px total
      const PADDING: Record<typeof col, number> = {
        name: 24,
        category: 24,
        dist_type: 36,
        units: 24,
        nominal: 24,
        sampled: 24,
      };
      const pad = PADDING[col];
      // read rendered text from every content cell — handles all formatting
      // (uppercase CSS, toPrecision, em-dash substitution) without a switch
      for (const cell of container.querySelectorAll<HTMLElement>(
        `[data-distcol-content="${col}"]`,
      )) {
        width = Math.max(
          width,
          this._measureTextWidth((cell.innerText ?? "").trim(), cell) + pad,
        );
      }
      this.distColWidths[col] = Math.ceil(width);
      this._persistDistColWidths();
    },

    // -----------------------------------------------------------------------
    // Logs: sorting, filtering & styling
    // -----------------------------------------------------------------------
    get filteredLogEntries(): LogEntry[] {
      const text = this.logFilterMessage.trim();
      let regex: RegExp | null = null;
      if (text && this.logFilterRegex) {
        try {
          regex = new RegExp(text, "i");
        } catch {
          regex = null;
        }
      }

      const filtered = this.logEntries.filter((e) => {
        if (
          this.logFilterLevels.length > 0 &&
          !this.logFilterLevels.includes(e.level)
        )
          return false;
        if (text) {
          if (regex) {
            if (!regex.test(e.message)) return false;
          } else if (!e.message.toLowerCase().includes(text.toLowerCase())) {
            return false;
          }
        }
        return true;
      });

      const dir = this.logSortAsc ? 1 : -1;
      return filtered.slice().sort((a, b) => {
        if (this.logSortKey === "level") {
          const av = LOG_LEVEL_SEVERITY[a.level] ?? 0;
          const bv = LOG_LEVEL_SEVERITY[b.level] ?? 0;
          return av === bv ? a.timestamp - b.timestamp : (av - bv) * dir;
        }
        return (a.timestamp - b.timestamp) * dir;
      });
    },

    get logLevels(): string[] {
      return Array.from(new Set(this.logEntries.map((e) => e.level))).sort(
        (a, b) => (LOG_LEVEL_SEVERITY[a] ?? 0) - (LOG_LEVEL_SEVERITY[b] ?? 0),
      );
    },

    toggleLogSort(key: "timestamp" | "level") {
      if (this.logSortKey === key) {
        this.logSortAsc = !this.logSortAsc;
      } else {
        this.logSortKey = key;
        this.logSortAsc = true;
      }
    },

    toggleLogLevelFilter(level: string) {
      const idx = this.logFilterLevels.indexOf(level);
      if (idx === -1) this.logFilterLevels.push(level);
      else this.logFilterLevels.splice(idx, 1);
    },

    _persistLogColWidths() {
      try {
        localStorage.setItem(
          "mojo:trial-logs:col-widths",
          JSON.stringify(this.logColWidths),
        );
      } catch {
        // ignore storage errors
      }
    },

    startLogColResize(e: MouseEvent, col: "time" | "level" | "source") {
      e.preventDefault();
      const startX = e.clientX;
      const startWidth = this.logColWidths[col];
      const MIN: Record<typeof col, number> = {
        time: 60,
        level: 56,
        source: 60,
      };
      const onMove = (ev: MouseEvent) => {
        this.logColWidths[col] = Math.max(
          MIN[col],
          startWidth + (ev.clientX - startX),
        );
      };
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        this._persistLogColWidths();
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },

    // format a number with 4 significant figures, switching to exponential
    // notation when the exponent is < -4 or >= 4 (matches Python's g format)
    fmtSigFig(v: number | null): string {
      if (v === null) return "—";
      if (v === 0) return "0";
      const abs = Math.abs(v);
      const exp = Math.floor(Math.log10(abs));
      if (exp < -4 || exp >= 4) return v.toExponential(3);
      return parseFloat(v.toPrecision(4)).toString();
    },

    // formats every drawn value for a dist table row, regardless of whether it
    // sampled numbers, labels, or (for permutations) a list of items per draw
    fmtSampled(entry: DistEntry): string {
      if (entry.sampled_permutations && entry.sampled_permutations.length > 0) {
        return entry.sampled_permutations
          .map((perm) => `[${perm.join(", ")}]`)
          .join("; ");
      }
      if (entry.sampled_values && entry.sampled_values.length > 0) {
        return entry.sampled_values.map((v) => this.fmtSigFig(v)).join(", ");
      }
      if (entry.sampled_labels && entry.sampled_labels.length > 0) {
        return entry.sampled_labels.join(", ");
      }
      return "—";
    },

    // formats a percentile in the standard P{x} notation (e.g. P95.7) rather
    // than the nonstandard "%ile" shorthand
    fmtPercentile(p: number): string {
      return `P${p.toFixed(1)}`;
    },

    _measureTextWidth(text: string, refEl: HTMLElement): number {
      const canvas = (this._logMeasureCanvas ??=
        document.createElement("canvas"));
      const ctx = canvas.getContext("2d");
      if (!ctx) return 0;
      ctx.font = getComputedStyle(refEl).font;
      return ctx.measureText(text).width;
    },

    autoFitLogColumn(col: "time" | "level" | "source") {
      const container = this.$refs.logTable as HTMLElement | undefined;
      if (!container) return;

      // text-overflow:ellipsis cells report their box size (not content size)
      // via scrollWidth, so measure the actual text with a canvas instead.
      const headerEl = container.querySelector<HTMLElement>(
        `[data-logcol-header="${col}"]`,
      );
      if (!headerEl) return;
      const contentEl = container.querySelector<HTMLElement>(
        `[data-logcol-content="${col}"]`,
      );

      const HEADER_ICON_ALLOWANCE = 20; // sort chevron + gap
      const CELL_PADDING = 16; // px-2 on the cell (8px each side)
      const BADGE_PADDING = 16; // px-2 on the level badge (8px each side)

      let width =
        this._measureTextWidth(headerEl.textContent?.trim() ?? "", headerEl) +
        HEADER_ICON_ALLOWANCE;

      if (contentEl) {
        for (const entry of this.filteredLogEntries) {
          let text: string;
          switch (col) {
            case "time":
              text = this.formatLogTime(entry.timestamp);
              break;
            case "level":
              text = entry.level;
              break;
            case "source":
              text = this.logSourceShort(entry);
              break;
          }
          width = Math.max(width, this._measureTextWidth(text, contentEl));
        }
      }

      const padding =
        col === "level" ? CELL_PADDING + BADGE_PADDING : CELL_PADDING;
      this.logColWidths[col] = Math.ceil(width) + padding;
      this._persistLogColWidths();
    },

    logSourceShort(entry: LogEntry): string {
      const file = entry.pathname.split("/").pop() ?? "";
      return entry.lineno != null ? `${file}:${entry.lineno}` : file;
    },

    logSourceFull(entry: LogEntry): string {
      return entry.lineno != null
        ? `${entry.pathname}:${entry.lineno}`
        : entry.pathname;
    },

    logLevelClass(level: string): string {
      switch (level) {
        case "CRITICAL":
        case "ERROR":
          return "bg-rose-100 dark:bg-rose-900/50 text-rose-700 dark:text-rose-400";
        case "WARNING":
          return "bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-400";
        case "INFO":
          return "bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-400";
        case "DEBUG":
          return "bg-cyan-100 dark:bg-cyan-900/50 text-cyan-700 dark:text-cyan-400";
        default:
          return "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400";
      }
    },

    formatLogTime(timestamp: number, _tick?: number): string {
      const diff = Date.now() - timestamp;
      if (diff < 24 * 60 * 60 * 1000)
        return window.notifTimeAgo(timestamp, _tick);
      return new Date(timestamp).toLocaleString();
    },

    _updateIsScrubbable() {
      const sel = this.selectedMedia?.toLowerCase() ?? "";
      this.mediaIsScrubbable =
        sel.endsWith(".mp4") ||
        sel.endsWith(".webm") ||
        (sel.endsWith(".gif") && this._gifConvertStatus === "ready");
    },

    _syncOverlayVisibility() {
      const overlay = document.getElementById(
        "playback-line-overlay",
      ) as HTMLElement | null;
      const lineEl = document.getElementById(
        "playback-line-el",
      ) as HTMLElement | null;
      const isTimeAxis = this.config.xAxis?.col === "time";
      const hasYAxes = Object.keys(this.config.yAxes).length > 0;
      const lineVisible =
        this.mediaShowLine &&
        this.mediaScrubMode === "play" &&
        this.mediaIsScrubbable &&
        isTimeAxis &&
        hasYAxes;
      const framesVisible =
        this.mediaShowFrames &&
        !!this._mediaFrameInterval &&
        isTimeAxis &&
        hasYAxes;
      if (overlay)
        overlay.style.display = lineVisible || framesVisible ? "block" : "none";
      if (lineEl) lineEl.style.display = lineVisible ? "block" : "none";
    },

    _renderFrameMarkers() {
      const framesPath = document.getElementById(
        "playback-frames-path",
      ) as SVGPathElement | null;
      if (!framesPath) return;
      this._syncOverlayVisibility();
      const hasYAxes = Object.keys(this.config.yAxes).length > 0;
      if (
        !this.mediaShowFrames ||
        !this._mediaFrameInterval ||
        this.config.xAxis?.col !== "time" ||
        !hasYAxes
      ) {
        framesPath.setAttribute("d", "");
        return;
      }
      type PlotEl = HTMLElement & {
        _fullLayout?: {
          xaxis: { l2p(v: number): number; range: [number, number] };
          margin: { l: number; r: number; t: number; b: number };
        };
      };
      const plotEl = document.getElementById("plot-area") as PlotEl | null;
      const fullLayout = plotEl?._fullLayout;
      const rect = plotEl?.getBoundingClientRect();
      if (!plotEl || !fullLayout) return;
      const video = document.getElementById(
        "media-video-player",
      ) as HTMLVideoElement | null;
      const duration =
        video?.duration && isFinite(video.duration) ? video.duration : Infinity;
      const interval = this._mediaFrameInterval;
      const ph = rect!.height;
      const markerHeight = 5;
      const markerTop = ph - fullLayout.margin.b - 20;
      const markerBot = markerTop - markerHeight;
      const [xMin, xMax] = fullLayout.xaxis.range;
      const kStart = Math.max(0, Math.floor(xMin / interval));
      const kEnd = Math.ceil(
        Math.min(isFinite(duration) ? duration : xMax, xMax) / interval,
      );
      let d = "";
      for (let k = kStart; k <= kEnd; k++) {
        const px = fullLayout.margin.l + fullLayout.xaxis.l2p(k * interval);
        d += `M${px},${markerTop}L${px},${markerBot}`;
      }
      framesPath.setAttribute("d", d);
    },

    _updatePlaybackLine() {
      const isTimeAxis = this.config.xAxis?.col === "time";
      // loop only runs on time axis: line, zoom-looping, and frame markers all require it
      const shouldRun =
        this.mediaScrubMode === "play" &&
        this.mediaFiles.length > 0 &&
        this.mediaIsScrubbable &&
        isTimeAxis;
      if (!shouldRun || this._mediaRafId !== null) return;
      const tick = () => {
        const curTimeAxis = this.config.xAxis?.col === "time";
        if (
          this.mediaScrubMode !== "play" ||
          this.mediaFiles.length === 0 ||
          !this.mediaIsScrubbable ||
          !curTimeAxis
        ) {
          this._mediaRafId = null;
          this._syncOverlayVisibility();
          return;
        }
        const video = document.getElementById(
          "media-video-player",
        ) as HTMLVideoElement | null;
        const plotEl = document.getElementById("plot-area") as
          | (HTMLElement & {
              _fullLayout?: {
                xaxis: { l2p(v: number): number; range: [number, number] };
                margin: { l: number; r: number; t: number; b: number };
              };
            })
          | null;
        if (video && plotEl && video.duration > 0 && !isNaN(video.duration)) {
          const fullLayout = plotEl._fullLayout;
          if (fullLayout) {
            const [xMin, xMax] = fullLayout.xaxis.range;
            const safeMin = Math.max(0, xMin);
            const safeMax = Math.min(video.duration, xMax);
            if (safeMax > safeMin) {
              if (video.currentTime >= safeMax) video.currentTime = safeMin;
              else if (video.currentTime < safeMin) video.currentTime = safeMin;
            }
            this._syncOverlayVisibility();
            if (this.mediaShowLine) {
              const lineEl = document.getElementById(
                "playback-line-el",
              ) as HTMLElement | null;
              if (lineEl) {
                lineEl.style.top = fullLayout.margin.t + "px";
                lineEl.style.bottom = fullLayout.margin.b + "px";
                const t = this._mediaFrameInterval
                  ? Math.round(video.currentTime / this._mediaFrameInterval) *
                    this._mediaFrameInterval
                  : video.currentTime;
                lineEl.style.left =
                  fullLayout.margin.l + fullLayout.xaxis.l2p(t) + "px";
              }
            }
            if (this.mediaShowFrames) this._renderFrameMarkers();
          }
        }
        this._mediaRafId = requestAnimationFrame(tick);
      };
      this._mediaRafId = requestAnimationFrame(tick);
    },

    async fetchMediaFiles() {
      try {
        const resp = await fetch(`/mosaic/${this.trialId}/media`);
        if (!resp.ok) return;
        const data = (await resp.json()) as TrialMediaResponse;
        this._mediaFpsMap = Object.fromEntries(
          data.files.map((f: TrialMediaFile) => [f.name, f.fps]),
        );
        this._mediaMtimeMap = Object.fromEntries(
          data.files.map((f: TrialMediaFile) => [f.name, f.mtime]),
        );
        this.mediaFiles = data.files.map((f: TrialMediaFile) => f.name);
        if (this.mediaFiles.length > 0) {
          const saved = localStorage.getItem("mojo:media:file");
          this.selectedMedia =
            saved && this.mediaFiles.includes(saved)
              ? saved
              : this.mediaFiles[0]!;
        }
        this._applySelectedMediaFps();
        this._updateIsScrubbable();
      } catch {
        // dojo offline - no media available
      }
      this._updatePlaybackLine();
      this._renderFrameMarkers();
      if (this.mediaMiniplayerOpen && this.mediaFiles.length > 0)
        this._startMiniplayer();
    },

    // builds a media file URL with an mtime cache-buster, so a regenerated
    // file with the same name forces the browser to reload it instead of
    // reusing a stale cached video/image from before the rerun
    _mediaFileUrl(filename: string, suffix = ""): string {
      const base = `/mosaic/${this.trialId}/media/${filename}${suffix}`;
      const mtime = this._mediaMtimeMap[filename];
      return mtime !== undefined ? `${base}?t=${mtime}` : base;
    },

    _applySelectedMediaFps() {
      const fps = this.selectedMedia
        ? (this._mediaFpsMap[this.selectedMedia] ?? null)
        : null;
      this._mediaFrameInterval = fps && fps > 0 ? 1 / fps : null;
    },

    _onVideoLoaded() {
      const video = document.getElementById(
        "media-video-player",
      ) as HTMLVideoElement | null;
      if (video) video.playbackRate = this.mediaPlaybackRate;
      if (this.selectedMedia?.toLowerCase().endsWith(".gif")) {
        this._gifConvertStatus = "ready";
        // mirror the img's auto-play behaviour now that the video element takes over
        void video?.play();
      }
    },

    _onVideoError() {
      if (this.selectedMedia?.toLowerCase().endsWith(".gif")) {
        this._gifConvertStatus = "failed";
      }
    },

    _miniDragStart(e: MouseEvent) {
      const wrapper = document.getElementById(
        "mini-wrapper",
      ) as HTMLElement | null;
      const canvas = document.getElementById(
        "mini-canvas",
      ) as HTMLElement | null;
      if (!wrapper) return;
      const startX = e.clientX;
      const startY = e.clientY;
      const startLeft = parseInt(wrapper.style.left) || 8;
      const startTop = parseInt(wrapper.style.top) || 8;
      const card = wrapper.parentElement;
      if (canvas) canvas.style.cursor = "grabbing";
      const onMove = (ev: MouseEvent) => {
        const maxLeft = card
          ? Math.max(0, card.offsetWidth - wrapper.offsetWidth - 4)
          : 9999;
        const maxTop = card
          ? Math.max(0, card.offsetHeight - wrapper.offsetHeight - 4)
          : 9999;
        wrapper.style.left =
          Math.max(4, Math.min(maxLeft, startLeft + ev.clientX - startX)) +
          "px";
        wrapper.style.top =
          Math.max(4, Math.min(maxTop, startTop + (ev.clientY - startY))) +
          "px";
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        if (canvas) canvas.style.cursor = "grab";
        try {
          localStorage.setItem("mojo:media:mini:left", wrapper.style.left);
          localStorage.setItem("mojo:media:mini:top", wrapper.style.top);
        } catch {
          /* ignore */
        }
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },

    _miniResizeStart(e: MouseEvent) {
      const wrapper = document.getElementById(
        "mini-wrapper",
      ) as HTMLElement | null;
      if (!wrapper) return;
      const startX = e.clientX;
      const startY = e.clientY;
      const startW = wrapper.offsetWidth;
      const startH = wrapper.offsetHeight;
      // use the video's natural aspect ratio for Shift-snap; fall back to 16:9
      const video = document.getElementById(
        "media-video-player",
      ) as HTMLVideoElement | null;
      const aspectRatio =
        video && video.videoWidth && video.videoHeight
          ? video.videoWidth / video.videoHeight
          : 16 / 9;
      const onMove = (ev: MouseEvent) => {
        const dw = ev.clientX - startX;
        const dh = ev.clientY - startY;
        let newW = Math.max(120, startW + dw);
        let newH = Math.max(68, startH + dh);
        if (ev.shiftKey) {
          // constrain to aspect ratio — follow whichever axis moved more
          if (Math.abs(dw) >= Math.abs(dh)) {
            newH = Math.max(68, Math.round(newW / aspectRatio));
          } else {
            newW = Math.max(120, Math.round(newH * aspectRatio));
          }
        }
        wrapper.style.width = newW + "px";
        wrapper.style.height = newH + "px";
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        try {
          localStorage.setItem("mojo:media:mini:w", wrapper.style.width);
          localStorage.setItem("mojo:media:mini:h", wrapper.style.height);
        } catch {
          /* ignore */
        }
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },

    _startMiniplayer() {
      const wrapper = document.getElementById(
        "mini-wrapper",
      ) as HTMLElement | null;
      const canvas = document.getElementById(
        "mini-canvas",
      ) as HTMLCanvasElement | null;
      if (!wrapper || !canvas || _mini.rafId !== null) return;
      // restore saved position and size
      try {
        const sl = localStorage.getItem("mojo:media:mini:left");
        const st = localStorage.getItem("mojo:media:mini:top");
        const sw = localStorage.getItem("mojo:media:mini:w");
        const sh = localStorage.getItem("mojo:media:mini:h");
        if (sl) wrapper.style.left = sl;
        if (st) wrapper.style.top = st;
        if (sw) wrapper.style.width = sw;
        if (sh) wrapper.style.height = sh;
      } catch {
        /* ignore */
      }
      wrapper.style.display = "block";
      const paint = () => {
        const isGif =
          this.selectedMedia?.toLowerCase().endsWith(".gif") ?? false;
        const useVideo = !isGif || this._gifConvertStatus === "ready";
        const srcEl = useVideo
          ? (document.getElementById(
              "media-video-player",
            ) as HTMLVideoElement | null)
          : (document.getElementById(
              "media-gif-player",
            ) as HTMLImageElement | null);
        if (srcEl) {
          const ctx = canvas.getContext("2d");
          if (ctx) {
            const vEl = srcEl as HTMLVideoElement;
            if (isGif || vEl.readyState === undefined || vEl.readyState >= 2) {
              ctx.drawImage(
                srcEl as CanvasImageSource,
                0,
                0,
                canvas.width,
                canvas.height,
              );
            }
          }
        }
        _mini.rafId = requestAnimationFrame(paint);
      };
      _mini.rafId = requestAnimationFrame(paint);
    },

    _stopMiniplayer() {
      if (_mini.rafId !== null) {
        cancelAnimationFrame(_mini.rafId);
        _mini.rafId = null;
      }
      const wrapper = document.getElementById(
        "mini-wrapper",
      ) as HTMLElement | null;
      if (wrapper) wrapper.style.display = "none";
    },

    async startBackgroundDiscovery() {
      const currentId = ++this.discoveryId;
      const pendingCols = this.columns.filter(
        (c) => !Object.prototype.hasOwnProperty.call(this.data ?? {}, c),
      );
      if (pendingCols.length > 0)
        await this.trickleFetch(
          this.trialId,
          pendingCols,
          "Current",
          false,
          currentId,
        );
      if (currentId !== this.discoveryId) return;

      const start = Math.min(this.vsDraft.range[0], this.vsDraft.range[1]);
      const end = Math.max(this.vsDraft.range[0], this.vsDraft.range[1]);
      const activeCols = [
        this.config.xAxis!.col!,
        ...Object.keys(this.config.yAxes),
      ];

      const pinnedSet = new Set(this.vsDraft.pinned);
      const draftIds = this.allTrials.filter((id) => {
        const n = parseInt(id.split("_").pop() ?? "");
        return ((n >= start && n <= end) || pinnedSet.has(n)) && id !== this.trialId;
      });

      for (const id of draftIds) {
        if (currentId !== this.discoveryId) return;
        const existing = this.vsDatasets[id];
        const needsFetch =
          !existing ||
          activeCols.some(
            (c) => !Object.prototype.hasOwnProperty.call(existing, c),
          );
        if (needsFetch)
          await this.trickleFetch(
            id,
            activeCols,
            `Draft ${id}`,
            true,
            currentId,
          );
      }
    },

    // -----------------------------------------------------------------------
    // Shapes
    // -----------------------------------------------------------------------
    setPlacementMode(type: "vline" | "hline" | "rect") {
      this.placementMode = type;
      this.rectStart = null;
      this.shapeDraft = null;
      const label =
        type === "vline"
          ? "Vertical Line"
          : type === "hline"
            ? "Horizontal Line"
            : "Area Rectangle";
      this.notify(`Mode: ${label}. Click plot to place.`, "info");
    },

    deleteShape(index: number) {
      this.config.shapes.splice(index, 1);
      this.saveAndRender();
    },

    handlePlotClickForShapes(pt: { x: number; y: number }): boolean {
      if (!this.placementMode) return false;
      const defaultStyle = this.nextAvailableStyle(
        this.config.shapes.map((s) => ({ color: s.color, dash: s.dash ?? "solid" })),
      );
      let newShape: Shape | null = null;

      if (this.placementMode === "vline") {
        newShape = {
          type: "vline",
          x0: pt.x,
          color: defaultStyle.color,
          dash: defaultStyle.dash,
          label: "",
        };
      } else if (this.placementMode === "hline") {
        newShape = {
          type: "hline",
          y0: pt.y,
          color: defaultStyle.color,
          dash: defaultStyle.dash,
          label: "",
        };
      } else if (this.placementMode === "rect") {
        if (!this.rectStart) {
          this.rectStart = { x: pt.x, y: pt.y };
          return true;
        }
        newShape = {
          type: "rect",
          x0: this.rectStart.x,
          x1: pt.x,
          y0: this.rectStart.y,
          y1: pt.y,
          color: defaultStyle.color,
          dash: defaultStyle.dash,
          label: "",
        };
        this.rectStart = null;
      }

      if (newShape) {
        this.config.shapes.push(newShape);
        this.placementMode = null;
        this.saveAndRender();
      }
      return true;
    },

    saveShape() {
      if (!this.shapeDraft) return;
      if (this.shapeEditIndex !== null) {
        this.config.shapes[this.shapeEditIndex] = { ...this.shapeDraft };
      } else {
        this.config.shapes.push({ ...this.shapeDraft });
      }
      this.shapeDraft = null;
      this.shapeEditIndex = null;
      this.saveAndRender();
    },

    startShapeEdit(index: number) {
      this.shapeEditIndex = index;
      this.shapeDraft = { ...this.config.shapes[index]! };
      this.shapesOpen = true;
    },

    cancelShapeDraft() {
      this.shapeDraft = null;
      this.shapeEditIndex = null;
      this.rectStart = null;
    },

    // -----------------------------------------------------------------------
    // Annotations
    // -----------------------------------------------------------------------
    saveAnnotation() {
      if (!this.annDraft || !this.annDraft.text.trim()) return;
      if (this.annEditIndex !== null) {
        this.config.annotations[this.annEditIndex] = { ...this.annDraft };
      } else {
        this.config.annotations.push({ ...this.annDraft });
      }
      this.cancelAnnDraft();
      this.saveAndRender();
    },

    startAnnEdit(index: number) {
      this.annEditIndex = index;
      this.annDraft = { ...this.config.annotations[index]! };
      void this.$nextTick(() =>
        (this.$refs["annInput"] as HTMLInputElement | undefined)?.focus(),
      );
    },

    cancelAnnDraft() {
      this.annDraft = null;
      this.annEditIndex = null;
    },

    jumpToAnnotation(ann: Annotation) {
      const el = document.getElementById("plot-area") as
        | (HTMLElement & {
            _fullLayout?: {
              xaxis: { p2l(v: number): number };
              yaxis: { p2l(v: number): number };
              margin: { l: number; t: number };
            };
          })
        | null;
      if (!el || !this.data) return;
      const xValues = this.data[this.config.xAxis!.col!] ?? [];
      const xMin = xValues[0] ?? 0;
      const xMax = xValues[xValues.length - 1] ?? 100;
      const xSpan = (xMax - xMin) * 0.1;
      let newRangeX: [number, number] = [ann.x - xSpan / 2, ann.x + xSpan / 2];
      if (newRangeX[0] < xMin) {
        newRangeX[1] += xMin - newRangeX[0];
        newRangeX[0] = xMin;
      }
      if (newRangeX[1] > xMax) {
        newRangeX[0] -= newRangeX[1] - xMax;
        newRangeX[1] = xMax;
      }

      const fullY = this.calculatePaddedRange(
        Object.keys(this.config.yAxes),
        false,
      );
      const ySpan = Math.abs(fullY[1] - fullY[0]) * 0.2;
      const newRangeY: [number, number] = [
        ann.y - ySpan / 2,
        ann.y + ySpan / 2,
      ];

      this.config.rangeX = newRangeX;
      this.config.rangeY = newRangeY;
      void Plotly.relayout(el, {
        "xaxis.range": newRangeX,
        "yaxis.range": newRangeY,
        "xaxis.autorange": false,
        "yaxis.autorange": false,
      });
      this.saveAndRender();
    },

    deleteAnnotation(index: number) {
      this.config.annotations.splice(index, 1);
      this.saveAndRender();
    },

    editAnnotation(index: number) {
      const ann = this.config.annotations[index]!;
      const newText = prompt("Update Annotation:", ann.text);
      if (newText !== null && newText.trim() !== "") {
        this.config.annotations[index]!.text = newText;
        this.saveAndRender();
      }
    },

    // -----------------------------------------------------------------------
    // Column accessors
    // -----------------------------------------------------------------------
    get selectableYColumns(): string[] {
      if (!this.columns) return [];
      if (!this.config.refFrame) return this.columns;
      return this.columns.filter((col) => {
        const parts = col.split(":");
        const suffix = parts.pop();
        const family = parts.join(":");
        return (
          ["x", "y", "z"].includes(suffix ?? "") &&
          (this.rotateableVectors ?? []).includes(family)
        );
      });
    },

    get availableQuats(): string[] {
      if (!this.columns || !Array.isArray(this.columns)) return [];
      return this.columns
        .filter((c) => c.endsWith(":w"))
        .map((c) => c.replace(":w", ""));
    },

    // -----------------------------------------------------------------------
    // Init
    // -----------------------------------------------------------------------
    async init() {
      this.theme = document.documentElement.classList.contains("dark")
        ? "dark"
        : "light";
      const currentNum = parseInt(this.trialId.split("_").pop() ?? "");
      this.warpId = isNaN(currentNum) ? null : currentNum;
      void this.fetchTrialStatus();
      void this.fetchTrialLogs();
      void this.fetchMediaFiles();
      void this.fetchDists();

      // initialize tab state (populates labTabs, labActiveTabId, labName, labGraph)
      this._initTabs();
      window.mojoLabOnDirtyChange = (dirty: boolean) => {
        const tab = this.labTabs.find((t) => t.id === this.labActiveTabId);
        if (tab) tab.dirty = dirty;
      };
      // LabTab.savedState is the single source of truth for "what does clean
      // look like for this tab" - _signal_lab.html never keeps its own copy,
      // it always asks for the active tab's baseline through these two bridges.
      // That structurally rules out the stale-copy bugs a locally-cached
      // baseline used to cause (forgotten syncs, baselines surviving a tab
      // switch, ordering footguns around when the cache had to be refreshed).
      window.mojoLabGetBaseline = () => {
        const tab = this.labTabs.find((t) => t.id === this.labActiveTabId);
        return tab?.savedState ?? null;
      };
      window.mojoLabSetBaseline = (state: string | null) => {
        const tab = this.labTabs.find((t) => t.id === this.labActiveTabId);
        if (tab) tab.savedState = state;
      };

      // bind video element handlers programmatically so `this` resolves to the
      // trialViewer component — template @event handlers in nested x-data scopes
      // lose the correct `this` binding when calling parent methods
      void this.$nextTick(() => {
        const video = document.getElementById(
          "media-video-player",
        ) as HTMLVideoElement | null;
        if (video) {
          video.onloadedmetadata = () => this._onVideoLoaded();
          video.onerror = () => this._onVideoError();
        }
      });

      const observer = new MutationObserver((mutations) => {
        if (mutations.some((m) => m.attributeName === "class")) {
          this.theme = document.documentElement.classList.contains("dark")
            ? "dark"
            : "light";
          if (this.data && Object.keys(this.config.yAxes).length > 0)
            this.renderPlot();
        }
      });
      observer.observe(document.documentElement, { attributes: true });

      try {
        const schemaResp = await fetch("/mosaic/api/filter-schema");
        this.filterSchemas = (await schemaResp.json()) as FilterSchema[];
      } catch (e) {
        console.warn("Failed to load filter schemas", e);
      }

      try {
        const statusResp = await fetch("/monitor/api/status/job");
        const statusData = (await statusResp.json()) as {
          error?: boolean;
          is_complete: boolean;
          padding_style: string;
        };
        if (statusData && !statusData.error) {
          (Alpine.store("dojo") as DojoStore).updateSync(
            Date.now(),
            statusData.is_complete,
          );
          const match = statusData.padding_style.match(/\d+/);
          this.paddingLen = match ? parseInt(match[0]!) : 2;
        }
      } catch (e) {
        console.warn("Dojo offline", e);
      }

      try {
        const initialCols = [
          this.config.xAxis!.col!,
          ...Object.keys(this.config.yAxes),
        ];
        const response = await this.fetchTrialData(this.trialId, initialCols);
        this.columns = response.columns.all.sort();
        this.rotateableVectors = response.columns.rotatable_vectors ?? [];
        this.columnMetadata = response.columns.column_metadata ?? {};
        this.data = response.data;
        void this.loadLabSchemas();

        const params = new URLSearchParams(window.location.search);
        const shared = params.get("v");
        if (shared) {
          this.hydrateFromUrl(shared);
          this.vsDraft.enabled = this.config.vsEnabled;
          this.vsDraft.range = [...this.config.vsRange];
          this.vsDraft.pinned = [...(this.config.vsPinned ?? [])];
          this.config.vsEnabled = false;
        } else {
          this.loadConfig();
          this.vsDraft.enabled = this.config.vsEnabled;
          this.vsDraft.range = [...this.config.vsRange];
          this.vsDraft.pinned = [...(this.config.vsPinned ?? [])];
        }

        // Migrate old profiles: if refFrame is set but no series has a RotationFilter,
        // inject it now (before watchers are registered so this is a silent migration).
        if (this.config.refFrame) {
          const hasRotation = Object.values(this.config.yAxes).some((y) =>
            y.filters.some((f) => f.type === "rotation"),
          );
          if (!hasRotation) this.applyRefFrame(this.config.refFrame);
        }

        void this.$nextTick(() => {
          this.pushHistory();
        });

        void this.$nextTick(async () => {
          await this.renderPlot();
          // wait one layout pass before reading getBoundingClientRect for frame markers
          requestAnimationFrame(() => {
            const plotEl = document.getElementById("plot-area") as
              | (HTMLElement & { _fullLayout?: unknown })
              | null;
            console.debug(
              "[init RAF] _fullLayout present:",
              !!plotEl?._fullLayout,
              "rect:",
              plotEl?.getBoundingClientRect(),
            );
            this._renderFrameMarkers();
            this._syncOverlayVisibility();
          });
          const plotEl = document.getElementById("plot-area") as HTMLElement & {
            on(
              event: string,
              handler: (event: Record<string, unknown>) => void,
            ): void;
            _fullLayout?: {
              xaxis: {
                p2l(v: number): number;
                l2p(v: number): number;
                range: [number, number];
              };
              yaxis: { p2l(v: number): number };
              margin: { l: number; r: number; t: number; b: number };
            };
          };

          // re-render frame markers after every complete Plotly render so positions
          // always reflect the final settled layout (range, margins, dimensions)
          this._attachPlotEventHandlers();

          // placementMode uses normal click
          plotEl.addEventListener("click", (e) => {
            if (!this.placementMode) return;
            const target = e.target as HTMLElement;
            if (
              !target.classList.contains("nsewdrag") &&
              !target.classList.contains("drag")
            )
              return;
            const rect = plotEl.getBoundingClientRect();
            const fullLayout = plotEl._fullLayout;
            if (!fullLayout) return;
            this.handlePlotClickForShapes({
              x: fullLayout.xaxis.p2l(
                e.clientX - rect.left - fullLayout.margin.l,
              ),
              y: fullLayout.yaxis.p2l(
                e.clientY - rect.top - fullLayout.margin.t,
              ),
            });
          });

          // middle-click anywhere over the plot opens annotation editor.
          // Listening at document level so Plotly's stopPropagation on inner SVG elements
          // cannot block the event.
          document.addEventListener("mousedown", (e) => {
            if (e.button !== 1) return;
            const rect = plotEl.getBoundingClientRect();
            if (
              e.clientX < rect.left ||
              e.clientX > rect.right ||
              e.clientY < rect.top ||
              e.clientY > rect.bottom
            )
              return;
            e.preventDefault(); // suppress browser auto-scroll cursor
            const fullLayout = plotEl._fullLayout;
            if (!fullLayout) return;
            const xVal = fullLayout.xaxis.p2l(
              e.clientX - rect.left - fullLayout.margin.l,
            );
            const yVal = fullLayout.yaxis.p2l(
              e.clientY - rect.top - fullLayout.margin.t,
            );
            setTimeout(() => {
              this.annDraft = { x: xVal, y: yVal, text: "" };
              this.annEditIndex = null;
              this.annotationsOpen = true;
              void this.$nextTick(() => {
                (
                  document.querySelector(
                    '[x-ref="annInput"]',
                  ) as HTMLInputElement | null
                )?.focus();
              });
            }, 0);
          });

          // intercept Plotly's own notifier and route through our toast
          new MutationObserver((mutations) => {
            for (const { addedNodes } of mutations) {
              for (const node of addedNodes) {
                if (!(node instanceof HTMLElement)) continue;
                const notif = node.classList.contains("plotly-notifier")
                  ? node
                  : node.querySelector?.(".plotly-notifier");
                if (!notif) continue;
                const text = notif.textContent?.replace(/×/g, "").trim();
                if (text) this.notify(text, "info");
                (notif as HTMLElement).style.display = "none";
              }
            }
          }).observe(document.body, { childList: true, subtree: true });

          // scrub video on mousemove: use axis time value when x-axis is "time",
          // otherwise fall back to pixel fraction so phase-space plots still work.
          plotEl.addEventListener("mousemove", (e: MouseEvent) => {
            if (this.mediaScrubMode !== "scrub") return;
            const video = document.getElementById(
              "media-video-player",
            ) as HTMLVideoElement | null;
            if (!video || !video.duration || isNaN(video.duration)) return;
            const fullLayout = plotEl._fullLayout;
            if (!fullLayout) return;
            const rect = plotEl.getBoundingClientRect();
            const relX = e.clientX - rect.left - fullLayout.margin.l;
            if (this.config.xAxis?.col === "time") {
              const t = fullLayout.xaxis.p2l(relX);
              video.currentTime = Math.max(0, Math.min(video.duration, t));
            } else {
              const plotAreaWidth =
                rect.width - fullLayout.margin.l - fullLayout.margin.r;
              if (plotAreaWidth <= 0) return;
              video.currentTime =
                video.duration * Math.max(0, Math.min(1, relX / plotAreaWidth));
            }
          });

          setTimeout(() => {
            if (plotEl?.offsetParent !== null) Plotly.Plots.resize(plotEl);
          }, 100);
        });
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        this.errorState = msg.includes("not found") ? "not_found" : "empty";
        this.notify(msg, "error");
      } finally {
        this.loading = false;
        (Alpine.store("dojo") as DojoStore).startGlobalSync();
        (Alpine.store("dojo") as DojoStore).setPageReady(true);
      }

      // Capture phase so this runs before Alpine's bubble-phase window listeners
      // (e.g. @keydown.escape.window in base.html). stopImmediatePropagation()
      // in the Escape branch then prevents those listeners from firing when a
      // panel was open.
      window.addEventListener(
        "keydown",
        (e) => {
          if (e.repeat) return;

          // dialog open → handle Escape/Enter exclusively, block all other shortcuts
          const dojoStore = Alpine.store("dojo") as DojoStore;
          if (dojoStore?.dialog?.show) {
            if (e.key === "Escape" || e.key === "Enter") {
              e.preventDefault();
              e.stopPropagation();
              if (e.key === "Escape") dojoStore.dialog.cancel();
              else dojoStore.dialog.confirm();
            }
            return;
          }

          const targetEl = e.target as HTMLElement;
          const tag = targetEl.tagName;
          const isTextInput =
            ["INPUT", "TEXTAREA", "SELECT"].includes(tag) ||
            targetEl.isContentEditable;
          if (e.key === "/" && !isTextInput) {
            e.preventDefault();
            (
              document.querySelector(
                "input[data-warp-input]",
              ) as HTMLElement | null
            )?.focus();
          }
          if (e.key === "Escape") {
            const anyOpen = !!(
              this.placementMode ||
              this.annotationsOpen ||
              this.shapesOpen ||
              this.xMenuOpen ||
              this.yMenuOpen ||
              this.refFrameMenuOpen ||
              this.settingsOpen ||
              this.downloadOpen ||
              this.editorOpen ||
              this.profilesOpen ||
              this.vsMenuOpen ||
              this.labOpen ||
              (Alpine.store("dojo") as DojoStore).overlayCount > 0 ||
              isTextInput
            );
            if (isTextInput) targetEl.blur();
            this.placementMode = null;
            this.rectStart = null;
            this.cancelAnnDraft();
            this.cancelShapeDraft();
            this.annotationsOpen = false;
            this.shapesOpen = false;
            this.xMenuOpen = this.yMenuOpen = this.refFrameMenuOpen = false;
            this.settingsOpen = this.downloadOpen = this.editorOpen = false;
            this.profilesOpen = this.vsMenuOpen = false;
            this.profileSearch = "";
            if (!this.labOpen || !window.mojoLabHasUnsavedChanges?.()) {
              this.labOpen = false;
            } else {
              void (
                window.mojoConfirm?.({
                  title: "Unsaved changes",
                  message: "Close the lab and discard unsaved changes?",
                  confirmLabel: "Discard",
                  cancelLabel: "Keep editing",
                  variant: "warning",
                }) ?? Promise.resolve(false)
              ).then((ok) => {
                if (ok) {
                  window.mojoLabRevertToSaved?.();
                  this.labOpen = false;
                }
              });
            }
            window.dispatchEvent(new CustomEvent("mojo:escape"));
            // Stop immediate propagation when something was open so Alpine's
            // bubble-phase @keydown.escape.window handler doesn't also fire.
            // This prevents Escape from both closing the lab and exiting fullscreen.
            if (anyOpen) e.stopImmediatePropagation();
          }
          if (
            (e.metaKey || e.ctrlKey) &&
            e.key.toLowerCase() === "c" &&
            !isTextInput
          ) {
            if (this.labOpen) {
              e.preventDefault();
              document.dispatchEvent(new CustomEvent("mojo:lab-clear"));
            }
          }
          if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
            e.preventDefault();
            if (this.labOpen) {
              const nameEl = document.getElementById(
                "lab-name-input",
              ) as HTMLInputElement | null;
              const name = nameEl?.value.trim() ?? "";
              if (name) {
                const graph = window.mojoLabSerialize?.();
                if (graph) void this.saveLabGraph(name, graph);
              } else {
                nameEl?.focus();
                nameEl?.setSelectionRange(0, 0);
              }
            } else if (!isTextInput) {
              this.profilesOpen = true;
              void this.loadProfiles();
              void this.$nextTick(() => {
                const el = document.getElementById(
                  "profile-name-input",
                ) as HTMLInputElement | null;
                if (el) {
                  el.focus();
                  el.setSelectionRange(el.value.length, el.value.length);
                }
              });
            }
          }
          if ((e.metaKey || e.ctrlKey) && !isTextInput) {
            if (e.key === "ArrowLeft") {
              e.preventDefault();
              document.getElementById("nav-prev")?.click();
            } else if (e.key === "ArrowRight") {
              e.preventDefault();
              document.getElementById("nav-next")?.click();
            }
          }
          if (isTextInput) return;

          if (e.key === "<") {
            e.preventDefault();
            const prev = [...this.mediaSpeedPresets]
              .reverse()
              .find((p) => p < this.mediaPlaybackRate);
            if (prev !== undefined) this.mediaPlaybackRate = prev;
          } else if (e.key === ">") {
            e.preventDefault();
            const next = this.mediaSpeedPresets.find(
              (p) => p > this.mediaPlaybackRate,
            );
            if (next !== undefined) this.mediaPlaybackRate = next;
          }

          const isZ = e.key.toLowerCase() === "z";
          const isY = e.key.toLowerCase() === "y";
          const cmdOrCtrl = e.metaKey || e.ctrlKey;
          if (cmdOrCtrl && isZ) {
            e.preventDefault();
            if (this.labOpen) {
              e.shiftKey ? window.mojoLabRedo?.() : window.mojoLabUndo?.();
            } else {
              if (e.shiftKey) this.redo();
              else this.undo();
            }
          }
          if (cmdOrCtrl && isY) {
            e.preventDefault();
            if (this.labOpen) window.mojoLabRedo?.();
            else this.redo();
          }
          if (this.labOpen && cmdOrCtrl && e.shiftKey) {
            if (e.key.toLowerCase() === "a") {
              e.preventDefault();
              window.mojoLabArrange?.();
            } else if (e.key.toLowerCase() === "f") {
              e.preventDefault();
              window.mojoLabFitView?.();
            }
          }
        },
        { capture: true },
      );

      const resp = await fetch("/mosaic/api/trials");
      const data = (await resp.json()) as TrialManifest;
      this.allTrials = data.trials ?? [];

      if (this.allTrials.length) {
        const ids = this.allTrials
          .map((id) => parseInt(id.split("_").pop() ?? ""))
          .filter((n) => !isNaN(n));
        const minFleet = Math.min(...ids);
        const maxFleet = Math.max(...ids);
        if (this.config.vsRange[0] === 0 && this.config.vsRange[1] === 0) {
          this.config.vsRange = [minFleet, maxFleet];
          this.vsDraft.range = [minFleet, maxFleet];
        }
      }

      this.$watch("vsDraft.range", () => {
        if (this.discoveryTimeout) clearTimeout(this.discoveryTimeout);
        this.discoveryTimeout = setTimeout(() => {
          if (this.vsDraft.enabled) void this.startBackgroundDiscovery();
        }, 500);
      });

      this.$watch("vsDraft.pinned", () => {
        if (this.discoveryTimeout) clearTimeout(this.discoveryTimeout);
        this.discoveryTimeout = setTimeout(() => {
          if (this.vsDraft.enabled) void this.startBackgroundDiscovery();
        }, 500);
      });

      this.$watch("profileSearch", (val: string) => {
        try {
          localStorage.setItem("mojo:profile:search", val);
        } catch {
          /* ignore */
        }
      });

      this.$watch("mediaScrubMode", (mode: string) => {
        if (mode === "scrub") {
          (
            document.getElementById(
              "media-video-player",
            ) as HTMLVideoElement | null
          )?.pause();
        }
        try {
          localStorage.setItem("mojo:media:mode", mode);
        } catch {
          /* ignore */
        }
        this._syncOverlayVisibility();
        this._updatePlaybackLine();
      });

      this.$watch("mediaShowLine", (val: boolean) => {
        try {
          localStorage.setItem("mojo:media:show-line", val ? "1" : "0");
        } catch {
          /* ignore */
        }
        this._syncOverlayVisibility();
        this._updatePlaybackLine();
      });

      this.$watch("mediaShowFrames", (val: boolean) => {
        try {
          localStorage.setItem("mojo:media:show-frames", val ? "1" : "0");
        } catch {
          /* ignore */
        }
        this._syncOverlayVisibility();
        this._renderFrameMarkers();
        this._updatePlaybackLine();
      });

      this.$watch("mediaPlaybackRate", (rate: number) => {
        try {
          localStorage.setItem("mojo:media:rate", String(rate));
        } catch {
          /* ignore */
        }
        const video = document.getElementById(
          "media-video-player",
        ) as HTMLVideoElement | null;
        if (video) video.playbackRate = rate;
      });

      this.$watch("config.rangeX", () => {
        requestAnimationFrame(() => this._renderFrameMarkers());
      });

      this.$watch("selectedMedia", (file: string | null) => {
        if (file)
          try {
            localStorage.setItem("mojo:media:file", file);
          } catch {
            /* ignore */
          }
        const sel = (file ?? "").toLowerCase();
        this._gifConvertStatus = sel.endsWith(".gif") ? "loading" : "none";
        this._applySelectedMediaFps();
        this._updateIsScrubbable();
        this._renderFrameMarkers();
        this._updatePlaybackLine();
        if (this.mediaMiniplayerOpen) {
          this._stopMiniplayer();
          void this.$nextTick(() => this._startMiniplayer());
        }
        // catch cache-hit: browser may have loaded metadata before @loadedmetadata bound
        if (sel.endsWith(".gif")) {
          void this.$nextTick(() => {
            const video = document.getElementById(
              "media-video-player",
            ) as HTMLVideoElement | null;
            if (video && video.readyState >= HTMLMediaElement.HAVE_METADATA) {
              this._onVideoLoaded();
            }
          });
        }
      });

      this.$watch("mediaMiniplayerOpen", (open: boolean) => {
        try {
          localStorage.setItem("mojo:media:mini", open ? "1" : "0");
        } catch {
          /* ignore */
        }
        if (open && this.mediaFiles.length > 0) this._startMiniplayer();
        else this._stopMiniplayer();
      });

      this.$watch("_gifConvertStatus", () => {
        this._updateIsScrubbable();
        this._syncOverlayVisibility();
        this._updatePlaybackLine();
      });

      this.$watch("config.xAxis.col", (newCol: string) => {
        if (
          newCol &&
          !Object.prototype.hasOwnProperty.call(this.data ?? {}, newCol)
        ) {
          void (async () => {
            try {
              const resp = await this.fetchTrialData(this.trialId, [newCol]);
              this.data = { ...(this.data ?? {}), ...resp.data };
              this.saveAndRender();
            } catch {
              // non-critical
            }
          })();
        }
        requestAnimationFrame(() => {
          this._syncOverlayVisibility();
          this._renderFrameMarkers();
          this._updatePlaybackLine();
        });
      });

      this.$watch(
        "config.refFrame",
        (newValue: string | null, oldValue: string | null) => {
          if (newValue === oldValue) return;
          this.notify(`Frame: ${newValue || "world"}`, "info");
          this.discoveryId++;
          this.applyRefFrame(newValue);
          // config watcher handles re-fetch and re-render when yAxes.filters change
        },
      );

      this.$watch("config", async (value: PlotConfig, oldValue: PlotConfig) => {
        // re-validate on every config change, not just raw-JSON edits, so fixes
        // made through the UI (column pickers, filters, etc.) clear a stale
        // Config Error banner instead of requiring a page refresh
        this.configErrors = this.validateConfig(value);
        this.isValidConfig = this.configErrors.length === 0;
        this.isValidJson = true;

        if (!this.isEditingRaw) {
          this.configRaw = JSON.stringify(value, null, 4);
          try {
            localStorage.removeItem("mojo:config:raw-draft");
          } catch {}
        }
        if (
          this.config.vsEnabled &&
          oldValue?.vsEnabled &&
          (value.xAxis!.col! !== oldValue?.xAxis?.col ||
            Object.keys(value.yAxes).length !==
              Object.keys(oldValue.yAxes ?? {}).length)
        ) {
          await this.syncVsRange();
        }
        this.pushHistory();

        // detect filter changes by comparing against the last-fetched fingerprint rather
        // than oldValue, because Alpine.js $watch does not reliably deep-clone oldValue
        // for nested reactive objects - both value and oldValue may point to the same data
        const changedFilterCols = Object.keys(value.yAxes).filter((col) => {
          const current = JSON.stringify(
            (value.yAxes[col]?.filters ?? []).filter(
              (f) => f.enabled !== false,
            ),
          );
          return current !== (this.filterFingerprints[col] ?? "[]");
        });
        // detect x-axis filter changes
        const xFilterCurrent = JSON.stringify(
          (value.xAxis?.filters ?? []).filter((f) => f.enabled !== false),
        );
        const xFilterChanged = xFilterCurrent !== this.xAxisFilterFingerprint;
        if (xFilterChanged) {
          this.xAxisFilterFingerprint = xFilterCurrent;
          if (this.data) delete this.data[value.xAxis!.col!];
        }

        const colsToRefetch = [
          ...(xFilterChanged ? [value.xAxis!.col!] : []),
          ...changedFilterCols,
        ];
        if (colsToRefetch.length > 0) {
          changedFilterCols.forEach((col) => {
            this.filterFingerprints[col] = JSON.stringify(
              (value.yAxes[col]?.filters ?? []).filter(
                (f) => f.enabled !== false,
              ),
            );
            if (this.data) delete this.data[col];
          });
          this.vsDatasets = {};
          const resp = await this.fetchTrialData(this.trialId, colsToRefetch);
          this.data = { ...(this.data ?? {}), ...resp.data };
          if (this.config.vsEnabled) await this.syncVsRange();
        }

        this.saveAndRender();
        this._syncOverlayVisibility();
        requestAnimationFrame(() => this._renderFrameMarkers());
      });

      // re-fetch data and column manifest when display unit system changes so the
      // plot values and unit dropdowns reflect the new unit system immediately
      this.$watch(
        "config.displayUnitSystem",
        async (newVal: string | null, oldVal: string | null) => {
          if (newVal === oldVal) return;
          const activeCols = [
            this.config.xAxis!.col!,
            ...Object.keys(this.config.yAxes),
          ];
          this.vsDatasets = {};
          try {
            const resp = await this.fetchTrialData(this.trialId, activeCols);
            this.columnMetadata = resp.columns.column_metadata ?? {};
            // replace entirely so background-hydrated columns with stale unit values
            // are not used; startBackgroundDiscovery re-hydrates the rest
            this.data = resp.data;
            this.renderPlot();
            // re-index frame markers after the plot re-renders with the new unit scale
            requestAnimationFrame(() => {
              this._renderFrameMarkers();
              this._syncOverlayVisibility();
            });
            void this.startBackgroundDiscovery();
          } catch (e) {
            console.warn("Display unit system re-fetch failed", e);
          }
        },
      );

      // re-fetch all data when max_points changes; also clear VS cache since
      // all previously fetched comparison datasets used the old point limit
      this.$watch(
        "config.maxPoints",
        async (newVal: number | null, oldVal: number | null) => {
          if (newVal === oldVal) return;
          const activeCols = [
            this.config.xAxis!.col!,
            ...Object.keys(this.config.yAxes),
          ];
          this.vsDatasets = {};
          try {
            const resp = await this.fetchTrialData(this.trialId, activeCols);
            this.data = resp.data;
            this.renderPlot();
            void this.startBackgroundDiscovery();
          } catch (e) {
            console.warn("Max points re-fetch failed", e);
          }
        },
      );

      void this.startBackgroundDiscovery();
      this.configRaw =
        localStorage.getItem("mojo:config:raw-draft") ??
        JSON.stringify(this.config, null, 4);
      this.updateFromRaw();

      // persist dist filter state across page loads and trial navigation
      this.$watch("distFilterName", (v: string) => {
        try { localStorage.setItem("mojo:dists:filter-name", v); } catch { /* ignore */ }
      });
      this.$watch("distFilterCategories", (v: string[] | null) => {
        try { localStorage.setItem("mojo:dists:filter-categories", JSON.stringify(v)); } catch { /* ignore */ }
      });
      this.$watch("distFilterTypes", (v: string[] | null) => {
        try { localStorage.setItem("mojo:dists:filter-types", JSON.stringify(v)); } catch { /* ignore */ }
      });
      this.$watch("distFilterUnits", (v: string[] | null) => {
        try { localStorage.setItem("mojo:dists:filter-units", JSON.stringify(v)); } catch { /* ignore */ }
      });

      // re-pull distribution metadata when new job data arrives
      window.addEventListener("mojo-data-updated", () => {
        void this.fetchDists();
      });

      window.addEventListener("mojo-sensai-plot-config", (e) => {
        const detail = (e as CustomEvent<PlotConfig>).detail;
        if (detail && typeof detail === "object") {
          this.config = { ...detail } as PlotConfig;
        }
      });

      window.addEventListener("mojo-sensai-undo", () => {
        this.undo();
      });
    },

    // -----------------------------------------------------------------------
    // VS (comparison) mode
    // -----------------------------------------------------------------------
    async syncVsRange() {
      try {
        const resp = await fetch("/mosaic/api/trials");
        const data = (await resp.json()) as TrialManifest;
        this.allTrials = data.trials ?? [];
      } catch (e) {
        console.warn("Manifest sync failed", e);
      }

      if (!this.vsDraft.enabled) {
        this.config.vsEnabled = false;
        this.vsDatasets = {};
        return;
      }

      this.vsLoading = true;
      try {
        const start = Math.min(this.vsDraft.range[0], this.vsDraft.range[1]);
        const end = Math.max(this.vsDraft.range[0], this.vsDraft.range[1]);
        let activeCols = [
          this.config.xAxis!.col!,
          ...Object.keys(this.config.yAxes),
        ];

        if (this.config.refFrame) {
          const families = new Set<string>();
          Object.keys(this.config.yAxes).forEach((col) => {
            if (col.includes(":"))
              families.add(col.substring(0, col.lastIndexOf(":")));
          });
          families.forEach((fam) =>
            activeCols.push(`${fam}:x`, `${fam}:y`, `${fam}:z`),
          );
          activeCols.push(
            `${this.config.refFrame}:w`,
            `${this.config.refFrame}:x`,
            `${this.config.refFrame}:y`,
            `${this.config.refFrame}:z`,
          );
        }
        activeCols = [...new Set(activeCols)];

        const currentNum = parseInt(this.trialId.split("_").pop() ?? "");
        const pinnedSet = new Set(this.vsDraft.pinned);
        const targetIds = this.allTrials.filter((id) => {
          const n = parseInt(id.split("_").pop() ?? "");
          return ((n >= start && n <= end) || pinnedSet.has(n)) && n !== currentNum;
        });

        await Promise.all(
          targetIds.map(async (id) => {
            const existing = this.vsDatasets[id];
            const needsFetch =
              !existing ||
              activeCols.some(
                (col) => !Object.prototype.hasOwnProperty.call(existing, col),
              ) ||
              this.config.refFrame !== null;
            if (needsFetch) {
              const response = await this.fetchTrialData(id, activeCols);
              this.vsDatasets[id] = {
                ...(this.vsDatasets[id] ?? {}),
                ...response.data,
              };
            }
          }),
        );

        this.vsDatasets = { ...this.vsDatasets };
        this.config.vsRange = [start, end];
        this.config.vsPinned = [...this.vsDraft.pinned];
        this.config.vsEnabled = true;
        if (targetIds.length > 0) {
          this.notify(
            `Comparing ${targetIds.length} trial${targetIds.length === 1 ? "" : "s"}`,
            "info",
          );
        }
      } finally {
        this.vsLoading = false;
      }
    },

    handleVsToggle() {
      if (!this.vsDraft.enabled) {
        this.config.vsEnabled = false;
        this.vsDatasets = {};
        this.renderPlot();
      }
    },

    setVsPreset(delta: number) {
      const cur = parseInt(this.trialId.split("_").pop() ?? "0");
      this.vsDraft.range = [cur - delta, cur + delta];
    },

    setVsAll() {
      const nums = this.allTrials
        .map((t) => parseInt(t.split("_").pop() ?? ""))
        .filter((n) => !isNaN(n));
      if (!nums.length) return;
      this.vsDraft.range = [Math.min(...nums), Math.max(...nums)];
    },

    isVsPreset(delta: number): boolean {
      const cur = parseInt(this.trialId.split("_").pop() ?? "0");
      const [a, b] = this.vsDraft.range;
      return Math.min(a, b) === cur - delta && Math.max(a, b) === cur + delta;
    },

    isVsAll(): boolean {
      const nums = this.allTrials
        .map((t) => parseInt(t.split("_").pop() ?? ""))
        .filter((n) => !isNaN(n));
      if (!nums.length) return false;
      const [a, b] = this.vsDraft.range;
      return (
        Math.min(a, b) === Math.min(...nums) &&
        Math.max(a, b) === Math.max(...nums)
      );
    },

    vsInRangeCount(): number {
      const lo = Math.min(this.vsDraft.range[0], this.vsDraft.range[1]);
      const hi = Math.max(this.vsDraft.range[0], this.vsDraft.range[1]);
      const cur = parseInt(this.trialId.split("_").pop() ?? "");
      return this.allTrials.filter((id) => {
        const n = parseInt(id.split("_").pop() ?? "");
        return n >= lo && n <= hi && n !== cur;
      }).length;
    },

    vsTotalCount(): number {
      const lo = Math.min(this.vsDraft.range[0], this.vsDraft.range[1]);
      const hi = Math.max(this.vsDraft.range[0], this.vsDraft.range[1]);
      const cur = parseInt(this.trialId.split("_").pop() ?? "");
      const pinnedSet = new Set(this.vsDraft.pinned);
      return this.allTrials.filter((id) => {
        const n = parseInt(id.split("_").pop() ?? "");
        return ((n >= lo && n <= hi) || pinnedSet.has(n)) && n !== cur;
      }).length;
    },

    toggleVsPin(n: number) {
      const idx = this.vsDraft.pinned.indexOf(n);
      if (idx === -1) {
        this.vsDraft.pinned = [...this.vsDraft.pinned, n].sort((a, b) => a - b);
      } else {
        this.vsDraft.pinned = this.vsDraft.pinned.filter((x) => x !== n);
      }
    },

    // -----------------------------------------------------------------------
    // Column filtering & search
    // -----------------------------------------------------------------------
    smartSort(list: string[]): string[] {
      return list.sort((a, b) => {
        const aT = a.toLowerCase() === "time";
        const bT = b.toLowerCase() === "time";
        if (aT && !bT) return -1;
        if (!aT && bT) return 1;
        return a.localeCompare(b, undefined, { sensitivity: "base" });
      });
    },

    getFilteredCols(field: string): string[] {
      if (!this.columns || !Array.isArray(this.columns)) return [];
      const base =
        field === "x" || field === "nodeCol"
          ? this.columns
          : field === "nodeQuat"
            ? this.availableQuats
            : this.selectableYColumns;
      const search =
        (this as unknown as Record<string, string>)[field + "Search"] ?? "";
      if (!search) return this.smartSort([...base]);
      try {
        let pattern = search.replace(/\*/g, ".*").replace(/\/?:/g, ".*:");
        if (pattern.endsWith("/")) pattern = pattern.replace(/\/$/, "\\/?");
        if (pattern.startsWith(":")) pattern = ".*" + pattern;
        if (pattern.toLowerCase() === "time") pattern = "^time$";
        const query = new RegExp(pattern, "i");
        return this.smartSort(base.filter((c) => query.test(c)));
      } catch {
        return this.smartSort(
          base.filter((c) => c.toLowerCase().includes(search.toLowerCase())),
        );
      }
    },

    toggleRegexSegment(
      field: string,
      segment: string,
      depth: number | "suffix",
    ) {
      const key = field + "Search";
      const self = this as unknown as Record<string, string>;
      let [pathPart = "", suffixPart = ""] = (self[key] ?? "").split(":");

      if (depth === "suffix") {
        const cleanSeg = segment.replace(":", "");
        let items = (suffixPart ?? "")
          .replace(/[()]/g, "")
          .split("|")
          .filter(Boolean);
        items = items.includes(cleanSeg)
          ? items.filter((i) => i !== cleanSeg)
          : [...items, cleanSeg];
        suffixPart =
          items.length > 1 ? `(${items.sort().join("|")})` : (items[0] ?? "");
      } else {
        let parts = (pathPart ?? "").split("/").filter((p) => p !== "");
        let target = parts[depth] ?? "";
        let items = target.replace(/[()]/g, "").split("|").filter(Boolean);
        items = items.includes(segment)
          ? items.filter((i) => i !== segment)
          : [...items, segment];
        if (items.length === 0) {
          parts = parts.slice(0, depth);
        } else {
          parts[depth] =
            items.length === 1
              ? (items[0] ?? "")
              : `(${items.sort().join("|")})`;
        }
        pathPart = parts.join("/");
        if (pathPart && pathPart.toLowerCase() !== "time") {
          const isFolder = this.columns.some((c) =>
            c.toLowerCase().startsWith(pathPart!.toLowerCase() + "/"),
          );
          if (isFolder) pathPart += "/";
        }
      }
      self[key] = (pathPart ?? "") + (suffixPart ? ":" + suffixPart : "");
    },

    getSegmentsAtDepth(field: string, depth: number): string[] {
      const base =
        field === "x" || field === "nodeCol"
          ? this.columns
          : field === "nodeQuat"
            ? this.availableQuats
            : this.selectableYColumns;
      const search =
        (this as unknown as Record<string, string>)[field + "Search"] ?? "";
      const pathSearch = search.split(":")[0] ?? "";
      const parts = pathSearch.split("/").filter((p) => p !== "");
      const selected = (parts[depth] ?? "")
        .replace(/[()]/g, "")
        .split("|")
        .filter(Boolean);
      const prefixParts = parts.slice(0, depth);
      const prefix = prefixParts.join("/").replace(/\//g, "\\/?");
      const regex = new RegExp("^" + (prefix ? prefix : ""), "i");
      const segments = base
        .filter((c) => regex.test(c))
        .map((c) => {
          const p = c.split(":")[0]!.split("/");
          return p[depth] ?? null;
        })
        .filter(Boolean) as string[];
      return this.smartSort([...new Set([...selected, ...segments])]);
    },

    getAvailableSuffixes(field: string): string[] {
      const base =
        field === "x" || field === "nodeCol"
          ? this.columns
          : field === "nodeQuat"
            ? this.availableQuats
            : this.selectableYColumns;
      const search =
        (this as unknown as Record<string, string>)[field + "Search"] ?? "";
      const [pathPart = "", suffixPart = ""] = search.split(":");
      const selected = (suffixPart ?? "")
        .replace(/[()]/g, "")
        .split("|")
        .filter(Boolean)
        .map((s) => ":" + s);
      const pathRegex = new RegExp(
        "^" + (pathPart ?? "").replace(/\//g, "\\/?"),
        "i",
      );
      const matches = base.filter((c) => pathRegex.test(c));
      const available = matches
        .map((c) => (c.includes(":") ? ":" + c.split(":").pop() : null))
        .filter(Boolean) as string[];
      return this.smartSort([...new Set([...selected, ...available])]);
    },

    isSegmentActive(
      field: string,
      seg: string,
      depth: number | "suffix",
    ): boolean {
      const search =
        (this as unknown as Record<string, string>)[field + "Search"] ?? "";
      if (depth === "suffix") {
        const suffixPart = search.split(":")[1] ?? "";
        const items = suffixPart
          .replace(/[()]/g, "")
          .split("|")
          .filter(Boolean);
        return items.includes(seg.replace(":", ""));
      } else {
        const pathPart = search.split(":")[0] ?? "";
        const levels = pathPart.split("/").filter((p) => p !== "");
        const levelContent = levels[depth] ?? "";
        const items = levelContent
          .replace(/[()]/g, "")
          .split("|")
          .filter(Boolean);
        return items.includes(seg);
      }
    },

    getActiveLevels(field: string): number[] {
      const search =
        (this as unknown as Record<string, string>)[field + "Search"] ?? "";
      const pathOnly = search.split(":")[0] ?? "";
      const parts = pathOnly.split("/").filter((p) => p !== "");
      return Array.from({ length: parts.length + 1 }, (_, i) => i);
    },

    // -----------------------------------------------------------------------
    // JSON editor
    // -----------------------------------------------------------------------
    get highlightedJson(): string {
      if (!this.configRaw) return "";
      let html = this.configRaw
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
      const regex =
        /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?|[\[\]{},])|(\S+)/g;
      return html.replace(
        regex,
        (match, _token, _i1, _i2, _i3, garbage: string | undefined) => {
          if (garbage)
            return `<span class="text-rose-500 underline decoration-wavy underline-offset-2 font-bold">${garbage}</span>`;
          let cls = "text-slate-500 dark:text-slate-400";
          if (/^"/.test(match)) {
            cls = /:$/.test(match)
              ? "text-cyan-600 dark:text-cyan-300"
              : "text-emerald-600 dark:text-emerald-400";
          } else if (/true|false/.test(match)) {
            cls = "text-violet-600 dark:text-violet-400";
          } else if (/null/.test(match)) {
            cls = "text-rose-500";
          } else if (/-?\d/.test(match)) {
            cls = "text-amber-600 dark:text-amber-500";
          }
          return `<span class="${cls}">${match}</span>`;
        },
      );
    },

    validateConfig(cfg: PlotConfig): string[] {
      // schema-level checks (types, required fields, enums, discriminated unions, ...)
      const errors: string[] = validateAgainstSchema(cfg, PLOT_CONFIG_SCHEMA);
      const labsNoted = new Set<string>();
      const schemasLoaded = this.labSchemas.length > 0;

      const checkCol = (col: string, label: string) => {
        if (col.startsWith("Lab/")) {
          if (!schemasLoaded) return; // wait for schemas before reporting Lab issues
          // lab names may contain '/' (nested folders); the output label is
          // always the final segment, so split from the right
          const labRest = col.slice(4);
          const labSplitIdx = labRest.lastIndexOf("/");
          const labName =
            labSplitIdx >= 0 ? labRest.slice(0, labSplitIdx) : labRest;
          if (labsNoted.has(labName)) return;
          const lab = this.labSchemas.find((l) => l.name === labName);
          if (!lab) {
            labsNoted.add(labName);
            errors.push(`Lab "${labName}" not found.`);
          } else if (lab.missing.length > 0) {
            labsNoted.add(labName);
            errors.push(
              `Lab "${labName}" requires: ${lab.signal_in_columns.join(", ")}; missing: ${lab.missing.join(", ")}.`,
            );
          }
        } else if (!this.columns.includes(col)) {
          errors.push(`${label} "${col}" not found in telemetry.`);
        }
      };

      if (cfg.xAxis?.col) checkCol(cfg.xAxis.col, "X-Axis");
      if (typeof cfg.yAxes !== "object" || Array.isArray(cfg.yAxes)) {
        errors.push("yAxes must be a hashmap.");
      } else {
        Object.keys(cfg.yAxes).forEach((y) => checkCol(y, "Y-Axis"));
      }
      if (cfg.vsRange && cfg.vsRange[0] > cfg.vsRange[1])
        errors.push("Comparison range start cannot be greater than end.");
      return errors;
    },

    updateFromRaw() {
      try {
        localStorage.setItem("mojo:config:raw-draft", this.configRaw);
      } catch {}
      try {
        const parsed = JSON.parse(this.configRaw) as PlotConfig;
        this.isValidJson = true;
        if (parsed && typeof parsed === "object") {
          this.configErrors = this.validateConfig(parsed);
          this.isValidConfig = this.configErrors.length === 0;
          if (this.isValidConfig) {
            const prevRefFrame = this.config.refFrame ?? null;
            this.isEditingRaw = true;
            this.config = { ...this.config, ...parsed };
            // Apply rotation filters synchronously. $watch("config.refFrame") fires
            // asynchronously after the whole config object is replaced, so filters
            // would be wrong during the first render if we relied solely on the watch.
            const nextRefFrame =
              (this.config.refFrame as string | null) ?? null;
            if (nextRefFrame !== prevRefFrame) {
              this.applyRefFrame(nextRefFrame);
            }
            void this.$nextTick(() => {
              this.isEditingRaw = false;
            });
          }
        }
      } catch {
        this.isValidJson = false;
        this.isValidConfig = false;
      }
    },

    // -----------------------------------------------------------------------
    // Config persistence
    // -----------------------------------------------------------------------
    loadConfig() {
      const saved = localStorage.getItem("mojo_mosaic_config");
      if (saved) {
        try {
          const parsed = JSON.parse(saved) as Partial<PlotConfig>;
          const { vsEnabled: _vs, ...rest } = parsed;
          this.config = { ...this.config, ...rest };
        } catch {
          console.error("Stored config corrupt");
        }
      } else {
        if (this.columns.includes("time")) this.config.xAxis!.col! = "time";
      }

      const savedHistory = localStorage.getItem("mojo_mosaic_history");
      if (savedHistory) {
        try {
          const { stack, index } = JSON.parse(savedHistory) as {
            stack: string[];
            index: number;
          };
          this.historyStack = stack;
          this.historyIndex = index;
        } catch {
          console.warn("History recovery failed.");
          this.pushHistory();
        }
      } else {
        this.pushHistory();
      }
      this.configRaw = JSON.stringify(this.config, null, 4);
    },

    saveAndRender() {
      localStorage.setItem("mojo_mosaic_config", JSON.stringify(this.config));
      this.persistHistory();
      this.renderPlot();
      void this.$nextTick(() => {
        const el = document.getElementById("plot-area");
        if (el && el.offsetParent !== null) Plotly.Plots.resize(el);
      });
    },

    hydrateFromUrl(blob: string) {
      try {
        const decoded = LZString.decompressFromEncodedURIComponent(blob);
        if (!decoded) throw new Error("Decompression failed");
        const parsed = JSON.parse(decoded) as Partial<PlotConfig>;
        this.config = { ...this.config, ...parsed };
        this.notify("Shared view loaded", "success");
      } catch {
        this.notify("Failed to decode shared link", "error");
        this.loadConfig();
      }
    },

    // -----------------------------------------------------------------------
    // Exports / clipboard
    // -----------------------------------------------------------------------
    copyShareLink() {
      try {
        const encoded = LZString.compressToEncodedURIComponent(
          JSON.stringify(this.config),
        );
        const shareBase = this.externalUrl + window.location.pathname;
        void this.copyToClipboard(
          `${shareBase}?v=${encoded}`,
          "Shareable link copied!",
        );
      } catch {
        this.notify("Link generation failed", "error");
      }
    },

    copyRawConfig() {
      void this.copyToClipboard(this.configRaw, "JSON Config copied!");
    },

    initChartResize(hostEl: HTMLElement | undefined) {
      if (!hostEl || hostEl.dataset.resizeAttached) return;
      hostEl.dataset.resizeAttached = "true";

      restorePersistedHeight(hostEl, "mojo:chart:height");

      // Plotly.Plots.resize() can take longer than a single frame, so a
      // simple rAF throttle would drop requests that arrive mid-resize and
      // leave the plot visibly lagging behind the cursor. Instead, queue at
      // most one follow-up resize so it keeps catching up to the latest size.
      let resizeRaf: number | null = null;
      let resizeQueued = false;
      const doResize = () => {
        resizeRaf = null;
        const plotEl = document.getElementById("plot-area");
        if (plotEl && plotEl.offsetParent !== null) Plotly.Plots.resize(plotEl);
        if (resizeQueued) {
          resizeQueued = false;
          resizeRaf = requestAnimationFrame(doResize);
        }
      };
      const resizePlot = () => {
        if (resizeRaf !== null) {
          resizeQueued = true;
          return;
        }
        resizeRaf = requestAnimationFrame(doResize);
      };

      attachVerticalResizeHandle(hostEl, {
        storageKey: "mojo:chart:height",
        minHeight: 300,
        onResize: resizePlot,
        getResetHeight: () => "600px",
      });

      // Fill (or shrink to) the restored height once the plot has rendered.
      resizePlot();
    },

    initCodeMirror(hostEl: HTMLElement) {
      if (!hostEl || typeof CM === "undefined" || _cm.editor) return;
      const {
        EditorView,
        basicSetup,
        json,
        jsonParseLinter,
        oneDarkHighlightStyle,
        EditorState,
        Compartment,
        linter,
        lintGutter,
        syntaxHighlighting,
        defaultHighlightStyle,
      } = CM;
      const self = this;

      // Restore persisted height before creating the editor so it sizes correctly.
      restorePersistedHeight(hostEl, "mojo:json-editor:height");

      // --- themes (base chrome only; highlight handled separately) ---
      const darkTheme = EditorView.theme(
        {
          "&": { backgroundColor: "#020617", color: "#cbd5e1", height: "100%" },
          ".cm-scroller": {
            overflow: "auto",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: "0.875rem",
            lineHeight: "1.625",
          },
          ".cm-content": { padding: "1rem", caretColor: "#06b6d4" },
          ".cm-cursor": { borderLeftColor: "#06b6d4" },
          ".cm-gutters": {
            backgroundColor: "#0f172a",
            color: "#475569",
            borderRight: "1px solid #1e293b",
          },
          ".cm-activeLineGutter": { backgroundColor: "rgba(15,23,42,0.6)" },
          ".cm-activeLine": { backgroundColor: "rgba(15,23,42,0.4)" },
          ".cm-selectionBackground": { backgroundColor: "#1e293b !important" },
          "&.cm-focused .cm-selectionBackground": {
            backgroundColor: "#1e293b !important",
          },
          ".cm-matchingBracket": { color: "#22d3ee", fontWeight: "bold" },
          ".cm-tooltip": {
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            color: "#cbd5e1",
          },
          ".cm-panels": {
            backgroundColor: "#0f172a",
            borderColor: "#1e293b",
            color: "#cbd5e1",
          },
          ".cm-searchMatch": { backgroundColor: "rgba(34,211,238,0.18)" },
          ".cm-searchMatch.cm-searchMatch-selected": {
            backgroundColor: "rgba(34,211,238,0.35)",
          },
          ".cm-lintRange-error": {
            backgroundImage: "none",
            textDecoration: "underline wavy #ef4444 1.5px",
            textUnderlineOffset: "3px",
          },
          ".cm-lintRange-warning": {
            backgroundImage: "none",
            textDecoration: "underline wavy #f59e0b 1.5px",
            textUnderlineOffset: "3px",
          },
          ".cm-diagnostic-error": { borderLeft: "3px solid #ef4444" },
        },
        { dark: true },
      );

      const lightTheme = EditorView.theme(
        {
          "&": { backgroundColor: "#ffffff", color: "#0f172a", height: "100%" },
          ".cm-scroller": {
            overflow: "auto",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: "0.875rem",
            lineHeight: "1.625",
          },
          ".cm-content": { padding: "1rem", caretColor: "#0891b2" },
          ".cm-cursor": { borderLeftColor: "#0891b2" },
          ".cm-gutters": {
            backgroundColor: "#f8fafc",
            color: "#94a3b8",
            borderRight: "1px solid #e2e8f0",
          },
          ".cm-activeLineGutter": { backgroundColor: "rgba(241,245,249,0.6)" },
          ".cm-activeLine": { backgroundColor: "rgba(241,245,249,0.5)" },
          ".cm-selectionBackground": { backgroundColor: "#e2e8f0 !important" },
          "&.cm-focused .cm-selectionBackground": {
            backgroundColor: "#e2e8f0 !important",
          },
          ".cm-matchingBracket": { color: "#0891b2", fontWeight: "bold" },
          ".cm-tooltip": {
            backgroundColor: "#f8fafc",
            border: "1px solid #e2e8f0",
            color: "#0f172a",
          },
          ".cm-panels": { backgroundColor: "#f8fafc", borderColor: "#e2e8f0" },
          ".cm-searchMatch": { backgroundColor: "rgba(8,145,178,0.15)" },
          ".cm-searchMatch.cm-searchMatch-selected": {
            backgroundColor: "rgba(8,145,178,0.3)",
          },
          ".cm-lintRange-error": {
            backgroundImage: "none",
            textDecoration: "underline wavy #ef4444 1.5px",
            textUnderlineOffset: "3px",
          },
          ".cm-lintRange-warning": {
            backgroundImage: "none",
            textDecoration: "underline wavy #f59e0b 1.5px",
            textUnderlineOffset: "3px",
          },
          ".cm-diagnostic-error": { borderLeft: "3px solid #ef4444" },
        },
        { dark: false },
      );

      const isDark = () => document.documentElement.classList.contains("dark");
      const themeComp = new Compartment();
      const highlightComp = new Compartment();
      const makeTheme = (dark: boolean) => (dark ? darkTheme : lightTheme);
      const makeHighlight = (dark: boolean) =>
        syntaxHighlighting(
          dark ? oneDarkHighlightStyle : defaultHighlightStyle,
        );

      const startState = EditorState.create({
        doc: this.configRaw,
        extensions: [
          basicSetup,
          json(),
          lintGutter(),
          linter(jsonParseLinter()),
          themeComp.of(makeTheme(isDark())),
          highlightComp.of(makeHighlight(isDark())),
          EditorView.updateListener.of((update) => {
            if (update.docChanged && !_cm.updating) {
              const text = update.state.doc.toString();
              _cm.updating = true;
              self.configRaw = text;
              if (_cm.debounce !== null) clearTimeout(_cm.debounce);
              _cm.debounce = setTimeout(() => {
                self.updateFromRaw();
                _cm.debounce = null;
              }, 500);
              _cm.updating = false;
            }
          }),
        ],
      });

      _cm.editor = new EditorView({ state: startState, parent: hostEl });

      // Custom resize handle
      attachVerticalResizeHandle(hostEl, {
        storageKey: "mojo:json-editor:height",
        minHeight: 128,
        getResetHeight: () => {
          // .cm-scroller fills the host at 100% height, so its scrollHeight
          // equals the panel height when content is shorter (useless for
          // shrinking). .cm-content has natural height matching actual content.
          const content = hostEl.querySelector<HTMLElement>(".cm-content");
          if (!content) return undefined;
          return Math.max(128, content.offsetHeight) + "px";
        },
      });

      // Swap theme when dark mode toggles.
      new MutationObserver(() => {
        const dark = isDark();
        _cm.editor?.dispatch({
          effects: [
            themeComp.reconfigure(makeTheme(dark)),
            highlightComp.reconfigure(makeHighlight(dark)),
          ],
        });
      }).observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["class"],
      });

      // Sync external configRaw changes into CM.
      this.$watch("configRaw", (val: string) => {
        if (!_cm.updating && _cm.editor) {
          const current = _cm.editor.state.doc.toString() as string;
          if (current !== val) {
            _cm.updating = true;
            _cm.editor.dispatch({
              changes: { from: 0, to: current.length, insert: val },
            });
            _cm.updating = false;
          }
        }
      });
    },

    initMetadataViewer(hostEl: HTMLElement, jsonText: string): object | null {
      if (!hostEl || typeof CM === "undefined") return null;
      const {
        EditorView,
        EditorState,
        json,
        syntaxHighlighting,
        oneDarkHighlightStyle,
        defaultHighlightStyle,
      } = CM;
      const isDark = document.documentElement.classList.contains("dark");
      const darkTheme = EditorView.theme(
        {
          "&": { backgroundColor: "#020617", color: "#cbd5e1" },
          ".cm-scroller": {
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: "0.8rem",
            lineHeight: "1.625",
          },
          ".cm-content": { padding: "0.6rem 0.75rem", caretColor: "#06b6d4" },
          ".cm-gutters": { display: "none" },
          ".cm-cursor, .cm-dropCursor": { display: "none" },
          ".cm-activeLine": { backgroundColor: "transparent" },
          ".cm-selectionBackground": { backgroundColor: "#1e293b !important" },
          "&.cm-focused .cm-selectionBackground": {
            backgroundColor: "#1e293b !important",
          },
        },
        { dark: true },
      );
      const lightTheme = EditorView.theme(
        {
          "&": { backgroundColor: "#ffffff", color: "#0f172a" },
          ".cm-scroller": {
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: "0.8rem",
            lineHeight: "1.625",
          },
          ".cm-content": { padding: "0.6rem 0.75rem", caretColor: "#0891b2" },
          ".cm-gutters": { display: "none" },
          ".cm-cursor, .cm-dropCursor": { display: "none" },
          ".cm-activeLine": { backgroundColor: "transparent" },
          ".cm-selectionBackground": { backgroundColor: "#e2e8f0 !important" },
          "&.cm-focused .cm-selectionBackground": {
            backgroundColor: "#e2e8f0 !important",
          },
        },
        { dark: false },
      );
      const state = EditorState.create({
        doc: jsonText,
        extensions: [
          EditorState.readOnly.of(true),
          json(),
          isDark ? darkTheme : lightTheme,
          syntaxHighlighting(
            isDark ? oneDarkHighlightStyle : defaultHighlightStyle,
          ),
        ],
      });
      return new EditorView({ state, parent: hostEl });
    },

    async resetConfig() {
      const ok = await window.mojoConfirm?.({
        title: "Reset settings",
        message:
          "Reset plot to factory defaults? This will clear your current view.",
        confirmLabel: "Reset",
        cancelLabel: "Cancel",
        variant: "info",
      });
      if (ok) {
        localStorage.removeItem("mojo_mosaic_config");
        this.config = JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as PlotConfig;
        if (this.columns.includes("time")) this.config.xAxis!.col! = "time";
        this.notify("Settings Reset", "info");
        this.configRaw = JSON.stringify(this.config, null, 4);
      }
    },

    async copyToClipboard(text: string, successMsg = "Copied to clipboard!") {
      if (navigator.clipboard && window.isSecureContext) {
        try {
          await navigator.clipboard.writeText(text);
          this.notify(successMsg, "success");
          return;
        } catch (err) {
          console.warn("Modern clipboard failed, falling back...", err);
        }
      }
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.cssText = "position:fixed;left:-9999px;top:0";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        if (document.execCommand("copy")) {
          this.notify(successMsg, "success");
        } else throw new Error("execCommand returned false");
      } catch {
        this.notify("Failed to copy to clipboard", "error");
      }
      document.body.removeChild(textArea);
    },

    async downloadPlot(format: string, scale = 1) {
      const el = document.getElementById("plot-area") as HTMLElement & {
        layout: { paper_bgcolor: string; plot_bgcolor: string };
      };
      if (!el) return;
      const plotlyFormat = format === "jpg" ? "jpeg" : format;
      const isDark = document.documentElement.classList.contains("dark");
      const bgColor = isDark ? tw.slate[800] : "#ffffff";
      const resW = Math.round(1280 * scale);
      const resH = Math.round(720 * scale);
      this.notify(
        `Exporting ${resW}x${resH} ${format.toUpperCase()}...`,
        "info",
      );
      try {
        const origPaper = el.layout.paper_bgcolor;
        const origPlot = el.layout.plot_bgcolor;
        await Plotly.relayout(el, {
          paper_bgcolor: bgColor,
          plot_bgcolor: bgColor,
        });
        const dataUrl = await Plotly.toImage(el, {
          format: plotlyFormat,
          width: 1280,
          height: 720,
          scale,
        });
        await Plotly.relayout(el, {
          paper_bgcolor: origPaper,
          plot_bgcolor: origPlot,
        });
        const link = document.createElement("a");
        link.href = dataUrl;
        link.download = `${this.trialId}_${resW}p.${format}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        this.notify(
          `${format.toUpperCase()} saved (${resW}×${resH})`,
          "success",
        );
      } catch (e) {
        console.error("Export failed", e);
        this.notify("Export failed", "error");
      } finally {
        this.downloadOpen = false;
      }
    },

    downloadCSV() {
      if (!this.data || Object.keys(this.config.yAxes).length === 0) return;
      const activeCols = [
        this.config.xAxis!.col!,
        ...Object.keys(this.config.yAxes),
      ];
      const rowCount = this.data[this.config.xAxis!.col!]?.length ?? 0;
      let csv = activeCols.join(",") + "\n";
      for (let i = 0; i < rowCount; i++) {
        csv +=
          activeCols.map((col) => this.data![col]?.[i] ?? "").join(",") + "\n";
      }
      const link = document.createElement("a");
      link.href = URL.createObjectURL(
        new Blob([csv], { type: "text/csv;charset=utf-8;" }),
      );
      link.setAttribute("download", `${this.trialId}_filtered.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      this.downloadOpen = false;
      this.notify("Filtered CSV Exported", "success");
    },

    downloadJSON() {
      const link = document.createElement("a");
      link.href = URL.createObjectURL(
        new Blob([JSON.stringify(this.config, null, 4)], {
          type: "application/json",
        }),
      );
      link.setAttribute("download", `${this.trialId}_config.json`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      this.downloadOpen = false;
      this.notify("Configuration JSON Exported", "success");
    },

    handleDrop(e: DragEvent) {
      const file = e.dataTransfer?.files[0];
      if (!file) return; // not a file drop (e.g. internal tab reorder) — ignore silently
      if (file.type !== "application/json" && !file.name.endsWith(".json")) {
        this.notify("Please drop a .json file", "error");
        return;
      }
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const imported = JSON.parse(
            event.target?.result as string,
          ) as Partial<PlotConfig>;
          this.config = { ...this.config, ...imported };
          this.notify("Configuration restored!", "success");
          this.configRaw = JSON.stringify(this.config, null, 4);
        } catch {
          this.notify("Invalid Config File", "error");
        }
      };
      reader.readAsText(file);
    },

    // -----------------------------------------------------------------------
    // Y-axis management
    // -----------------------------------------------------------------------
    toggleY(col: string) {
      if (this.config.yAxes[col]) {
        const { [col]: _, ...rest } = this.config.yAxes;
        this.config.yAxes = rest;
      } else {
        const usedStyles = Object.values(this.config.yAxes).map((y) => ({
          color: y.color,
          dash: y.dash,
        }));
        const nextStyle = this.nextAvailableStyle(usedStyles);
        const initFilters: FilterEntry[] = this.config.refFrame
          ? [
              {
                type: "rotation",
                quatCol: this.config.refFrame,
                invert: true,
                enabled: true,
              },
            ]
          : [];
        this.config.yAxes[col] = {
          color: nextStyle.color,
          label: "",
          width: 3,
          opacity: 1,
          filters: initFilters,
          dash: nextStyle.dash,
          marker: "none",
        };
        // eagerly fetch if this column has no cached data yet
        if (!Object.prototype.hasOwnProperty.call(this.data ?? {}, col)) {
          void (async () => {
            try {
              const resp = await this.fetchTrialData(this.trialId, [col]);
              this.data = { ...(this.data ?? {}), ...resp.data };
              this.saveAndRender();
            } catch {
              // non-critical - empty trace shown until data arrives
            }
          })();
        }
      }
      this.saveAndRender();
    },

    clearYAxes() {
      if (Object.keys(this.config.yAxes).length === 0) return;
      this.config.yAxes = {};
      this.saveAndRender();
      this.configRaw = JSON.stringify(this.config, null, 4);
      this.notify("Signals Cleared", "info");
    },

    applyRefFrame(frame: string | null) {
      for (const col of Object.keys(this.config.yAxes)) {
        const yConfig = this.config.yAxes[col];
        if (!yConfig) continue;
        if (frame) {
          const newEntry: FilterEntry = {
            type: "rotation",
            quatCol: frame,
            invert: true,
            enabled: true,
          };
          const idx = yConfig.filters.findIndex((f) => f.type === "rotation");
          if (idx >= 0) {
            // Replace in-place to preserve the user's chosen position in the stack
            yConfig.filters = [
              ...yConfig.filters.slice(0, idx),
              newEntry,
              ...yConfig.filters.slice(idx + 1),
            ];
          } else {
            yConfig.filters = [newEntry, ...yConfig.filters];
          }
        } else {
          const idx = yConfig.filters.findIndex((f) => f.type === "rotation");
          if (idx >= 0) {
            yConfig.filters = [
              ...yConfig.filters.slice(0, idx),
              ...yConfig.filters.slice(idx + 1),
            ];
          }
        }
      }
    },

    warpToTrial() {
      if (
        this.warpId === null ||
        this.warpId === undefined ||
        this.warpId === ("" as unknown)
      )
        return;
      const paddedNum = String(this.warpId).padStart(this.paddingLen, "0");
      window.location.href = `/mosaic/trial_${paddedNum}`;
    },

    getSignalColor(index: number): string {
      return this.plotColors[index % this.plotColors.length] ?? tw.cyan[500];
    },

    // picks the lowest-index (color, dash) pair not already in use by `used`,
    // so removing an earlier item in the cycle and adding a new one doesn't
    // collide with a pair still in use. Cycles through every color before
    // advancing to the next dash style, and falls back to round-robin by
    // count once every color/dash combination is taken.
    nextAvailableStyle(
      used: { color: string; dash: DashStyle }[],
    ): { color: string; dash: DashStyle } {
      const usedKeys = new Set(used.map((u) => `${u.color}|${u.dash}`));
      const numColors = this.plotColors.length;
      const numCombos = numColors * this.dashStyles.length;
      const styleAt = (i: number) => ({
        color: this.getSignalColor(i % numColors),
        dash: this.dashStyles[Math.floor(i / numColors) % this.dashStyles.length]!,
      });
      let i = 0;
      while (i < numCombos) {
        const style = styleAt(i);
        if (!usedKeys.has(`${style.color}|${style.dash}`)) return style;
        i++;
      }
      return styleAt(used.length);
    },

    getYProps(axis: string, index: number) {
      const obj = this.config.yAxes[axis] ?? ({} as Partial<YAxisConfig>);
      return {
        name: axis,
        label: obj.label || axis,
        color: obj.color || this.getSignalColor(index),
        width: obj.width ?? 3,
        opacity: obj.opacity ?? 1.0,
        dash: obj.dash ?? "solid",
        marker: obj.marker ?? "none",
      };
    },

    // -----------------------------------------------------------------------
    // Filter stack management
    // -----------------------------------------------------------------------
    getFilterSchema(filterType: string): FilterSchema | undefined {
      return this.filterSchemas.find((s) => s.type === filterType);
    },

    get groupedFilterSchemas(): {
      category: string;
      schemas: FilterSchema[];
    }[] {
      const ORDER = [
        "Smoothing",
        "Arithmetic",
        "Trigonometry",
        "Calculus",
        "Comparison",
        "Bounding",
        "Misc",
      ];
      const groups: Record<string, FilterSchema[]> = {};
      for (const s of this.filterSchemas) {
        const cat = s.category ?? "Misc";
        (groups[cat] ??= []).push(s);
      }
      return ORDER.filter((c) => groups[c]?.length).map((c) => ({
        category: c,
        schemas: groups[c],
      }));
    },

    evalMathExpr(expr: string): number | null {
      const s = String(expr ?? "").trim();
      if (!s) return null;
      const n = Number(s);
      if (!isNaN(n)) return n;
      try {
        // Expose a safe math context - no access to globals beyond these names.
        const fn = new Function(
          "pi",
          "e",
          "sin",
          "cos",
          "tan",
          "asin",
          "acos",
          "atan",
          "atan2",
          "sqrt",
          "cbrt",
          "log",
          "log2",
          "log10",
          "abs",
          "floor",
          "ceil",
          "round",
          "sign",
          "pow",
          "exp",
          "max",
          "min",
          `"use strict"; return (${s})`,
        );
        const result = fn(
          Math.PI,
          Math.E,
          Math.sin,
          Math.cos,
          Math.tan,
          Math.asin,
          Math.acos,
          Math.atan,
          Math.atan2,
          Math.sqrt,
          Math.cbrt,
          Math.log,
          Math.log2,
          Math.log10,
          Math.abs,
          Math.floor,
          Math.ceil,
          Math.round,
          Math.sign,
          Math.pow,
          Math.exp,
          Math.max,
          Math.min,
        ) as unknown;
        if (typeof result === "number" && isFinite(result)) return result;
      } catch {
        // invalid expression - fall through
      }
      return null;
    },

    getUnitOptions(
      groups: UnitGroup[] | undefined,
      fromUnit: string | null | undefined,
      colDimension?: string | null,
    ): UnitGroup[] {
      if (!groups) return [];
      // normalize Pint canonical strings ("m / s ** 2") to compact ("m/s^2") for matching
      const normalize = (u: string) => u.replace(/\s+/g, "").replace(/\*\*/g, "^");
      if (fromUnit) {
        const norm = normalize(fromUnit);
        const match = groups.find((g) =>
          g.units.some((u) => u === fromUnit || u === norm),
        );
        if (match) return [match];
      }
      // fall back to dimension-based group filtering when column dimension is known
      if (colDimension && groups.some((g) => g.dimension)) {
        const compatible = groups.filter((g) => g.dimension === colDimension);
        if (compatible.length > 0) return compatible;
      }
      return groups;
    },

    // returns the concrete unit of col after walking its active filter stack;
    // starts from column_metadata and updates when a unit filter's toUnit changes it;
    // pass filtersOverride for axes (e.g. x-axis) that store filters outside config.yAxes
    effectiveUnit(col: string, filtersOverride?: FilterEntry[]): string | null {
      let unit: string | null = this.columnMetadata[col]?.unit ?? null;
      const filters = filtersOverride ?? this.config.yAxes[col]?.filters ?? [];
      for (const f of filters) {
        if (f.enabled === false || f.type !== "unit") continue;
        const to = (f as Record<string, unknown>)["toUnit"] as string | undefined;
        if (to) unit = to;
      }
      return unit;
    },

    getFilterSummary(entry: FilterEntry): string {
      const schema = this.filterSchemas.find((s) => s.type === entry.type);
      if (!schema || schema.params.length === 0) return "";
      if (entry.type === "unit")
        return `${entry["from_unit"] ?? "?"} → ${entry["to_unit"] ?? "?"}`;
      const parts = schema.params
        .filter((p) => (entry as Record<string, unknown>)[p.name] != null)
        .map((p) => {
          const val = (entry as Record<string, unknown>)[p.name];
          if (typeof val === "boolean")
            return `${p.name}=${val ? "on" : "off"}`;
          if (typeof val === "number") return `${p.name}=${formatNum(val)}`;
          return `${p.name}=${val as string}`;
        });
      return parts.slice(0, 3).join(", ");
    },

    addFilterToTemp(temp: YAxisConfig, filterType: string, col?: string) {
      const schema = this.filterSchemas.find((s) => s.type === filterType);
      if (!schema) return;
      if (!temp.filters) temp.filters = [];
      if (
        filterType === "rotation" &&
        temp.filters.some((f) => f.type === "rotation")
      )
        return;
      const entry: FilterEntry = { type: filterType, enabled: true };
      for (const p of schema.params) {
        (entry as Record<string, unknown>)[p.name] = p.default;
      }
      // prefill fromUnit with a known unit group string; prefer group_unit (pre-resolved by
      // Python to the nearest group equivalent), then unit (when a display unit system is
      // active), so the dropdown shows a valid pre-selected option rather than "- select -"
      if (filterType === "unit" && col) {
        const meta = this.columnMetadata[col];
        const metaUnit = meta?.group_unit ?? meta?.unit;
        if (metaUnit) {
          (entry as Record<string, unknown>)["fromUnit"] = metaUnit;
        }
      }
      temp.filters.push(entry);
    },

    removeFilterFromTemp(temp: YAxisConfig, index: number) {
      if (!temp.filters) return;
      temp.filters.splice(index, 1);
    },

    moveFilterInTemp(temp: YAxisConfig, index: number, direction: number) {
      if (!temp.filters) return;
      const newIdx = index + direction;
      if (newIdx < 0 || newIdx >= temp.filters.length) return;
      const [item] = temp.filters.splice(index, 1);
      if (item) temp.filters.splice(newIdx, 0, item);
    },

    setFilterParamOnTemp(
      temp: YAxisConfig,
      filterIndex: number,
      paramName: string,
      value: unknown,
    ) {
      if (!temp.filters?.[filterIndex]) return;
      (temp.filters[filterIndex] as Record<string, unknown>)[paramName] = value;
    },

    duplicateFilterInTemp(temp: YAxisConfig, index: number) {
      if (!temp.filters?.[index]) return;
      const copy = JSON.parse(
        JSON.stringify(temp.filters[index]),
      ) as FilterEntry;
      temp.filters.splice(index + 1, 0, copy);
    },

    // -----------------------------------------------------------------------
    // Profiles
    // Encode each path segment individually so 'project/name' becomes 'project/name'
    // in the URL (not 'project%2Fname'), matching the {name:path} FastAPI route.
    _profileUrl(name: string): string {
      return `/mosaic/api/profiles/${name.split("/").map(encodeURIComponent).join("/")}`;
    },

    // ── Lab ──────────────────────────────────────────────────────────────────
    relTime(ms: number): string {
      const diff = Date.now() - ms;
      const min = Math.floor(diff / 60000);
      if (min < 1) return "just now";
      if (min < 60) return `${min}m ago`;
      const h = Math.floor(min / 60);
      if (h < 24) return `${h}h ago`;
      const d = Math.floor(h / 24);
      return d === 1 ? "yesterday" : `${d}d ago`;
    },

    async loadLabSchemas() {
      try {
        const resp = await fetch("/mosaic/api/lab");
        if (!resp.ok) return;
        const all = (await resp.json()) as Omit<
          (typeof this.labSchemas)[0],
          "valid" | "missing"
        >[];
        // Deduplicate and sort inputs/outputs for each lab.
        const schemas = all.map((lab) => ({
          ...lab,
          signal_in_columns: [...new Set(lab.signal_in_columns)].sort(),
          outputs: [...new Set(lab.outputs)].sort(),
          is_template: lab.is_template ?? false,
          template_inputs: lab.template_inputs ?? [],
          template_outputs: lab.template_outputs ?? [],
        }));
        // Iterative BFS: a lab is valid when all its inputs are already available.
        // Labs that read from other valid labs' outputs need multiple passes to resolve.
        const baseColumns = this.columns.filter((c) => !c.startsWith("Lab/"));
        const available = new Set(baseColumns);
        const validLabs = new Set<string>();
        let changed = true;
        while (changed) {
          changed = false;
          for (const lab of schemas) {
            if (validLabs.has(lab.name)) continue;
            if (lab.signal_in_columns.every((c) => available.has(c))) {
              validLabs.add(lab.name);
              lab.outputs.forEach((o) => available.add(`Lab/${lab.name}/${o}`));
              changed = true;
            }
          }
        }
        this.labSchemas = schemas.map((lab) => ({
          ...lab,
          missing: lab.signal_in_columns.filter((c) => !available.has(c)),
          valid: validLabs.has(lab.name),
        }));
        // Rebuild virtual Lab columns from scratch - removes stale entries from deleted labs.
        this.columns = [...available].sort();
      } catch {
        // Lab endpoint unavailable - silently ignore
      }
    },

    async refreshLabValidation() {
      await this.loadLabSchemas();
      void this.loadProfiles();
    },

    // ── tab helpers ──────────────────────────────────────────────────────────

    _tabId(): string {
      return `t${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
    },

    _initTabs() {
      try {
        const raw = localStorage.getItem("mojo:lab:tabs");
        if (raw) {
          const tabs = JSON.parse(raw) as LabTab[];
          if (Array.isArray(tabs) && tabs.length > 0) {
            this.labTabs = tabs;
            const activeId = localStorage.getItem("mojo:lab:activeTab") ?? "";
            this.labActiveTabId =
              tabs.find((t) => t.id === activeId)?.id ?? tabs[0]!.id;
            const active = this.labTabs.find(
              (t) => t.id === this.labActiveTabId,
            )!;
            this.labName = active.name;
            this.labGraph = active.graph;
            return;
          }
        }
      } catch {}
      // fall back to old single-lab format
      const name = localStorage.getItem("mojo:lab:name") ?? "";
      const graph = (() => {
        try {
          const s = localStorage.getItem("mojo:lab:draft");
          return s ? (JSON.parse(s) as object) : null;
        } catch {
          return null;
        }
      })();
      const id = this._tabId();
      this.labTabs = [
        { id, name, graph, savedState: null, dirty: false, viewport: null },
      ];
      this.labActiveTabId = id;
      this.labName = name;
      this.labGraph = graph;
    },

    _snapshotActiveTab() {
      if (!this.labActiveTabId) return;
      const tab = this.labTabs.find((t) => t.id === this.labActiveTabId);
      if (!tab) return;
      // run any pending debounced undo-history snapshot first so the stack's
      // top entry matches exactly what we persist onto the tab
      window.mojoLabFlushSnapshot?.();
      tab.graph = window.mojoLabSerialize?.() ?? tab.graph;
      tab.name = this.labName;
      // tab.savedState is NOT touched here - it's the tab's own baseline,
      // owned exclusively by this LabTab object (see mojoLabGetBaseline /
      // mojoLabSetBaseline) and never derived from a transient local copy.
      tab.viewport = window.mojoLabGetViewport?.() ?? tab.viewport;
      // keep labGraph (the value mojoLabInit reloads from on reopen) in sync,
      // otherwise closing and reopening the lab restores the pre-edit graph
      this.labGraph = tab.graph;
    },

    _persistTabs() {
      // persist tab list to localStorage WITHOUT snapshotting the live canvas —
      // safe to call immediately after _activateTab() before mojoLabInit fires
      try {
        localStorage.setItem("mojo:lab:tabs", JSON.stringify(this.labTabs));
        localStorage.setItem("mojo:lab:activeTab", this.labActiveTabId ?? "");
      } catch {}
    },

    _saveTabs() {
      this._snapshotActiveTab();
      this._persistTabs();
    },

    async _activateTab(tabId: string) {
      this.labActiveTabId = tabId;
      const tab = this.labTabs.find((t) => t.id === tabId);
      if (!tab) return;
      this.labName = tab.name;
      this.labGraph = tab.graph;
      if (this.labOpen) {
        await this.$nextTick();
        document.dispatchEvent(new CustomEvent("mojo:lab-activate-tab"));
      }
    },

    async switchTab(tabId: string) {
      if (tabId === this.labActiveTabId) return;
      this._snapshotActiveTab();
      await this._activateTab(tabId);
      // persist only - the canvas hasn't reloaded the new tab's graph yet
      // (mojoLabInit fires async via the mojo:lab-activate-tab event), so
      // re-snapshotting here would serialize the still-displayed old graph
      // onto the newly active tab and clobber it
      this._persistTabs();
    },

    async newTab() {
      this._snapshotActiveTab();
      const id = this._tabId();
      this.labTabs.push({
        id,
        name: "",
        graph: null,
        savedState: null,
        viewport: null,
        dirty: false,
      });
      await this._activateTab(id);
      this._persistTabs();
    },

    async closeTab(tabId: string) {
      const tabIdx = this.labTabs.findIndex((t) => t.id === tabId);
      if (tabIdx === -1) return;
      const tab = this.labTabs[tabIdx]!;
      if (tabId === this.labActiveTabId) this._snapshotActiveTab();
      const isDirty =
        tabId === this.labActiveTabId
          ? (window.mojoLabHasUnsavedChanges?.() ?? false)
          : tab.dirty;
      if (isDirty) {
        const ok = await window.mojoConfirm?.({
          title: "Unsaved changes",
          message: tab.name
            ? `Close "${tab.name}" and discard unsaved changes?`
            : "Close this tab and discard unsaved changes?",
          confirmLabel: "Close",
          cancelLabel: "Keep editing",
          variant: "warning",
        });
        if (!ok) return;
      }
      this.labTabs.splice(tabIdx, 1);
      window.mojoLabDiscardHistory?.(tabId);
      if (this.labTabs.length === 0) {
        const newId = this._tabId();
        this.labTabs.push({
          id: newId,
          name: "",
          graph: null,
          savedState: null,
          viewport: null,
          dirty: false,
        });
        await this._activateTab(newId);
      } else if (tabId === this.labActiveTabId) {
        const newActive =
          this.labTabs[Math.min(tabIdx, this.labTabs.length - 1)]!;
        await this._activateTab(newActive.id);
      }
      // persist only - see switchTab for why we must not re-snapshot here
      this._persistTabs();
    },

    async loadLabInNewTab(labName: string) {
      // if this lab is already open in a tab, switch to it rather than
      // duplicating it (and preserve any unsaved edits already in that tab)
      const existing = this.labTabs.find((t) => t.name === labName);
      if (existing) {
        if (existing.id !== this.labActiveTabId) {
          this._snapshotActiveTab();
          await this._activateTab(existing.id);
          this._persistTabs();
        }
        return;
      }
      const safePath = labName.split("/").map(encodeURIComponent).join("/");
      try {
        const resp = await fetch(`/mosaic/api/lab/${safePath}`);
        if (!resp.ok) throw new Error(resp.statusText);
        const graph = (await resp.json()) as object;

        // reuse the current tab if it is blank (untitled + no unsaved changes)
        const activeTab = this.labTabs.find(
          (t) => t.id === this.labActiveTabId,
        );
        if (activeTab && !activeTab.name && !activeTab.dirty) {
          activeTab.name = labName;
          activeTab.graph = graph;
          activeTab.savedState = null;
          activeTab.dirty = false;
          this.labName = labName;
          this.labGraph = graph;
          if (this.labOpen) {
            await this.$nextTick();
            document.dispatchEvent(new CustomEvent("mojo:lab-activate-tab"));
          }
        } else {
          this._snapshotActiveTab();
          const id = this._tabId();
          this.labTabs.push({
            id,
            name: labName,
            graph,
            savedState: null,
            viewport: null,
            dirty: false,
          });
          await this._activateTab(id);
        }
        // persist without snapshotting — mojoLabInit hasn't fired yet, so the
        // canvas is still showing the previous tab's graph; re-snapshotting
        // here would serialize that stale content onto the new tab
        this._persistTabs();
      } catch (err) {
        this.notify(`Failed to load "${labName}": ${String(err)}`, "error");
      }
    },

    async saveLabGraph(name: string, graph: object) {
      const trimmed = name.trim();
      if (!trimmed) return;
      const exists = this.labSchemas.some((s) => s.name === trimmed);
      if (exists) {
        const ok = await window.mojoConfirm?.({
          title: "Overwrite lab",
          message: `"${trimmed}" already exists. Replace it with the current graph?`,
          confirmLabel: "Overwrite",
          cancelLabel: "Cancel",
          variant: "warning",
        });
        if (!ok) return;
      }
      const safePath = trimmed.split("/").map(encodeURIComponent).join("/");
      try {
        const resp = await fetch(`/mosaic/api/lab/${safePath}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(graph),
        });
        if (!resp.ok) {
          const detail = await resp.text().catch(() => resp.statusText);
          this.notify(`Save failed: ${detail}`, "error");
          return;
        }
        this.notify(`Lab "${trimmed}" saved`, "success");
        // the just-saved content is the new clean baseline for the active tab
        window.mojoLabRebaseline?.();
        this.labName = trimmed;
        const activeTab = this.labTabs.find(
          (t) => t.id === this.labActiveTabId,
        );
        if (activeTab) {
          activeTab.name = trimmed;
          activeTab.dirty = false;
        }
        this._saveTabs();
        await this.refreshLabValidation();
        // compute the transitive closure of labs whose outputs may now be stale:
        // the saved lab itself, plus any lab that (directly or transitively) reads from it
        const dependents = new Map<string, string[]>();
        for (const lab of this.labSchemas) {
          for (const col of lab.signal_in_columns) {
            if (col.startsWith("Lab/")) {
              // lab names may contain '/' (nested folders); the output label is
              // always the final segment, so split from the right
              const depRest = col.slice(4);
              const depSplitIdx = depRest.lastIndexOf("/");
              const src = depSplitIdx >= 0 ? depRest.slice(0, depSplitIdx) : "";
              if (src) {
                if (!dependents.has(src)) dependents.set(src, []);
                dependents.get(src)!.push(lab.name);
              }
            }
          }
        }
        const toInvalidate = new Set<string>([trimmed]);
        const bfsQueue = [trimmed];
        while (bfsQueue.length > 0) {
          const cur = bfsQueue.shift()!;
          for (const dep of dependents.get(cur) ?? []) {
            if (!toInvalidate.has(dep)) {
              toInvalidate.add(dep);
              bfsQueue.push(dep);
            }
          }
        }
        // evict all stale entries from the client-side data cache
        const newData = { ...(this.data ?? {}) };
        let evicted = false;
        for (const labName of toInvalidate) {
          const prefix = `Lab/${labName}/`;
          for (const key of Object.keys(newData)) {
            if (key.startsWith(prefix)) {
              delete newData[key];
              evicted = true;
            }
          }
        }
        if (evicted) this.data = newData;
        // re-fetch currently plotted cols that were just evicted
        const activeCols = [
          ...Object.keys(this.config.yAxes),
          this.config.xAxis?.col ?? "",
        ].filter((c) => {
          for (const labName of toInvalidate) {
            if (
              c.startsWith(`Lab/${labName}/`) &&
              !Object.prototype.hasOwnProperty.call(this.data ?? {}, c)
            )
              return true;
          }
          return false;
        });
        if (activeCols.length > 0) {
          try {
            const refetch = await this.fetchTrialData(this.trialId, activeCols);
            this.data = { ...(this.data ?? {}), ...refetch.data };
            this.saveAndRender();
          } catch {
            // non-critical: plot drops stale trace until background discovery refetches
          }
        }
      } catch (err) {
        this.notify(`Save failed: ${String(err)}`, "error");
      }
    },

    selectNodeColumn(col: string) {
      if (this.nodePickingColumn !== null) {
        // Defined in _signal_lab.html - updates the LiteGraph node property
        if (typeof window.mojoLabSelectNodeColumn === "function") {
          window.mojoLabSelectNodeColumn(this.nodePickingColumn, col);
        }
      }
      this.nodePickingColumn = null;
      this.nodeColSearch = "";
    },

    selectNodeQuat(base: string) {
      if (this.nodePickingQuat !== null) {
        // Defined in _signal_lab.html - updates the LiteGraph node property
        if (typeof window.mojoLabSelectNodeQuat === "function") {
          window.mojoLabSelectNodeQuat(this.nodePickingQuat, base);
        }
      }
      this.nodePickingQuat = null;
      this.nodeQuatSearch = "";
    },

    selectNodeTemplate(name: string) {
      if (this.nodePickingTemplate !== null) {
        if (typeof window.mojoLabSelectNodeTemplate === "function") {
          window.mojoLabSelectNodeTemplate(this.nodePickingTemplate, name);
        }
      }
      this.nodePickingTemplate = null;
    },

    async deleteLabGraph(name: string) {
      const safePath = name.split("/").map(encodeURIComponent).join("/");
      await fetch(`/mosaic/api/lab/${safePath}`, {
        method: "DELETE",
      });
      this.notify(`Lab "${name}" deleted`, "info");
      await this.refreshLabValidation();
    },

    // -----------------------------------------------------------------------
    async loadProfiles() {
      try {
        const resp = await fetch("/mosaic/api/profiles");
        this.profiles = (await resp.json()) as Array<{
          name: string;
          modified: number;
        }>;

        const colSet = new Set(this.columns);
        const frames = new Set(
          this.columns
            .filter((c) => c.endsWith(":w"))
            .map((c) => c.replace(":w", "")),
        );
        const warnings: Record<string, string[]> = {};
        await Promise.all(
          this.profiles.map(async (p) => {
            try {
              const pr = await fetch(this._profileUrl(p.name));
              if (!pr.ok) return;
              const cfg = (await pr.json()) as Partial<PlotConfig>;
              const w: string[] = [];
              if (cfg.xAxis?.col && !colSet.has(cfg.xAxis.col))
                w.push(`x-axis "${cfg.xAxis!.col!}"`);
              for (const key of Object.keys(cfg.yAxes ?? {})) {
                if (!colSet.has(key)) w.push(`"${key}"`);
              }
              if (cfg.refFrame && !frames.has(cfg.refFrame))
                w.push(`frame "${cfg.refFrame}"`);
              if (w.length) warnings[p.name] = w;
            } catch {
              /* skip */
            }
          }),
        );
        this.profileWarnings = warnings;
      } catch (e) {
        console.warn("[mojo] Failed to load profiles", e);
      }
    },

    async saveProfile() {
      const name = this.profileNameDraft.trim();
      if (!name) {
        this.notify("Enter a profile name", "error");
        return;
      }
      const normalise = (s: string) => s.toLowerCase().replace(/\s+/g, "_");
      const existing = this.profiles.find(
        (p) => normalise(p.name) === normalise(name),
      );
      if (existing) {
        const ok = await window.mojoConfirm?.({
          title: "Overwrite profile",
          message: `"${existing.name}" already exists. Replace it with the current configuration?`,
          confirmLabel: "Overwrite",
          cancelLabel: "Cancel",
          variant: "warning",
        });
        if (!ok) return;
      }
      try {
        const resp = await fetch(this._profileUrl(name), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.config),
        });
        if (!resp.ok) throw new Error("Save failed");
        const result = (await resp.json()) as { name: string };
        this.profileNameDraft = "";
        await this.loadProfiles();
        this.notify(`Profile "${result.name}" saved`, "success");
      } catch {
        this.notify("Failed to save profile", "error");
      }
    },

    async loadProfile(name: string) {
      try {
        const resp = await fetch(this._profileUrl(name));
        if (!resp.ok) {
          const body = (await resp.json().catch(() => ({}))) as {
            detail?: string;
          };
          throw new Error(body.detail ?? `HTTP ${resp.status}`);
        }
        const loaded = (await resp.json()) as Partial<PlotConfig>;

        const colSet = new Set(this.columns);
        const frames = new Set(
          this.columns
            .filter((c) => c.endsWith(":w"))
            .map((c) => c.replace(":w", "")),
        );
        // columns not present in this trial are tolerated: the profile still loads
        // (so it can be used as a starting point), but those signals won't plot
        // until matching columns exist.
        const missing: string[] = [];
        if (
          loaded.xAxis?.col &&
          !loaded.xAxis.col.startsWith("Lab/") &&
          !colSet.has(loaded.xAxis.col)
        )
          missing.push(`x-axis "${loaded.xAxis!.col!}"`);
        for (const key of Object.keys(loaded.yAxes ?? {})) {
          if (!key.startsWith("Lab/") && !colSet.has(key))
            missing.push(`signal "${key}"`);
        }
        if (loaded.refFrame && !frames.has(loaded.refFrame))
          missing.push(`frame "${loaded.refFrame}"`);

        this.config = { ...this.config, ...loaded };

        if (missing.length) {
          this.notify(
            `Profile "${name}" loaded, but won't plot until added to this trial: ${missing.join(", ")}`,
            "info",
          );
        } else {
          this.notify(`Profile "${name}" loaded`, "success");
        }

        // Fetch data for any columns the profile introduces that aren't cached yet.
        const needed: string[] = [];
        if (loaded.xAxis?.col && !this.data?.[loaded.xAxis.col])
          needed.push(loaded.xAxis.col);
        for (const col of Object.keys(loaded.yAxes ?? {})) {
          if (!this.data?.[col]) needed.push(col);
        }
        if (needed.length > 0) {
          const fetched = await this.fetchTrialData(this.trialId, needed);
          this.data = { ...(this.data ?? {}), ...fetched.data };
        }

        void this.$nextTick(() => {
          this.configErrors = this.validateConfig(this.config as PlotConfig);
          this.isValidConfig = this.configErrors.length === 0;
          this.isValidJson = true;
          this.saveAndRender();
        });
      } catch (e) {
        this.notify(
          `Failed to load "${name}": ${(e as Error).message}`,
          "error",
        );
      }
    },

    async deleteProfile(name: string) {
      const ok = await window.mojoConfirm?.({
        title: "Delete profile",
        message: `Delete "${name}"? This cannot be undone.`,
        confirmLabel: "Delete",
        cancelLabel: "Cancel",
        variant: "danger",
      });
      if (!ok) return;
      try {
        const resp = await fetch(this._profileUrl(name), { method: "DELETE" });
        if (!resp.ok) throw new Error("Delete failed");
        await this.loadProfiles();
        this.notify(`Profile "${name}" deleted`, "info");
      } catch {
        this.notify(`Failed to delete "${name}"`, "error");
      }
    },

    applySignalConfig(col: string, temp: YAxisConfig) {
      // deep copy prevents temp.filters from sharing a reference with config.yAxes[col].filters
      this.config.yAxes[col] = JSON.parse(JSON.stringify(temp)) as YAxisConfig;
      delete this.signalDrafts[col];
      // config watcher handles pushHistory + filter re-fetch + saveAndRender
    },

    getDraft(col: string): { draft: YAxisConfig; baseSnapshot: string } | null {
      return (
        (
          this.signalDrafts as Record<
            string,
            { draft: YAxisConfig; baseSnapshot: string }
          >
        )[col] ?? null
      );
    },

    saveDraft(col: string, draft: YAxisConfig, baseSnapshot: string) {
      (
        this.signalDrafts as Record<
          string,
          { draft: YAxisConfig; baseSnapshot: string }
        >
      )[col] = { draft, baseSnapshot };
    },

    clearDraft(col: string) {
      delete (
        this.signalDrafts as Record<
          string,
          { draft: YAxisConfig; baseSnapshot: string }
        >
      )[col];
    },

    // -----------------------------------------------------------------------
    // Range helpers
    // -----------------------------------------------------------------------
    calculatePaddedRange(keys: string[], padding = true): [number, number] {
      let globalMin = Infinity;
      let globalMax = -Infinity;
      const activeDatasets: Array<Record<string, number[]>> = [this.data ?? {}];

      if (this.config.vsEnabled) {
        const [start, end] = this.config.vsRange;
        const pinnedSet = new Set(this.config.vsPinned ?? []);
        Object.entries(this.vsDatasets).forEach(([vsId, dataset]) => {
          const n = parseInt(vsId.split("_").pop() ?? "");
          if ((n >= start && n <= end) || pinnedSet.has(n)) activeDatasets.push(dataset);
        });
      }

      activeDatasets.forEach((dataset) => {
        keys.forEach((key) => {
          const series = dataset[key];
          if (!series) return;
          for (let j = 0; j < series.length; j++) {
            const val = series[j] ?? 0;
            if (val < globalMin) globalMin = val;
            if (val > globalMax) globalMax = val;
          }
        });
      });

      if (globalMin === Infinity) return [0, 1];
      if (globalMin === globalMax) return [globalMin - 1, globalMax + 1];
      const pad = padding ? (globalMax - globalMin) / 16 : 0;
      return [globalMin - pad, globalMax + pad];
    },

    formatNum,
    breakableLabel,

    // reads the manual x/y axis min/max fields as strings for display; empty means autoscale
    rangeBoundValue(axis: "x" | "y", bound: "min" | "max"): string {
      const range = axis === "x" ? this.config.rangeX : this.config.rangeY;
      if (!range) return "";
      const val = bound === "min" ? range[0] : range[1];
      return val === null ? "" : String(val);
    },

    // sets a single x/y axis min/max field; an empty value reverts that side to autoscale
    setRangeBound(axis: "x" | "y", bound: "min" | "max", value: string) {
      const trimmed = value.trim();
      const num = trimmed === "" ? null : this.evalMathExpr(trimmed);
      if (trimmed !== "" && num === null) return;

      const current =
        (axis === "x" ? this.config.rangeX : this.config.rangeY) ??
        ([null, null] as [number | null, number | null]);
      const next: [number | null, number | null] =
        bound === "min" ? [num, current[1]] : [current[0], num];

      const resolved = next[0] === null && next[1] === null ? null : next;
      if (axis === "x") this.config.rangeX = resolved;
      else this.config.rangeY = resolved;
      void this.saveAndRender();
    },

    // resolves a possibly-partial axis range into a concrete [min, max], falling back
    // to the padded data range for whichever side is unset
    resolveAxisRange(
      configRange: [number | null, number | null] | null,
      keys: string[],
    ): [number, number] | null {
      if (!configRange || (configRange[0] === null && configRange[1] === null))
        return null;
      const [min, max] = configRange;
      if (min !== null && max !== null) return [min, max];
      const auto = this.calculatePaddedRange(keys);
      return [min ?? auto[0], max ?? auto[1]];
    },

    // (re)attaches the Plotly event handlers that drive zoom/pan range tracking,
    // double-click-to-reset, and frame-marker syncing. Plotly.purge clears the plot
    // element's internal event emitter, so this must be called again after every
    // Plotly.newPlot (not just once during init).
    _attachPlotEventHandlers() {
      const plotEl = document.getElementById("plot-area") as
        | (HTMLElement & {
            on(
              event: string,
              handler: (event: Record<string, unknown>) => void,
            ): void;
          })
        | null;
      if (!plotEl) return;

      plotEl.on("plotly_afterplot", () => {
        requestAnimationFrame(() => {
          this._renderFrameMarkers();
          this._syncOverlayVisibility();
        });
      });

      plotEl.on("plotly_doubleclick", () => {
        this.config.rangeX = null;
        this.config.rangeY = null;
        void this.renderPlot();
      });

      plotEl.on("plotly_relayout", (event) => {
        if (event["xaxis.autorange"] || event["yaxis.autorange"]) {
          this.config.rangeX = null;
          this.config.rangeY = null;
          void this.renderPlot();
          return;
        }
        if (event["xaxis.range[0]"] !== undefined) {
          this.config.rangeX = [
            event["xaxis.range[0]"] as number,
            event["xaxis.range[1]"] as number,
          ];
        }
        if (event["yaxis.range[0]"] !== undefined) {
          this.config.rangeY = [
            event["yaxis.range[0]"] as number,
            event["yaxis.range[1]"] as number,
          ];
        }
      });
    },

    // -----------------------------------------------------------------------
    // Plotly render
    // -----------------------------------------------------------------------
    renderPlot() {
      if (!this.data) return;

      const isDark = document.documentElement.classList.contains("dark");
      const textColor = isDark ? tw.slate[400] : tw.slate[600];
      const majorGrid = isDark ? tw.slate[950] : tw.slate[200];
      const minorGrid = isDark ? tw.slate[900] : tw.slate[100];
      const tooltipBg = isDark ? tw.slate[900] : "#ffffff";
      const tooltipFont = isDark ? tw.slate[50] : tw.slate[900];
      const tooltipBorder = tw.cyan[500];
      const spikeColor = tw.cyan[500];

      const isHoverDisabled = this.config.hover === "none";
      const showX =
        this.config.showSpike &&
        !isHoverDisabled &&
        (this.config.hover.includes("x") || this.config.hover === "closest");
      const showY =
        this.config.showSpike &&
        !isHoverDisabled &&
        (this.config.hover.includes("y") || this.config.hover === "closest");

      const isPolar = this.config.plotType === "polar";

      // a marker symbol of "none" hides per-point markers regardless of lineMode
      const traceMode = (marker: string): string => {
        if (marker !== "none") return this.config.lineMode;
        if (this.config.lineMode === "lines+markers") return "lines";
        if (this.config.lineMode === "markers") return "none";
        return this.config.lineMode;
      };

      const yKeys = Object.keys(this.config.yAxes);
      let traces: object[] = yKeys
        .map((key, i) => {
          const p = this.getYProps(key, i);
          if (!this.data![p.name]) {
            return null;
          }
          const unit = this.effectiveUnit(key);
          const traceLabel =
            p.label + (unit ? ` (${unit.replace(/\s+/g, "")})` : "");
          const lineStyle = {
            width: p.width,
            color: p.color,
            shape: this.config.interp,
            dash: p.dash,
          };
          if (isPolar) {
            return {
              r: this.data![p.name]!,
              theta: this.data![this.config.xAxis!.col!],
              name: traceLabel,
              mode: traceMode(p.marker),
              type: "scatterpolar",
              line: lineStyle,
              marker: { size: 6, symbol: p.marker },
              opacity: p.opacity,
              hoverlabel: {
                namelength: -1,
                bgcolor: tooltipBg,
                bordercolor: tooltipBorder,
                font: { family: "monospace", size: 12, color: tooltipFont },
              },
              hovertemplate: `<b>${key}</b><br>θ: %{theta:.4f}<br>r: %{r:.4f}<extra></extra>`,
            };
          }
          return {
            x: this.data![this.config.xAxis!.col!],
            y: this.data![p.name]!,
            name: traceLabel,
            mode: traceMode(p.marker),
            type: "scatter",
            line: lineStyle,
            marker: { size: 6, symbol: p.marker },
            opacity: p.opacity,
            hoverlabel: {
              namelength: -1,
              bgcolor: tooltipBg,
              bordercolor: tooltipBorder,
              font: { family: "monospace", size: 12, color: tooltipFont },
            },
            hovertemplate: `<b>${key}</b><br>%{x}: %{y:.4f}<extra></extra>`,
          };
        })
        .filter((t): t is NonNullable<typeof t> => t !== null);

      if (this.config.vsEnabled) {
        const [start, end] = this.config.vsRange;
        const pinnedSet = new Set(this.config.vsPinned ?? []);
        const legendTracker = new Set<string>();
        const sortedVsIds = Object.keys(this.vsDatasets).sort(
          (a, b) =>
            parseInt(a.split("_").pop() ?? "0") -
            parseInt(b.split("_").pop() ?? "0"),
        );
        sortedVsIds.forEach((vsId) => {
          const n = parseInt(vsId.split("_").pop() ?? "");
          if ((!((n >= start && n <= end) || pinnedSet.has(n))) || vsId === this.trialId) return;
          const dataset = this.vsDatasets[vsId];
          if (!dataset) return;
          const vsTraces = yKeys
            .map((key, i) => {
              const p = this.getYProps(key, i);
              if (!dataset[p.name]) return null;
              const isFirst = !legendTracker.has(key);
              const lineStyle = {
                width: 1,
                color: p.color,
                shape: this.config.interp,
                dash: "dot",
              };
              const t = isPolar
                ? {
                    r: dataset[p.name]!,
                    theta: dataset[this.config.xAxis!.col!],
                    name: `${p.label} (<i>vs.</i>)`,
                    legendgroup: `group_${key}`,
                    showlegend: isFirst,
                    mode: traceMode(p.marker),
                    type: "scatterpolar",
                    line: lineStyle,
                    opacity: 0.35,
                    marker: { size: 4, symbol: p.marker },
                    hoverlabel: { namelength: -1 },
                    hovertemplate: `<b>${key}</b> (#${n})<br>θ: %{theta:.4f}<br>r: %{r:.4f}<extra></extra>`,
                  }
                : {
                    x: dataset[this.config.xAxis!.col!],
                    y: dataset[p.name]!,
                    name: `${p.label} (<i>vs.</i>)`,
                    legendgroup: `group_${key}`,
                    showlegend: isFirst,
                    mode: traceMode(p.marker),
                    type: "scatter",
                    line: lineStyle,
                    opacity: 0.35,
                    marker: { size: 4, symbol: p.marker },
                    hoverlabel: { namelength: -1 },
                    hovertemplate: `<b>${key}</b> (#${n})<br>%{x}: %{y:.4f}<extra></extra>`,
                  };
              legendTracker.add(key);
              return t;
            })
            .filter((t): t is NonNullable<typeof t> => t !== null);
          traces = [...traces, ...vsTraces];
        });
      }

      const resolvedRangeX = this.resolveAxisRange(this.config.rangeX, [
        this.config.xAxis!.col!,
      ]);

      const xCol = this.config.xAxis!.col!;
      const xUnit = this.effectiveUnit(xCol, this.config.xAxis?.filters ?? []);
      const xAxisText =
        this.config.xAxisTitle ||
        (xUnit ? `${xCol} (${xUnit.replace(/\s+/g, "")})` : xCol);

      const xAxisObj = {
        type: this.config.xScale ?? "linear",
        ...(resolvedRangeX
          ? {
              autorange: false as const,
              range:
                this.config.xScale === "log"
                  ? [
                      Math.log10(Math.max(1e-6, resolvedRangeX[0])),
                      Math.log10(Math.max(1e-6, resolvedRangeX[1])),
                    ]
                  : resolvedRangeX,
            }
          : { autorange: true as const }),
        dtick:
          this.config.xScale === "log" && this.config.xLogBase
            ? Math.log10(this.config.xLogBase)
            : undefined,
        gridcolor: majorGrid,
        showgrid: this.config.grid !== "none",
        minor: { showgrid: this.config.grid === "all", gridcolor: minorGrid },
        zeroline: false,
        tickfont: { color: textColor, size: 14 },
        title: {
          text: xAxisText,
          font: { size: 14, color: textColor, family: "monospace" },
        },
        showspikes: showX,
        spikemode: "across",
        spikelinecolor: spikeColor,
        spikethickness: -2,
      };

      const frameLabel = this.config.refFrame
        ? `<br><span style="color: ${textColor}; font-size: 14px; opacity: 0.6;">[Frame: ${this.config.refFrame}]</span>`
        : "";

      const resolvedRangeY = this.resolveAxisRange(
        this.config.rangeY,
        Object.keys(this.config.yAxes),
      );

      const yAxisObj = {
        type: this.config.yScale ?? "linear",
        ...(resolvedRangeY
          ? {
              autorange: false as const,
              range:
                this.config.yScale === "log"
                  ? [
                      Math.log10(Math.max(1e-6, resolvedRangeY[0])),
                      Math.log10(Math.max(1e-6, resolvedRangeY[1])),
                    ]
                  : resolvedRangeY,
            }
          : { autorange: true as const }),
        dtick:
          this.config.yScale === "log" && this.config.yLogBase
            ? Math.log10(this.config.yLogBase)
            : undefined,
        gridcolor: majorGrid,
        showgrid: this.config.grid !== "none",
        minor: { showgrid: this.config.grid === "all", gridcolor: minorGrid },
        zeroline: false,
        tickfont: { color: textColor, size: 14 },
        title: {
          text: this.config.yAxisTitle + frameLabel,
          font: { size: 14, color: textColor, family: "monospace" },
        },
        showspikes: showY,
        spikemode: "across",
        spikelinecolor: spikeColor,
        spikethickness: -2,
      };

      const polarLayout = isPolar
        ? {
            polar: {
              bgcolor: "rgba(0,0,0,0)",
              radialaxis: {
                color: textColor,
                gridcolor: majorGrid,
                tickfont: { color: textColor, size: 14, family: "monospace" },
                title: {
                  text: this.config.yAxisTitle || "r",
                  font: { size: 14, color: textColor, family: "monospace" },
                },
              },
              angularaxis: {
                color: textColor,
                gridcolor: majorGrid,
                tickfont: { color: textColor, size: 14, family: "monospace" },
                title: {
                  text: xAxisText,
                  font: { size: 14, color: textColor, family: "monospace" },
                },
              },
            },
          }
        : { xaxis: xAxisObj, yaxis: yAxisObj };

      const layout = {
        uirevision: `${this.trialId}_${this.config.xAxis!.col!}_${Object.keys(this.config.yAxes).join("_")}_${this.config.plotType}`,
        title: this.config.title
          ? {
              text: this.config.title,
              font: {
                family: "monospace",
                size: 16,
                color: isDark ? tw.slate[200] : tw.slate[800],
                weight: "bold",
              },
              x: 0,
              xanchor: "left",
            }
          : null,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        margin: {
          t: this.config.title ? 60 : 30,
          r: this.config.legendPos === "right" ? 150 : 30,
          b: this.config.legendPos === "bottom" ? 80 : 50,
          l: this.config.yAxisTitle ? 80 : 60,
        },
        hovermode: isHoverDisabled ? false : this.config.hover,
        hoverlabel: {
          bgcolor: tooltipBg,
          bordercolor: tooltipBorder,
          font: { family: "monospace", size: 12, color: tooltipFont },
          align: "left",
        },
        showlegend: this.config.legendPos !== "hidden",
        legend:
          this.config.legendPos === "right"
            ? {
                orientation: "v",
                x: 1.02,
                y: 1,
                font: { family: "monospace", size: 14, color: textColor },
                groupclick: "togglegroup",
              }
            : {
                orientation: "h",
                y: -0.2,
                x: 0.5,
                xanchor: "center",
                font: { family: "monospace", size: 14, color: textColor },
                groupclick: "togglegroup",
              },
        ...polarLayout,
        annotations: isPolar
          ? []
          : [
              ...(this.config.annotations ?? []).map((ann) => ({
                x: ann.x,
                y: ann.y,
                text: ann.text,
                showarrow: true,
                arrowhead: 2,
                ax: 0,
                ay: -40,
                font: {
                  family: "monospace",
                  size: 12,
                  color: isDark ? tw.slate[50] : tw.slate[900],
                },
                bgcolor: isDark ? tw.slate[800] : tw.slate[50],
                bordercolor: tw.cyan[500],
                borderwidth: 1,
                borderpad: 4,
              })),
              ...(this.config.shapes ?? [])
                .filter((s) => s.label)
                .map((s) => {
                  let x = 0,
                    y = 0,
                    xanchor = "left",
                    yanchor = "bottom",
                    xref = "x",
                    yref = "y";
                  if (s.type === "vline") {
                    x = s.x0;
                    y = 1;
                    yref = "paper";
                  } else if (s.type === "hline") {
                    x = 1;
                    y = s.y0;
                    xref = "paper";
                    xanchor = "right";
                  } else if (s.type === "rect") {
                    x = s.x0;
                    y = s.y1;
                  }
                  return {
                    x,
                    y,
                    xref,
                    yref,
                    text: `<b>${s.label}</b>`,
                    showarrow: false,
                    xanchor,
                    yanchor,
                    font: {
                      size: 10,
                      color: s.color || tw.cyan[500],
                      family: "monospace",
                    },
                    bgcolor: isDark
                      ? tw.slate[900] + "B3"
                      : tw.slate[50] + "B3",
                    borderpad: 2,
                  };
                }),
            ],
        shapes: isPolar
          ? []
          : (this.config.shapes ?? []).map((s) => {
              const shapeColor = s.color || tw.cyan[500];
              const base = {
                line: { color: shapeColor, width: 2, dash: s.dash ?? "solid" },
                layer: "below",
              };
              if (s.type === "vline")
                return {
                  ...base,
                  type: "line",
                  x0: s.x0,
                  x1: s.x0,
                  y0: 0,
                  y1: 1,
                  yref: "paper",
                };
              if (s.type === "hline")
                return {
                  ...base,
                  type: "line",
                  y0: s.y0,
                  y1: s.y0,
                  x0: 0,
                  x1: 1,
                  xref: "paper",
                };
              if (s.type === "rect")
                return {
                  ...base,
                  type: "rect",
                  x0: s.x0,
                  x1: s.x1,
                  y0: s.y0,
                  y1: s.y1,
                  fillcolor: isDark ? `${shapeColor}1A` : `${shapeColor}26`,
                  line: { ...base.line, width: 1 },
                };
              return base;
            }),
      };

      const config = {
        responsive: true,
        displaylogo: false,
        displayModeBar: true,
        modeBarButtonsToRemove: ["toImage"],
        doubleClick: false as const,
      };
      const plotEl = document.getElementById("plot-area");
      if (plotEl && this._renderedPlotType !== this.config.plotType) {
        Plotly.purge(plotEl);
        this._renderedPlotType = this.config.plotType ?? null;
        // Plotly.purge clears the plot element's event emitter, so the
        // zoom/relayout/doubleclick handlers must be re-attached after recreating it.
        return Plotly.newPlot("plot-area", traces, layout, config).then(() =>
          this._attachPlotEventHandlers(),
        );
      }
      return Plotly.react("plot-area", traces, layout, config);
    },
  };
  return self;
}

window.trialViewer = trialViewer;
