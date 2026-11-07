import { resolve } from "path";
import { defineConfig, type Plugin } from "vite";
import tailwindcss from "@tailwindcss/vite";
import { viteStaticCopy } from "vite-plugin-static-copy";
import entries from "./entries.json" with { type: "json" };

// entries.json maps each built file name to its source. It is the one list
// shared by this build (below) and by shared.py's asset(), which points the
// templates at these sources instead of the built files while the dev server
// is in use (scripts/dev_dojo.sh).

// where the Dojo itself listens while the dev server fronts it
// (scripts/dev_dojo.sh sets this)
const DOJO_TARGET = process.env.DOJO_TARGET ?? "http://127.0.0.1:8000";

// how each Dojo path is proxied. the browser's own Host header is kept
// (changeOrigin is what Vite's string form of an entry turns on, and it
// rewrites Host to the Dojo's address): the Dojo builds absolute URLs from it,
// like the redirect from /monitor to /monitor/, and with Host rewritten that
// sent the browser off Vite to the Dojo's own port, which serves none of the
// sources
const toDojo = { target: DOJO_TARGET, changeOrigin: false };

// the Jinja templates are siblings of this ts/ directory, not descendants of
// it, so they sit outside Vite's module graph
const TEMPLATES_DIR = resolve(import.meta.dirname, "../..");

// a built file name's key in Rollup's `input`: JS entries are keyed by name
// without the extension (entryFileNames adds `.js` back), while main.css is
// keyed `main_css` since `main` is already taken by store.ts (see
// assetFileNames below).
function inputKey(file: string): string {
  return file.endsWith(".css")
    ? file.replace(/\.css$/, "_css")
    : file.replace(/\.js$/, "");
}

// Vite never notices a template edit on its own (see TEMPLATES_DIR), and the
// Alpine markup in them is half of any UI change. Once the folder is watched,
// Vite reloads the page whenever an .html file in it is saved, and Jinja
// re-reads the file on the next request by itself.
function watchTemplates(): Plugin {
  return {
    name: "dojo-watch-templates",
    apply: "serve",
    configureServer(server) {
      server.watcher.add(TEMPLATES_DIR);
    },
  };
}

// Dojo has no HTML entry points of its own (Jinja2 templates own the
// <script>/<link> tags and reference these outputs by fixed path), so every
// page bundle and the CSS bundle are listed explicitly as Rollup inputs
// rather than using Vite's default index.html-driven app mode.
export default defineConfig({
  // plotly.js's polar trace code (scatterpolar -> its d3 dependencies)
  // references the bare Node global `global` at module-eval time; browsers
  // have no such global, so without this it throws "global is not defined"
  // as soon as that chunk loads, before any chart is even drawn. The dev
  // server doesn't rewrite its pre-bundled dependencies this way; it defines
  // `global` at runtime instead, from the env module its client loads first
  // (hence base.html loading /@vite/client ahead of every other script).
  define: {
    global: "globalThis",
  },
  plugins: [
    tailwindcss(),
    watchTemplates(),
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
  // `npm run dev` (via scripts/dev_dojo.sh): the browser talks to this server,
  // which serves the TypeScript sources straight from src/ (the templates
  // point at them when MOJO_DOJO_DEV is set, see shared.py) and proxies every
  // path the Dojo owns through to it, so nothing needs building to test an
  // edit. The built dist/ is only what ships.
  server: {
    port: 5173,
    // dist/ is rebuilt by `npm run build` and must not trigger a reload, and
    // the __pycache__ folders are churn from the Dojo itself.
    watch: { ignored: ["**/static/dist/**", "**/__pycache__/**"] },
    proxy: {
      // the Dojo's root, which redirects to /monitor
      "^/$": toDojo,
      "/monitor": toDojo,
      "/mosaic": toDojo,
      "/morph": toDojo,
      "/settings": toDojo,
      "/sensai": toDojo,
      "/changelog": toDojo,
      "/mojo-static": toDojo,
      // the well-known paths browsers probe directly (see main.py)
      "/favicon.ico": toDojo,
      "/apple-touch-icon.png": toDojo,
      "/favicon-32x32.png": toDojo,
      "/favicon-16x16.png": toDojo,
      // the Optuna dashboard (morph.py) is mounted at the Dojo's root
      "/dashboard": toDojo,
      "/api": toDojo,
      "/static": toDojo,
    },
  },
  optimizeDeps: {
    // with no index.html there is nothing for Vite to crawl for the
    // dependencies to pre-bundle, so it would discover each one as the page
    // first imports it and reload the page every time it found another. Naming
    // the entries up front lets it find them all at startup.
    entries: Object.values(entries).filter((src) => src.endsWith(".ts")),
  },
  build: {
    outDir: resolve(import.meta.dirname, "../dist"),
    emptyOutDir: true,
    sourcemap: true,
    target: "es2020",
    rollupOptions: {
      input: Object.fromEntries(
        Object.entries(entries).map(([file, src]) => [
          inputKey(file),
          resolve(import.meta.dirname, src),
        ]),
      ),
      output: {
        // fixed, non-hashed names for every entry: templates reference
        // these paths directly (no manifest-based resolution), same
        // convention flask-website's own Vite setup uses.
        entryFileNames: "[name].js",
        // same reasoning extended to shared/vendor chunks (plotly, and
        // whatever else Rollup splits out across entries): static/dist/ is
        // committed to git (see CLAUDE.md), so a content hash here doesn't
        // just bust CDN caches the way it would on a normal deployed site --
        // it renames a multi-hundred-KB file on essentially every build,
        // even ones that never touch that chunk's actual code, because the
        // hash also shifts whenever the shared-chunk graph or build config
        // changes elsewhere. A stable name means git only sees a real diff
        // when the chunk's own output actually changes.
        chunkFileNames: "assets/[name].js",
        // the CSS entry's input key can't just be "main" (the store.ts JS
        // entry already claims that key in `input` above), so it's keyed
        // "main_css" and renamed back to main.css here.
        assetFileNames: (asset) =>
          asset.name === "main_css.css" ? "main.css" : "[name][extname]",
      },
    },
  },
});
