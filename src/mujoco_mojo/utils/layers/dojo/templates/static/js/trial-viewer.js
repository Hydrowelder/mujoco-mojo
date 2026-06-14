"use strict";
(() => {
  // src/lib/options.ts
  var DASH_OPTIONS = ["solid", "dash", "dot", "dashdot"];
  var MARKER_OPTIONS = [
    "none",
    "circle",
    "square",
    "diamond",
    "cross"
  ];
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
        try {
          Alpine.store("dojo").addNotification?.(msg, type);
        } catch {
        }
      }
    };
  }

  // src/trial-viewer.ts
  var tw = {
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
      950: "#020617"
    },
    cyan: { 400: "#22d3ee", 500: "#06b6d4", 600: "#0891b2" },
    emerald: { 500: "#10b981" },
    blue: { 500: "#3b82f6" },
    violet: { 500: "#8b5cf6" },
    amber: { 500: "#f59e0b" },
    rose: { 500: "#ef4444" }
  };
  var LOG_LEVEL_SEVERITY = {
    DEBUG: 10,
    INFO: 20,
    WARNING: 30,
    ERROR: 40,
    CRITICAL: 50
  };
  var DEFAULT_CONFIG = {
    xAxis: { col: "time", filters: [] },
    yAxes: {},
    refFrame: null,
    grid: "all",
    lineMode: "lines",
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
    shapes: []
  };
  var _cm = {
    editor: null,
    updating: false,
    debounce: null
  };
  var _mini = { rafId: null };
  function trialViewer(trialId, externalUrl) {
    const self = {
      // Alpine magic (injected at runtime - declared here for TS)
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
      _renderedPlotType: null,
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
      plotColors: [
        tw.cyan[500],
        tw.emerald[500],
        tw.blue[500],
        tw.violet[500],
        tw.amber[500],
        tw.rose[500]
      ],
      // Toast (shared mixin)
      ...createToastMixin(),
      // Options - exposed so templates can use opts.lineMode, opts.interpLabel(...), etc.
      opts: OPTIONS,
      // --- PLOT CONFIGURATION ---
      config: JSON.parse(JSON.stringify(DEFAULT_CONFIG)),
      // --- JSON EDITOR STATE ---
      configRaw: "",
      isValidJson: true,
      isValidConfig: true,
      configErrors: [],
      isEditingRaw: false,
      // --- PROFILES ---
      profiles: [],
      profileWarnings: {},
      profileSearch: localStorage.getItem("mojo:profile:search") ?? "",
      profilesOpen: false,
      profileNameDraft: "",
      // --- FILTER SCHEMAS (loaded from /mosaic/api/filter-schema on init) ---
      filterSchemas: [],
      // tracks the last filter fingerprint that was fetched for each col; used to detect
      // real filter changes without relying on Alpine.js's (unreliable) oldValue deep clone
      filterFingerprints: {},
      xAxisFilterFingerprint: "[]",
      // deduplicates filter error toasts so VS mode (N parallel fetches) shows each error once
      _shownFilterErrors: /* @__PURE__ */ new Set(),
      // in-progress signal editor edits that survive closing/reopening the panel
      signalDrafts: {},
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
      // --- FILTER LAB ---
      labOpen: localStorage.getItem("mojo:lab:open") === "1",
      labGraph: null,
      labName: "",
      labTabs: [],
      labActiveTabId: null,
      nodePickingColumn: null,
      nodeColSearch: "",
      nodePickingQuat: null,
      nodeQuatSearch: "",
      nodePickingTemplate: null,
      labSchemas: [],
      // --- SHAPES ---
      shapesOpen: false,
      placementMode: null,
      rectStart: null,
      shapeDraft: null,
      shapeEditIndex: null,
      // --- TRIAL STATUS ---
      trialStatus: null,
      _trialStatusPoll: null,
      // --- TRIAL LOGS ---
      logFilename: null,
      logEntries: [],
      logSortKey: "timestamp",
      logSortAsc: true,
      logFilterLevels: [],
      // empty = all levels
      logLevelMenuOpen: false,
      logFilterMessage: "",
      logFilterRegex: false,
      logColWidths: (() => {
        try {
          const saved = localStorage.getItem("mojo:trial-logs:col-widths");
          if (saved) return JSON.parse(saved);
        } catch {
        }
        return { time: 176, level: 96, source: 160 };
      })(),
      _logColResize: null,
      _logMeasureCanvas: null,
      // --- MEDIA PLAYER ---
      mediaFiles: [],
      selectedMedia: null,
      mediaScrubMode: localStorage.getItem("mojo:media:mode") ?? "play",
      mediaShowLine: localStorage.getItem("mojo:media:show-line") === "1",
      mediaShowFrames: localStorage.getItem("mojo:media:show-frames") === "1",
      mediaPlaybackRate: Number(localStorage.getItem("mojo:media:rate")) || 1,
      mediaSpeedPresets: [0.2, 0.5, 1, 2, 4],
      mediaMiniplayerOpen: localStorage.getItem("mojo:media:mini") === "1",
      mediaIsScrubbable: false,
      _gifConvertStatus: "none",
      _mediaRafId: null,
      _mediaFpsMap: {},
      _mediaMtimeMap: {},
      _mediaFrameInterval: null,
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
            this.historyStack[this.historyIndex] ?? "{}"
          );
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
            this.historyStack[this.historyIndex] ?? "{}"
          );
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
          JSON.stringify({ stack: this.historyStack, index: this.historyIndex })
        );
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
        if (requiredCols.length > 0)
          colParams.append("cols", requiredCols.join(","));
        const filtersPayload = {};
        const toActiveFilters = (filters) => filters.filter((f) => f.enabled !== false).map(
          (f) => Object.fromEntries(
            Object.entries(f).filter(([k]) => k !== "enabled")
          )
        );
        for (const col of requiredCols) {
          const yConfig = this.config.yAxes[col];
          if (yConfig?.filters && yConfig.filters.length > 0) {
            const active = toActiveFilters(yConfig.filters);
            if (active.length > 0) filtersPayload[col] = active;
          }
          if (col === this.config.xAxis.col) {
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
        const resp = await fetch(url, { cache: "no-store" });
        if (!resp.ok) throw new Error(`Trial ${id} failed`);
        const result = await resp.json();
        if (result.filter_errors && result.filter_errors.length > 0) {
          result.filter_errors.forEach((msg) => {
            if (!this._shownFilterErrors.has(msg)) {
              this._shownFilterErrors.add(msg);
              this.notify(msg, "error");
              setTimeout(
                () => this._shownFilterErrors.delete(msg),
                5e3
              );
            }
          });
        }
        return result;
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
              this.vsDatasets[id] = {
                ...this.vsDatasets[id] ?? {},
                ...resp.data
              };
              this.vsDatasets = { ...this.vsDatasets };
            } else {
              this.data = { ...this.data ?? {}, ...resp.data };
            }
            if (Object.keys(this.config.yAxes).some((y) => chunk.includes(y)))
              this.renderPlot();
            console.debug(
              `Dojo Hydration [${label}]: ${i + chunk.length}/${columnList.length}`
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
          this.trialStatus = await resp.json();
        } catch {
        }
        if (this.trialStatus && this.trialStatus.completion === "incomplete") {
          if (this._trialStatusPoll === null) {
            this._trialStatusPoll = setInterval(() => {
              void this.fetchTrialStatus();
              void this.fetchTrialLogs();
            }, 3e3);
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
            cache: "no-store"
          });
          if (!resp.ok) return;
          const result = await resp.json();
          this.logFilename = result.filename;
          this.logEntries = result.entries;
        } catch {
        }
      },
      // -----------------------------------------------------------------------
      // Logs: sorting, filtering & styling
      // -----------------------------------------------------------------------
      get filteredLogEntries() {
        const text = this.logFilterMessage.trim();
        let regex = null;
        if (text && this.logFilterRegex) {
          try {
            regex = new RegExp(text, "i");
          } catch {
            regex = null;
          }
        }
        const filtered = this.logEntries.filter((e) => {
          if (this.logFilterLevels.length > 0 && !this.logFilterLevels.includes(e.level))
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
      get logLevels() {
        return Array.from(new Set(this.logEntries.map((e) => e.level))).sort(
          (a, b) => (LOG_LEVEL_SEVERITY[a] ?? 0) - (LOG_LEVEL_SEVERITY[b] ?? 0)
        );
      },
      toggleLogSort(key) {
        if (this.logSortKey === key) {
          this.logSortAsc = !this.logSortAsc;
        } else {
          this.logSortKey = key;
          this.logSortAsc = true;
        }
      },
      toggleLogLevelFilter(level) {
        const idx = this.logFilterLevels.indexOf(level);
        if (idx === -1) this.logFilterLevels.push(level);
        else this.logFilterLevels.splice(idx, 1);
      },
      _persistLogColWidths() {
        try {
          localStorage.setItem(
            "mojo:trial-logs:col-widths",
            JSON.stringify(this.logColWidths)
          );
        } catch {
        }
      },
      startLogColResize(e, col) {
        e.preventDefault();
        const startX = e.clientX;
        const startWidth = this.logColWidths[col];
        const onMove = (ev) => {
          this.logColWidths[col] = Math.max(40, startWidth + (ev.clientX - startX));
        };
        const onUp = () => {
          window.removeEventListener("mousemove", onMove);
          window.removeEventListener("mouseup", onUp);
          this._persistLogColWidths();
        };
        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
      },
      _measureTextWidth(text, refEl) {
        const canvas = this._logMeasureCanvas ?? (this._logMeasureCanvas = document.createElement("canvas"));
        const ctx = canvas.getContext("2d");
        if (!ctx) return 0;
        ctx.font = getComputedStyle(refEl).font;
        return ctx.measureText(text).width;
      },
      autoFitLogColumn(col) {
        const container = this.$refs.logTable;
        if (!container) return;
        const headerEl = container.querySelector(
          `[data-logcol-header="${col}"]`
        );
        if (!headerEl) return;
        const contentEl = container.querySelector(
          `[data-logcol-content="${col}"]`
        );
        const HEADER_ICON_ALLOWANCE = 20;
        const CELL_PADDING = 16;
        const BADGE_PADDING = 16;
        let width = this._measureTextWidth(headerEl.textContent?.trim() ?? "", headerEl) + HEADER_ICON_ALLOWANCE;
        if (contentEl) {
          for (const entry of this.filteredLogEntries) {
            let text;
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
        const padding = col === "level" ? CELL_PADDING + BADGE_PADDING : CELL_PADDING;
        this.logColWidths[col] = Math.ceil(width) + padding;
        this._persistLogColWidths();
      },
      logSourceShort(entry) {
        const file = entry.pathname.split("/").pop() ?? "";
        return entry.lineno != null ? `${file}:${entry.lineno}` : file;
      },
      logSourceFull(entry) {
        return entry.lineno != null ? `${entry.pathname}:${entry.lineno}` : entry.pathname;
      },
      logLevelClass(level) {
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
      formatLogTime(timestamp, _tick) {
        const diff = Date.now() - timestamp;
        if (diff < 24 * 60 * 60 * 1e3) return window.notifTimeAgo(timestamp, _tick);
        return new Date(timestamp).toLocaleString();
      },
      _updateIsScrubbable() {
        const sel = this.selectedMedia?.toLowerCase() ?? "";
        this.mediaIsScrubbable = sel.endsWith(".mp4") || sel.endsWith(".webm") || sel.endsWith(".gif") && this._gifConvertStatus === "ready";
      },
      _syncOverlayVisibility() {
        const overlay = document.getElementById(
          "playback-line-overlay"
        );
        const lineEl = document.getElementById(
          "playback-line-el"
        );
        const isTimeAxis = this.config.xAxis?.col === "time";
        const hasYAxes = Object.keys(this.config.yAxes).length > 0;
        const lineVisible = this.mediaShowLine && this.mediaScrubMode === "play" && this.mediaIsScrubbable && isTimeAxis && hasYAxes;
        const framesVisible = this.mediaShowFrames && !!this._mediaFrameInterval && isTimeAxis && hasYAxes;
        if (overlay)
          overlay.style.display = lineVisible || framesVisible ? "block" : "none";
        if (lineEl) lineEl.style.display = lineVisible ? "block" : "none";
      },
      _renderFrameMarkers() {
        const framesPath = document.getElementById(
          "playback-frames-path"
        );
        if (!framesPath) return;
        this._syncOverlayVisibility();
        const hasYAxes = Object.keys(this.config.yAxes).length > 0;
        if (!this.mediaShowFrames || !this._mediaFrameInterval || this.config.xAxis?.col !== "time" || !hasYAxes) {
          framesPath.setAttribute("d", "");
          return;
        }
        const plotEl = document.getElementById("plot-area");
        const fullLayout = plotEl?._fullLayout;
        const rect = plotEl?.getBoundingClientRect();
        if (!plotEl || !fullLayout) return;
        const video = document.getElementById(
          "media-video-player"
        );
        const duration = video?.duration && isFinite(video.duration) ? video.duration : Infinity;
        const interval = this._mediaFrameInterval;
        const ph = rect.height;
        const markerHeight = 5;
        const markerTop = ph - fullLayout.margin.b - 20;
        const markerBot = markerTop - markerHeight;
        const [xMin, xMax] = fullLayout.xaxis.range;
        const kStart = Math.max(0, Math.floor(xMin / interval));
        const kEnd = Math.ceil(
          Math.min(isFinite(duration) ? duration : xMax, xMax) / interval
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
        const shouldRun = this.mediaScrubMode === "play" && this.mediaFiles.length > 0 && this.mediaIsScrubbable && isTimeAxis;
        if (!shouldRun || this._mediaRafId !== null) return;
        const tick = () => {
          const curTimeAxis = this.config.xAxis?.col === "time";
          if (this.mediaScrubMode !== "play" || this.mediaFiles.length === 0 || !this.mediaIsScrubbable || !curTimeAxis) {
            this._mediaRafId = null;
            this._syncOverlayVisibility();
            return;
          }
          const video = document.getElementById(
            "media-video-player"
          );
          const plotEl = document.getElementById("plot-area");
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
                  "playback-line-el"
                );
                if (lineEl) {
                  lineEl.style.top = fullLayout.margin.t + "px";
                  lineEl.style.bottom = fullLayout.margin.b + "px";
                  const t = this._mediaFrameInterval ? Math.round(video.currentTime / this._mediaFrameInterval) * this._mediaFrameInterval : video.currentTime;
                  lineEl.style.left = fullLayout.margin.l + fullLayout.xaxis.l2p(t) + "px";
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
          const data = await resp.json();
          this._mediaFpsMap = Object.fromEntries(
            data.files.map((f) => [f.name, f.fps])
          );
          this._mediaMtimeMap = Object.fromEntries(
            data.files.map((f) => [f.name, f.mtime])
          );
          this.mediaFiles = data.files.map((f) => f.name);
          if (this.mediaFiles.length > 0) {
            const saved = localStorage.getItem("mojo:media:file");
            this.selectedMedia = saved && this.mediaFiles.includes(saved) ? saved : this.mediaFiles[0];
          }
          this._applySelectedMediaFps();
          this._updateIsScrubbable();
        } catch {
        }
        this._updatePlaybackLine();
        this._renderFrameMarkers();
        if (this.mediaMiniplayerOpen && this.mediaFiles.length > 0)
          this._startMiniplayer();
      },
      // builds a media file URL with an mtime cache-buster, so a regenerated
      // file with the same name forces the browser to reload it instead of
      // reusing a stale cached video/image from before the rerun
      _mediaFileUrl(filename, suffix = "") {
        const base = `/mosaic/${this.trialId}/media/${filename}${suffix}`;
        const mtime = this._mediaMtimeMap[filename];
        return mtime !== void 0 ? `${base}?t=${mtime}` : base;
      },
      _applySelectedMediaFps() {
        const fps = this.selectedMedia ? this._mediaFpsMap[this.selectedMedia] ?? null : null;
        this._mediaFrameInterval = fps && fps > 0 ? 1 / fps : null;
      },
      _onVideoLoaded() {
        const video = document.getElementById(
          "media-video-player"
        );
        if (video) video.playbackRate = this.mediaPlaybackRate;
        if (this.selectedMedia?.toLowerCase().endsWith(".gif")) {
          this._gifConvertStatus = "ready";
          void video?.play();
        }
      },
      _onVideoError() {
        if (this.selectedMedia?.toLowerCase().endsWith(".gif")) {
          this._gifConvertStatus = "failed";
        }
      },
      _miniDragStart(e) {
        const wrapper = document.getElementById(
          "mini-wrapper"
        );
        const canvas = document.getElementById(
          "mini-canvas"
        );
        if (!wrapper) return;
        const startX = e.clientX;
        const startY = e.clientY;
        const startLeft = parseInt(wrapper.style.left) || 8;
        const startTop = parseInt(wrapper.style.top) || 8;
        const card = wrapper.parentElement;
        if (canvas) canvas.style.cursor = "grabbing";
        const onMove = (ev) => {
          const maxLeft = card ? Math.max(0, card.offsetWidth - wrapper.offsetWidth - 4) : 9999;
          const maxTop = card ? Math.max(0, card.offsetHeight - wrapper.offsetHeight - 4) : 9999;
          wrapper.style.left = Math.max(4, Math.min(maxLeft, startLeft + ev.clientX - startX)) + "px";
          wrapper.style.top = Math.max(4, Math.min(maxTop, startTop + (ev.clientY - startY))) + "px";
        };
        const onUp = () => {
          document.removeEventListener("mousemove", onMove);
          document.removeEventListener("mouseup", onUp);
          if (canvas) canvas.style.cursor = "grab";
          try {
            localStorage.setItem("mojo:media:mini:left", wrapper.style.left);
            localStorage.setItem("mojo:media:mini:top", wrapper.style.top);
          } catch {
          }
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
      },
      _miniResizeStart(e) {
        const wrapper = document.getElementById(
          "mini-wrapper"
        );
        if (!wrapper) return;
        const startX = e.clientX;
        const startY = e.clientY;
        const startW = wrapper.offsetWidth;
        const startH = wrapper.offsetHeight;
        const video = document.getElementById(
          "media-video-player"
        );
        const aspectRatio = video && video.videoWidth && video.videoHeight ? video.videoWidth / video.videoHeight : 16 / 9;
        const onMove = (ev) => {
          const dw = ev.clientX - startX;
          const dh = ev.clientY - startY;
          let newW = Math.max(120, startW + dw);
          let newH = Math.max(68, startH + dh);
          if (ev.shiftKey) {
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
          }
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
      },
      _startMiniplayer() {
        const wrapper = document.getElementById(
          "mini-wrapper"
        );
        const canvas = document.getElementById(
          "mini-canvas"
        );
        if (!wrapper || !canvas || _mini.rafId !== null) return;
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
        }
        wrapper.style.display = "block";
        const paint = () => {
          const isGif = this.selectedMedia?.toLowerCase().endsWith(".gif") ?? false;
          const useVideo = !isGif || this._gifConvertStatus === "ready";
          const srcEl = useVideo ? document.getElementById(
            "media-video-player"
          ) : document.getElementById(
            "media-gif-player"
          );
          if (srcEl) {
            const ctx = canvas.getContext("2d");
            if (ctx) {
              const vEl = srcEl;
              if (isGif || vEl.readyState === void 0 || vEl.readyState >= 2) {
                ctx.drawImage(
                  srcEl,
                  0,
                  0,
                  canvas.width,
                  canvas.height
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
          "mini-wrapper"
        );
        if (wrapper) wrapper.style.display = "none";
      },
      async startBackgroundDiscovery() {
        const currentId = ++this.discoveryId;
        const pendingCols = this.columns.filter(
          (c) => !Object.prototype.hasOwnProperty.call(this.data ?? {}, c)
        );
        if (pendingCols.length > 0)
          await this.trickleFetch(
            this.trialId,
            pendingCols,
            "Current",
            false,
            currentId
          );
        if (currentId !== this.discoveryId) return;
        const start = Math.min(this.vsDraft.range[0], this.vsDraft.range[1]);
        const end = Math.max(this.vsDraft.range[0], this.vsDraft.range[1]);
        const activeCols = [
          this.config.xAxis.col,
          ...Object.keys(this.config.yAxes)
        ];
        const draftIds = this.allTrials.filter((id) => {
          const n = parseInt(id.split("_").pop() ?? "");
          return n >= start && n <= end && id !== this.trialId;
        });
        for (const id of draftIds) {
          if (currentId !== this.discoveryId) return;
          const existing = this.vsDatasets[id];
          const needsFetch = !existing || activeCols.some(
            (c) => !Object.prototype.hasOwnProperty.call(existing, c)
          );
          if (needsFetch)
            await this.trickleFetch(
              id,
              activeCols,
              `Draft ${id}`,
              true,
              currentId
            );
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
        const defaultColor = this.plotColors[this.config.shapes.length % this.plotColors.length];
        let newShape = null;
        if (this.placementMode === "vline") {
          newShape = { type: "vline", x0: pt.x, color: defaultColor, label: "" };
        } else if (this.placementMode === "hline") {
          newShape = {
            type: "hline",
            x0: pt.x,
            y0: pt.y,
            color: defaultColor,
            label: ""
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
            label: ""
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
        void this.$nextTick(
          () => this.$refs["annInput"]?.focus()
        );
      },
      cancelAnnDraft() {
        this.annDraft = null;
        this.annEditIndex = null;
      },
      jumpToAnnotation(ann) {
        const el = document.getElementById("plot-area");
        if (!el || !this.data) return;
        const xValues = this.data[this.config.xAxis.col] ?? [];
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
        const fullY = this.calculatePaddedRange(
          Object.keys(this.config.yAxes),
          false
        );
        const ySpan = Math.abs(fullY[1] - fullY[0]) * 0.2;
        const newRangeY = [
          ann.y - ySpan / 2,
          ann.y + ySpan / 2
        ];
        this.config.rangeX = newRangeX;
        this.config.rangeY = newRangeY;
        void Plotly.relayout(el, {
          "xaxis.range": newRangeX,
          "yaxis.range": newRangeY,
          "xaxis.autorange": false,
          "yaxis.autorange": false
        });
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
          return ["x", "y", "z"].includes(suffix ?? "") && (this.rotateableVectors ?? []).includes(family);
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
        void this.fetchTrialStatus();
        void this.fetchTrialLogs();
        void this.fetchMediaFiles();
        this._initTabs();
        window.mojoLabOnDirtyChange = (dirty) => {
          const tab = this.labTabs.find((t) => t.id === this.labActiveTabId);
          if (tab) tab.dirty = dirty;
        };
        window.mojoLabGetBaseline = () => {
          const tab = this.labTabs.find((t) => t.id === this.labActiveTabId);
          return tab?.savedState ?? null;
        };
        window.mojoLabSetBaseline = (state) => {
          const tab = this.labTabs.find((t) => t.id === this.labActiveTabId);
          if (tab) tab.savedState = state;
        };
        void this.$nextTick(() => {
          const video = document.getElementById(
            "media-video-player"
          );
          if (video) {
            video.onloadedmetadata = () => this._onVideoLoaded();
            video.onerror = () => this._onVideoError();
          }
        });
        const observer = new MutationObserver((mutations) => {
          if (mutations.some((m) => m.attributeName === "class")) {
            this.theme = document.documentElement.classList.contains("dark") ? "dark" : "light";
            if (this.data && Object.keys(this.config.yAxes).length > 0)
              this.renderPlot();
          }
        });
        observer.observe(document.documentElement, { attributes: true });
        try {
          const schemaResp = await fetch("/mosaic/api/filter-schema");
          this.filterSchemas = await schemaResp.json();
        } catch (e) {
          console.warn("Failed to load filter schemas", e);
        }
        try {
          const statusResp = await fetch("/monitor/api/status/job");
          const statusData = await statusResp.json();
          if (statusData && !statusData.error) {
            Alpine.store("dojo").updateSync(
              Date.now(),
              statusData.is_complete
            );
            const match = statusData.padding_style.match(/\d+/);
            this.paddingLen = match ? parseInt(match[0]) : 2;
          }
        } catch (e) {
          console.warn("Dojo offline", e);
        }
        try {
          const initialCols = [
            this.config.xAxis.col,
            ...Object.keys(this.config.yAxes)
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
          if (this.config.refFrame) {
            const hasRotation = Object.values(this.config.yAxes).some(
              (y) => y.filters.some((f) => f.type === "rotation")
            );
            if (!hasRotation) this.applyRefFrame(this.config.refFrame);
          }
          void this.$nextTick(() => {
            this.pushHistory();
          });
          void this.$nextTick(async () => {
            await this.renderPlot();
            requestAnimationFrame(() => {
              const plotEl2 = document.getElementById("plot-area");
              console.debug(
                "[init RAF] _fullLayout present:",
                !!plotEl2?._fullLayout,
                "rect:",
                plotEl2?.getBoundingClientRect()
              );
              this._renderFrameMarkers();
              this._syncOverlayVisibility();
            });
            const plotEl = document.getElementById("plot-area");
            this._attachPlotEventHandlers();
            plotEl.addEventListener("click", (e) => {
              if (!this.placementMode) return;
              const target = e.target;
              if (!target.classList.contains("nsewdrag") && !target.classList.contains("drag"))
                return;
              const rect = plotEl.getBoundingClientRect();
              const fullLayout = plotEl._fullLayout;
              if (!fullLayout) return;
              this.handlePlotClickForShapes({
                x: fullLayout.xaxis.p2l(
                  e.clientX - rect.left - fullLayout.margin.l
                ),
                y: fullLayout.yaxis.p2l(
                  e.clientY - rect.top - fullLayout.margin.t
                )
              });
            });
            document.addEventListener("mousedown", (e) => {
              if (e.button !== 1) return;
              const rect = plotEl.getBoundingClientRect();
              if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom)
                return;
              e.preventDefault();
              const fullLayout = plotEl._fullLayout;
              if (!fullLayout) return;
              const xVal = fullLayout.xaxis.p2l(
                e.clientX - rect.left - fullLayout.margin.l
              );
              const yVal = fullLayout.yaxis.p2l(
                e.clientY - rect.top - fullLayout.margin.t
              );
              setTimeout(() => {
                this.annDraft = { x: xVal, y: yVal, text: "" };
                this.annEditIndex = null;
                this.annotationsOpen = true;
                void this.$nextTick(() => {
                  document.querySelector(
                    '[x-ref="annInput"]'
                  )?.focus();
                });
              }, 0);
            });
            new MutationObserver((mutations) => {
              for (const { addedNodes } of mutations) {
                for (const node of addedNodes) {
                  if (!(node instanceof HTMLElement)) continue;
                  const notif = node.classList.contains("plotly-notifier") ? node : node.querySelector?.(".plotly-notifier");
                  if (!notif) continue;
                  const text = notif.textContent?.replace(/×/g, "").trim();
                  if (text) this.notify(text, "info");
                  notif.style.display = "none";
                }
              }
            }).observe(document.body, { childList: true, subtree: true });
            plotEl.addEventListener("mousemove", (e) => {
              if (this.mediaScrubMode !== "scrub") return;
              const video = document.getElementById(
                "media-video-player"
              );
              if (!video || !video.duration || isNaN(video.duration)) return;
              const fullLayout = plotEl._fullLayout;
              if (!fullLayout) return;
              const rect = plotEl.getBoundingClientRect();
              const relX = e.clientX - rect.left - fullLayout.margin.l;
              if (this.config.xAxis?.col === "time") {
                const t = fullLayout.xaxis.p2l(relX);
                video.currentTime = Math.max(0, Math.min(video.duration, t));
              } else {
                const plotAreaWidth = rect.width - fullLayout.margin.l - fullLayout.margin.r;
                if (plotAreaWidth <= 0) return;
                video.currentTime = video.duration * Math.max(0, Math.min(1, relX / plotAreaWidth));
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
          Alpine.store("dojo").startGlobalSync();
          Alpine.store("dojo").setPageReady(true);
        }
        window.addEventListener(
          "keydown",
          (e) => {
            if (e.repeat) return;
            const dojoStore = Alpine.store("dojo");
            if (dojoStore?.dialog?.show) {
              if (e.key === "Escape" || e.key === "Enter") {
                e.preventDefault();
                e.stopPropagation();
                if (e.key === "Escape") dojoStore.dialog.cancel();
                else dojoStore.dialog.confirm();
              }
              return;
            }
            const targetEl = e.target;
            const tag = targetEl.tagName;
            const isTextInput = ["INPUT", "TEXTAREA", "SELECT"].includes(tag) || targetEl.isContentEditable;
            if (e.key === "/" && !isTextInput) {
              e.preventDefault();
              document.querySelector(
                'input[type="number"]'
              )?.focus();
            }
            if (e.key === "Escape") {
              const anyOpen = !!(this.placementMode || this.annotationsOpen || this.shapesOpen || this.xMenuOpen || this.yMenuOpen || this.refFrameMenuOpen || this.settingsOpen || this.downloadOpen || this.editorOpen || this.profilesOpen || this.vsMenuOpen || this.labOpen || Alpine.store("dojo").overlayCount > 0 || isTextInput);
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
                void (window.mojoConfirm?.({
                  title: "Unsaved changes",
                  message: "Close the lab and discard unsaved changes?",
                  confirmLabel: "Discard",
                  cancelLabel: "Keep editing",
                  variant: "warning"
                }) ?? Promise.resolve(false)).then((ok) => {
                  if (ok) {
                    window.mojoLabRevertToSaved?.();
                    this.labOpen = false;
                  }
                });
              }
              window.dispatchEvent(new CustomEvent("mojo:escape"));
              if (anyOpen) e.stopImmediatePropagation();
            }
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "c" && !isTextInput) {
              if (this.labOpen) {
                e.preventDefault();
                document.dispatchEvent(new CustomEvent("mojo:lab-clear"));
              }
            }
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
              e.preventDefault();
              if (this.labOpen) {
                const nameEl = document.getElementById(
                  "lab-name-input"
                );
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
                    "profile-name-input"
                  );
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
              const prev = [...this.mediaSpeedPresets].reverse().find((p) => p < this.mediaPlaybackRate);
              if (prev !== void 0) this.mediaPlaybackRate = prev;
            } else if (e.key === ">") {
              e.preventDefault();
              const next = this.mediaSpeedPresets.find(
                (p) => p > this.mediaPlaybackRate
              );
              if (next !== void 0) this.mediaPlaybackRate = next;
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
          { capture: true }
        );
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
            if (this.vsDraft.enabled) void this.startBackgroundDiscovery();
          }, 500);
        });
        this.$watch("profileSearch", (val) => {
          try {
            localStorage.setItem("mojo:profile:search", val);
          } catch {
          }
        });
        this.$watch("mediaScrubMode", (mode) => {
          if (mode === "scrub") {
            document.getElementById(
              "media-video-player"
            )?.pause();
          }
          try {
            localStorage.setItem("mojo:media:mode", mode);
          } catch {
          }
          this._syncOverlayVisibility();
          this._updatePlaybackLine();
        });
        this.$watch("mediaShowLine", (val) => {
          try {
            localStorage.setItem("mojo:media:show-line", val ? "1" : "0");
          } catch {
          }
          this._syncOverlayVisibility();
          this._updatePlaybackLine();
        });
        this.$watch("mediaShowFrames", (val) => {
          try {
            localStorage.setItem("mojo:media:show-frames", val ? "1" : "0");
          } catch {
          }
          this._syncOverlayVisibility();
          this._renderFrameMarkers();
          this._updatePlaybackLine();
        });
        this.$watch("mediaPlaybackRate", (rate) => {
          try {
            localStorage.setItem("mojo:media:rate", String(rate));
          } catch {
          }
          const video = document.getElementById(
            "media-video-player"
          );
          if (video) video.playbackRate = rate;
        });
        this.$watch("config.rangeX", () => {
          requestAnimationFrame(() => this._renderFrameMarkers());
        });
        this.$watch("selectedMedia", (file) => {
          if (file)
            try {
              localStorage.setItem("mojo:media:file", file);
            } catch {
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
          if (sel.endsWith(".gif")) {
            void this.$nextTick(() => {
              const video = document.getElementById(
                "media-video-player"
              );
              if (video && video.readyState >= HTMLMediaElement.HAVE_METADATA) {
                this._onVideoLoaded();
              }
            });
          }
        });
        this.$watch("mediaMiniplayerOpen", (open) => {
          try {
            localStorage.setItem("mojo:media:mini", open ? "1" : "0");
          } catch {
          }
          if (open && this.mediaFiles.length > 0) this._startMiniplayer();
          else this._stopMiniplayer();
        });
        this.$watch("_gifConvertStatus", () => {
          this._updateIsScrubbable();
          this._syncOverlayVisibility();
          this._updatePlaybackLine();
        });
        this.$watch("config.xAxis.col", (newCol) => {
          if (newCol && !Object.prototype.hasOwnProperty.call(this.data ?? {}, newCol)) {
            void (async () => {
              try {
                const resp2 = await this.fetchTrialData(this.trialId, [newCol]);
                this.data = { ...this.data ?? {}, ...resp2.data };
                this.saveAndRender();
              } catch {
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
          (newValue, oldValue) => {
            if (newValue === oldValue) return;
            this.notify(`Frame: ${newValue || "world"}`, "info");
            this.discoveryId++;
            this.applyRefFrame(newValue);
          }
        );
        this.$watch("config", async (value, oldValue) => {
          if (!this.isEditingRaw) {
            this.configRaw = JSON.stringify(value, null, 4);
            try {
              localStorage.removeItem("mojo:config:raw-draft");
            } catch {
            }
          }
          if (this.config.vsEnabled && oldValue?.vsEnabled && (value.xAxis.col !== oldValue?.xAxis?.col || Object.keys(value.yAxes).length !== Object.keys(oldValue.yAxes ?? {}).length)) {
            await this.syncVsRange();
          }
          this.pushHistory();
          const changedFilterCols = Object.keys(value.yAxes).filter((col) => {
            const current = JSON.stringify(
              (value.yAxes[col]?.filters ?? []).filter(
                (f) => f.enabled !== false
              )
            );
            return current !== (this.filterFingerprints[col] ?? "[]");
          });
          const xFilterCurrent = JSON.stringify(
            (value.xAxis?.filters ?? []).filter((f) => f.enabled !== false)
          );
          const xFilterChanged = xFilterCurrent !== this.xAxisFilterFingerprint;
          if (xFilterChanged) {
            this.xAxisFilterFingerprint = xFilterCurrent;
            if (this.data) delete this.data[value.xAxis.col];
          }
          const colsToRefetch = [
            ...xFilterChanged ? [value.xAxis.col] : [],
            ...changedFilterCols
          ];
          if (colsToRefetch.length > 0) {
            changedFilterCols.forEach((col) => {
              this.filterFingerprints[col] = JSON.stringify(
                (value.yAxes[col]?.filters ?? []).filter(
                  (f) => f.enabled !== false
                )
              );
              if (this.data) delete this.data[col];
            });
            this.vsDatasets = {};
            const resp2 = await this.fetchTrialData(this.trialId, colsToRefetch);
            this.data = { ...this.data ?? {}, ...resp2.data };
            if (this.config.vsEnabled) await this.syncVsRange();
          }
          this.saveAndRender();
          this._syncOverlayVisibility();
          requestAnimationFrame(() => this._renderFrameMarkers());
        });
        void this.startBackgroundDiscovery();
        this.configRaw = localStorage.getItem("mojo:config:raw-draft") ?? JSON.stringify(this.config, null, 4);
        this.updateFromRaw();
        window.addEventListener("mojo-sensai-plot-config", (e) => {
          const detail = e.detail;
          if (detail && typeof detail === "object") {
            this.config = { ...detail };
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
          let activeCols = [
            this.config.xAxis.col,
            ...Object.keys(this.config.yAxes)
          ];
          if (this.config.refFrame) {
            const families = /* @__PURE__ */ new Set();
            Object.keys(this.config.yAxes).forEach((col) => {
              if (col.includes(":"))
                families.add(col.substring(0, col.lastIndexOf(":")));
            });
            families.forEach(
              (fam) => activeCols.push(`${fam}:x`, `${fam}:y`, `${fam}:z`)
            );
            activeCols.push(
              `${this.config.refFrame}:w`,
              `${this.config.refFrame}:x`,
              `${this.config.refFrame}:y`,
              `${this.config.refFrame}:z`
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
              const needsFetch = !existing || activeCols.some(
                (col) => !Object.prototype.hasOwnProperty.call(existing, col)
              ) || this.config.refFrame !== null;
              if (needsFetch) {
                const response = await this.fetchTrialData(id, activeCols);
                this.vsDatasets[id] = {
                  ...this.vsDatasets[id] ?? {},
                  ...response.data
                };
              }
            })
          );
          this.vsDatasets = { ...this.vsDatasets };
          this.config.vsRange = [start, end];
          this.config.vsEnabled = true;
          if (targetIds.length > 0) {
            this.notify(
              `Comparing ${targetIds.length} trial${targetIds.length === 1 ? "" : "s"}`,
              "info"
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
      setVsPreset(delta) {
        const cur = parseInt(this.trialId.split("_").pop() ?? "0");
        this.vsDraft.range = [cur - delta, cur + delta];
      },
      setVsAll() {
        const nums = this.allTrials.map((t) => parseInt(t.split("_").pop() ?? "")).filter((n) => !isNaN(n));
        if (!nums.length) return;
        this.vsDraft.range = [Math.min(...nums), Math.max(...nums)];
      },
      isVsPreset(delta) {
        const cur = parseInt(this.trialId.split("_").pop() ?? "0");
        const [a, b] = this.vsDraft.range;
        return Math.min(a, b) === cur - delta && Math.max(a, b) === cur + delta;
      },
      isVsAll() {
        const nums = this.allTrials.map((t) => parseInt(t.split("_").pop() ?? "")).filter((n) => !isNaN(n));
        if (!nums.length) return false;
        const [a, b] = this.vsDraft.range;
        return Math.min(a, b) === Math.min(...nums) && Math.max(a, b) === Math.max(...nums);
      },
      vsInRangeCount() {
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
        const base = field === "x" || field === "nodeCol" ? this.columns : field === "nodeQuat" ? this.availableQuats : this.selectableYColumns;
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
          return this.smartSort(
            base.filter((c) => c.toLowerCase().includes(search.toLowerCase()))
          );
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
            const isFolder = this.columns.some(
              (c) => c.toLowerCase().startsWith(pathPart.toLowerCase() + "/")
            );
            if (isFolder) pathPart += "/";
          }
        }
        self2[key] = (pathPart ?? "") + (suffixPart ? ":" + suffixPart : "");
      },
      getSegmentsAtDepth(field, depth) {
        const base = field === "x" || field === "nodeCol" ? this.columns : field === "nodeQuat" ? this.availableQuats : this.selectableYColumns;
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
        const base = field === "x" || field === "nodeCol" ? this.columns : field === "nodeQuat" ? this.availableQuats : this.selectableYColumns;
        const search = this[field + "Search"] ?? "";
        const [pathPart = "", suffixPart = ""] = search.split(":");
        const selected = (suffixPart ?? "").replace(/[()]/g, "").split("|").filter(Boolean).map((s) => ":" + s);
        const pathRegex = new RegExp(
          "^" + (pathPart ?? "").replace(/\//g, "\\/?"),
          "i"
        );
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
        return html.replace(
          regex,
          (match, _token, _i1, _i2, _i3, garbage) => {
            if (garbage)
              return `<span class="text-rose-500 underline decoration-wavy underline-offset-2 font-bold">${garbage}</span>`;
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
          }
        );
      },
      validateConfig(cfg) {
        const errors = [];
        const labsNoted = /* @__PURE__ */ new Set();
        const schemasLoaded = this.labSchemas.length > 0;
        const checkCol = (col, label) => {
          if (col.startsWith("Lab/")) {
            if (!schemasLoaded) return;
            const labRest = col.slice(4);
            const labSplitIdx = labRest.lastIndexOf("/");
            const labName = labSplitIdx >= 0 ? labRest.slice(0, labSplitIdx) : labRest;
            if (labsNoted.has(labName)) return;
            const lab = this.labSchemas.find((l) => l.name === labName);
            if (!lab) {
              labsNoted.add(labName);
              errors.push(`Lab "${labName}" not found.`);
            } else if (lab.missing.length > 0) {
              labsNoted.add(labName);
              errors.push(
                `Lab "${labName}" requires: ${lab.signal_in_columns.join(", ")}; missing: ${lab.missing.join(", ")}.`
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
        } catch {
        }
        try {
          const parsed = JSON.parse(this.configRaw);
          this.isValidJson = true;
          if (parsed && typeof parsed === "object") {
            this.configErrors = this.validateConfig(parsed);
            this.isValidConfig = this.configErrors.length === 0;
            if (this.isValidConfig) {
              const prevRefFrame = this.config.refFrame ?? null;
              this.isEditingRaw = true;
              this.config = { ...this.config, ...parsed };
              const nextRefFrame = this.config.refFrame ?? null;
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
            const parsed = JSON.parse(saved);
            this.config = { ...this.config, ...parsed };
          } catch {
            console.error("Stored config corrupt");
          }
        } else {
          if (this.columns.includes("time")) this.config.xAxis.col = "time";
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
          const encoded = LZString.compressToEncodedURIComponent(
            JSON.stringify(this.config)
          );
          const shareBase = this.externalUrl + window.location.pathname;
          void this.copyToClipboard(
            `${shareBase}?v=${encoded}`,
            "Shareable link copied!"
          );
        } catch {
          this.notify("Link generation failed", "error");
        }
      },
      copyRawConfig() {
        void this.copyToClipboard(this.configRaw, "JSON Config copied!");
      },
      initCodeMirror(hostEl) {
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
          defaultHighlightStyle
        } = CM;
        const self2 = this;
        const savedH = localStorage.getItem("mojo:json-editor:height");
        if (savedH) hostEl.style.height = savedH;
        const darkTheme = EditorView.theme(
          {
            "&": { backgroundColor: "#020617", color: "#cbd5e1", height: "100%" },
            ".cm-scroller": {
              overflow: "auto",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
              fontSize: "0.875rem",
              lineHeight: "1.625"
            },
            ".cm-content": { padding: "1rem", caretColor: "#06b6d4" },
            ".cm-cursor": { borderLeftColor: "#06b6d4" },
            ".cm-gutters": {
              backgroundColor: "#0f172a",
              color: "#475569",
              borderRight: "1px solid #1e293b"
            },
            ".cm-activeLineGutter": { backgroundColor: "rgba(15,23,42,0.6)" },
            ".cm-activeLine": { backgroundColor: "rgba(15,23,42,0.4)" },
            ".cm-selectionBackground": { backgroundColor: "#1e293b !important" },
            "&.cm-focused .cm-selectionBackground": {
              backgroundColor: "#1e293b !important"
            },
            ".cm-matchingBracket": { color: "#22d3ee", fontWeight: "bold" },
            ".cm-tooltip": {
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              color: "#cbd5e1"
            },
            ".cm-panels": {
              backgroundColor: "#0f172a",
              borderColor: "#1e293b",
              color: "#cbd5e1"
            },
            ".cm-searchMatch": { backgroundColor: "rgba(34,211,238,0.18)" },
            ".cm-searchMatch.cm-searchMatch-selected": {
              backgroundColor: "rgba(34,211,238,0.35)"
            },
            ".cm-lintRange-error": {
              backgroundImage: "none",
              textDecoration: "underline wavy #ef4444 1.5px",
              textUnderlineOffset: "3px"
            },
            ".cm-lintRange-warning": {
              backgroundImage: "none",
              textDecoration: "underline wavy #f59e0b 1.5px",
              textUnderlineOffset: "3px"
            },
            ".cm-diagnostic-error": { borderLeft: "3px solid #ef4444" }
          },
          { dark: true }
        );
        const lightTheme = EditorView.theme(
          {
            "&": { backgroundColor: "#ffffff", color: "#0f172a", height: "100%" },
            ".cm-scroller": {
              overflow: "auto",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
              fontSize: "0.875rem",
              lineHeight: "1.625"
            },
            ".cm-content": { padding: "1rem", caretColor: "#0891b2" },
            ".cm-cursor": { borderLeftColor: "#0891b2" },
            ".cm-gutters": {
              backgroundColor: "#f8fafc",
              color: "#94a3b8",
              borderRight: "1px solid #e2e8f0"
            },
            ".cm-activeLineGutter": { backgroundColor: "rgba(241,245,249,0.6)" },
            ".cm-activeLine": { backgroundColor: "rgba(241,245,249,0.5)" },
            ".cm-selectionBackground": { backgroundColor: "#e2e8f0 !important" },
            "&.cm-focused .cm-selectionBackground": {
              backgroundColor: "#e2e8f0 !important"
            },
            ".cm-matchingBracket": { color: "#0891b2", fontWeight: "bold" },
            ".cm-tooltip": {
              backgroundColor: "#f8fafc",
              border: "1px solid #e2e8f0",
              color: "#0f172a"
            },
            ".cm-panels": { backgroundColor: "#f8fafc", borderColor: "#e2e8f0" },
            ".cm-searchMatch": { backgroundColor: "rgba(8,145,178,0.15)" },
            ".cm-searchMatch.cm-searchMatch-selected": {
              backgroundColor: "rgba(8,145,178,0.3)"
            },
            ".cm-lintRange-error": {
              backgroundImage: "none",
              textDecoration: "underline wavy #ef4444 1.5px",
              textUnderlineOffset: "3px"
            },
            ".cm-lintRange-warning": {
              backgroundImage: "none",
              textDecoration: "underline wavy #f59e0b 1.5px",
              textUnderlineOffset: "3px"
            },
            ".cm-diagnostic-error": { borderLeft: "3px solid #ef4444" }
          },
          { dark: false }
        );
        const isDark = () => document.documentElement.classList.contains("dark");
        const themeComp = new Compartment();
        const highlightComp = new Compartment();
        const makeTheme = (dark) => dark ? darkTheme : lightTheme;
        const makeHighlight = (dark) => syntaxHighlighting(
          dark ? oneDarkHighlightStyle : defaultHighlightStyle
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
                self2.configRaw = text;
                if (_cm.debounce !== null) clearTimeout(_cm.debounce);
                _cm.debounce = setTimeout(() => {
                  self2.updateFromRaw();
                  _cm.debounce = null;
                }, 500);
                _cm.updating = false;
              }
            })
          ]
        });
        _cm.editor = new EditorView({ state: startState, parent: hostEl });
        const handle = document.createElement("div");
        handle.style.cssText = "height:14px;cursor:ns-resize;display:flex;align-items:center;justify-content:center;flex-shrink:0;";
        const grip = document.createElement("div");
        grip.style.cssText = "width:36px;height:4px;border-radius:2px;background:#334155;transition:background 150ms,width 150ms;pointer-events:none;";
        handle.appendChild(grip);
        handle.addEventListener("mouseenter", () => {
          grip.style.background = "#06b6d4";
          grip.style.width = "52px";
        });
        handle.addEventListener("mouseleave", () => {
          grip.style.background = "#334155";
          grip.style.width = "36px";
        });
        hostEl.insertAdjacentElement("afterend", handle);
        handle.addEventListener("mousedown", (e) => {
          const startY = e.clientY;
          const startH = hostEl.offsetHeight;
          let prevY = startY;
          document.body.style.userSelect = "none";
          document.body.style.cursor = "ns-resize";
          const onMove = (ev) => {
            const dy = ev.clientY - prevY;
            prevY = ev.clientY;
            const newH = Math.max(128, startH + (ev.clientY - startY));
            hostEl.style.height = newH + "px";
            if (dy > 0) window.scrollBy(0, dy);
          };
          const onUp = () => {
            document.body.style.userSelect = "";
            document.body.style.cursor = "";
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
            try {
              localStorage.setItem(
                "mojo:json-editor:height",
                hostEl.style.height
              );
            } catch {
            }
          };
          document.addEventListener("mousemove", onMove);
          document.addEventListener("mouseup", onUp);
          e.preventDefault();
        });
        handle.addEventListener("dblclick", () => {
          const scroller = hostEl.querySelector(
            ".cm-scroller"
          );
          if (scroller) {
            hostEl.style.height = scroller.scrollHeight + "px";
            try {
              localStorage.setItem(
                "mojo:json-editor:height",
                hostEl.style.height
              );
            } catch {
            }
          }
        });
        new MutationObserver(() => {
          const dark = isDark();
          _cm.editor?.dispatch({
            effects: [
              themeComp.reconfigure(makeTheme(dark)),
              highlightComp.reconfigure(makeHighlight(dark))
            ]
          });
        }).observe(document.documentElement, {
          attributes: true,
          attributeFilter: ["class"]
        });
        this.$watch("configRaw", (val) => {
          if (!_cm.updating && _cm.editor) {
            const current = _cm.editor.state.doc.toString();
            if (current !== val) {
              _cm.updating = true;
              _cm.editor.dispatch({
                changes: { from: 0, to: current.length, insert: val }
              });
              _cm.updating = false;
            }
          }
        });
      },
      async resetConfig() {
        const ok = await window.mojoConfirm?.({
          title: "Reset settings",
          message: "Reset plot to factory defaults? This will clear your current view.",
          confirmLabel: "Reset",
          cancelLabel: "Cancel",
          variant: "info"
        });
        if (ok) {
          localStorage.removeItem("mojo_mosaic_config");
          this.config = JSON.parse(JSON.stringify(DEFAULT_CONFIG));
          if (this.columns.includes("time")) this.config.xAxis.col = "time";
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
        this.notify(
          `Exporting ${resW}x${resH} ${format.toUpperCase()}...`,
          "info"
        );
        try {
          const origPaper = el.layout.paper_bgcolor;
          const origPlot = el.layout.plot_bgcolor;
          await Plotly.relayout(el, {
            paper_bgcolor: bgColor,
            plot_bgcolor: bgColor
          });
          const dataUrl = await Plotly.toImage(el, {
            format: plotlyFormat,
            width: 1280,
            height: 720,
            scale
          });
          await Plotly.relayout(el, {
            paper_bgcolor: origPaper,
            plot_bgcolor: origPlot
          });
          const link = document.createElement("a");
          link.href = dataUrl;
          link.download = `${this.trialId}_${resW}p.${format}`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          this.notify(
            `${format.toUpperCase()} saved (${resW}\xD7${resH})`,
            "success"
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
          this.config.xAxis.col,
          ...Object.keys(this.config.yAxes)
        ];
        const rowCount = this.data[this.config.xAxis.col]?.length ?? 0;
        let csv = activeCols.join(",") + "\n";
        for (let i = 0; i < rowCount; i++) {
          csv += activeCols.map((col) => this.data[col]?.[i] ?? "").join(",") + "\n";
        }
        const link = document.createElement("a");
        link.href = URL.createObjectURL(
          new Blob([csv], { type: "text/csv;charset=utf-8;" })
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
            type: "application/json"
          })
        );
        link.setAttribute("download", `${this.trialId}_config.json`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        this.downloadOpen = false;
        this.notify("Configuration JSON Exported", "success");
      },
      handleDrop(e) {
        const file = e.dataTransfer?.files[0];
        if (!file) return;
        if (file.type !== "application/json" && !file.name.endsWith(".json")) {
          this.notify("Please drop a .json file", "error");
          return;
        }
        const reader = new FileReader();
        reader.onload = (event) => {
          try {
            const imported = JSON.parse(
              event.target?.result
            );
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
          const initFilters = this.config.refFrame ? [
            {
              type: "rotation",
              quatCol: this.config.refFrame,
              invert: true,
              enabled: true
            }
          ] : [];
          this.config.yAxes[col] = {
            color: this.getSignalColor(nextIndex),
            label: "",
            width: 3,
            opacity: 1,
            filters: initFilters,
            dash: "solid",
            marker: "none"
          };
          if (!Object.prototype.hasOwnProperty.call(this.data ?? {}, col)) {
            void (async () => {
              try {
                const resp = await this.fetchTrialData(this.trialId, [col]);
                this.data = { ...this.data ?? {}, ...resp.data };
                this.saveAndRender();
              } catch {
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
      applyRefFrame(frame) {
        for (const col of Object.keys(this.config.yAxes)) {
          const yConfig = this.config.yAxes[col];
          if (!yConfig) continue;
          if (frame) {
            const newEntry = {
              type: "rotation",
              quatCol: frame,
              invert: true,
              enabled: true
            };
            const idx = yConfig.filters.findIndex((f) => f.type === "rotation");
            if (idx >= 0) {
              yConfig.filters = [
                ...yConfig.filters.slice(0, idx),
                newEntry,
                ...yConfig.filters.slice(idx + 1)
              ];
            } else {
              yConfig.filters = [newEntry, ...yConfig.filters];
            }
          } else {
            const idx = yConfig.filters.findIndex((f) => f.type === "rotation");
            if (idx >= 0) {
              yConfig.filters = [
                ...yConfig.filters.slice(0, idx),
                ...yConfig.filters.slice(idx + 1)
              ];
            }
          }
        }
      },
      warpToTrial() {
        if (this.warpId === null || this.warpId === void 0 || this.warpId === "")
          return;
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
          marker: obj.marker ?? "none"
        };
      },
      // -----------------------------------------------------------------------
      // Filter stack management
      // -----------------------------------------------------------------------
      getFilterSchema(filterType) {
        return this.filterSchemas.find((s) => s.type === filterType);
      },
      get groupedFilterSchemas() {
        const ORDER = [
          "Smoothing",
          "Arithmetic",
          "Trigonometry",
          "Calculus",
          "Comparison",
          "Bounding",
          "Misc"
        ];
        const groups = {};
        for (const s of this.filterSchemas) {
          const cat = s.category ?? "Misc";
          (groups[cat] ?? (groups[cat] = [])).push(s);
        }
        return ORDER.filter((c) => groups[c]?.length).map((c) => ({
          category: c,
          schemas: groups[c]
        }));
      },
      evalMathExpr(expr) {
        const s = String(expr ?? "").trim();
        if (!s) return null;
        const n = Number(s);
        if (!isNaN(n)) return n;
        try {
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
            `"use strict"; return (${s})`
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
            Math.min
          );
          if (typeof result === "number" && isFinite(result)) return result;
        } catch {
        }
        return null;
      },
      getUnitOptions(groups, fromUnit) {
        if (!groups) return [];
        if (!fromUnit) return groups;
        const match = groups.find((g) => g.units.includes(fromUnit));
        return match ? [match] : groups;
      },
      getFilterSummary(entry) {
        const schema = this.filterSchemas.find((s) => s.type === entry.type);
        if (!schema || schema.params.length === 0) return "";
        if (entry.type === "unit")
          return `${entry["from_unit"] ?? "?"} \u2192 ${entry["to_unit"] ?? "?"}`;
        const parts = schema.params.filter((p) => entry[p.name] != null).map((p) => {
          const val = entry[p.name];
          if (typeof val === "boolean")
            return `${p.name}=${val ? "on" : "off"}`;
          if (typeof val === "number")
            return `${p.name}=${parseFloat(val.toFixed(4))}`;
          return `${p.name}=${val}`;
        });
        return parts.slice(0, 3).join(", ");
      },
      addFilterToTemp(temp, filterType) {
        const schema = this.filterSchemas.find((s) => s.type === filterType);
        if (!schema) return;
        if (!temp.filters) temp.filters = [];
        if (filterType === "rotation" && temp.filters.some((f) => f.type === "rotation"))
          return;
        const entry = { type: filterType, enabled: true };
        for (const p of schema.params) {
          entry[p.name] = p.default;
        }
        temp.filters.push(entry);
      },
      removeFilterFromTemp(temp, index) {
        if (!temp.filters) return;
        temp.filters.splice(index, 1);
      },
      moveFilterInTemp(temp, index, direction) {
        if (!temp.filters) return;
        const newIdx = index + direction;
        if (newIdx < 0 || newIdx >= temp.filters.length) return;
        const [item] = temp.filters.splice(index, 1);
        if (item) temp.filters.splice(newIdx, 0, item);
      },
      setFilterParamOnTemp(temp, filterIndex, paramName, value) {
        if (!temp.filters?.[filterIndex]) return;
        temp.filters[filterIndex][paramName] = value;
      },
      duplicateFilterInTemp(temp, index) {
        if (!temp.filters?.[index]) return;
        const copy = JSON.parse(
          JSON.stringify(temp.filters[index])
        );
        temp.filters.splice(index + 1, 0, copy);
      },
      // -----------------------------------------------------------------------
      // Profiles
      // Encode each path segment individually so 'project/name' becomes 'project/name'
      // in the URL (not 'project%2Fname'), matching the {name:path} FastAPI route.
      _profileUrl(name) {
        return `/mosaic/api/profiles/${name.split("/").map(encodeURIComponent).join("/")}`;
      },
      // ── Lab ──────────────────────────────────────────────────────────────────
      relTime(ms) {
        const diff = Date.now() - ms;
        const min = Math.floor(diff / 6e4);
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
          const all = await resp.json();
          const schemas = all.map((lab) => ({
            ...lab,
            signal_in_columns: [...new Set(lab.signal_in_columns)].sort(),
            outputs: [...new Set(lab.outputs)].sort(),
            is_template: lab.is_template ?? false,
            template_inputs: lab.template_inputs ?? [],
            template_outputs: lab.template_outputs ?? []
          }));
          const baseColumns = this.columns.filter((c) => !c.startsWith("Lab/"));
          const available = new Set(baseColumns);
          const validLabs = /* @__PURE__ */ new Set();
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
            valid: validLabs.has(lab.name)
          }));
          this.columns = [...available].sort();
        } catch {
        }
      },
      async refreshLabValidation() {
        await this.loadLabSchemas();
        void this.loadProfiles();
      },
      // ── tab helpers ──────────────────────────────────────────────────────────
      _tabId() {
        return `t${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
      },
      _initTabs() {
        try {
          const raw = localStorage.getItem("mojo:lab:tabs");
          if (raw) {
            const tabs = JSON.parse(raw);
            if (Array.isArray(tabs) && tabs.length > 0) {
              this.labTabs = tabs;
              const activeId = localStorage.getItem("mojo:lab:activeTab") ?? "";
              this.labActiveTabId = tabs.find((t) => t.id === activeId)?.id ?? tabs[0].id;
              const active = this.labTabs.find(
                (t) => t.id === this.labActiveTabId
              );
              this.labName = active.name;
              this.labGraph = active.graph;
              return;
            }
          }
        } catch {
        }
        const name = localStorage.getItem("mojo:lab:name") ?? "";
        const graph = (() => {
          try {
            const s = localStorage.getItem("mojo:lab:draft");
            return s ? JSON.parse(s) : null;
          } catch {
            return null;
          }
        })();
        const id = this._tabId();
        this.labTabs = [{ id, name, graph, savedState: null, dirty: false, viewport: null }];
        this.labActiveTabId = id;
        this.labName = name;
        this.labGraph = graph;
      },
      _snapshotActiveTab() {
        if (!this.labActiveTabId) return;
        const tab = this.labTabs.find((t) => t.id === this.labActiveTabId);
        if (!tab) return;
        window.mojoLabFlushSnapshot?.();
        tab.graph = window.mojoLabSerialize?.() ?? tab.graph;
        tab.name = this.labName;
        tab.viewport = window.mojoLabGetViewport?.() ?? tab.viewport;
        this.labGraph = tab.graph;
      },
      _persistTabs() {
        try {
          localStorage.setItem("mojo:lab:tabs", JSON.stringify(this.labTabs));
          localStorage.setItem("mojo:lab:activeTab", this.labActiveTabId ?? "");
        } catch {
        }
      },
      _saveTabs() {
        this._snapshotActiveTab();
        this._persistTabs();
      },
      async _activateTab(tabId) {
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
      async switchTab(tabId) {
        if (tabId === this.labActiveTabId) return;
        this._snapshotActiveTab();
        await this._activateTab(tabId);
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
          dirty: false
        });
        await this._activateTab(id);
        this._persistTabs();
      },
      async closeTab(tabId) {
        const tabIdx = this.labTabs.findIndex((t) => t.id === tabId);
        if (tabIdx === -1) return;
        const tab = this.labTabs[tabIdx];
        if (tabId === this.labActiveTabId) this._snapshotActiveTab();
        const isDirty = tabId === this.labActiveTabId ? window.mojoLabHasUnsavedChanges?.() ?? false : tab.dirty;
        if (isDirty) {
          const ok = await window.mojoConfirm?.({
            title: "Unsaved changes",
            message: tab.name ? `Close "${tab.name}" and discard unsaved changes?` : "Close this tab and discard unsaved changes?",
            confirmLabel: "Close",
            cancelLabel: "Keep editing",
            variant: "warning"
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
            dirty: false
          });
          await this._activateTab(newId);
        } else if (tabId === this.labActiveTabId) {
          const newActive = this.labTabs[Math.min(tabIdx, this.labTabs.length - 1)];
          await this._activateTab(newActive.id);
        }
        this._persistTabs();
      },
      async loadLabInNewTab(labName) {
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
          const graph = await resp.json();
          const activeTab = this.labTabs.find(
            (t) => t.id === this.labActiveTabId
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
              dirty: false
            });
            await this._activateTab(id);
          }
          this._persistTabs();
        } catch (err) {
          this.notify(`Failed to load "${labName}": ${String(err)}`, "error");
        }
      },
      async saveLabGraph(name, graph) {
        const trimmed = name.trim();
        if (!trimmed) return;
        const exists = this.labSchemas.some((s) => s.name === trimmed);
        if (exists) {
          const ok = await window.mojoConfirm?.({
            title: "Overwrite lab",
            message: `"${trimmed}" already exists. Replace it with the current graph?`,
            confirmLabel: "Overwrite",
            cancelLabel: "Cancel",
            variant: "warning"
          });
          if (!ok) return;
        }
        const safePath = trimmed.split("/").map(encodeURIComponent).join("/");
        try {
          const resp = await fetch(`/mosaic/api/lab/${safePath}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(graph)
          });
          if (!resp.ok) {
            const detail = await resp.text().catch(() => resp.statusText);
            this.notify(`Save failed: ${detail}`, "error");
            return;
          }
          this.notify(`Lab "${trimmed}" saved`, "success");
          window.mojoLabRebaseline?.();
          this.labName = trimmed;
          const activeTab = this.labTabs.find(
            (t) => t.id === this.labActiveTabId
          );
          if (activeTab) {
            activeTab.name = trimmed;
            activeTab.dirty = false;
          }
          this._saveTabs();
          await this.refreshLabValidation();
          const dependents = /* @__PURE__ */ new Map();
          for (const lab of this.labSchemas) {
            for (const col of lab.signal_in_columns) {
              if (col.startsWith("Lab/")) {
                const depRest = col.slice(4);
                const depSplitIdx = depRest.lastIndexOf("/");
                const src = depSplitIdx >= 0 ? depRest.slice(0, depSplitIdx) : "";
                if (src) {
                  if (!dependents.has(src)) dependents.set(src, []);
                  dependents.get(src).push(lab.name);
                }
              }
            }
          }
          const toInvalidate = /* @__PURE__ */ new Set([trimmed]);
          const bfsQueue = [trimmed];
          while (bfsQueue.length > 0) {
            const cur = bfsQueue.shift();
            for (const dep of dependents.get(cur) ?? []) {
              if (!toInvalidate.has(dep)) {
                toInvalidate.add(dep);
                bfsQueue.push(dep);
              }
            }
          }
          const newData = { ...this.data ?? {} };
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
          const activeCols = [
            ...Object.keys(this.config.yAxes),
            this.config.xAxis?.col ?? ""
          ].filter((c) => {
            for (const labName of toInvalidate) {
              if (c.startsWith(`Lab/${labName}/`) && !Object.prototype.hasOwnProperty.call(this.data ?? {}, c))
                return true;
            }
            return false;
          });
          if (activeCols.length > 0) {
            try {
              const refetch = await this.fetchTrialData(this.trialId, activeCols);
              this.data = { ...this.data ?? {}, ...refetch.data };
              this.saveAndRender();
            } catch {
            }
          }
        } catch (err) {
          this.notify(`Save failed: ${String(err)}`, "error");
        }
      },
      selectNodeColumn(col) {
        if (this.nodePickingColumn !== null) {
          if (typeof window.mojoLabSelectNodeColumn === "function") {
            window.mojoLabSelectNodeColumn(this.nodePickingColumn, col);
          }
        }
        this.nodePickingColumn = null;
        this.nodeColSearch = "";
      },
      selectNodeQuat(base) {
        if (this.nodePickingQuat !== null) {
          if (typeof window.mojoLabSelectNodeQuat === "function") {
            window.mojoLabSelectNodeQuat(this.nodePickingQuat, base);
          }
        }
        this.nodePickingQuat = null;
        this.nodeQuatSearch = "";
      },
      selectNodeTemplate(name) {
        if (this.nodePickingTemplate !== null) {
          if (typeof window.mojoLabSelectNodeTemplate === "function") {
            window.mojoLabSelectNodeTemplate(this.nodePickingTemplate, name);
          }
        }
        this.nodePickingTemplate = null;
      },
      async deleteLabGraph(name) {
        const safePath = name.split("/").map(encodeURIComponent).join("/");
        await fetch(`/mosaic/api/lab/${safePath}`, {
          method: "DELETE"
        });
        this.notify(`Lab "${name}" deleted`, "info");
        await this.refreshLabValidation();
      },
      // -----------------------------------------------------------------------
      async loadProfiles() {
        try {
          const resp = await fetch("/mosaic/api/profiles");
          this.profiles = await resp.json();
          const colSet = new Set(this.columns);
          const frames = new Set(
            this.columns.filter((c) => c.endsWith(":w")).map((c) => c.replace(":w", ""))
          );
          const warnings = {};
          await Promise.all(
            this.profiles.map(async (p) => {
              try {
                const pr = await fetch(this._profileUrl(p.name));
                if (!pr.ok) return;
                const cfg = await pr.json();
                const w = [];
                if (cfg.xAxis?.col && !colSet.has(cfg.xAxis.col))
                  w.push(`x-axis "${cfg.xAxis.col}"`);
                for (const key of Object.keys(cfg.yAxes ?? {})) {
                  if (!colSet.has(key)) w.push(`"${key}"`);
                }
                if (cfg.refFrame && !frames.has(cfg.refFrame))
                  w.push(`frame "${cfg.refFrame}"`);
                if (w.length) warnings[p.name] = w;
              } catch {
              }
            })
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
        const normalise = (s) => s.toLowerCase().replace(/\s+/g, "_");
        const existing = this.profiles.find(
          (p) => normalise(p.name) === normalise(name)
        );
        if (existing) {
          const ok = await window.mojoConfirm?.({
            title: "Overwrite profile",
            message: `"${existing.name}" already exists. Replace it with the current configuration?`,
            confirmLabel: "Overwrite",
            cancelLabel: "Cancel",
            variant: "warning"
          });
          if (!ok) return;
        }
        try {
          const resp = await fetch(this._profileUrl(name), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(this.config)
          });
          if (!resp.ok) throw new Error("Save failed");
          const result = await resp.json();
          this.profileNameDraft = "";
          await this.loadProfiles();
          this.notify(`Profile "${result.name}" saved`, "success");
        } catch {
          this.notify("Failed to save profile", "error");
        }
      },
      async loadProfile(name) {
        try {
          const resp = await fetch(this._profileUrl(name));
          if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            throw new Error(body.detail ?? `HTTP ${resp.status}`);
          }
          const loaded = await resp.json();
          const colSet = new Set(this.columns);
          const frames = new Set(
            this.columns.filter((c) => c.endsWith(":w")).map((c) => c.replace(":w", ""))
          );
          const missing = [];
          if (loaded.xAxis?.col && !loaded.xAxis.col.startsWith("Lab/") && !colSet.has(loaded.xAxis.col))
            missing.push(`x-axis "${loaded.xAxis.col}"`);
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
              "info"
            );
          } else {
            this.notify(`Profile "${name}" loaded`, "success");
          }
          const needed = [];
          if (loaded.xAxis?.col && !this.data?.[loaded.xAxis.col])
            needed.push(loaded.xAxis.col);
          for (const col of Object.keys(loaded.yAxes ?? {})) {
            if (!this.data?.[col]) needed.push(col);
          }
          if (needed.length > 0) {
            const fetched = await this.fetchTrialData(this.trialId, needed);
            this.data = { ...this.data ?? {}, ...fetched.data };
          }
          void this.$nextTick(() => {
            this.configErrors = this.validateConfig(this.config);
            this.isValidConfig = this.configErrors.length === 0;
            this.isValidJson = true;
            this.saveAndRender();
          });
        } catch (e) {
          this.notify(
            `Failed to load "${name}": ${e.message}`,
            "error"
          );
        }
      },
      async deleteProfile(name) {
        const ok = await window.mojoConfirm?.({
          title: "Delete profile",
          message: `Delete "${name}"? This cannot be undone.`,
          confirmLabel: "Delete",
          cancelLabel: "Cancel",
          variant: "danger"
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
      applySignalConfig(col, temp) {
        this.config.yAxes[col] = JSON.parse(JSON.stringify(temp));
        delete this.signalDrafts[col];
      },
      getDraft(col) {
        return this.signalDrafts[col] ?? null;
      },
      saveDraft(col, draft, baseSnapshot) {
        this.signalDrafts[col] = { draft, baseSnapshot };
      },
      clearDraft(col) {
        delete this.signalDrafts[col];
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
      // reads the manual x/y axis min/max fields as strings for display; empty means autoscale
      rangeBoundValue(axis, bound) {
        const range = axis === "x" ? this.config.rangeX : this.config.rangeY;
        if (!range) return "";
        const val = bound === "min" ? range[0] : range[1];
        return val === null ? "" : String(val);
      },
      // sets a single x/y axis min/max field; an empty value reverts that side to autoscale
      setRangeBound(axis, bound, value) {
        const trimmed = value.trim();
        const num = trimmed === "" ? null : this.evalMathExpr(trimmed);
        if (trimmed !== "" && num === null) return;
        const current = (axis === "x" ? this.config.rangeX : this.config.rangeY) ?? [null, null];
        const next = bound === "min" ? [num, current[1]] : [current[0], num];
        const resolved = next[0] === null && next[1] === null ? null : next;
        if (axis === "x") this.config.rangeX = resolved;
        else this.config.rangeY = resolved;
        void this.saveAndRender();
      },
      // resolves a possibly-partial axis range into a concrete [min, max], falling back
      // to the padded data range for whichever side is unset
      resolveAxisRange(configRange, keys) {
        if (!configRange || configRange[0] === null && configRange[1] === null)
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
        const plotEl = document.getElementById("plot-area");
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
          if (event["xaxis.range[0]"] !== void 0) {
            this.config.rangeX = [
              event["xaxis.range[0]"],
              event["xaxis.range[1]"]
            ];
          }
          if (event["yaxis.range[0]"] !== void 0) {
            this.config.rangeY = [
              event["yaxis.range[0]"],
              event["yaxis.range[1]"]
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
        const showX = this.config.showSpike && !isHoverDisabled && (this.config.hover.includes("x") || this.config.hover === "closest");
        const showY = this.config.showSpike && !isHoverDisabled && (this.config.hover.includes("y") || this.config.hover === "closest");
        const isPolar = this.config.plotType === "polar";
        const yKeys = Object.keys(this.config.yAxes);
        let traces = yKeys.map((key, i) => {
          const p = this.getYProps(key, i);
          if (!this.data[p.name]) {
            return null;
          }
          const lineStyle = {
            width: p.width,
            color: p.color,
            shape: this.config.interp,
            dash: p.dash
          };
          if (isPolar) {
            return {
              r: this.data[p.name],
              theta: this.data[this.config.xAxis.col],
              name: p.label,
              mode: this.config.lineMode,
              type: "scatterpolar",
              line: lineStyle,
              marker: { size: 6, symbol: p.marker },
              opacity: p.opacity,
              hoverlabel: {
                namelength: -1,
                bgcolor: tooltipBg,
                bordercolor: tooltipBorder,
                font: { family: "monospace", size: 12, color: tooltipFont }
              },
              hovertemplate: `<b>${key}</b><br>\u03B8: %{theta:.4f}<br>r: %{r:.4f}<extra></extra>`
            };
          }
          return {
            x: this.data[this.config.xAxis.col],
            y: this.data[p.name],
            name: p.label,
            mode: this.config.lineMode,
            type: "scatter",
            line: lineStyle,
            marker: { size: 6, symbol: p.marker },
            opacity: p.opacity,
            hoverlabel: {
              namelength: -1,
              bgcolor: tooltipBg,
              bordercolor: tooltipBorder,
              font: { family: "monospace", size: 12, color: tooltipFont }
            },
            hovertemplate: `<b>${key}</b><br>%{x}: %{y:.4f}<extra></extra>`
          };
        }).filter((t) => t !== null);
        if (this.config.vsEnabled) {
          const [start, end] = this.config.vsRange;
          const legendTracker = /* @__PURE__ */ new Set();
          const sortedVsIds = Object.keys(this.vsDatasets).sort(
            (a, b) => parseInt(a.split("_").pop() ?? "0") - parseInt(b.split("_").pop() ?? "0")
          );
          sortedVsIds.forEach((vsId) => {
            const n = parseInt(vsId.split("_").pop() ?? "");
            if (n < start || n > end || vsId === this.trialId) return;
            const dataset = this.vsDatasets[vsId];
            if (!dataset) return;
            const vsTraces = yKeys.map((key, i) => {
              const p = this.getYProps(key, i);
              if (!dataset[p.name]) return null;
              const isFirst = !legendTracker.has(key);
              const lineStyle = {
                width: 1,
                color: p.color,
                shape: this.config.interp,
                dash: "dot"
              };
              const t = isPolar ? {
                r: dataset[p.name],
                theta: dataset[this.config.xAxis.col],
                name: `${p.label} (<i>vs.</i>)`,
                legendgroup: `group_${key}`,
                showlegend: isFirst,
                mode: this.config.lineMode,
                type: "scatterpolar",
                line: lineStyle,
                opacity: 0.35,
                marker: { size: 4, symbol: p.marker },
                hoverlabel: { namelength: -1 },
                hovertemplate: `<b>${key}</b> (#${n})<br>\u03B8: %{theta:.4f}<br>r: %{r:.4f}<extra></extra>`
              } : {
                x: dataset[this.config.xAxis.col],
                y: dataset[p.name],
                name: `${p.label} (<i>vs.</i>)`,
                legendgroup: `group_${key}`,
                showlegend: isFirst,
                mode: this.config.lineMode,
                type: "scatter",
                line: lineStyle,
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
        const resolvedRangeX = this.resolveAxisRange(this.config.rangeX, [
          this.config.xAxis.col
        ]);
        const xAxisObj = {
          type: this.config.xScale ?? "linear",
          ...resolvedRangeX ? {
            autorange: false,
            range: this.config.xScale === "log" ? [
              Math.log10(Math.max(1e-6, resolvedRangeX[0])),
              Math.log10(Math.max(1e-6, resolvedRangeX[1]))
            ] : resolvedRangeX
          } : { autorange: true },
          dtick: this.config.xScale === "log" && this.config.xLogBase ? Math.log10(this.config.xLogBase) : void 0,
          gridcolor: majorGrid,
          showgrid: this.config.grid !== "none",
          minor: { showgrid: this.config.grid === "all", gridcolor: minorGrid },
          zeroline: false,
          tickfont: { color: textColor, size: 14 },
          title: {
            text: this.config.xAxisTitle || this.config.xAxis.col,
            font: { size: 14, color: textColor, family: "monospace" }
          },
          showspikes: showX,
          spikemode: "across",
          spikelinecolor: spikeColor,
          spikethickness: -2
        };
        const frameLabel = this.config.refFrame ? `<br><span style="color: ${textColor}; font-size: 14px; opacity: 0.6;">[Frame: ${this.config.refFrame}]</span>` : "";
        const resolvedRangeY = this.resolveAxisRange(
          this.config.rangeY,
          Object.keys(this.config.yAxes)
        );
        const yAxisObj = {
          type: this.config.yScale ?? "linear",
          ...resolvedRangeY ? {
            autorange: false,
            range: this.config.yScale === "log" ? [
              Math.log10(Math.max(1e-6, resolvedRangeY[0])),
              Math.log10(Math.max(1e-6, resolvedRangeY[1]))
            ] : resolvedRangeY
          } : { autorange: true },
          dtick: this.config.yScale === "log" && this.config.yLogBase ? Math.log10(this.config.yLogBase) : void 0,
          gridcolor: majorGrid,
          showgrid: this.config.grid !== "none",
          minor: { showgrid: this.config.grid === "all", gridcolor: minorGrid },
          zeroline: false,
          tickfont: { color: textColor, size: 14 },
          title: {
            text: this.config.yAxisTitle + frameLabel,
            font: { size: 14, color: textColor, family: "monospace" }
          },
          showspikes: showY,
          spikemode: "across",
          spikelinecolor: spikeColor,
          spikethickness: -2
        };
        const polarLayout = isPolar ? {
          polar: {
            bgcolor: "rgba(0,0,0,0)",
            radialaxis: {
              color: textColor,
              gridcolor: majorGrid,
              tickfont: { color: textColor, size: 14, family: "monospace" },
              title: {
                text: this.config.yAxisTitle || "r",
                font: { size: 14, color: textColor, family: "monospace" }
              }
            },
            angularaxis: {
              color: textColor,
              gridcolor: majorGrid,
              tickfont: { color: textColor, size: 14, family: "monospace" },
              title: {
                text: this.config.xAxisTitle || this.config.xAxis.col,
                font: { size: 14, color: textColor, family: "monospace" }
              }
            }
          }
        } : { xaxis: xAxisObj, yaxis: yAxisObj };
        const layout = {
          uirevision: `${this.trialId}_${this.config.xAxis.col}_${Object.keys(this.config.yAxes).join("_")}_${this.config.plotType}`,
          title: this.config.title ? {
            text: this.config.title,
            font: {
              family: "monospace",
              size: 16,
              color: isDark ? tw.slate[200] : tw.slate[800],
              weight: "bold"
            },
            x: 0,
            xanchor: "left"
          } : null,
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          margin: {
            t: this.config.title ? 60 : 30,
            r: this.config.legendPos === "right" ? 150 : 30,
            b: this.config.legendPos === "bottom" ? 80 : 50,
            l: this.config.yAxisTitle ? 80 : 60
          },
          hovermode: isHoverDisabled ? false : this.config.hover,
          hoverlabel: {
            bgcolor: tooltipBg,
            bordercolor: tooltipBorder,
            font: { family: "monospace", size: 12, color: tooltipFont },
            align: "left"
          },
          showlegend: this.config.legendPos !== "hidden",
          legend: this.config.legendPos === "right" ? {
            orientation: "v",
            x: 1.02,
            y: 1,
            font: { family: "monospace", size: 14, color: textColor },
            groupclick: "togglegroup"
          } : {
            orientation: "h",
            y: -0.2,
            x: 0.5,
            xanchor: "center",
            font: { family: "monospace", size: 14, color: textColor },
            groupclick: "togglegroup"
          },
          ...polarLayout,
          annotations: isPolar ? [] : [
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
                color: isDark ? tw.slate[50] : tw.slate[900]
              },
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
                  family: "monospace"
                },
                bgcolor: isDark ? tw.slate[900] + "B3" : tw.slate[50] + "B3",
                borderpad: 2
              };
            })
          ],
          shapes: isPolar ? [] : (this.config.shapes ?? []).map((s) => {
            const shapeColor = s.color || tw.cyan[500];
            const base = {
              line: { color: shapeColor, width: 2, dash: s.dash ?? "solid" },
              layer: "below"
            };
            if (s.type === "vline")
              return {
                ...base,
                type: "line",
                x0: s.x0,
                x1: s.x0,
                y0: 0,
                y1: 1,
                yref: "paper"
              };
            if (s.type === "hline")
              return {
                ...base,
                type: "line",
                y0: s.y0,
                y1: s.y0,
                x0: 0,
                x1: 1,
                xref: "paper"
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
                line: { ...base.line, width: 1 }
              };
            return base;
          })
        };
        const config = {
          responsive: true,
          displaylogo: false,
          displayModeBar: true,
          modeBarButtonsToRemove: ["toImage"],
          doubleClick: false
        };
        const plotEl = document.getElementById("plot-area");
        if (plotEl && this._renderedPlotType !== this.config.plotType) {
          Plotly.purge(plotEl);
          this._renderedPlotType = this.config.plotType ?? null;
          return Plotly.newPlot("plot-area", traces, layout, config).then(
            () => this._attachPlotEventHandlers()
          );
        }
        return Plotly.react("plot-area", traces, layout, config);
      }
    };
    return self;
  }
  window.trialViewer = trialViewer;
})();
//# sourceMappingURL=trial-viewer.js.map
