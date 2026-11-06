import { defineConfig } from "vitest/config";

// kept separate from vite.config.ts on purpose: that file is the production
// build and the dev server (Tailwind, the static copy, the proxy to the
// Dojo), none of which tests need. tests run in plain Node by default; a test
// that needs a DOM (localStorage, document) opts in per file with a
// `// @vitest-environment happy-dom` comment on its first line, so the
// pure-logic tests stay fast and can't lean on browser globals by accident.
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
    coverage: {
      provider: "v8",
      // every source file, not just the ones a test happens to import, so the
      // report shows what is untested instead of leaving it out and looking
      // better than it is
      include: ["src/**/*.ts"],
      exclude: ["src/**/*.test.ts", "src/**/*.d.ts"],
      // skipFull: false so a file at 100% still gets a row; by default it is
      // hidden, which reads as "not covered at all"
      reporter: [["text", { skipFull: false }], "html"],
    },
  },
});
