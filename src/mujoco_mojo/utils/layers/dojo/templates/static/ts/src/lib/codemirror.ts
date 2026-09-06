// re-exports the CodeMirror pieces trial-viewer.ts and sensai.ts use, in one
// place, mirroring what the old esbuild-only `cm-bundle.ts` -> window.CM
// indirection used to provide as a global. Under Vite, shared dependencies
// like these are deduped natively within a bundle, so this is just for a
// single shared import path -- not a separate build step anymore.
export { EditorView, basicSetup } from "codemirror";
export { json, jsonParseLinter } from "@codemirror/lang-json";
export { oneDarkHighlightStyle } from "@codemirror/theme-one-dark";
export { EditorState, Compartment } from "@codemirror/state";
export { linter, lintGutter } from "@codemirror/lint";
export { syntaxHighlighting, defaultHighlightStyle } from "@codemirror/language";
