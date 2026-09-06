import { resolve } from "path";
import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import { viteStaticCopy } from "vite-plugin-static-copy";

// Dojo has no HTML entry points of its own (Jinja2 templates own the
// <script>/<link> tags and reference these outputs by fixed path), so every
// page bundle and the CSS bundle are listed explicitly as Rollup inputs
// rather than using Vite's default index.html-driven app mode.
export default defineConfig({
  // plotly.js's polar trace code (scatterpolar -> its d3 dependencies)
  // references the bare Node global `global` at module-eval time; browsers
  // have no such global, so without this it throws "global is not defined"
  // as soon as that chunk loads, before any chart is even drawn.
  define: {
    global: "globalThis",
  },
  plugins: [
    tailwindcss(),
    // litegraph.js's npm build is a bare global-assigning IIFE with no
    // module exports (verified: `(function(global) { var LiteGraph =
    // (global.LiteGraph = {...}) })(this)`), so it can't be bundled via
    // `import` the way the other libraries are -- it's copied as-is into
    // the build output and loaded via a classic <script> tag instead, same
    // as it was vendored before, just npm-managed for version tracking now.
    viteStaticCopy({
      targets: [
        {
          src: "node_modules/litegraph.js/build/litegraph.js",
          dest: "vendored",
          rename: { stripBase: true },
        },
        {
          src: "node_modules/litegraph.js/css/litegraph.css",
          dest: "vendored",
          rename: { stripBase: true },
        },
        // marks static/dist/ as a package for hatchling's wheel build to
        // pick up, matching static/__init__.py and static/vendored/__init__.py
        {
          src: "static-pkg/__init__.py",
          dest: ".",
          rename: { stripBase: true },
        },
      ],
    }),
  ],
  resolve: {
    alias: {
      // plotly.js's registry.js has an unconditional-at-parse-time (but
      // dead at runtime for us) `require("maplibre-gl/dist/maplibre-gl.css")`
      // reached only when registering a "map" (mapbox/maplibre) trace type
      // -- Dojo only registers bar/scatter/scatterpolar (see lib/plotly.ts),
      // so that branch never actually runs, but Vite's static analysis
      // still bundled the 70kB CSS file into the build. Aliased to an inert
      // module so it costs nothing instead.
      "maplibre-gl/dist/maplibre-gl.css": resolve(import.meta.dirname, "src/lib/empty.ts"),
    },
  },
  build: {
    outDir: resolve(import.meta.dirname, "../dist"),
    emptyOutDir: true,
    sourcemap: true,
    target: "es2020",
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, "src/store.ts"),
        monitor: resolve(import.meta.dirname, "src/monitor.ts"),
        mosaic: resolve(import.meta.dirname, "src/mosaic.ts"),
        "trial-viewer": resolve(import.meta.dirname, "src/trial-viewer.ts"),
        sensai: resolve(import.meta.dirname, "src/sensai.ts"),
        main_css: resolve(import.meta.dirname, "src/styles/main.css"),
      },
      output: {
        // fixed, non-hashed names for every entry: templates reference
        // these paths directly (no manifest-based resolution), same
        // convention flask-website's own Vite setup uses.
        entryFileNames: "[name].js",
        // the CSS entry's input key can't just be "main" (the store.ts JS
        // entry already claims that key in `input` above), so it's keyed
        // "main_css" and renamed back to main.css here.
        assetFileNames: (asset) =>
          asset.name === "main_css.css" ? "main.css" : "[name][extname]",
      },
    },
  },
});
