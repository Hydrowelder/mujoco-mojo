"use strict";
(() => {
  // src/lib/options.ts
  var DASH_OPTIONS = ["solid", "dash", "dot", "dashdot"];
  var MARKER_OPTIONS = ["none", "circle", "square", "diamond", "cross"];
  var GRID_OPTIONS = ["none", "major", "all"];
  var LINE_MODE_OPTIONS = [
    { label: "Lines", value: "lines" },
    { label: "Markers", value: "markers" },
    { label: "Both", value: "lines+markers" }
  ];
  var INTERP_OPTIONS = [
    { label: "Linear", value: "linear" },
    { label: "Spline", value: "spline" },
    { label: "Step (HV)", value: "hv" },
    { label: "Step (VH)", value: "vh" },
    { label: "Step (HVH)", value: "hvh" },
    { label: "Step (VHV)", value: "vhv" }
  ];
  var HOVER_OPTIONS = [
    { label: "Unified X", value: "x unified" },
    { label: "Unified Y", value: "y unified" },
    { label: "Closest", value: "closest" },
    { label: "X Axis", value: "x" },
    { label: "Y Axis", value: "y" },
    { label: "Off", value: "none" }
  ];
  var LEGEND_POS_OPTIONS = ["bottom", "right", "hidden"];
  var SCALE_OPTIONS = ["linear", "log"];
  function labelOf(options, value) {
    return options.find((o) => o.value === value)?.label ?? value;
  }
  var OPTIONS = {
    dash: DASH_OPTIONS,
    marker: MARKER_OPTIONS,
    grid: GRID_OPTIONS,
    lineMode: LINE_MODE_OPTIONS,
    interp: INTERP_OPTIONS,
    hover: HOVER_OPTIONS,
    legendPos: LEGEND_POS_OPTIONS,
    scale: SCALE_OPTIONS,
    lineModeLabel: (v) => labelOf(LINE_MODE_OPTIONS, v),
    interpLabel: (v) => labelOf(INTERP_OPTIONS, v),
    hoverLabel: (v) => labelOf(HOVER_OPTIONS, v)
  };

  // src/lib/toast.ts
  function createToastMixin() {
    return {
      showToast: false,
      toastMessage: "",
      toastType: "success",
      notify(msg, type = "success") {
        this.toastMessage = msg;
        this.toastType = type;
        this.showToast = true;
        setTimeout(() => {
          this.showToast = false;
        }, 3e3);
      }
    };
  }

  // src/trial-viewer.ts
  var tw = {
    slate: { 50: "#f8fafc", 100: "#f1f5f9", 200: "#e2e8f0", 300: "#cbd5e1", 400: "#94a3b8", 500: "#64748b", 600: "#475569", 700: "#334155", 800: "#1e293b", 900: "#0f172a", 950: "#020617" },
    cyan: { 400: "#22d3ee", 500: "#06b6d4", 600: "#0891b2" },
    emerald: { 500: "#10b981" },
    blue: { 500: "#3b82f6" },
    violet: { 500: "#8b5cf6" },
    amber: { 500: "#f59e0b" },
    rose: { 500: "#ef4444" }
  };
  var DEFAULT_CONFIG = {
    xAxis: "time",
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
    vsEnabled: false,
    vsRange: [0, 10],
    annotations: [],
    shapes: []
  };
  function trialViewer(trialId, externalUrl) {
    const self = {
      // Alpine magic (injected at runtime — declared here for TS)
      ...null,
      // --- BASE STATE ---
      trialId,
      externalUrl,
      warpId: null,
      paddingLen: 2,
      loading: true,
      isMac: /Mac|iPhone|iPod|iPad/.test(navigator.platform),
      data: null,
      errorState: null,
      // --- UI / MENU STATES ---
      theme: "dark",
      xMenuOpen: false,
      xSearch: "",
      yMenuOpen: false,
      ySearch: "",
      refFrameMenuOpen: false,
      settingsOpen: false,
      downloadOpen: false,
      activeFrame: null,
      dragCounter: 0,
      editorOpen: false,
      columns: [],
      rotateableVectors: [],
      discoveryId: 0,
      plotColors: [tw.cyan[500], tw.emerald[500], tw.blue[500], tw.violet[500], tw.amber[500], tw.rose[500]],
      // Toast (shared mixin)
      ...createToastMixin(),
      // Options — exposed so templates can use opts.lineMode, opts.interpLabel(...), etc.
      opts: OPTIONS,
      // --- PLOT CONFIGURATION ---
      config: JSON.parse(JSON.stringify(DEFAULT_CONFIG)),
      // --- JSON EDITOR STATE ---
      configRaw: "",
      isValidJson: true,
      isValidConfig: true,
      configErrors: [],
      isEditingRaw: false,
      // --- MATCHUP STATE ---
      vsDatasets: {},
      allTrials: [],
      vsMenuOpen: false,
      vsLoading: false,
      vsDraft: { enabled: false, range: [0, 0] },
      discoveryTimeout: null,
      // --- HISTORY STATE ---
      historyStack: [],
      historyIndex: -1,
      isUndoing: false,
      maxHistory: 50,
      // --- ANNOTATIONS ---
      annotationsOpen: false,
      annDraft: null,
      annEditIndex: null,
      // --- SHAPES ---
      shapesOpen: false,
      placementMode: null,
      rectStart: null,
      shapeDraft: null,
      shapeEditIndex: null,
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
          this.config = JSON.parse(this.historyStack[this.historyIndex] ?? "{}");
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
          this.config = JSON.parse(this.historyStack[this.historyIndex] ?? "{}");
          this.persistHistory();
          void this.$nextTick(() => {
            this.isUndoing = false;
          });
          this.notify("Redo", "info");
        }
      },
      persistHistory() {
        localStorage.setItem("mojo_mosaic_history", JSON.stringify({ stack: this.historyStack, index: this.historyIndex }));
      },
      shiftY(index, direction, isWarp = false) {
        const keys = Object.keys(this.config.yAxes);
        if (keys.length < 2) return;
        const newKeys = [...keys];
        const movedKey = newKeys.splice(index, 1)[0];
        if (isWarp) {
          direction === -1 ? newKeys.unshift(movedKey) : newKeys.push(movedKey);
        } else {
          newKeys.splice(index + direction, 0, movedKey);
        }
        const newYAxes = {};
        newKeys.forEach((k) => {
          newYAxes[k] = this.config.yAxes[k];
        });
        this.config.yAxes = newYAxes;
        this.saveAndRender();
      },
      // -----------------------------------------------------------------------
      // Data fetching
      // -----------------------------------------------------------------------
      async fetchTrialData(id, requiredCols = []) {
        let url = `/mosaic/${id}/data`;
        const colParams = new URLSearchParams();
        if (requiredCols.length > 0) colParams.append("cols", requiredCols.join(","));
        if (this.config.refFrame) colParams.append("rotate_by", this.config.refFrame);
        const queryStr = colParams.toString();
        if (queryStr) url += `?${queryStr}`;
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`Trial ${id} failed`);
        return resp.json();
      },
      async trickleFetch(id, columnList, label, isVsDataset, loopId) {
        const CHUNK_SIZE = 10;
        for (let i = 0; i < columnList.length; i += CHUNK_SIZE) {
          if (loopId !== this.discoveryId) return;
          await new Promise((r) => setTimeout(r, 50));
          const chunk = columnList.slice(i, i + CHUNK_SIZE);
          try {
            const resp = await this.fetchTrialData(id, chunk);
            if (isVsDataset) {
              this.vsDatasets[id] = { ...this.vsDatasets[id] ?? {}, ...resp.data };
              this.vsDatasets = { ...this.vsDatasets };
            } else {
              this.data = { ...this.data ?? {}, ...resp.data };
            }
            if (Object.keys(this.config.yAxes).some((y) => chunk.includes(y))) this.renderPlot();
            console.debug(`Dojo Hydration [${label}]: ${i + chunk.length}/${columnList.length}`);
          } catch (e) {
            console.warn(`Hydration failed for ${id}`, e);
          }
        }
      },
      async startBackgroundDiscovery() {
        const currentId = ++this.discoveryId;
        const pendingCols = this.columns.filter((c) => !Object.prototype.hasOwnProperty.call(this.data ?? {}, c));
        if (pendingCols.length > 0) await this.trickleFetch(this.trialId, pendingCols, "Current", false, currentId);
        if (currentId !== this.discoveryId) return;
        const start = Math.min(this.vsDraft.range[0], this.vsDraft.range[1]);
        const end = Math.max(this.vsDraft.range[0], this.vsDraft.range[1]);
        const activeCols = [this.config.xAxis, ...Object.keys(this.config.yAxes)];
        const draftIds = this.allTrials.filter((id) => {
          const n = parseInt(id.split("_").pop() ?? "");
          return n >= start && n <= end && id !== this.trialId;
        });
        for (const id of draftIds) {
          if (currentId !== this.discoveryId) return;
          const existing = this.vsDatasets[id];
          const needsFetch = !existing || activeCols.some((c) => !Object.prototype.hasOwnProperty.call(existing, c));
          if (needsFetch) await this.trickleFetch(id, activeCols, `Draft ${id}`, true, currentId);
        }
      },
      // -----------------------------------------------------------------------
      // Shapes
      // -----------------------------------------------------------------------
      setPlacementMode(type) {
        this.placementMode = type;
        this.rectStart = null;
        this.shapeDraft = null;
        const label = type === "vline" ? "Vertical Line" : type === "hline" ? "Horizontal Line" : "Area Rectangle";
        this.notify(`Mode: ${label}. Click plot to place.`, "info");
      },
      deleteShape(index) {
        this.config.shapes.splice(index, 1);
        this.saveAndRender();
      },
      handlePlotClickForShapes(pt) {
        if (!this.placementMode) return false;
        const defaultColor = tw.cyan[500];
        let newShape = null;
        if (this.placementMode === "vline") {
          newShape = { type: "vline", x0: pt.x, color: defaultColor, label: "" };
        } else if (this.placementMode === "hline") {
          newShape = { type: "hline", x0: pt.x, y0: pt.y, color: defaultColor, label: "" };
        } else if (this.placementMode === "rect") {
          if (!this.rectStart) {
            this.rectStart = { x: pt.x, y: pt.y };
            return true;
          }
          newShape = { type: "rect", x0: this.rectStart.x, x1: pt.x, y0: this.rectStart.y, y1: pt.y, color: defaultColor, label: "" };
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
      startShapeEdit(index) {
        this.shapeEditIndex = index;
        this.shapeDraft = { ...this.config.shapes[index] };
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
      startAnnEdit(index) {
        this.annEditIndex = index;
        this.annDraft = { ...this.config.annotations[index] };
        void this.$nextTick(() => this.$refs["annInput"]?.focus());
      },
      cancelAnnDraft() {
        this.annDraft = null;
        this.annEditIndex = null;
      },
      jumpToAnnotation(ann) {
        const el = document.getElementById("plot-area");
        if (!el || !this.data) return;
        const xValues = this.data[this.config.xAxis] ?? [];
        const xMin = xValues[0] ?? 0;
        const xMax = xValues[xValues.length - 1] ?? 100;
        const xSpan = (xMax - xMin) * 0.1;
        let newRangeX = [ann.x - xSpan / 2, ann.x + xSpan / 2];
        if (newRangeX[0] < xMin) {
          newRangeX[1] += xMin - newRangeX[0];
          newRangeX[0] = xMin;
        }
        if (newRangeX[1] > xMax) {
          newRangeX[0] -= newRangeX[1] - xMax;
          newRangeX[1] = xMax;
        }
        const fullY = this.calculatePaddedRange(Object.keys(this.config.yAxes), false);
        const ySpan = Math.abs(fullY[1] - fullY[0]) * 0.2;
        const newRangeY = [ann.y - ySpan / 2, ann.y + ySpan / 2];
        this.config.rangeX = newRangeX;
        this.config.rangeY = newRangeY;
        void Plotly.relayout(el, { "xaxis.range": newRangeX, "yaxis.range": newRangeY, "xaxis.autorange": false, "yaxis.autorange": false });
        this.saveAndRender();
      },
      deleteAnnotation(index) {
        this.config.annotations.splice(index, 1);
        this.saveAndRender();
      },
      editAnnotation(index) {
        const ann = this.config.annotations[index];
        const newText = prompt("Update Annotation:", ann.text);
        if (newText !== null && newText.trim() !== "") {
          this.config.annotations[index].text = newText;
          this.saveAndRender();
        }
      },
      // -----------------------------------------------------------------------
      // Column accessors
      // -----------------------------------------------------------------------
      get selectableYColumns() {
        if (!this.columns) return [];
        if (!this.config.refFrame) return this.columns;
        return this.columns.filter((col) => {
          const parts = col.split(":");
          const suffix = parts.pop();
          const family = parts.join(":");
          return ["x", "y", "z"].includes(suffix ?? "") && this.rotateableVectors.includes(family);
        });
      },
      get availableQuats() {
        if (!this.columns || !Array.isArray(this.columns)) return [];
        return this.columns.filter((c) => c.endsWith(":w")).map((c) => c.replace(":w", ""));
      },
      // -----------------------------------------------------------------------
      // Init
      // -----------------------------------------------------------------------
      async init() {
        this.theme = document.documentElement.classList.contains("dark") ? "dark" : "light";
        const currentNum = parseInt(this.trialId.split("_").pop() ?? "");
        this.warpId = isNaN(currentNum) ? null : currentNum;
        const observer = new MutationObserver((mutations) => {
          if (mutations.some((m) => m.attributeName === "class")) {
            this.theme = document.documentElement.classList.contains("dark") ? "dark" : "light";
            if (this.data && Object.keys(this.config.yAxes).length > 0) this.renderPlot();
          }
        });
        observer.observe(document.documentElement, { attributes: true });
        try {
          const statusResp = await fetch("/monitor/api/status");
          const statusData = await statusResp.json();
          if (statusData && !statusData.error) {
            Alpine.store("dojo").updateSync(Date.now(), statusData.is_complete);
            const match = statusData.padding_style.match(/\d+/);
            this.paddingLen = match ? parseInt(match[0]) : 2;
          }
        } catch (e) {
          console.warn("Dojo offline", e);
        }
        try {
          const initialCols = [this.config.xAxis, ...Object.keys(this.config.yAxes)];
          const response = await this.fetchTrialData(this.trialId, initialCols);
          this.columns = response.columns.all.sort();
          this.rotateableVectors = response.columns.rotateable_vectors;
          this.data = response.data;
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
          void this.$nextTick(() => {
            this.pushHistory();
          });
          void this.$nextTick(async () => {
            await this.renderPlot();
            const plotEl = document.getElementById("plot-area");
            plotEl.on("plotly_relayout", (event) => {
              if (event["xaxis.autorange"] ?? event["yaxis.autorange"]) {
                this.config.rangeX = null;
                this.config.rangeY = null;
                this.renderPlot();
                return;
              }
              if (event["xaxis.range[0]"] !== void 0) {
                this.config.rangeX = [event["xaxis.range[0]"], event["xaxis.range[1]"]];
              }
              if (event["yaxis.range[0]"] !== void 0) {
                this.config.rangeY = [event["yaxis.range[0]"], event["yaxis.range[1]"]];
              }
            });
            plotEl.addEventListener("click", (e) => {
              const target = e.target;
              const isPlotValue = target.classList.contains("nsewdrag") || target.classList.contains("drag");
              if (!isPlotValue) return;
              const rect = plotEl.getBoundingClientRect();
              const fullLayout = plotEl._fullLayout;
              if (!fullLayout) return;
              const xVal = fullLayout.xaxis.p2l(e.clientX - rect.left - fullLayout.margin.l);
              const yVal = fullLayout.yaxis.p2l(e.clientY - rect.top - fullLayout.margin.t);
              const pt = { x: xVal, y: yVal };
              if (this.placementMode) {
                this.handlePlotClickForShapes(pt);
                return;
              }
              setTimeout(() => {
                this.annDraft = { x: pt.x, y: pt.y, text: "" };
                this.annEditIndex = null;
                this.annotationsOpen = true;
                void this.$nextTick(() => {
                  const input = document.querySelector('[x-ref="annInput"]');
                  input?.focus();
                });
              }, 0);
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
          Alpine.store("dojo").startGlobalSync();
          Alpine.store("dojo").setPageReady(true);
        }
        window.addEventListener("keydown", (e) => {
          if (e.repeat) return;
          const tag = e.target.tagName;
          if (e.key === "/" && !["INPUT", "TEXTAREA"].includes(tag)) {
            e.preventDefault();
            document.querySelector('input[type="number"]')?.focus();
          }
          if (e.key === "Escape") {
            this.yMenuOpen = this.settingsOpen = this.editorOpen = false;
            if (["INPUT", "TEXTAREA"].includes(tag)) e.target.blur();
          }
          if (["INPUT", "TEXTAREA"].includes(tag)) return;
          if (e.key === "ArrowLeft") document.getElementById("nav-prev")?.click();
          if (e.key === "ArrowRight") document.getElementById("nav-next")?.click();
          const isZ = e.key.toLowerCase() === "z";
          const isY = e.key.toLowerCase() === "y";
          const cmdOrCtrl = e.metaKey || e.ctrlKey;
          if (cmdOrCtrl && isZ) {
            e.preventDefault();
            if (e.shiftKey) this.redo();
            else this.undo();
          }
          if (cmdOrCtrl && isY) {
            e.preventDefault();
            this.redo();
          }
        });
        const resp = await fetch("/mosaic/api/trials");
        const data = await resp.json();
        this.allTrials = data.trials ?? [];
        if (this.allTrials.length) {
          const ids = this.allTrials.map((id) => parseInt(id.split("_").pop() ?? "")).filter((n) => !isNaN(n));
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
            if (this.vsDraft.enabled) {
              console.debug("Predictive Sync: User adjusted range, starting hydration...");
              void this.startBackgroundDiscovery();
            }
          }, 500);
        });
        this.$watch("config.refFrame", async (newValue, oldValue) => {
          console.debug(`[Mojo] Frame Change: ${oldValue ?? "world"} -> ${newValue ?? "world"}`);
          this.discoveryId++;
          this.data = {};
          this.vsDatasets = {};
          const initialCols = [this.config.xAxis, ...Object.keys(this.config.yAxes)];
          const response = await this.fetchTrialData(this.trialId, initialCols);
          this.columns = response.columns.all.sort();
          this.rotateableVectors = response.columns.rotateable_vectors;
          this.data = response.data;
          void this.startBackgroundDiscovery();
          if (this.config.vsEnabled) await this.syncVsRange();
          this.saveAndRender();
        });
        this.$watch("config", async (value, oldValue) => {
          if (!this.isEditingRaw) this.configRaw = JSON.stringify(value, null, 4);
          if (this.config.vsEnabled && oldValue?.vsEnabled && (value.xAxis !== oldValue.xAxis || Object.keys(value.yAxes).length !== Object.keys(oldValue.yAxes ?? {}).length)) {
            await this.syncVsRange();
          }
          this.pushHistory();
          this.saveAndRender();
        });
        void this.startBackgroundDiscovery();
        this.configRaw = JSON.stringify(this.config, null, 4);
      },
      // -----------------------------------------------------------------------
      // VS (comparison) mode
      // -----------------------------------------------------------------------
      async syncVsRange() {
        try {
          const resp = await fetch("/mosaic/api/trials");
          const data = await resp.json();
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
          let activeCols = [this.config.xAxis, ...Object.keys(this.config.yAxes)];
          if (this.config.refFrame) {
            const families = /* @__PURE__ */ new Set();
            Object.keys(this.config.yAxes).forEach((col) => {
              if (col.includes(":")) families.add(col.substring(0, col.lastIndexOf(":")));
            });
            families.forEach((fam) => activeCols.push(`${fam}:x`, `${fam}:y`, `${fam}:z`));
            activeCols.push(`${this.config.refFrame}:w`, `${this.config.refFrame}:x`, `${this.config.refFrame}:y`, `${this.config.refFrame}:z`);
          }
          activeCols = [...new Set(activeCols)];
          const currentNum = parseInt(this.trialId.split("_").pop() ?? "");
          const targetIds = this.allTrials.filter((id) => {
            const n = parseInt(id.split("_").pop() ?? "");
            return n >= start && n <= end && n !== currentNum;
          });
          await Promise.all(targetIds.map(async (id) => {
            const existing = this.vsDatasets[id];
            const needsFetch = !existing || activeCols.some((col) => !Object.prototype.hasOwnProperty.call(existing, col)) || this.config.refFrame !== null;
            if (needsFetch) {
              const response = await this.fetchTrialData(id, activeCols);
              this.vsDatasets[id] = { ...this.vsDatasets[id] ?? {}, ...response.data };
            }
          }));
          this.vsDatasets = { ...this.vsDatasets };
          this.config.vsRange = [start, end];
          this.config.vsEnabled = true;
        } finally {
          this.vsLoading = false;
        }
      },
      handleVsToggle() {
        if (!this.vsDraft.enabled) {
          this.config.vsEnabled = false;
          this.renderPlot();
        }
      },
      // -----------------------------------------------------------------------
      // Column filtering & search
      // -----------------------------------------------------------------------
      smartSort(list) {
        return list.sort((a, b) => {
          const aT = a.toLowerCase() === "time";
          const bT = b.toLowerCase() === "time";
          if (aT && !bT) return -1;
          if (!aT && bT) return 1;
          return a.localeCompare(b, void 0, { sensitivity: "base" });
        });
      },
      getFilteredCols(field) {
        if (!this.columns || !Array.isArray(this.columns)) return [];
        const base = field === "x" ? this.columns : this.selectableYColumns;
        const search = this[field + "Search"] ?? "";
        if (!search) return this.smartSort([...base]);
        try {
          let pattern = search.replace(/\*/g, ".*").replace(/\/?:/g, ".*:");
          if (pattern.endsWith("/")) pattern = pattern.replace(/\/$/, "\\/?");
          if (pattern.startsWith(":")) pattern = ".*" + pattern;
          if (pattern.toLowerCase() === "time") pattern = "^time$";
          const query = new RegExp(pattern, "i");
          return this.smartSort(base.filter((c) => query.test(c)));
        } catch {
          return this.smartSort(base.filter((c) => c.toLowerCase().includes(search.toLowerCase())));
        }
      },
      toggleRegexSegment(field, segment, depth) {
        const key = field + "Search";
        const self2 = this;
        let [pathPart = "", suffixPart = ""] = (self2[key] ?? "").split(":");
        if (depth === "suffix") {
          const cleanSeg = segment.replace(":", "");
          let items = (suffixPart ?? "").replace(/[()]/g, "").split("|").filter(Boolean);
          items = items.includes(cleanSeg) ? items.filter((i) => i !== cleanSeg) : [...items, cleanSeg];
          suffixPart = items.length > 1 ? `(${items.sort().join("|")})` : items[0] ?? "";
        } else {
          let parts = (pathPart ?? "").split("/").filter((p) => p !== "");
          let target = parts[depth] ?? "";
          let items = target.replace(/[()]/g, "").split("|").filter(Boolean);
          items = items.includes(segment) ? items.filter((i) => i !== segment) : [...items, segment];
          if (items.length === 0) {
            parts = parts.slice(0, depth);
          } else {
            parts[depth] = items.length === 1 ? items[0] ?? "" : `(${items.sort().join("|")})`;
          }
          pathPart = parts.join("/");
          if (pathPart && pathPart.toLowerCase() !== "time") {
            const isFolder = this.columns.some((c) => c.toLowerCase().startsWith(pathPart.toLowerCase() + "/"));
            if (isFolder) pathPart += "/";
          }
        }
        self2[key] = (pathPart ?? "") + (suffixPart ? ":" + suffixPart : "");
      },
      getSegmentsAtDepth(field, depth) {
        const base = field === "x" ? this.columns : this.selectableYColumns;
        const search = this[field + "Search"] ?? "";
        const pathSearch = search.split(":")[0] ?? "";
        const parts = pathSearch.split("/").filter((p) => p !== "");
        const selected = (parts[depth] ?? "").replace(/[()]/g, "").split("|").filter(Boolean);
        const prefixParts = parts.slice(0, depth);
        const prefix = prefixParts.join("/").replace(/\//g, "\\/?");
        const regex = new RegExp("^" + (prefix ? prefix : ""), "i");
        const segments = base.filter((c) => regex.test(c)).map((c) => {
          const p = c.split(":")[0].split("/");
          return p[depth] ?? null;
        }).filter(Boolean);
        return this.smartSort([.../* @__PURE__ */ new Set([...selected, ...segments])]);
      },
      getAvailableSuffixes(field) {
        const base = field === "x" ? this.columns : this.selectableYColumns;
        const search = this[field + "Search"] ?? "";
        const [pathPart = "", suffixPart = ""] = search.split(":");
        const selected = (suffixPart ?? "").replace(/[()]/g, "").split("|").filter(Boolean).map((s) => ":" + s);
        const pathRegex = new RegExp("^" + (pathPart ?? "").replace(/\//g, "\\/?"), "i");
        const matches = base.filter((c) => pathRegex.test(c));
        const available = matches.map((c) => c.includes(":") ? ":" + c.split(":").pop() : null).filter(Boolean);
        return this.smartSort([.../* @__PURE__ */ new Set([...selected, ...available])]);
      },
      isSegmentActive(field, seg, depth) {
        const search = this[field + "Search"] ?? "";
        if (depth === "suffix") {
          const suffixPart = search.split(":")[1] ?? "";
          const items = suffixPart.replace(/[()]/g, "").split("|").filter(Boolean);
          return items.includes(seg.replace(":", ""));
        } else {
          const pathPart = search.split(":")[0] ?? "";
          const levels = pathPart.split("/").filter((p) => p !== "");
          const levelContent = levels[depth] ?? "";
          const items = levelContent.replace(/[()]/g, "").split("|").filter(Boolean);
          return items.includes(seg);
        }
      },
      getActiveLevels(field) {
        const search = this[field + "Search"] ?? "";
        const pathOnly = search.split(":")[0] ?? "";
        const parts = pathOnly.split("/").filter((p) => p !== "");
        return Array.from({ length: parts.length + 1 }, (_, i) => i);
      },
      // -----------------------------------------------------------------------
      // JSON editor
      // -----------------------------------------------------------------------
      get highlightedJson() {
        if (!this.configRaw) return "";
        let html = this.configRaw.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        const regex = /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?|[\[\]{},])|(\S+)/g;
        return html.replace(regex, (match, _token, _i1, _i2, _i3, garbage) => {
          if (garbage) return `<span class="text-rose-500 underline decoration-wavy underline-offset-2 font-bold">${garbage}</span>`;
          let cls = "text-slate-500 dark:text-slate-400";
          if (/^"/.test(match)) {
            cls = /:$/.test(match) ? "text-cyan-600 dark:text-cyan-300" : "text-emerald-600 dark:text-emerald-400";
          } else if (/true|false/.test(match)) {
            cls = "text-violet-600 dark:text-violet-400";
          } else if (/null/.test(match)) {
            cls = "text-rose-500";
          } else if (/-?\d/.test(match)) {
            cls = "text-amber-600 dark:text-amber-500";
          }
          return `<span class="${cls}">${match}</span>`;
        });
      },
      validateConfig(cfg) {
        const errors = [];
        if (!this.columns.includes(cfg.xAxis)) errors.push(`X-Axis "${cfg.xAxis}" not found in telemetry.`);
        if (typeof cfg.yAxes !== "object" || Array.isArray(cfg.yAxes)) {
          errors.push("yAxes must be a hashmap.");
        } else {
          Object.keys(cfg.yAxes).forEach((y) => {
            if (!this.columns.includes(y)) errors.push(`Y-Axis "${y}" missing.`);
          });
        }
        if (cfg.vsRange && cfg.vsRange[0] > cfg.vsRange[1]) errors.push("Comparison range start cannot be greater than end.");
        return errors;
      },
      updateFromRaw() {
        try {
          const parsed = JSON.parse(this.configRaw);
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
            const parsed = JSON.parse(saved);
            this.config = { ...this.config, ...parsed };
          } catch {
            console.error("Stored config corrupt");
          }
        } else {
          if (this.columns.includes("time")) this.config.xAxis = "time";
        }
        const savedHistory = localStorage.getItem("mojo_mosaic_history");
        if (savedHistory) {
          try {
            const { stack, index } = JSON.parse(savedHistory);
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
      hydrateFromUrl(blob) {
        try {
          const decoded = LZString.decompressFromEncodedURIComponent(blob);
          if (!decoded) throw new Error("Decompression failed");
          const parsed = JSON.parse(decoded);
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
          const encoded = LZString.compressToEncodedURIComponent(JSON.stringify(this.config));
          const shareBase = this.externalUrl + window.location.pathname;
          void this.copyToClipboard(`${shareBase}?v=${encoded}`, "Shareable link copied!");
        } catch {
          this.notify("Link generation failed", "error");
        }
      },
      copyRawConfig() {
        void this.copyToClipboard(this.configRaw, "JSON Config copied!");
      },
      resetConfig() {
        if (confirm("Reset plot to factory defaults? This will clear your current view.")) {
          localStorage.removeItem("mojo_mosaic_config");
          this.config = JSON.parse(JSON.stringify(DEFAULT_CONFIG));
          if (this.columns.includes("time")) this.config.xAxis = "time";
          this.notify("Settings Reset", "info");
          this.configRaw = JSON.stringify(this.config, null, 4);
        }
      },
      async copyToClipboard(text, successMsg = "Copied to clipboard!") {
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
      async downloadPlot(format, scale = 1) {
        const el = document.getElementById("plot-area");
        if (!el) return;
        const plotlyFormat = format === "jpg" ? "jpeg" : format;
        const isDark = document.documentElement.classList.contains("dark");
        const bgColor = isDark ? tw.slate[800] : "#ffffff";
        const resW = Math.round(1280 * scale);
        const resH = Math.round(720 * scale);
        this.notify(`Exporting ${resW}x${resH} ${format.toUpperCase()}...`, "info");
        try {
          const origPaper = el.layout.paper_bgcolor;
          const origPlot = el.layout.plot_bgcolor;
          await Plotly.relayout(el, { paper_bgcolor: bgColor, plot_bgcolor: bgColor });
          const dataUrl = await Plotly.toImage(el, { format: plotlyFormat, width: 1280, height: 720, scale });
          await Plotly.relayout(el, { paper_bgcolor: origPaper, plot_bgcolor: origPlot });
          const link = document.createElement("a");
          link.href = dataUrl;
          link.download = `${this.trialId}_${resW}p.${format}`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        } catch (e) {
          console.error("Export failed", e);
        } finally {
          this.downloadOpen = false;
        }
      },
      downloadCSV() {
        if (!this.data || Object.keys(this.config.yAxes).length === 0) return;
        const activeCols = [this.config.xAxis, ...Object.keys(this.config.yAxes)];
        const rowCount = this.data[this.config.xAxis]?.length ?? 0;
        let csv = activeCols.join(",") + "\n";
        for (let i = 0; i < rowCount; i++) {
          csv += activeCols.map((col) => this.data[col]?.[i] ?? "").join(",") + "\n";
        }
        const link = document.createElement("a");
        link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }));
        link.setAttribute("download", `${this.trialId}_filtered.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        this.downloadOpen = false;
        this.notify("Filtered CSV Exported", "success");
      },
      downloadJSON() {
        const link = document.createElement("a");
        link.href = URL.createObjectURL(new Blob([JSON.stringify(this.config, null, 4)], { type: "application/json" }));
        link.setAttribute("download", `${this.trialId}_config.json`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        this.downloadOpen = false;
        this.notify("Configuration JSON Exported", "success");
      },
      handleDrop(e) {
        const file = e.dataTransfer?.files[0];
        if (!file || file.type !== "application/json" && !file.name.endsWith(".json")) {
          this.notify("Please drop a .json file", "error");
          return;
        }
        const reader = new FileReader();
        reader.onload = (event) => {
          try {
            const imported = JSON.parse(event.target?.result);
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
      toggleY(col) {
        if (this.config.yAxes[col]) {
          const { [col]: _, ...rest } = this.config.yAxes;
          this.config.yAxes = rest;
        } else {
          const nextIndex = Object.keys(this.config.yAxes).length;
          this.config.yAxes[col] = {
            color: this.getSignalColor(nextIndex),
            label: "",
            width: 3,
            opacity: 1,
            scale: "1.0",
            dash: "solid",
            marker: "none"
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
      warpToTrial() {
        if (this.warpId === null || this.warpId === void 0 || this.warpId === "") return;
        const paddedNum = String(this.warpId).padStart(this.paddingLen, "0");
        window.location.href = `/mosaic/trial_${paddedNum}`;
      },
      getSignalColor(index) {
        return this.plotColors[index % this.plotColors.length] ?? tw.cyan[500];
      },
      getYProps(axis, index) {
        const obj = this.config.yAxes[axis] ?? {};
        return {
          name: axis,
          label: obj.label || axis,
          color: obj.color || this.getSignalColor(index),
          width: obj.width ?? 3,
          opacity: obj.opacity ?? 1,
          dash: obj.dash ?? "solid",
          marker: obj.marker ?? "none",
          scale: obj.scale ?? "1.0"
        };
      },
      parseScale(scaleStr) {
        try {
          const safe = String(scaleStr).replace(/pi/gi, String(Math.PI)).replace(/[^-()\d/*+.]/g, "");
          return Function('"use strict"; return (' + safe + ")")() || 1;
        } catch {
          return 1;
        }
      },
      // -----------------------------------------------------------------------
      // Range helpers
      // -----------------------------------------------------------------------
      calculatePaddedRange(keys, padding = true) {
        let globalMin = Infinity;
        let globalMax = -Infinity;
        const activeDatasets = [this.data ?? {}];
        if (this.config.vsEnabled) {
          const [start, end] = this.config.vsRange;
          Object.entries(this.vsDatasets).forEach(([vsId, dataset]) => {
            const n = parseInt(vsId.split("_").pop() ?? "");
            if (n >= start && n <= end) activeDatasets.push(dataset);
          });
        }
        activeDatasets.forEach((dataset) => {
          keys.forEach((key, i) => {
            const p = this.getYProps(key, i);
            const scale = this.parseScale(p.scale);
            const series = dataset[key];
            if (!series) return;
            for (let j = 0; j < series.length; j++) {
              const val = (series[j] ?? 0) * scale;
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
        const showX = this.config.showSpike && !isHoverDisabled && (this.config.hover.includes("x") || this.config.hover === "closest");
        const showY = this.config.showSpike && !isHoverDisabled && (this.config.hover.includes("y") || this.config.hover === "closest");
        const displayRangeX = this.config.rangeX ?? this.calculatePaddedRange([this.config.xAxis], false);
        const displayRangeY = this.config.rangeY ?? this.calculatePaddedRange(Object.keys(this.config.yAxes));
        const yKeys = Object.keys(this.config.yAxes);
        let traces = yKeys.map((key, i) => {
          const p = this.getYProps(key, i);
          const scale = this.parseScale(p.scale);
          if (!this.data[p.name]) return null;
          return {
            x: this.data[this.config.xAxis],
            y: this.data[p.name].map((v) => v * scale),
            name: p.label,
            mode: this.config.linemode,
            type: "scatter",
            line: { width: p.width, color: p.color, shape: this.config.interp, dash: p.dash },
            marker: { size: 6, symbol: p.marker },
            opacity: p.opacity,
            hoverlabel: { namelength: -1, bgcolor: tooltipBg, bordercolor: tooltipBorder, font: { family: "monospace", size: 12, color: tooltipFont } },
            hovertemplate: `<b>${key}</b><br>%{x}: %{y:.4f}<extra></extra>`
          };
        }).filter((t) => t !== null);
        if (this.config.vsEnabled) {
          const [start, end] = this.config.vsRange;
          const legendTracker = /* @__PURE__ */ new Set();
          const sortedVsIds = Object.keys(this.vsDatasets).sort((a, b) => parseInt(a.split("_").pop() ?? "0") - parseInt(b.split("_").pop() ?? "0"));
          sortedVsIds.forEach((vsId) => {
            const n = parseInt(vsId.split("_").pop() ?? "");
            if (n < start || n > end || vsId === this.trialId) return;
            const dataset = this.vsDatasets[vsId];
            if (!dataset) return;
            const vsTraces = yKeys.map((key, i) => {
              const p = this.getYProps(key, i);
              if (!dataset[p.name]) return null;
              const scale = this.parseScale(p.scale);
              const isFirst = !legendTracker.has(key);
              const t = {
                x: dataset[this.config.xAxis],
                y: dataset[p.name].map((v) => v * scale),
                name: `${p.label} (<i>vs.</i>)`,
                legendgroup: `group_${key}`,
                showlegend: isFirst,
                mode: this.config.linemode,
                type: "scatter",
                line: { width: 1, color: p.color, shape: this.config.interp, dash: "dot" },
                opacity: 0.35,
                marker: { size: 4, symbol: p.marker },
                hoverlabel: { namelength: -1 },
                hovertemplate: `<b>${key}</b> (#${n})<br>%{x}: %{y:.4f}<extra></extra>`
              };
              legendTracker.add(key);
              return t;
            }).filter((t) => t !== null);
            traces = [...traces, ...vsTraces];
          });
        }
        const xAxisObj = {
          type: this.config.xScale ?? "linear",
          range: this.config.xScale === "log" ? [Math.log10(Math.max(1e-6, displayRangeX[0])), Math.log10(Math.max(1e-6, displayRangeX[1]))] : displayRangeX,
          dtick: this.config.xScale === "log" && this.config.xLogBase ? Math.log10(this.config.xLogBase) : void 0,
          gridcolor: majorGrid,
          showgrid: this.config.grid !== "none",
          minor: { showgrid: this.config.grid === "all", gridcolor: minorGrid },
          zeroline: false,
          tickfont: { color: textColor, size: 14 },
          title: { text: this.config.xAxisTitle || this.config.xAxis, font: { size: 14, color: textColor, family: "monospace" } },
          autorange: false,
          showspikes: showX,
          spikemode: "across",
          spikelinecolor: spikeColor,
          spikethickness: -2
        };
        const frameLabel = this.config.refFrame ? `<br><span style="color: ${textColor}; font-size: 14px; opacity: 0.6;">[Frame: ${this.config.refFrame}]</span>` : "";
        const yAxisObj = {
          type: this.config.yScale ?? "linear",
          range: this.config.yScale === "log" ? [Math.log10(Math.max(1e-6, displayRangeY[0])), Math.log10(Math.max(1e-6, displayRangeY[1]))] : displayRangeY,
          dtick: this.config.yScale === "log" && this.config.yLogBase ? Math.log10(this.config.yLogBase) : void 0,
          gridcolor: majorGrid,
          showgrid: this.config.grid !== "none",
          minor: { showgrid: this.config.grid === "all", gridcolor: minorGrid },
          zeroline: false,
          tickfont: { color: textColor, size: 14 },
          title: { text: this.config.yAxisTitle + frameLabel, font: { size: 14, color: textColor, family: "monospace" } },
          autorange: false,
          showspikes: showY,
          spikemode: "across",
          spikelinecolor: spikeColor,
          spikethickness: -2
        };
        const layout = {
          uirevision: `${this.trialId}_${this.config.xAxis}_${Object.keys(this.config.yAxes).join("_")}`,
          title: this.config.title ? { text: this.config.title, font: { family: "monospace", size: 16, color: isDark ? tw.slate[200] : tw.slate[800], weight: "bold" }, x: 0, xanchor: "left" } : null,
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          margin: { t: this.config.title ? 60 : 30, r: this.config.legendPos === "right" ? 150 : 30, b: this.config.legendPos === "bottom" ? 80 : 50, l: this.config.yAxisTitle ? 80 : 60 },
          hovermode: isHoverDisabled ? false : this.config.hover,
          hoverlabel: { bgcolor: tooltipBg, bordercolor: tooltipBorder, font: { family: "monospace", size: 12, color: tooltipFont }, align: "left" },
          showlegend: this.config.legendPos !== "hidden",
          legend: this.config.legendPos === "right" ? { orientation: "v", x: 1.02, y: 1, font: { family: "monospace", size: 14, color: textColor }, groupclick: "togglegroup" } : { orientation: "h", y: -0.2, x: 0.5, xanchor: "center", font: { family: "monospace", size: 14, color: textColor }, groupclick: "togglegroup" },
          xaxis: xAxisObj,
          yaxis: yAxisObj,
          annotations: [
            ...(this.config.annotations ?? []).map((ann) => ({
              x: ann.x,
              y: ann.y,
              text: ann.text,
              showarrow: true,
              arrowhead: 2,
              ax: 0,
              ay: -40,
              font: { family: "monospace", size: 12, color: isDark ? tw.slate[50] : tw.slate[900] },
              bgcolor: isDark ? tw.slate[800] : tw.slate[50],
              bordercolor: tw.cyan[500],
              borderwidth: 1,
              borderpad: 4
            })),
            ...(this.config.shapes ?? []).filter((s) => s.label).map((s) => {
              let x = s.x0, y = s.y0 ?? 0, xanchor = "left", yanchor = "bottom", xref = "x", yref = "y";
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
              return { x, y, xref, yref, text: `<b>${s.label}</b>`, showarrow: false, xanchor, yanchor, font: { size: 10, color: s.color || tw.cyan[500], family: "monospace" }, bgcolor: isDark ? tw.slate[900] + "B3" : tw.slate[50] + "B3", borderpad: 2 };
            })
          ],
          shapes: (this.config.shapes ?? []).map((s) => {
            const shapeColor = s.color || tw.cyan[500];
            const base = { line: { color: shapeColor, width: 2, dash: s.dash ?? "solid" }, layer: "below" };
            if (s.type === "vline") return { ...base, type: "line", x0: s.x0, x1: s.x0, y0: 0, y1: 1, yref: "paper" };
            if (s.type === "hline") return { ...base, type: "line", y0: s.y0, y1: s.y0, x0: 0, x1: 1, xref: "paper" };
            if (s.type === "rect") return { ...base, type: "rect", x0: s.x0, x1: s.x1, y0: s.y0, y1: s.y1, fillcolor: isDark ? `${shapeColor}1A` : `${shapeColor}26`, line: { ...base.line, width: 1 } };
            return base;
          })
        };
        const config = { responsive: true, displaylogo: false, displayModeBar: true, modeBarButtonsToRemove: ["toImage"] };
        return Plotly.react("plot-area", traces, layout, config);
      }
    };
    return self;
  }
  window.trialViewer = trialViewer;
})();
//# sourceMappingURL=trial-viewer.js.map
