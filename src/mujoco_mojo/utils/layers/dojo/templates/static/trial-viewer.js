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
    editorOpen: false, // Controls the visibility of the JSON editor drawer
    ySearch: "",
    columns: [],
    showToast: false,
    toastMessage: "",

    // --- SINGLE SOURCE OF TRUTH: PLOT CONFIGURATION ---
    // This object is the master state. Changes here trigger re-renders.
    config: {
      xAxis: "time",
      yAxes: [],
      grid: "all",
      linemode: "lines", // Renamed from markerMode for clarity
      interp: "linear", // line interpolation (linear, spline, etc)
      hover: "x unified",
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
        const decoded = atob(blob.replace(/-/g, "+").replace(/_/g, "/"));
        const parsed = JSON.parse(decoded);

        // We only merge the config; we no longer touch documentElement.classList
        this.config = { ...this.config, ...parsed };

        this.toastMessage = "Shared view loaded";
        this.showToast = true;
        setTimeout(() => (this.showToast = false), 3000);
      } catch (e) {
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
        const encoded = btoa(minified)
          .replace(/\+/g, "-")
          .replace(/\//g, "_")
          .replace(/=+$/, "");

        const shareBase = this.externalUrl + window.location.pathname;
        const finalUrl = `${shareBase}?v=${encoded}`;

        // 1. Attempt the modern "Kosher" way first
        if (navigator.clipboard && window.isSecureContext) {
          navigator.clipboard.writeText(finalUrl).then(() => {
            this.notifySuccess();
          });
        } else {
          // 2. Fallback for Local IPs / Insecure Contexts
          const textArea = document.createElement("textarea");
          textArea.value = finalUrl;

          // Ensure it's invisible but part of the DOM
          textArea.style.position = "fixed";
          textArea.style.left = "-9999px";
          textArea.style.top = "0";
          document.body.appendChild(textArea);

          textArea.focus();
          textArea.select();

          try {
            // for now, this method is a fallback. execCommand is only being used
            // since this feature is only useful while not on localhost or https
            // dojo is most likely served on http so this is needed
            const successful = document.execCommand("copy");
            if (successful) this.notifySuccess();
          } catch (err) {
            console.error("Fallback copy failed", err);
          }

          document.body.removeChild(textArea);
        }
      } catch (e) {
        console.error("Link generation failed", e);
      }
    },

    notifySuccess() {
      this.toastMessage = "Shareable link copied!";
      this.showToast = true;
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
      const tooltipBorder = tw.cyan[500];
      const spikeColor = isDark ? tw.cyan[500] : tw.slate[400];

      // Map traces from selected signals
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
        namelength: -1, // Full name display in tooltips
        hoverlabel: {
          bgcolor: tooltipBg,
          bordercolor: tooltipBorder,
          font: {
            family: "monospace",
            size: 12,
            color: isDark ? "#f8fafc" : "#0f172a",
          },
        },
      }));

      const layout = {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        margin: { t: 20, r: 20, b: 40, l: 60 },
        hovermode: this.config.hover,
        hoverlabel: {
          bgcolor: tooltipBg,
          bordercolor: tooltipBorder,
          font: {
            family: "monospace",
            size: 12,
            color: isDark ? "#f8fafc" : "#0f172a",
          },
          align: "left",
        },
        showlegend: true,
        legend: {
          font: { size: 10, color: textColor },
          orientation: "h",
          y: -0.2,
        },
        xaxis: {
          gridcolor: majorGrid,
          showgrid: this.config.grid !== "none",
          minor: { showgrid: this.config.grid === "all", gridcolor: minorGrid },
          zeroline: false,
          tickfont: { color: textColor },
          title: {
            text: this.config.xAxis,
            font: { size: 10, color: textColor, family: "monospace" },
          },

          // Unified Hover Spikes
          showspikes: true,
          spikemode: "across",
          spikesnap: "cursor",
          spikelinecolor: spikeColor,
          spikethickness: 1,
          spikedash: "solid",
          hoverlabel: {
            bgcolor: tooltipBg,
            font: { color: isDark ? "#f8fafc" : "#0f172a" },
          },
        },
        yaxis: {
          gridcolor: majorGrid,
          showgrid: this.config.grid !== "none",
          minor: { showgrid: this.config.grid === "all", gridcolor: minorGrid },
          zeroline: false,
          tickfont: { color: textColor },
        },
      };

      Plotly.newPlot("plot-area", traces, layout, {
        responsive: true,
        displayModeBar: true,
        displayLogo: false,
        modeBarButtonsToRemove: [],
      });
    },
  };
}
