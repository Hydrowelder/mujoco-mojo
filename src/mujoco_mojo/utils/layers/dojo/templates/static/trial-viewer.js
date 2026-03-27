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
    data: null,
    errorState: null,

    // --- UI / MENU STATES ---
    theme: "dark",
    yMenuOpen: false,
    settingsOpen: false,
    downloadOpen: false,
    isDragging: false, // tracks if a file is being hovered over the page
    editorOpen: false, // Controls the visibility of the JSON editor drawer
    ySearch: "",
    columns: [],
    showToast: false,
    toastMessage: "",
    toastType: "success",

    // --- SINGLE SOURCE OF TRUTH: PLOT CONFIGURATION ---
    // This object is the master state. Changes here trigger re-renders.
    config: {
      xAxis: "time",
      yAxes: [],
      grid: "all",
      linemode: "lines", // Renamed from markerMode for clarity
      interp: "linear", // line interpolation (linear, spline, etc)
      hover: "x unified", // "x unified", "y unified", "closest", "x", "y", "none"
      title: "",
      xAxisTitle: "",
      yAxisTitle: "",
      legendPos: "bottom", // "bottom", "right", "hidden"
    },

    // --- JSON EDITOR STATE ---
    configRaw: "", // Pretty-printed string for the <textarea>
    isValidJson: true, // Tracks if the user's manual JSON input is valid

    async init() {
      // Set initial theme
      this.theme = document.documentElement.classList.contains("dark")
        ? "dark"
        : "light";

      const currentNum = parseInt(this.trialId.split("_").pop());
      this.warpId = isNaN(currentNum) ? null : currentNum;

      // 1. Updated Theme Observer: Redraws plot AND updates config.theme
      const observer = new MutationObserver((mutations) => {
        const isThemeChange = mutations.some(
          (m) => m.attributeName === "class",
        );
        if (isThemeChange) {
          this.theme = document.documentElement.classList.contains("dark")
            ? "dark"
            : "light";
          if (this.data && this.config.yAxes.length > 0) this.renderPlot();
        }
      });
      observer.observe(document.documentElement, { attributes: true });

      // 2. State Watcher: Sync the JSON text area whenever the config object changes
      this.$watch("config", (value) => {
        this.configRaw = JSON.stringify(value, null, 4);
        this.saveAndRender();
      });

      // 3. Fetch Dojo Status (Sync & Padding length)
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

      // 4. Fetch Telemetry Data (DuckDB/JSON)
      try {
        const resp = await fetch(`/mosaic/${this.trialId}/data`);
        if (resp.status === 404) {
          this.errorState = "not_found";
          this.notify("Trial data not found", "error");
          throw new Error();
        }

        const json = await resp.json();
        if (json && Object.keys(json).length > 0) {
          this.data = json;
          this.columns = Object.keys(json).sort();

          // Check for shared config in URL
          const params = new URLSearchParams(window.location.search);
          const shared = params.get("v");
          if (shared) {
            this.hydrateFromUrl(shared);
          } else {
            this.loadConfig();
          }

          this.$nextTick(() => {
            this.renderPlot();
            // Handle initial resize for responsive layout
            setTimeout(() => {
              const el = document.getElementById("plot-area");
              if (el && el.offsetParent !== null) Plotly.Plots.resize(el);
            }, 100);
          });
        } else {
          this.errorState = "empty";
        }
      } catch (e) {
        this.data = null;
        this.notify("Failed to connect to Dojo server", "error");
      } finally {
        this.loading = false;
        Alpine.store("dojo").startGlobalSync();
        Alpine.store("dojo").setPageReady(true);
      }

      // 5. Global Keyboard Shortcuts
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
          this.yMenuOpen = false;
          this.settingsOpen = false;
          this.editorOpen = false;
          if (["INPUT", "TEXTAREA"].includes(e.target.tagName)) e.target.blur();
        }
        if (["INPUT", "TEXTAREA"].includes(e.target.tagName)) return;
        if (e.key === "ArrowLeft") document.getElementById("nav-prev")?.click();
        if (e.key === "ArrowRight")
          document.getElementById("nav-next")?.click();
      });
    },

    /**
     * Getter for filtered signals list in the Y-Axis menu
     */
    get filteredCols() {
      return !this.ySearch
        ? this.columns
        : this.columns.filter((c) =>
            c.toLowerCase().includes(this.ySearch.toLowerCase()),
          );
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

      // 2. Comprehensive RegEx: Keys, Strings, Numbers, Booleans, Null, and Structural ( { } [ ] , )
      const regex =
        /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?|[\[\]{},])/g;

      return html.replace(regex, (match) => {
        let cls = "text-slate-400 dark:text-slate-500"; // Default: Structural (braces/commas)

        if (/^"/.test(match)) {
          if (/:$/.test(match)) {
            cls = "text-cyan-700 dark:text-cyan-400"; // Keys
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
      });
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
     * Input Handler for JSON Editor
     * Uses Object.assign to maintain reactivity without breaking the object reference.
     */
    updateFromRaw() {
      try {
        const parsed = JSON.parse(this.configRaw);
        if (parsed && typeof parsed === "object") {
          // Update master config - Alpine watcher will trigger save/render
          this.config = { ...this.config, ...parsed };
          this.isValidJson = true;
        }
      } catch (e) {
        this.isValidJson = false;
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
      // Sync the text editor string with the loaded object
      this.configRaw = JSON.stringify(this.config, null, 4);
    },

    /**
     * Persistence: Saves state and triggers plot refresh
     */
    saveAndRender() {
      localStorage.setItem("mojo_mosaic_config", JSON.stringify(this.config));
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
      if (!this.data || this.config.yAxes.length === 0) return;

      // 1. Identify only the active columns (X + all selected Ys)
      const activeCols = [this.config.xAxis, ...this.config.yAxes];
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
      this.isDragging = false;
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
      if (this.config.yAxes.includes(col)) {
        this.config.yAxes = this.config.yAxes.filter((c) => c !== col);
      } else {
        this.config.yAxes = [...this.config.yAxes, col];
      }
      // Note: Watcher handles saveAndRender automatically
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
     * Plotly Engine: Renders the telemetry traces based on the current config object
     */
    renderPlot() {
      if (!this.data || this.config.yAxes.length === 0) return;

      const isDark = document.documentElement.classList.contains("dark");
      const plotColors = [
        tw.cyan[500],
        tw.emerald[500],
        tw.blue[500],
        tw.violet[500],
        tw.amber[500],
        tw.rose[500],
      ];
      const textColor = isDark ? tw.slate[400] : tw.slate[600];
      const majorGrid = isDark ? tw.slate[950] : tw.slate[200];
      const minorGrid = isDark ? tw.slate[900] : tw.slate[100];
      const tooltipBg = isDark ? tw.slate[900] : "#ffffff";
      const tooltipFont = isDark ? tw.slate[50] : tw.slate[900];
      const tooltipBorder = tw.cyan[500];
      const spikeColor = isDark ? tw.cyan[500] : tw.slate[400];

      const isHoverDisabled = this.config.hover === "none";

      const showX =
        !isHoverDisabled &&
        (this.config.hover.includes("x") || this.config.hover === "closest");
      const showY =
        !isHoverDisabled &&
        (this.config.hover.includes("y") || this.config.hover === "closest");

      const traces = this.config.yAxes.map((key, i) => ({
        x: this.data[this.config.xAxis],
        y: this.data[key],
        name: key,
        mode: this.config.linemode,
        type: "scatter",
        line: {
          width: 2,
          color: plotColors[i % plotColors.length],
          shape: this.config.interp,
        },
        marker: { size: 6 },
        namelength: -1,
        // Disable hover on individual traces if toggled off
        hoverinfo: isHoverDisabled ? "skip" : "all",
        hoverlabel: {
          bgcolor: tooltipBg,
          bordercolor: tooltipBorder,
          font: { family: "monospace", size: 12, color: tooltipFont },
        },
      }));

      const layout = {
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
        // DYNAMIC MARGINS: Expand space based on titles and legend placement
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
                font: { size: 10, color: textColor },
              }
            : {
                orientation: "h",
                y: -0.1,
                x: 0.5,
                xanchor: "center",
                font: { size: 10, color: textColor },
              },
        xaxis: {
          gridcolor: majorGrid,
          showgrid: this.config.grid !== "none",
          minor: { showgrid: this.config.grid === "all", gridcolor: minorGrid },
          zeroline: false,
          tickfont: { color: textColor },
          title: {
            text: this.config.xAxisTitle || this.config.xAxis, // Fallback to column name
            font: { size: 11, color: textColor, family: "monospace" },
          },
          showspikes: showX,
          spikemode: "across",
          spikelinecolor: spikeColor,
          spikethickness: 0.5,
          spikedash: "solid",
        },
        yaxis: {
          gridcolor: majorGrid,
          showgrid: this.config.grid !== "none",
          minor: { showgrid: this.config.grid === "all", gridcolor: minorGrid },
          zeroline: false,
          tickfont: { color: textColor },
          title: {
            text: this.config.yAxisTitle,
            font: { size: 11, color: textColor, family: "monospace" },
          },
          showspikes: showY,
          spikemode: "across",
          spikelinecolor: spikeColor,
          spikethickness: 0.5,
          spikedash: "solid",
        },
      };

      Plotly.newPlot("plot-area", traces, layout, {
        responsive: true,
        displaylogo: false,
        modeBarButtonsToRemove: ["toImage"],
      });
    },
  };
}
