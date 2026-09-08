import type { Alpine as AlpineType } from "alpinejs";

declare global {
  // Only store.ts (bundled into main.js, loaded on every page) does the
  // real `import Alpine from "alpinejs"` and assigns it to window.Alpine --
  // every other entry bundle (monitor.js, trial-viewer.js, ...) loads
  // alongside main.js on the same page but is a *separate* Vite/Rollup
  // module graph, so a second `import` there would bundle a second, disjoint
  // copy of Alpine with its own disconnected store state. Referencing the
  // bare `Alpine` global (typed here, actually window.Alpine set by
  // store.ts) keeps every page sharing the one real instance, same as the
  // vendored CDN script's global did before this migration.
  const Alpine: AlpineType;

  // Globals exposed by the compiled bundles for Alpine x-data usage
  interface Window {
    Alpine: AlpineType;
    // dojo.default_to_fullscreen (settings.py) - set by a plain inline
    // script in base.html's <head>, read once by store.ts when it builds
    // isFullscreen's initial value. A plain classic script (base.html's)
    // always finishes running before any type="module" script (main.js
    // included) even starts, since module scripts don't begin executing
    // until the whole document has finished parsing - so this is
    // guaranteed to be set by the time store.ts's alpine:init handler
    // reads it, regardless of where in the document either script tag
    // sits.
    __mojoDefaultToFullscreen?: boolean;
    formatTimeAgo(seconds: number): string;
    notifTimeAgo(timestamp: number, tick?: number): string;
    themeColor(name: string): string;
    trialViewer(trialId: string, externalUrl: string, showQuickFilters: boolean): object;
    monitor(): object;
    mosaic(): object;
    sensai(): object;
    sensaiMsgData(role: string): object;
    downloadSensAIHistory(): void;
    renderMarkdown(text: string): string;
    initSensAICodeBlocks(container: HTMLElement): void;
    // iro.js color-picker construction, called from _macros.html's
    // color_picker macro (the $watch/color:change wiring around the
    // returned picker stays inline there since it needs Alpine's reactive
    // scope, which can't cross into a bundled TS module cleanly)
    mojoCreateColorPicker(
      el: HTMLElement,
      width: number,
      boxHeight: number,
      initialColor: string,
    ): { color: { hexString: string; set(v: string): void }; on(event: string, callback: (color: { hexString: string }) => void): void };
    // _settings_panel.html's per-field color picker isn't bundled TS either
    // (built at runtime from the schema). VisualizationSettings accepts
    // either a Color enum member name or a raw hex code, so these are purely
    // informational/display helpers, not value coercion: the closest named
    // Color to an arbitrary hex, and resolving a field's current value (a
    // name or a hex) to the hex string used to paint a swatch/the wheel.
    mojoNearestColorName(hex: string, choices: Record<string, string>): string;
    mojoResolveColorHex(
      value: string | null | undefined,
      choices: Record<string, string>,
    ): string | null;
    mojoIsHexColor(value: unknown): boolean;
    // collapses a hex that exactly matches a named swatch back to that name
    // (mirrors Color.parse's own alias-collapsing server-side), for
    // immediate feedback rather than waiting on a save+reload round trip.
    mojoCollapseColorAlias(
      value: string | null | undefined,
      choices: Record<string, string>,
    ): string | null | undefined;
    // Signal Lab - defined in _signal_lab.html, called from trial-viewer.ts
    mojoLabSelectNodeColumn?(nodeId: number, col: string): void;
    mojoLabSelectNodeQuat?(nodeId: number, base: string): void;
    mojoLabSelectNodeTemplate?(nodeId: number, name: string): void;
    // Replaces the active tab's clean baseline with its current live state
    // (e.g. after a successful save, or clearing the graph)
    mojoLabRebaseline?(): void;
    mojoLabHasUnsavedChanges?(): boolean;
    mojoLabUndo?(): void;
    mojoLabRedo?(): void;
    // Immediately runs any pending debounced undo-history snapshot
    mojoLabFlushSnapshot?(): void;
    // Drops a closed tab's undo/redo history stack
    mojoLabDiscardHistory?(tabId: string): void;
    // Discards in-progress edits, restoring the graph to the last saved/loaded baseline
    mojoLabRevertToSaved?(): void;
    mojoLabArrange?(): void;
    mojoLabFitView?(): void;
    mojoLabSerialize?(): object | null;
    // Generic async confirm dialog (replaces native confirm())
    mojoConfirm?(opts: {
      title: string;
      message: string;
      confirmLabel?: string;
      cancelLabel?: string;
      variant?: "danger" | "warning" | "info";
    }): Promise<boolean>;
    // Generic async text-input dialog (replaces native prompt()) - resolves to
    // the trimmed input string, or null if cancelled / left blank.
    mojoPrompt?(opts: {
      title: string;
      message?: string;
      confirmLabel?: string;
      cancelLabel?: string;
      variant?: "danger" | "warning" | "info";
      placeholder?: string;
      value?: string;
    }): Promise<string | null>;
    // Baseline bridge: _signal_lab.html never caches its own copy of "what does
    // clean look like" - it always reads/writes the active tab's LabTab.savedState
    // (the single source of truth, owned by trial-viewer.ts) through these.
    mojoLabGetBaseline?(): string | null;
    mojoLabSetBaseline?(state: string | null): void;
    // Returns the canvas's current pan/zoom so it can be cached per tab
    mojoLabGetViewport?(): { scale: number; offset: [number, number] } | null;
    mojoLabOnDirtyChange?: ((dirty: boolean) => void) | null;
  }
}

// Alpine magic properties injected at runtime into component `this`
export interface AlpineMagics {
  $el: HTMLElement;
  $nextTick(callback?: () => void): Promise<void>;
  $watch<T>(
    expr: string,
    callback: (value: T, oldValue: T) => void,
  ): () => void;
  $refs: Readonly<Record<string, HTMLElement | undefined>>;
}
