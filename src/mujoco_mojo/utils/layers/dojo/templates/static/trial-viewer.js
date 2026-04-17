/**
 * TAILWIND OFFLINE PALETTE
 * Formalized hex values extracted from Tailwind CSS defaults.
 */
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
  cyan: {
    400: "#22d3ee",
    500: "#06b6d4",
    600: "#0891b2",
  },
  emerald: { 500: "#10b981" },
  blue: { 500: "#3b82f6" },
  violet: { 500: "#8b5cf6" },
  amber: { 500: "#f59e0b" },
  rose: { 500: "#ef4444" },
};

const DEFAULT_CONFIG = {
  xAxis: "time",
  yAxes: {}, // Key: signal name, Value: { label, color, width, etc. }
  refFrame: null,
  grid: "all",
  linemode: "lines", // Renamed from markerMode for clarity
  interp: "linear", // line interpolation (linear, spline, etc)
  hover: "closest", // "x unified", "y unified", "closest", "x", "y", "none"
  title: "",
  xAxisTitle: "",
  yAxisTitle: "",
  showSpike: true,
  legendPos: "bottom", // "bottom", "right", "hidden"
  rangeX: null,
  rangeY: null,
  xScale: "linear",
  yScale: "linear",
  vsEnabled: false,
  vsRange: [0, 10],
  annotations: [], // Stores { x, y, text }
  shapes: [], // Stores { type, x0, x1, y0, y1, label }
};

/**
 * trialViewer - Alpine.js Component
 * Handles telemetry data retrieval, Plotly rendering, and JSON configuration state.
 */
function trialViewer(trialId, externalUrl) {
  return {
    // --- BASE STATE ---
    trialId: trialId,
    externalUrl: externalUrl,
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
    dragCounter: 0, // tracks if a file is being hovered over the page
    editorOpen: false, // Controls the visibility of the JSON editor drawer
    columns: [],
    rotateableVectors: [],
    showToast: false,
    toastMessage: "",
    toastType: "success",
    discoveryId: 0,
    plotColors: [
      tw.cyan[500],
      tw.emerald[500],
      tw.blue[500],
      tw.violet[500],
      tw.amber[500],
      tw.rose[500],
    ],

    // --- SINGLE SOURCE OF TRUTH: PLOT CONFIGURATION ---
    // This object is the master state. Changes here trigger re-renders.
    config: JSON.parse(JSON.stringify(DEFAULT_CONFIG)), // deep clone the default config

    // --- JSON EDITOR STATE ---
    configRaw: "", // Pretty-printed string for the <textarea>
    isValidJson: true, // Tracks if the user's manual JSON input is valid
    isValidConfig: true, // Tracks logical correctness
    configErrors: [], // List of specific error strings
    isEditingRaw: false, // Guard to prevent auto-format loop

    // --- MATCHUP STATE ---
    vsDatasets: {}, // map of trial_id -> data object
    allTrials: [], // full list from /mosaic/api/trials
    vsMenuOpen: false,
    vsLoading: false,
    vsDraft: {
      enabled: false,
      range: [0, 0],
    },

    // --- HISTORY STATE ---
    historyStack: [],
    historyIndex: -1,
    isUndoing: false, // Flag to prevent watcher from capturing history during undo/redo
    maxHistory: 50,

    // --- ANNOTATIONS ---
    annotationsOpen: false,
    annDraft: null, // Holds { x, y, text } while typing
    annEditIndex: null,

    // --- SHAPES ---
    shapesOpen: false,
    placementMode: null, // 'vline', 'hline', 'rect'
    rectStart: null, // To store the first click of a rectangle
    shapeDraft: null,
    shapeEditIndex: null,

    pushHistory() {
      if (this.isUndoing) return;

      const snapshot = JSON.stringify(this.config);

      // If the state is identical to the current head, don't push
      if (this.historyStack[this.historyIndex] === snapshot) return;

      // Wipe any "redo" future if we make a new change
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
        this.config = JSON.parse(this.historyStack[this.historyIndex]);
        this.persistHistory();
        this.$nextTick(() => {
          this.isUndoing = false;
        });
        this.notify("Undo", "info");
      }
    },

    redo() {
      if (this.historyIndex < this.historyStack.length - 1) {
        this.isUndoing = true;
        this.historyIndex++;
        this.config = JSON.parse(this.historyStack[this.historyIndex]);
        this.persistHistory();
        this.$nextTick(() => {
          this.isUndoing = false;
        });
        this.notify("Redo", "info");
      }
    },

    persistHistory() {
      const bundle = {
        stack: this.historyStack,
        index: this.historyIndex,
      };
      localStorage.setItem("mojo_mosaic_history", JSON.stringify(bundle));
    },

    shiftY(index, direction, isWarp = false) {
      const keys = Object.keys(this.config.yAxes);
      if (keys.length < 2) return;

      let newKeys = [...keys];
      const movedKey = newKeys.splice(index, 1)[0];

      if (isWarp) {
        direction === -1 ? newKeys.unshift(movedKey) : newKeys.push(movedKey);
      } else {
        newKeys.splice(index + direction, 0, movedKey);
      }

      // Reconstruct the object to enforce the new insertion order
      const newYAxes = {};
      newKeys.forEach((k) => {
        newYAxes[k] = this.config.yAxes[k];
      });
      this.config.yAxes = newYAxes;

      this.saveAndRender();
    },

    async fetchTrialData(id, requiredCols = []) {
      console.debug(`loading ${id} (cols: ${requiredCols.join(",") || "all"})`);

      // Construct query param for columns
      let url = `/mosaic/${id}/data`;
      const colParams = new URLSearchParams();

      if (requiredCols.length > 0) {
        colParams.append("cols", requiredCols.join(","));
      }

      if (this.config.refFrame) {
        colParams.append("rotate_by", this.config.refFrame);
      }

      const queryStr = colParams.toString();
      if (queryStr) url += `?${queryStr}`;

      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`Trial ${id} failed`);

      return await resp.json();
    },

    /**
     * Helper to fetch in small chunks to keep the pipe clear
     */
    async trickleFetch(id, columnList, label, isVsDataset, loopId) {
      const CHUNK_SIZE = 10;
      for (let i = 0; i < columnList.length; i += CHUNK_SIZE) {
        // --- THE SAFETY CHECK ---
        // If a new discovery task started while we were waiting, exit now.
        if (loopId !== this.discoveryId) return;

        await new Promise((r) => setTimeout(r, 50));
        const chunk = columnList.slice(i, i + CHUNK_SIZE);

        try {
          const resp = await this.fetchTrialData(id, chunk);

          if (isVsDataset) {
            this.vsDatasets[id] = {
              ...(this.vsDatasets[id] || {}),
              ...resp.data,
            };
            this.vsDatasets = { ...this.vsDatasets };
          } else {
            this.data = { ...(this.data || {}), ...resp.data };
          }

          if (Object.keys(this.config.yAxes).some((y) => chunk.includes(y))) {
            this.renderPlot();
          }

          console.debug(
            `Dojo Hydration [${label}]: ${i + chunk.length}/${columnList.length}`,
          );
        } catch (e) {
          console.warn(`Hydration failed for ${id}`, e);
        }
      }
    },

    /**
     * Loads data as a background process to fill the cache
     */
    async startBackgroundDiscovery() {
      // Create a unique ID for this specific "worker" run
      const currentId = ++this.discoveryId;

      // 1. HORIZONTAL: Current Trial
      const pendingCols = this.columns.filter(
        (c) => !this.data.hasOwnProperty(c),
      );
      if (pendingCols.length > 0) {
        await this.trickleFetch(
          this.trialId,
          pendingCols,
          "Current",
          false,
          currentId,
        );
      }

      // 2. VERTICAL: vsDraft Range
      if (currentId !== this.discoveryId) return; // Exit if superseded

      const start = Math.min(this.vsDraft.range[0], this.vsDraft.range[1]);
      const end = Math.max(this.vsDraft.range[0], this.vsDraft.range[1]);
      const activeCols = [this.config.xAxis, ...Object.keys(this.config.yAxes)];

      const draftIds = this.allTrials.filter((id) => {
        const n = parseInt(id.split("_").pop());
        return n >= start && n <= end && id !== this.trialId;
      });

      for (const id of draftIds) {
        // Check again before starting a new fetch
        if (currentId !== this.discoveryId) return;

        const existing = this.vsDatasets[id];
        const needsFetch =
          !existing || activeCols.some((c) => !existing.hasOwnProperty(c));

        if (needsFetch) {
          await this.trickleFetch(
            id,
            activeCols,
            `Draft ${id}`,
            true,
            currentId,
          );
        }
      }
    },

    setPlacementMode(type) {
      this.placementMode = type;
      this.rectStart = null;
      this.shapeDraft = null; // Clear any existing draft if starting a new placement

      const label =
        type === "vline"
          ? "Vertical Line"
          : type === "hline"
            ? "Horizontal Line"
            : "Area Rectangle";

      this.notify(`Mode: ${label}. Click plot to place.`, "info");
    },

    deleteShape(index) {
      this.config.shapes.splice(index, 1);
      this.saveAndRender();
    },

    /**
     * Handle Shape Creation inside plotly_click listener
     */
    handlePlotClickForShapes(pt) {
      if (!this.placementMode) return false;
      const defaultColor = tw.cyan[500];

      let newShape = null;
      if (this.placementMode === "vline") {
        newShape = { type: "vline", x0: pt.x, color: defaultColor, label: "" };
      } else if (this.placementMode === "hline") {
        newShape = { type: "hline", y0: pt.y, color: defaultColor, label: "" };
      } else if (this.placementMode === "rect") {
        if (!this.rectStart) {
          this.rectStart = { x: pt.x, y: pt.y };
          return true; // Wait for second click
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
        if (!this.config.shapes) this.config.shapes = [];
        this.config.shapes.push(newShape); // Push directly to list
        this.placementMode = null; // Close placement mode
        this.saveAndRender(); // Update plot immediately
      }
      return true;
    },

    saveShape() {
      if (!this.config.shapes) this.config.shapes = [];
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
      // If they were in the middle of a rectangle, reset that too
      this.rectStart = null;
    },

    saveAnnotation() {
      if (!this.annDraft || !this.annDraft.text.trim()) return;

      if (this.annEditIndex !== null) {
        // Update existing
        this.config.annotations[this.annEditIndex] = { ...this.annDraft };
      } else {
        // Create new
        if (!this.config.annotations) this.config.annotations = [];
        this.config.annotations.push({ ...this.annDraft });
      }

      this.cancelAnnDraft();
      this.saveAndRender();
    },

    startAnnEdit(index) {
      this.annEditIndex = index;
      this.annDraft = { ...this.config.annotations[index] };
      this.$nextTick(() => this.$refs.annInput?.focus());
    },

    cancelAnnDraft() {
      this.annDraft = null;
      this.annEditIndex = null;
    },

    /**
     * Pokes the plot to center on the note's timestamp
     */
    jumpToAnnotation(ann) {
      const el = document.getElementById("plot-area");
      if (!el || !this.data) return;

      // 1. CALCULATE X (TIME) WINDOW
      const xValues = this.data[this.config.xAxis] || [];
      const xMin = xValues[0] || 0;
      const xMax = xValues[xValues.length - 1] || 100;

      // We'll show a 10% slice of the total trial duration
      const xSpan = (xMax - xMin) * 0.1;
      let newRangeX = [ann.x - xSpan / 2, ann.x + xSpan / 2];

      // Clamp X so we don't zoom past the start/end of the data
      if (newRangeX[0] < xMin) {
        newRangeX[1] += xMin - newRangeX[0];
        newRangeX[0] = xMin;
      }
      if (newRangeX[1] > xMax) {
        newRangeX[0] -= newRangeX[1] - xMax;
        newRangeX[1] = xMax;
      }

      // 2. CALCULATE Y (VALUE) WINDOW
      // We use the full padded range of your active signals to find a 'reasonable' scale
      const fullY = this.calculatePaddedRange(
        Object.keys(this.config.yAxes),
        false,
      );
      const yTotalHeight = Math.abs(fullY[1] - fullY[0]);

      // We'll show a 20% vertical slice centered on the point
      const ySpan = yTotalHeight * 0.2;
      const newRangeY = [ann.y - ySpan / 2, ann.y + ySpan / 2];

      // 3. APPLY TO STATE
      this.config.rangeX = newRangeX;
      this.config.rangeY = newRangeY;

      // 4. COMMAND PLOTLY
      // We use relayout here because it's an instant camera move.
      Plotly.relayout(el, {
        "xaxis.range": newRangeX,
        "yaxis.range": newRangeY,
        "xaxis.autorange": false,
        "yaxis.autorange": false,
      });

      this.saveAndRender();
    },

    /**
     * Remove an annotation by index
     */
    deleteAnnotation(index) {
      this.config.annotations.splice(index, 1);
      this.saveAndRender();
    },

    /**
     * Edit existing text
     */
    editAnnotation(index) {
      const ann = this.config.annotations[index];
      const newText = prompt("Update Annotation:", ann.text);

      if (newText !== null && newText.trim() !== "") {
        this.config.annotations[index].text = newText;
        this.saveAndRender();
      }
    },

    // Add this near your other getters like highlightedJson
    get selectableYColumns() {
      if (!this.columns) return [];
      if (!this.config.refFrame) return this.columns;

      return this.columns.filter((col) => {
        const parts = col.split(":");
        const suffix = parts.pop(); // e.g., 'z' or 'mag'
        const family = parts.join(":"); // e.g., 'Bodies/box1/xpos'

        // Only allow x, y, z components for rotation mode
        const isVectorComponent = ["x", "y", "z"].includes(suffix);
        return isVectorComponent && this.rotateableVectors.includes(family);
      });
    },

    get availableQuats() {
      // If the manifest hasn't loaded yet, return empty
      if (!this.columns || !Array.isArray(this.columns)) return [];
      return this.columns
        .filter((c) => c.endsWith(":w"))
        .map((c) => c.replace(":w", ""));
    },

    async init() {
      // 1. UI PRIMING
      // Detect theme and set up the Warp ID from the URL string
      this.theme = document.documentElement.classList.contains("dark")
        ? "dark"
        : "light";
      const currentNum = parseInt(this.trialId.split("_").pop());
      this.warpId = isNaN(currentNum) ? null : currentNum;

      // 2. DOM & STATE OBSERVERS
      // Watch for system theme changes (e.g., toggling dark mode via UI)
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

      // 3. FETCH EXTERNAL STATUS (Padding & Sync)
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

      // 4. THE MAIN DATA LOAD
      try {
        // Load the main data the user is requesting
        const initialCols = [
          this.config.xAxis,
          ...Object.keys(this.config.yAxes),
        ];
        const response = await this.fetchTrialData(this.trialId, initialCols);

        this.columns = response.columns.all.sort();
        this.rotateableVectors = response.columns.rotateable_vectors;

        this.data = response.data;

        // 5. CONFIG HYDRATION
        const params = new URLSearchParams(window.location.search);
        const shared = params.get("v");
        if (shared) {
          this.hydrateFromUrl(shared);
          // CAPTURE SHARED STATE INTO DRAFT UI
          this.vsDraft.enabled = this.config.vsEnabled;
          this.vsDraft.range = [...this.config.vsRange];

          // FORCE THE "REAL" PLOT STATE TO FALSE (Requires "Apply" click)
          // We do this so the plot doesn't fetch comparisons until requested
          this.config.vsEnabled = false;
        } else {
          this.loadConfig();
          this.vsDraft.enabled = this.config.vsEnabled;
          this.vsDraft.range = [...this.config.vsRange];
        }

        // Capture the very first state after hydration
        this.$nextTick(() => {
          this.pushHistory();
        });

        // 6. INITIAL PLOT RENDER & EVENT ATTACHMENT
        this.$nextTick(async () => {
          await this.renderPlot();
          const plotEl = document.getElementById("plot-area");

          // Attach the zoom/pan listener to capture manual ranges
          plotEl.on("plotly_relayout", (event) => {
            // Handle Reset (Double-click)
            if (event["xaxis.autorange"] || event["yaxis.autorange"]) {
              this.config.rangeX = null;
              this.config.rangeY = null;

              this.renderPlot();
              return;
            }
            // Handle Manual Zoom/Pan
            if (event["xaxis.range[0]"] !== undefined) {
              this.config.rangeX = [
                event["xaxis.range[0]"],
                event["xaxis.range[1]"],
              ];
            }
            if (event["yaxis.range[0]"] !== undefined) {
              this.config.rangeY = [
                event["yaxis.range[0]"],
                event["yaxis.range[1]"],
              ];
            }
          });

          // annotations listener
          plotEl.addEventListener("click", (e) => {
            // 1. Target check: 'nsewdrag' is the class Plotly uses for the grid area
            const isPlotValue =
              e.target.classList.contains("nsewdrag") ||
              e.target.classList.contains("drag");

            if (!isPlotValue) return;

            // 2. Coordinate Conversion
            const rect = plotEl.getBoundingClientRect();
            const fullLayout = plotEl._fullLayout;

            // Convert pixels to data coordinates using Plotly's math engine
            const xVal = fullLayout.xaxis.p2l(
              e.clientX - rect.left - fullLayout.margin.l,
            );
            const yVal = fullLayout.yaxis.p2l(
              e.clientY - rect.top - fullLayout.margin.t,
            );
            const pt = { x: xVal, y: yVal };

            // 3. PRIORITY 1: Shapes (Geometric primitives)
            if (this.placementMode) {
              this.handlePlotClickForShapes(pt);
              return;
            }

            // 4. PRIORITY 2: Annotations (Text Notes)
            setTimeout(() => {
              this.annDraft = {
                x: pt.x,
                y: pt.y,
                text: "",
              };
              this.annEditIndex = null;
              this.annotationsOpen = true;

              this.$nextTick(() => {
                const input = document.querySelector('[x-ref="annInput"]');
                if (input) input.focus();
              });
            }, 0);
          });

          // Handle initial resize for hidden containers
          setTimeout(() => {
            if (plotEl?.offsetParent !== null) Plotly.Plots.resize(plotEl);
          }, 100);
        });
      } catch (e) {
        // Catch 404s or malformed JSON from fetchTrialData
        this.errorState = e.message.includes("not found")
          ? "not_found"
          : "empty";
        this.notify(e.message, "error");
      } finally {
        this.loading = false;
        Alpine.store("dojo").startGlobalSync();
        Alpine.store("dojo").setPageReady(true);
      }

      // 7. GLOBAL KEYBOARD SHORTCUTS
      window.addEventListener("keydown", (e) => {
        if (e.repeat) return;
        if (
          e.key === "/" &&
          !["INPUT", "TEXTAREA"].includes(e.target.tagName)
        ) {
          e.preventDefault();
          document.querySelector('input[type="number"]')?.focus();
        }
        if (e.key === "Escape") {
          this.yMenuOpen = this.settingsOpen = this.editorOpen = false;
          if (["INPUT", "TEXTAREA"].includes(e.target.tagName)) e.target.blur();
        }
        if (["INPUT", "TEXTAREA"].includes(e.target.tagName)) return;
        if (e.key === "ArrowLeft") document.getElementById("nav-prev")?.click();
        if (e.key === "ArrowRight")
          document.getElementById("nav-next")?.click();

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

      // FETCH TRIAL MANIFEST (For the slider/dropdown)
      // Fetch the manifest so we know which IDs exist in the fleet
      const resp = await fetch("/mosaic/api/trials");
      const data = await resp.json();
      this.allTrials = data.trials || [];

      if (this.allTrials.length) {
        const ids = this.allTrials
          .map((id) => parseInt(id.split("_").pop()))
          .filter((n) => !isNaN(n));
        const minFleet = Math.min(...ids);
        const maxFleet = Math.max(...ids);

        // If the config is brand new [0,0], initialize it to the full fleet
        if (this.config.vsRange[0] === 0 && this.config.vsRange[1] === 0) {
          this.config.vsRange = [minFleet, maxFleet];
          this.vsDraft.range = [minFleet, maxFleet];
        }
      }

      // This watches the slider/draft range and prepares data before "Apply" is clicked.
      this.$watch("vsDraft.range", () => {
        // Debounce: Wait 500ms after the user stops sliding
        if (this.discoveryTimeout) clearTimeout(this.discoveryTimeout);

        this.discoveryTimeout = setTimeout(() => {
          // Only pre-fetch if comparisons are actually enabled in the UI
          if (this.vsDraft.enabled) {
            console.debug(
              "Predictive Sync: User adjusted range, starting hydration...",
            );
            this.startBackgroundDiscovery();
          }
        }, 500);
      });

      this.$watch("config.refFrame", async (newValue, oldValue) => {
        // Because we are watching a string (a primitive), newValue and oldValue
        // will actually be different!
        console.debug(
          `[Mojo] Frame Change: ${oldValue || "world"} -> ${newValue || "world"}`,
        );

        this.discoveryId++; // Kill active fetches
        this.data = {};
        this.vsDatasets = {};

        // Fetch immediate traces
        const initialCols = [
          this.config.xAxis,
          ...Object.keys(this.config.yAxes),
        ];
        const response = await this.fetchTrialData(this.trialId, initialCols);

        this.columns = response.columns.all.sort();
        this.rotateableVectors = response.columns.rotateable_vectors;
        this.data = response.data;

        // Trigger full background refresh in the new frame
        this.startBackgroundDiscovery();

        if (this.config.vsEnabled) {
          await this.syncVsRange();
        }

        // Call your standard save/render
        this.saveAndRender();
      });

      // Start the initial background load for the current trial + current draft
      this.startBackgroundDiscovery();

      this.configRaw = JSON.stringify(this.config, null, 4);

      // Watch the master config: Any change here triggers a save and a redraw
      this.$watch("config", async (value, oldValue) => {
        if (!this.isEditingRaw) {
          this.configRaw = JSON.stringify(value, null, 4);
        }

        // check if we need to fetch that data for the comparison trials.
        if (
          this.config.vsEnabled &&
          oldValue?.vsEnabled && // Only auto-sync if it was already on
          (value.xAxis !== oldValue?.xAxis ||
            Object.keys(value.yAxes).length !==
              Object.keys(oldValue?.yAxes || {}).length)
        ) {
          await this.syncVsRange();
        }

        this.pushHistory();
        this.saveAndRender();
      });
    },

    async syncVsRange() {
      // 1. Force refresh manifest
      try {
        const resp = await fetch("/mosaic/api/trials");
        const data = await resp.json();
        this.allTrials = data.trials || [];
      } catch (e) {
        console.warn("Manifest sync failed", e);
      }

      if (!this.vsDraft.enabled) {
        this.config.vsEnabled = false;
        this.vsDatasets = {};
        return;
      }

      // START LOADING
      this.vsLoading = true;

      try {
        const start = Math.min(this.vsDraft.range[0], this.vsDraft.range[1]);
        const end = Math.max(this.vsDraft.range[0], this.vsDraft.range[1]);
        let activeCols = [this.config.xAxis, ...Object.keys(this.config.yAxes)];

        if (this.config.refFrame) {
          const families = new Set();
          Object.keys(this.config.yAxes).forEach((col) => {
            if (col.includes(":")) {
              families.add(col.substring(0, col.lastIndexOf(":")));
            }
          });

          families.forEach((fam) => {
            activeCols.push(`${fam}:x`, `${fam}:y`, `${fam}:z`);
          });
          // Also need the quat itself if the backend needs it for calculation
          activeCols.push(
            `${this.config.refFrame}:w`,
            `${this.config.refFrame}:x`,
            `${this.config.refFrame}:y`,
            `${this.config.refFrame}:z`,
          );
        }
        activeCols = [...new Set(activeCols)];

        const currentNum = parseInt(this.trialId.split("_").pop());

        const targetIds = this.allTrials.filter((id) => {
          const n = parseInt(id.split("_").pop());
          return n >= start && n <= end && n !== currentNum;
        });

        // Fetch missing data
        await Promise.all(
          targetIds.map(async (id) => {
            const existing = this.vsDatasets[id];
            const needsFetch =
              !existing ||
              activeCols.some((col) => !existing.hasOwnProperty(col)) ||
              this.config.refFrame !== null; // Always fetch if we are in a non-world frame

            if (needsFetch) {
              const response = await this.fetchTrialData(id, activeCols);
              this.vsDatasets[id] = {
                ...(this.vsDatasets[id] || {}),
                ...response.data,
              };
            }
          }),
        );

        // 3. THE COMMIT
        // Now that data is in memory, update the master config.
        // This triggers the watcher, which calls saveAndRender() exactly once.
        this.vsDatasets = { ...this.vsDatasets };
        this.config.vsRange = [start, end];
        this.config.vsEnabled = true;
      } finally {
        this.vsLoading = false;
        // renderPlot is called automatically by the watcher on this.config
      }
    },

    /**
     * Specifically handles the toggle switch
     */
    handleVsToggle() {
      // If user turns it OFF, we kill the lines immediately without an 'Apply' click
      if (!this.vsDraft.enabled) {
        this.config.vsEnabled = false;
        this.renderPlot();
      }
      // If they turn it ON, we do nothing. They must click 'Apply' to see changes.
    },

    /**
     * SMART SORT: Pins 'time' to the top, then sorts alphabetically.
     */
    smartSort(list) {
      return list.sort((a, b) => {
        const aIsTime = a.toLowerCase() === "time";
        const bIsTime = b.toLowerCase() === "time";
        if (aIsTime && !bIsTime) return -1;
        if (!aIsTime && bIsTime) return 1;
        return a.localeCompare(b, undefined, { sensitivity: "base" });
      });
    },

    /**
     * REFINED GENERIC LOGIC
     */
    getFilteredCols(field) {
      // Safety: If columns haven't loaded yet, return empty array immediately
      if (!this.columns || !Array.isArray(this.columns)) return [];

      const base = field === "x" ? this.columns : this.selectableYColumns;
      const search = this[field + "Search"];

      if (!search) return this.smartSort([...base]);
      try {
        let pattern = search.replace(/\*/g, ".*");

        // The "Fuzzy Bridge":
        // This ensures that "xpos/" or "xpos" both match "xpos:x"
        // It makes the trailing slash optional when followed by a suffix
        pattern = pattern.replace(/\/?:/g, ".*:");

        // If the user manually typed a trailing slash but it's a leaf,
        // we make that slash optional in the regex.
        if (pattern.endsWith("/")) {
          pattern = pattern.replace(/\/$/, "\/?");
        }

        if (pattern.startsWith(":")) pattern = ".*" + pattern;
        if (pattern.toLowerCase() === "time") pattern = "^time$";

        const query = new RegExp(pattern, "i");
        return this.smartSort(base.filter((c) => query.test(c)));
      } catch (e) {
        return this.smartSort(
          this.smartSort(
            base.filter((c) => c.toLowerCase().includes(search.toLowerCase())),
          ),
        );
      }
    },

    toggleRegexSegment(field, segment, depth = null) {
      const key = field + "Search";
      let [pathPart, suffixPart] = (this[key] || "").split(":");
      pathPart = pathPart || "";
      suffixPart = suffixPart || "";

      if (depth === "suffix") {
        const cleanSeg = segment.replace(":", "");
        // CRITICAL: Strip parentheses before splitting to prevent nesting
        let items = suffixPart.replace(/[()]/g, "").split("|").filter(Boolean);

        items = items.includes(cleanSeg)
          ? items.filter((i) => i !== cleanSeg)
          : [...items, cleanSeg];

        // Rebuild flat: (x|y|z)
        suffixPart =
          items.length > 1 ? `(${items.sort().join("|")})` : items[0] || "";
      } else {
        let parts = pathPart.split("/").filter((p) => p !== "");
        let target = parts[depth] || "";
        let items = target.replace(/[()]/g, "").split("|").filter(Boolean);

        items = items.includes(segment)
          ? items.filter((i) => i !== segment)
          : [...items, segment];

        if (items.length === 0) {
          parts = parts.slice(0, depth);
        } else {
          parts[depth] =
            items.length === 1 ? items[0] : `(${items.sort().join("|")})`;
        }

        pathPart = parts.join("/");
        if (pathPart && pathPart.toLowerCase() !== "time") {
          const isFolder = this.columns.some((c) =>
            c.toLowerCase().startsWith(pathPart.toLowerCase() + "/"),
          );
          if (isFolder) pathPart += "/";
        }
      }
      this[key] = pathPart + (suffixPart ? ":" + suffixPart : "");
    },

    getSegmentsAtDepth(field, depth) {
      const base = field === "x" ? this.columns : this.selectableYColumns;
      const search = this[field + "Search"] || "";
      const pathSearch = search.split(":")[0] || "";
      const parts = pathSearch.split("/").filter((p) => p !== "");

      // 1. Orphan Logic (keep current selections visible)
      const selected = (parts[depth] || "")
        .replace(/[()]/g, "")
        .split("|")
        .filter(Boolean);

      // 2. Discovery Logic
      const prefixParts = parts.slice(0, depth);
      const prefix = prefixParts.join("/").replace(/\//g, "\\/?");
      // If prefix is empty, we match the start of the string
      const regex = new RegExp("^" + (prefix ? prefix : ""), "i");

      const segments = base
        .filter((c) => regex.test(c))
        .map((c) => {
          const p = c.split(":")[0].split("/");
          return p[depth] || null;
        })
        .filter(Boolean);

      return this.smartSort([...new Set([...selected, ...segments])]);
    },

    getAvailableSuffixes(field) {
      const base = field === "x" ? this.columns : this.selectableYColumns;
      const search = this[field + "Search"];
      const [pathPart, suffixPart] = search.split(":");

      // 1. Orphan logic
      const selected = (suffixPart || "")
        .replace(/[()]/g, "")
        .split("|")
        .filter(Boolean)
        .map((s) => ":" + s);

      // 2. Discovery: Find suffixes matching the current path
      const pathRegex = new RegExp(
        "^" + (pathPart || "").replace(/\//g, "\\/?"),
        "i",
      );
      const matches = base.filter((c) => pathRegex.test(c));

      const available = matches
        .map((c) => (c.includes(":") ? ":" + c.split(":").pop() : null))
        .filter(Boolean);
      return this.smartSort([...new Set([...selected, ...available])]);
    },

    /**
     * Helper to determine if a segment button should be highlighted.
     * This handles the regex stripping so the HTML stays clean.
     */
    isSegmentActive(field, seg, depth) {
      const search = this[field + "Search"] || "";
      if (depth === "suffix") {
        const suffixPart = search.split(":")[1] || "";
        const items = suffixPart
          .replace(/[()]/g, "")
          .split("|")
          .filter(Boolean);
        return items.includes(seg.replace(":", ""));
      } else {
        const pathPart = search.split(":")[0] || "";
        const levels = pathPart.split("/").filter((p) => p !== "");
        const levelContent = levels[depth] || "";
        const items = levelContent
          .replace(/[()]/g, "")
          .split("|")
          .filter(Boolean);
        return items.includes(seg);
      }
    },

    getActiveLevels(field) {
      const search = this[field + "Search"] || "";
      // Isolate path from suffix
      const pathOnly = search.split(":")[0] || "";
      const parts = pathOnly.split("/").filter((p) => p !== "");

      // Ensure we always show at least one level (the root)
      return Array.from({ length: parts.length + 1 }, (_, i) => i);
    },

    /**
     * GETTER: highlightedJson
     * Injects Tailwind CSS classes for syntax highlighting.
     */
    get highlightedJson() {
      if (!this.configRaw) return "";

      // 1. Escape HTML
      let html = this.configRaw
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

      /**
       * 2. REVISED REGEX
       * Group 1: Valid JSON Tokens
       * Group 5: "Garbage" (Any non-whitespace characters not matched by Group 1)
       */
      const regex =
        /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?|[\[\]{},])|(\S+)/g;

      return html.replace(
        regex,
        (match, token, _inner1, _inner2, _inner3, garbage) => {
          // If it's garbage (text that doesn't belong in JSON), make it scream
          if (garbage) {
            return `<span class="text-rose-500 underline decoration-wavy underline-offset-2 font-bold">${garbage}</span>`;
          }

          let cls = "text-slate-500 dark:text-slate-400"; // Default: Structural (braces/commas)

          if (/^"/.test(match)) {
            if (/:$/.test(match)) {
              cls = "text-cyan-600 dark:text-cyan-300"; // Keys
            } else {
              cls = "text-emerald-600 dark:text-emerald-400"; // Strings
            }
          } else if (/true|false/.test(match)) {
            cls = "text-violet-600 dark:text-violet-400"; // Booleans
          } else if (/null/.test(match)) {
            cls = "text-rose-500"; // Null
          } else if (/-?\d/.test(match)) {
            cls = "text-amber-600 dark:text-amber-500"; // Numbers
          }

          return `<span class="${cls}">${match}</span>`;
        },
      );
    },

    getYProps(axis, index) {
      const obj = this.config.yAxes[axis] || {};
      return {
        name: axis,
        label: obj.label || axis,
        color: obj.color || this.getSignalColor(index),
        width: obj.width || 3,
        opacity: obj.opacity || 1.0,
        dash: obj.dash || "solid",
        marker: obj.marker || "none",
        scale: obj.scale || "1.0",
      };
    },

    parseScale(scaleStr) {
      try {
        const safe = String(scaleStr)
          .replace(/pi/gi, Math.PI)
          .replace(/[^-()\d/*+.]/g, "");
        return Function(`"use strict"; return (${safe})`)() || 1.0;
      } catch {
        return 1.0;
      }
    },

    hydrateFromUrl(blob) {
      try {
        const decoded = LZString.decompressFromEncodedURIComponent(blob);
        if (!decoded) throw new Error("Decompression failed");
        const parsed = JSON.parse(decoded);

        // We only merge the config; we no longer touch documentElement.classList
        this.config = { ...this.config, ...parsed };

        this.notify("Shared view loaded", "success");
      } catch (e) {
        this.notify("Failed to decode shared link", "error");
        this.loadConfig();
      }
    },

    /**
     * Share Functionality:
     * Minifies the JSON and (optionally) compresses it for the URL.
     * For now, we'll use standard Base64 until we pull in LZ-String.
     */
    copyShareLink() {
      try {
        const minified = JSON.stringify(this.config);
        const encoded = LZString.compressToEncodedURIComponent(minified);
        const shareBase = this.externalUrl + window.location.pathname;

        // Just call the helper
        this.copyToClipboard(
          `${shareBase}?v=${encoded}`,
          "Shareable link copied!",
        );
      } catch (e) {
        this.notify("Link generation failed", "error");
      }
    },

    copyRawConfig() {
      this.copyToClipboard(this.configRaw, "JSON Config copied!");
    },

    resetConfig() {
      if (
        confirm(
          "Reset plot to factory defaults? This will clear your current view.",
        )
      ) {
        // 1. Wipe persistence
        localStorage.removeItem("mojo_mosaic_config");

        // 2. Restore defaults (Deep copy to break references)
        this.config = JSON.parse(JSON.stringify(DEFAULT_CONFIG));

        // 3. Re-sync the X-axis fallback if telemetry is loaded
        if (this.columns.includes("time")) this.config.xAxis = "time";

        this.notify("Settings Reset", "info");

        // 4. Update the editor text area
        this.configRaw = JSON.stringify(this.config, null, 4);
      }
    },

    /**
     * Universal Clipboard Helper
     * Handles Secure (HTTPS) and Insecure (HTTP) contexts
     */
    async copyToClipboard(text, successMsg = "Copied to clipboard!") {
      // 1. Try the modern API first (Requires HTTPS/Localhost)
      if (navigator.clipboard && window.isSecureContext) {
        try {
          await navigator.clipboard.writeText(text);
          this.notify(successMsg, "success");
          return;
        } catch (err) {
          console.warn("Modern clipboard failed, falling back...", err);
        }
      }

      // 2. Fallback for HTTP / Older Browsers
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.position = "fixed";
      textArea.style.left = "-9999px";
      textArea.style.top = "0";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      try {
        const successful = document.execCommand("copy");
        if (successful) {
          this.notify(successMsg, "success");
        } else {
          throw new Error("execCommand returned false");
        }
      } catch (err) {
        this.notify("Failed to copy to clipboard", "error");
        console.error("Clipboard fallback failed", err);
      }
      document.body.removeChild(textArea);
    },

    /**
     * Universal Notification Engine
     * @param {string} msg - The message to display
     * @param {string} type - success | error | info
     */
    notify(msg, type = "success") {
      this.toastMessage = msg;
      this.toastType = type;
      this.showToast = true;

      // Auto-hide after 3 seconds
      setTimeout(() => {
        this.showToast = false;
      }, 3000);
    },

    /**
     * Logical Validation for Mosaic Config
     */
    validateConfig(cfg) {
      let errors = [];

      // 1. Check X-Axis
      if (!this.columns.includes(cfg.xAxis)) {
        errors.push(`X-Axis "${cfg.xAxis}" not found in telemetry.`);
      }

      // 2. Check Y-Axes
      if (typeof cfg.yAxes !== "object" || Array.isArray(cfg.yAxes)) {
        errors.push("yAxes must be a hashmap.");
      } else {
        Object.keys(cfg.yAxes).forEach((y) => {
          if (!this.columns.includes(y)) errors.push(`Y-Axis "${y}" missing.`);
        });
      }

      // 3. Range Safety
      if (cfg.vsRange && cfg.vsRange[0] > cfg.vsRange[1]) {
        errors.push("Comparison range start cannot be greater than end.");
      }

      return errors;
    },

    /**
     * Input Handler for JSON Editor
     * Uses Object.assign to maintain reactivity without breaking the object reference.
     */
    updateFromRaw() {
      try {
        const parsed = JSON.parse(this.configRaw);
        this.isValidJson = true;

        if (parsed && typeof parsed === "object") {
          // Check for logical errors
          this.configErrors = this.validateConfig(parsed);
          this.isValidConfig = this.configErrors.length === 0;

          if (this.isValidConfig) {
            // THE GUARD: Set this to true so the watcher ignores the change
            this.isEditingRaw = true;

            this.config = { ...this.config, ...parsed };

            // Release the guard after the current reactive cycle
            this.$nextTick(() => {
              this.isEditingRaw = false;
            });
          }
        }
      } catch (e) {
        this.isValidJson = false;
        this.isValidConfig = false;
      }
    },

    /**
     * Hydration: Loads saved configuration from localStorage
     */
    loadConfig() {
      const saved = localStorage.getItem("mojo_mosaic_config");
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          // Merge parsed data into default config to prevent missing keys
          this.config = { ...this.config, ...parsed };
        } catch (e) {
          console.error("Stored config corrupt");
        }
      } else {
        // Default fallback: Set X-axis to 'time' if available
        if (this.columns.includes("time")) this.config.xAxis = "time";
      }

      // rehydrate history stack
      const savedHistory = localStorage.getItem("mojo_mosaic_history");
      if (savedHistory) {
        try {
          const { stack, index } = JSON.parse(savedHistory);
          this.historyStack = stack;
          this.historyIndex = index;
        } catch (e) {
          console.warn("History recovery failed, starting fresh.");
          this.pushHistory();
        }
      } else {
        this.pushHistory(); // First-time setup
      }

      // Sync the text editor string with the loaded object
      this.configRaw = JSON.stringify(this.config, null, 4);
    },

    /**
     * Persistence: Saves state and triggers plot refresh
     */
    saveAndRender() {
      localStorage.setItem("mojo_mosaic_config", JSON.stringify(this.config));
      this.persistHistory();
      this.renderPlot();

      // Guarded resize in case the plot container recently became visible
      this.$nextTick(() => {
        const el = document.getElementById("plot-area");
        if (el && el.offsetParent !== null) Plotly.Plots.resize(el);
      });
    },

    /**
     * Export Plot as Image (PNG, JPG, SVG)
     */
    async downloadPlot(format) {
      const el = document.getElementById("plot-area");
      if (!el) return;

      const plotlyFormat = format === "jpg" ? "jpeg" : format;
      const isDark = document.documentElement.classList.contains("dark");

      // Match the Metadata Card background exactly (#1e293b)
      const bgColor = isDark ? tw.slate[800] : "#ffffff";

      this.notify(`Preparing ${format.toUpperCase()}...`, "info");

      try {
        // 1. Capture the current "Glass" state so we can restore it
        const originalPaper = el.layout.paper_bgcolor;
        const originalPlot = el.layout.plot_bgcolor;

        // 2. TEMPORARILY apply the solid background for the snapshot
        await Plotly.relayout(el, {
          paper_bgcolor: bgColor,
          plot_bgcolor: bgColor,
        });

        // 3. Generate the image from the now-solid plot
        const dataUrl = await Plotly.toImage(el, {
          format: plotlyFormat,
          width: 1280,
          height: 720,
        });

        // 4. IMMEDIATELY restore the transparency for the UI
        await Plotly.relayout(el, {
          paper_bgcolor: originalPaper,
          plot_bgcolor: originalPlot,
        });

        // 5. Trigger the browser download
        const link = document.createElement("a");
        link.href = dataUrl;
        link.download = `${this.trialId}_plot.${format}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } catch (e) {
        console.error("Export failed", e);
      } finally {
        this.downloadOpen = false;
      }
    },

    /**
     * Export Raw Data as CSV
     */
    /**
     * Export ONLY currently displayed data as CSV
     */
    downloadCSV() {
      if (!this.data || Object.keys(this.config.yAxes).length === 0) return;

      // 1. Identify only the active columns (X + all selected Ys)
      const activeCols = [this.config.xAxis, ...Object.keys(this.config.yAxes)];
      const rowCount = this.data[this.config.xAxis].length;

      // 2. Build CSV with only those columns
      let csv = activeCols.join(",") + "\n";
      for (let i = 0; i < rowCount; i++) {
        csv += activeCols.map((col) => this.data[col][i]).join(",") + "\n";
      }

      // 3. Standard Blob Download
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.setAttribute("download", `${this.trialId}_filtered.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      this.downloadOpen = false;

      this.notify("Filtered CSV Exported", "success");
    },

    /**
     * Export the current Plot Configuration as a JSON file
     */
    downloadJSON() {
      const configString = JSON.stringify(this.config, null, 4);
      const blob = new Blob([configString], { type: "application/json" });

      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.setAttribute("download", `${this.trialId}_config.json`);
      document.body.appendChild(link);

      link.click();
      document.body.removeChild(link);

      this.downloadOpen = false;

      this.notify("Configuration JSON Exported", "success");
    },

    /**
     * Handle File Drop
     */
    handleDrop(e) {
      const file = e.dataTransfer.files[0];

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
          const importedConfig = JSON.parse(event.target.result);

          // Merge with current config to ensure we don't break reactivity
          this.config = { ...this.config, ...importedConfig };

          this.notify("Configuration restored!", "success");

          // Re-sync the raw text area if it's open
          this.configRaw = JSON.stringify(this.config, null, 4);
        } catch (err) {
          console.error("JSON Import failed", err);

          this.notify("Invalid Config File", "error");
        }
      };
      reader.readAsText(file);
    },

    /**
     * Toggle Logic: Adds/Removes signals from the Y-Axis array
     */
    toggleY(col) {
      if (this.config.yAxes[col]) {
        const { [col]: _, ...remainingY } = this.config.yAxes;
        this.config.yAxes = remainingY;
      } else {
        // Find the next available color index
        const nextIndex = Object.keys(this.config.yAxes).length;

        // Initialize with DEFAULTS so Alpine has a "path" to watch
        this.config.yAxes[col] = {
          color: this.getSignalColor(nextIndex), // Hard-set the default hex
          label: "",
          width: 3,
          opacity: 1,
          scale: "1.0",
          dash: "solid",
        };
      }
      this.saveAndRender();
    },

    /**
     * Clear all selected Y-Axis signals
     */
    clearYAxes() {
      if (Object.keys(this.config.yAxes).length === 0) return;

      this.config.yAxes = {};
      this.config.yAxes = { ...this.config.yAxes };
      this.saveAndRender(); // Saves to localStorage and updates Plotly

      // Update the JSON editor if it's open
      this.configRaw = JSON.stringify(this.config, null, 4);

      this.notify("Signals Cleared", "info");
    },

    /**
     * Navigation: Redirects to another trial within the same job
     */
    warpToTrial() {
      if (
        this.warpId === null ||
        this.warpId === undefined ||
        this.warpId === ""
      )
        return;

      const paddedNum = String(this.warpId).padStart(this.paddingLen, "0");
      window.location.href = `/mosaic/trial_${paddedNum}`;
    },

    /**
     * Helper to get color by index (with modulo for safety)
     */
    getSignalColor(index) {
      return this.plotColors[index % this.plotColors.length];
    },

    /**
     * Shared helper to find the min/max of current active datasets
     */
    calculatePaddedRange(keys, padding = true) {
      let globalMin = Infinity;
      let globalMax = -Infinity;
      const activeDatasets = [this.data];

      if (this.config.vsEnabled) {
        const [start, end] = this.config.vsRange;
        Object.entries(this.vsDatasets).forEach(([vsId, dataset]) => {
          const n = parseInt(vsId.split("_").pop());
          if (n >= start && n <= end) activeDatasets.push(dataset);
        });
      }

      activeDatasets.forEach((dataset) => {
        keys.forEach((key, i) => {
          const p = this.getYProps(key, i);
          const scale = this.parseScale(p.scale);
          const series = dataset[key];
          if (!series) return;
          for (let i = 0; i < series.length; i++) {
            const val = series[i] * scale;
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

    /**
     * Plotly Engine: Renders the telemetry traces based on the current config object
     */
    renderPlot() {
      if (!this.data) return;

      // const el = document.getElementById("plot-area");
      const isDark = document.documentElement.classList.contains("dark");

      const textColor = isDark ? tw.slate[400] : tw.slate[600];
      const majorGrid = isDark ? tw.slate[950] : tw.slate[200];
      const minorGrid = isDark ? tw.slate[900] : tw.slate[100];
      const tooltipBg = isDark ? tw.slate[900] : "#ffffff";
      const tooltipFont = isDark ? tw.slate[50] : tw.slate[900];
      const tooltipBorder = tw.cyan[500];
      const spikeColor = isDark ? tw.cyan[500] : tw.cyan[500];

      const isHoverDisabled = this.config.hover === "none";

      const showX =
        this.config.showSpike &&
        !isHoverDisabled &&
        (this.config.hover.includes("x") || this.config.hover === "closest");
      const showY =
        this.config.showSpike &&
        !isHoverDisabled &&
        (this.config.hover.includes("y") || this.config.hover === "closest");

      // Determine final display ranges
      const displayRangeX =
        this.config.rangeX ||
        this.calculatePaddedRange([this.config.xAxis], false);
      const displayRangeY =
        this.config.rangeY ||
        this.calculatePaddedRange(Object.keys(this.config.yAxes));

      // main traces
      const yKeys = Object.keys(this.config.yAxes);
      let traces = yKeys
        .map((key, i) => {
          const p = this.getYProps(key, i);
          const scale = this.parseScale(p.scale);

          if (!this.data[p.name]) return null;

          return {
            x: this.data[this.config.xAxis],
            y: this.data[p.name].map((v) => v * scale),
            name: p.label,
            mode: this.config.linemode,
            type: "scatter",
            line: {
              width: p.width,
              color: p.color,
              shape: this.config.interp,
              dash: p.dash,
            },
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
        .filter((trace) => trace !== null);

      // vs traces
      if (this.config.vsEnabled) {
        const [start, end] = this.config.vsRange;

        // Track which parameters have already created a legend entry
        const legendTracker = new Set();

        const sortedVsIds = Object.keys(this.vsDatasets).sort((a, b) => {
          const numA = parseInt(a.split("_").pop());
          const numB = parseInt(b.split("_").pop());
          return numA - numB;
        });

        sortedVsIds.forEach((vsId) => {
          const n = parseInt(vsId.split("_").pop());
          if (n < start || n > end || vsId === this.trialId) return;

          const dataset = this.vsDatasets[vsId];
          if (!dataset) return;

          const vsTraces = yKeys
            .map((key, i) => {
              const p = this.getYProps(key, i);

              if (!dataset[p.name]) {
                return null;
              }

              const scale = this.parseScale(p.scale);

              // Check if this specific parameter has shown up in the legend yet
              const isFirstEntryForThisParam = !legendTracker.has(key);

              const t = {
                x: dataset[this.config.xAxis],
                y: dataset[p.name].map((v) => v * scale),
                // Name it after the signal so the legend is clear
                name: `${p.label} (<i>vs.</i>)`,
                // Group by signal name so toggling one toggles all trials for that signal
                legendgroup: `group_${key}`,
                showlegend: isFirstEntryForThisParam,
                mode: this.config.linemode,
                type: "scatter",
                line: {
                  width: 1,
                  color: p.color,
                  shape: this.config.interp,
                  dash: "dot",
                },
                opacity: 0.35,
                marker: { size: 4, symbol: p.marker },
                hoverlabel: { namelength: -1 },
                hovertemplate: `<b>${key}</b> (#${n})<br>%{x}: %{y:.4f}<extra></extra>`,
              };

              // Mark this parameter as 'legend-accounted-for'
              legendTracker.add(key);
              return t;
            })
            .filter((trace) => trace !== null);
          traces = [...traces, ...vsTraces];
        });
      }

      // x axis config
      const xAxisObj = {
        type: this.config.xScale || "linear",
        range:
          this.config.xScale === "log"
            ? [
                Math.log10(Math.max(1e-6, displayRangeX[0])),
                Math.log10(Math.max(1e-6, displayRangeX[1])),
              ]
            : displayRangeX,
        dtick:
          this.config.xScale === "log" && this.config.xLogBase
            ? Math.log10(this.config.xLogBase)
            : undefined,
        // tickformat: ".3s",
        gridcolor: majorGrid,
        showgrid: this.config.grid !== "none",
        minor: { showgrid: this.config.grid === "all", gridcolor: minorGrid },
        zeroline: false,
        tickfont: { color: textColor, size: 14 },
        title: {
          text: this.config.xAxisTitle || this.config.xAxis,
          font: { size: 14, color: textColor, family: "monospace" },
        },
        autorange: false,
        showspikes: showX,
        spikemode: "across",
        spikelinecolor: spikeColor,
        spikethickness: -2,
      };

      const frameLabel = this.config.refFrame
        ? `<br><span style="color: ${textColor}; font-size: 14px; opacity: 0.6;">[Frame: ${this.config.refFrame}]</span>`
        : ``;

      // y axis config
      const yAxisObj = {
        type: this.config.yScale || "linear",
        range:
          this.config.yScale === "log"
            ? [
                Math.log10(Math.max(1e-6, displayRangeY[0])),
                Math.log10(Math.max(1e-6, displayRangeY[1])),
              ]
            : displayRangeY,
        dtick:
          this.config.yScale === "log" && this.config.yLogBase
            ? Math.log10(this.config.yLogBase)
            : undefined,
        // tickformat: ",.3f",
        gridcolor: majorGrid,
        showgrid: this.config.grid !== "none",
        minor: { showgrid: this.config.grid === "all", gridcolor: minorGrid },
        zeroline: false,
        tickfont: { color: textColor, size: 14 },
        title: {
          text: this.config.yAxisTitle + frameLabel,
          font: { size: 14, color: textColor, family: "monospace" },
        },
        autorange: false,
        showspikes: showY,
        spikemode: "across",
        spikelinecolor: spikeColor,
        spikethickness: -2,
      };

      // layout
      const layout = {
        uirevision: `${this.trialId}_${this.config.xAxis}_${Object.keys(this.config.yAxes).join("_")}`,
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
        xaxis: xAxisObj,
        yaxis: yAxisObj,
        annotations: [
          // 1. Existing Notes (with arrows)
          ...(this.config.annotations || []).map((ann) => ({
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

          // 2. Shape Labels (pinned to geometry)
          ...(this.config.shapes || [])
            .filter((s) => s.label)
            .map((s) => {
              let x = s.x0;
              let y = s.y0;
              let xanchor = "left";
              let yanchor = "bottom";
              let xref = "x";
              let yref = "y";

              // Positioning logic to keep labels on the plot edge or shape corner
              if (s.type === "vline") {
                y = 1;
                yref = "paper"; // Top of the plot
              } else if (s.type === "hline") {
                x = 1;
                xref = "paper";
                xanchor = "right"; // Right side of the plot
              } else if (s.type === "rect") {
                x = s.x0;
                y = s.y1; // Top-left corner of the rect
              }

              return {
                x,
                y,
                xref,
                yref,
                text: `<b>${s.label}</b>`,
                showarrow: false, // No arrows for shape labels
                xanchor,
                yanchor,
                font: {
                  size: 10,
                  color: s.color || tw.cyan[500],
                  family: "monospace",
                },
                bgcolor: isDark ? tw.slate[900] + "B3" : tw.slate[50] + "B3",
                borderpad: 2,
              };
            }),
        ],
        shapes: (this.config.shapes || []).map((s) => {
          const isDark = document.documentElement.classList.contains("dark");
          const shapeColor = s.color || tw.cyan[500];

          const base = {
            line: { color: shapeColor, width: 2, dash: s.dash || "solid" },
            layer: "below",
          };

          if (s.type === "vline") {
            return {
              ...base,
              type: "line",
              x0: s.x0,
              x1: s.x0,
              y0: 0,
              y1: 1,
              yref: "paper",
            };
          }
          if (s.type === "hline") {
            return {
              ...base,
              type: "line",
              y0: s.y0,
              y1: s.y0,
              x0: 0,
              x1: 1,
              xref: "paper",
            };
          }
          if (s.type === "rect") {
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
          }
        }),
      };

      // config
      const config = {
        responsive: true, // adapt to page changes
        displaylogo: false, // hide plotly logo
        displayModeBar: true, // keep mode bar always visible
        modeBarButtonsToRemove: ["toImage"], // we have our own download options
      };

      return Plotly.react("plot-area", traces, layout, config);
    },
  };
}
