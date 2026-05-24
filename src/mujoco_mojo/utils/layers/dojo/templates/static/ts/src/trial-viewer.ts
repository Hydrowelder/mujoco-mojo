import { OPTIONS } from "./lib/options";
import { createToastMixin } from "./lib/toast";
import type { AlpineMagics } from "./types/global";
import type {
  Annotation,
  DojoStore,
  FilterEntry,
  FilterSchema,
  PlotConfig,
  Shape,
  TrialDataResponse,
  TrialManifest,
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

const DEFAULT_CONFIG: PlotConfig = {
  xAxis: { col: "time", filters: [] },
  yAxes: {},
  refFrame: null,
  grid: "all",
  linemode: "lines",
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
  annotations: [],
  shapes: [],
};

// ---------------------------------------------------------------------------
// CodeMirror editor state (kept outside Alpine to avoid proxy issues)
// ---------------------------------------------------------------------------
const _cm: { editor: { state: { doc: { toString(): string } }; dispatch(tr: object): void; destroy(): void } | null; updating: boolean; debounce: ReturnType<typeof setTimeout> | null } = {
  editor: null,
  updating: false,
  debounce: null,
};

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
    discoveryId: 0,
    plotColors: [
      tw.cyan[500],
      tw.emerald[500],
      tw.blue[500],
      tw.violet[500],
      tw.amber[500],
      tw.rose[500],
    ],

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
    profileSearch: "",
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
    vsDraft: { enabled: false, range: [0, 0] as [number, number] },
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
    labGraph: (() => {
      try {
        const s = localStorage.getItem("mojo:lab:draft");
        return s ? (JSON.parse(s) as object) : null;
      } catch {
        return null;
      }
    })() as object | null,
    labName: localStorage.getItem("mojo:lab:name") ?? "",
    nodePickingColumn: null as number | null,
    nodeColSearch: "" as string,
    labSchemas: [] as Array<{
      name: string;
      signal_in_columns: string[];
      outputs: string[];
      modified: number;
      valid: boolean;
      missing: string[];
    }>,

    // --- SHAPES ---
    shapesOpen: false,
    placementMode: null as "vline" | "hline" | "rect" | null,
    rectStart: null as { x: number; y: number } | null,
    shapeDraft: null as Shape | null,
    shapeEditIndex: null as number | null,

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

      const queryStr = colParams.toString();
      if (queryStr) url += `?${queryStr}`;
      const resp = await fetch(url);
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

      const draftIds = this.allTrials.filter((id) => {
        const n = parseInt(id.split("_").pop() ?? "");
        return n >= start && n <= end && id !== this.trialId;
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
      const defaultColor =
        this.plotColors[this.config.shapes.length % this.plotColors.length]!;
      let newShape: Shape | null = null;

      if (this.placementMode === "vline") {
        newShape = { type: "vline", x0: pt.x, color: defaultColor, label: "" };
      } else if (this.placementMode === "hline") {
        newShape = {
          type: "hline",
          x0: pt.x,
          y0: pt.y,
          color: defaultColor,
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
          color: defaultColor,
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
        const statusResp = await fetch("/monitor/api/status");
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
        this.data = response.data;
        void this.loadLabSchemas();

        const params = new URLSearchParams(window.location.search);
        const shared = params.get("v");
        if (shared) {
          this.hydrateFromUrl(shared);
          this.vsDraft.enabled = this.config.vsEnabled;
          this.vsDraft.range = [...this.config.vsRange];
          this.config.vsEnabled = false;
        } else {
          this.loadConfig();
          this.vsDraft.enabled = this.config.vsEnabled;
          this.vsDraft.range = [...this.config.vsRange];
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
          const plotEl = document.getElementById("plot-area") as HTMLElement & {
            on(
              event: string,
              handler: (event: Record<string, unknown>) => void,
            ): void;
            _fullLayout?: {
              xaxis: { p2l(v: number): number };
              yaxis: { p2l(v: number): number };
              margin: { l: number; t: number };
            };
          };

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
          const targetEl = e.target as HTMLElement;
          const tag = targetEl.tagName;
          const isTextInput =
            ["INPUT", "TEXTAREA", "SELECT"].includes(tag) ||
            targetEl.isContentEditable;
          if (e.key === "/" && !isTextInput) {
            e.preventDefault();
            (
              document.querySelector(
                'input[type="number"]',
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
            this.labOpen = false;
            window.dispatchEvent(new CustomEvent("mojo:escape"));
            // Stop immediate propagation when something was open so Alpine's
            // bubble-phase @keydown.escape.window handler doesn't also fire.
            // This prevents Escape from both closing the lab and exiting fullscreen.
            if (anyOpen) e.stopImmediatePropagation();
          }
          if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
            e.preventDefault();
            if (!isTextInput) {
              if (this.labOpen) {
                const el = document.getElementById(
                  "lab-name-input",
                ) as HTMLInputElement | null;
                if (el) {
                  el.focus();
                  el.setSelectionRange(el.value.length, el.value.length);
                }
              } else {
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

      this.$watch("config.refFrame", (newValue: string | null, oldValue: string | null) => {
        if (newValue === oldValue) return;
        this.notify(`Frame: ${newValue || "world"}`, "info");
        this.discoveryId++;
        this.applyRefFrame(newValue);
        // config watcher handles re-fetch and re-render when yAxes.filters change
      });

      this.$watch("config", async (value: PlotConfig, oldValue: PlotConfig) => {
        if (!this.isEditingRaw) {
          this.configRaw = JSON.stringify(value, null, 4);
          try { localStorage.removeItem("mojo:config:raw-draft"); } catch {}
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
      });

      void this.startBackgroundDiscovery();
      this.configRaw =
        localStorage.getItem("mojo:config:raw-draft") ??
        JSON.stringify(this.config, null, 4);
      this.updateFromRaw();
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
        const targetIds = this.allTrials.filter((id) => {
          const n = parseInt(id.split("_").pop() ?? "");
          return n >= start && n <= end && n !== currentNum;
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
      return Math.min(a, b) === Math.min(...nums) && Math.max(a, b) === Math.max(...nums);
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
      const errors: string[] = [];
      const labsNoted = new Set<string>();
      const schemasLoaded = this.labSchemas.length > 0;

      const checkCol = (col: string, label: string) => {
        if (col.startsWith("Lab/")) {
          if (!schemasLoaded) return; // wait for schemas before reporting Lab issues
          const labName = col.slice(4).split("/")[0];
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
      try { localStorage.setItem("mojo:config:raw-draft", this.configRaw); } catch {}
      try {
        const parsed = JSON.parse(this.configRaw) as PlotConfig;
        this.isValidJson = true;
        if (parsed && typeof parsed === "object") {
          this.configErrors = this.validateConfig(parsed);
          this.isValidConfig = this.configErrors.length === 0;
          if (this.isValidConfig) {
            this.isEditingRaw = true;
            this.config = { ...this.config, ...parsed };
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
          this.config = { ...this.config, ...parsed };
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

    initCodeMirror(hostEl: HTMLElement) {
      if (!hostEl || typeof CM === "undefined" || _cm.editor) return;
      const { EditorView, basicSetup, json, oneDark, EditorState } = CM;
      const self = this;
      const startState = EditorState.create({
        doc: this.configRaw,
        extensions: [
          basicSetup,
          json(),
          oneDark,
          EditorView.theme({
            "&": { height: "auto" },
            ".cm-scroller": { fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: "0.875rem", lineHeight: "1.625" },
            ".cm-content": { padding: "1rem" },
            ".cm-gutters": { minHeight: "16rem" },
          }),
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
      this.$watch("configRaw", (val: string) => {
        if (!_cm.updating && _cm.editor) {
          const current = _cm.editor.state.doc.toString();
          if (current !== val) {
            _cm.updating = true;
            _cm.editor.dispatch({ changes: { from: 0, to: current.length, insert: val } });
            _cm.updating = false;
          }
        }
      });
    },

    resetConfig() {
      if (
        confirm(
          "Reset plot to factory defaults? This will clear your current view.",
        )
      ) {
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
      if (
        !file ||
        (file.type !== "application/json" && !file.name.endsWith(".json"))
      ) {
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
        const nextIndex = Object.keys(this.config.yAxes).length;
        const initFilters: FilterEntry[] = this.config.refFrame
          ? [{ type: "rotation", quat_col: this.config.refFrame, invert: true, enabled: true }]
          : [];
        this.config.yAxes[col] = {
          color: this.getSignalColor(nextIndex),
          label: "",
          width: 3,
          opacity: 1,
          filters: initFilters,
          dash: "solid",
          marker: "none",
        };
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
            quat_col: frame,
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

    get groupedFilterSchemas(): { category: string; schemas: FilterSchema[] }[] {
      const ORDER = ["Smoothing", "Arithmetic", "Trigonometry", "Calculus", "Comparison", "Bounding", "Misc"];
      const groups: Record<string, FilterSchema[]> = {};
      for (const s of this.filterSchemas) {
        const cat = s.category ?? "Misc";
        (groups[cat] ??= []).push(s);
      }
      return ORDER.filter((c) => groups[c]?.length).map((c) => ({ category: c, schemas: groups[c] }));
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
    ): UnitGroup[] {
      if (!groups) return [];
      if (!fromUnit) return groups;
      const match = groups.find((g) => g.units.includes(fromUnit));
      return match ? [match] : groups;
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
          if (typeof val === "number")
            return `${p.name}=${parseFloat(val.toFixed(4))}`;
          return `${p.name}=${val as string}`;
        });
      return parts.slice(0, 3).join(", ");
    },

    addFilterToTemp(temp: YAxisConfig, filterType: string) {
      const schema = this.filterSchemas.find((s) => s.type === filterType);
      if (!schema) return;
      if (!temp.filters) temp.filters = [];
      if (filterType === "rotation" && temp.filters.some((f) => f.type === "rotation"))
        return;
      const entry: FilterEntry = { type: filterType, enabled: true };
      for (const p of schema.params) {
        (entry as Record<string, unknown>)[p.name] = p.default;
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

    async saveLabGraph(name: string, graph: object) {
      const trimmed = name.trim();
      if (!trimmed) return;
      const exists = this.labSchemas.some((s) => s.name === trimmed);
      if (exists && !confirm(`Overwrite "${trimmed}"?`)) return;
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
        localStorage.setItem("mojo:lab:name", trimmed);
        this.notify(`Lab "${trimmed}" saved`, "success");
        await this.refreshLabValidation();
        // Evict stale computed data for this lab's outputs, then re-fetch anything
        // currently plotted so the chart updates immediately.
        const labPrefix = `Lab/${trimmed}/`;
        const staleCols = Object.keys(this.data ?? {}).filter((c) =>
          c.startsWith(labPrefix),
        );
        if (staleCols.length > 0) {
          const fresh = { ...(this.data ?? {}) };
          staleCols.forEach((c) => delete fresh[c]);
          this.data = fresh;
          const activeCols = staleCols.filter(
            (c) => c in this.config.yAxes || c === this.config.xAxis?.col,
          );
          if (activeCols.length > 0) {
            try {
              const refetch = await this.fetchTrialData(this.trialId, activeCols);
              this.data = { ...(this.data ?? {}), ...refetch.data };
              this.saveAndRender();
            } catch {
              // non-critical: plot drops the stale trace until background discovery refetches
            }
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
      if (existing && !confirm(`Overwrite profile "${existing.name}"?`)) return;
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
        const missing: string[] = [];
        if (loaded.xAxis?.col && !colSet.has(loaded.xAxis.col))
          missing.push(`x-axis "${loaded.xAxis!.col!}"`);
        for (const key of Object.keys(loaded.yAxes ?? {})) {
          if (!colSet.has(key)) missing.push(`signal "${key}"`);
        }
        if (loaded.refFrame && !frames.has(loaded.refFrame))
          missing.push(`frame "${loaded.refFrame}"`);

        if (missing.length) {
          throw new Error(
            `references columns not in this trial: ${missing.join(", ")}`,
          );
        }

        this.config = { ...this.config, ...loaded };
        this.notify(`Profile "${name}" loaded`, "success");
        void this.$nextTick(() => {
          this.configErrors = this.validateConfig(this.config as PlotConfig);
          this.isValidConfig = this.configErrors.length === 0;
          this.isValidJson = true;
        });
      } catch (e) {
        this.notify(
          `Failed to load "${name}": ${(e as Error).message}`,
          "error",
        );
      }
    },

    async deleteProfile(name: string) {
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
        Object.entries(this.vsDatasets).forEach(([vsId, dataset]) => {
          const n = parseInt(vsId.split("_").pop() ?? "");
          if (n >= start && n <= end) activeDatasets.push(dataset);
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
      const yKeys = Object.keys(this.config.yAxes);
      let traces: object[] = yKeys
        .map((key, i) => {
          const p = this.getYProps(key, i);
          if (!this.data![p.name]) return null;
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
              name: p.label,
              mode: this.config.linemode,
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
            name: p.label,
            mode: this.config.linemode,
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
        const legendTracker = new Set<string>();
        const sortedVsIds = Object.keys(this.vsDatasets).sort(
          (a, b) =>
            parseInt(a.split("_").pop() ?? "0") -
            parseInt(b.split("_").pop() ?? "0"),
        );
        sortedVsIds.forEach((vsId) => {
          const n = parseInt(vsId.split("_").pop() ?? "");
          if (n < start || n > end || vsId === this.trialId) return;
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
                    mode: this.config.linemode,
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
                    mode: this.config.linemode,
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

      const xAxisObj = {
        type: this.config.xScale ?? "linear",
        ...(this.config.rangeX
          ? {
              autorange: false as const,
              range:
                this.config.xScale === "log"
                  ? [
                      Math.log10(Math.max(1e-6, this.config.rangeX[0])),
                      Math.log10(Math.max(1e-6, this.config.rangeX[1])),
                    ]
                  : this.config.rangeX,
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
          text: this.config.xAxisTitle || this.config.xAxis!.col!,
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

      const yAxisObj = {
        type: this.config.yScale ?? "linear",
        ...(this.config.rangeY
          ? {
              autorange: false as const,
              range:
                this.config.yScale === "log"
                  ? [
                      Math.log10(Math.max(1e-6, this.config.rangeY[0])),
                      Math.log10(Math.max(1e-6, this.config.rangeY[1])),
                    ]
                  : this.config.rangeY,
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
                  text: this.config.xAxisTitle || this.config.xAxis!.col!,
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
                  let x = s.x0,
                    y = s.y0 ?? 0,
                    xanchor = "left",
                    yanchor = "bottom",
                    xref = "x",
                    yref = "y";
                  if (s.type === "vline") {
                    y = 1;
                    yref = "paper";
                  } else if (s.type === "hline") {
                    x = 1;
                    xref = "paper";
                    xanchor = "right";
                  } else if (s.type === "rect") {
                    x = s.x0;
                    y = s.y1 ?? 0;
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
        return Plotly.newPlot("plot-area", traces, layout, config);
      }
      return Plotly.react("plot-area", traces, layout, config);
    },
  };
  return self;
}

window.trialViewer = trialViewer;
