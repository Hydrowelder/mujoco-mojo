// re-exports the CodeMirror pieces trial-viewer.ts and sensai.ts use, in one
// place, mirroring what the old esbuild-only `cm-bundle.ts` -> window.CM
// indirection used to provide as a global. Under Vite, shared dependencies
// like these are deduped natively within a bundle, so this is just for a
// single shared import path -- not a separate build step anymore.
export { EditorView, basicSetup } from "codemirror";
export { hoverTooltip } from "@codemirror/view";
export type { Tooltip } from "@codemirror/view";
export { json, jsonParseLinter } from "@codemirror/lang-json";
export { oneDarkHighlightStyle } from "@codemirror/theme-one-dark";
export { EditorState, Compartment } from "@codemirror/state";
export { linter, lintGutter, forceLinting } from "@codemirror/lint";
export type { Diagnostic } from "@codemirror/lint";
export { syntaxHighlighting, defaultHighlightStyle, syntaxTree, StreamLanguage } from "@codemirror/language";
export type { Extension } from "@codemirror/state";
// Python and shell are the small stream parsers from legacy-modes (a few KB each), not the full Lezer grammars, which would add four times as much to the bundle
export { python as pythonMode } from "@codemirror/legacy-modes/mode/python";
export { shell as shellMode } from "@codemirror/legacy-modes/mode/shell";
// colors a token through a plain CSS class (tok-string, tok-number, ...), so what draws it can be CSS and follow the light/dark toggle
export { classHighlighter } from "@lezer/highlight";
export type { SyntaxNode } from "@lezer/common";
