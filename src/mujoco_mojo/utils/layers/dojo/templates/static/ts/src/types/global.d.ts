import type { Alpine as AlpineType } from "alpinejs";

declare global {
  const Alpine: AlpineType;

  // Minimal Plotly surface used by trial-viewer
  const Plotly: {
    react(
      el: string | HTMLElement,
      data: object[],
      layout: object,
      config?: object,
    ): Promise<void>;
    newPlot(
      el: string | HTMLElement,
      data: object[],
      layout: object,
      config?: object,
    ): Promise<void>;
    purge(el: string | HTMLElement): void;
    relayout(el: string | HTMLElement, update: object): Promise<void>;
    toImage(el: string | HTMLElement, opts: object): Promise<string>;
    Plots: { resize(el: HTMLElement): void };
  };

  const LZString: {
    compressToEncodedURIComponent(str: string): string;
    decompressFromEncodedURIComponent(str: string): string | null;
  };

  const iro: {
    ColorPicker: new (
      el: HTMLElement,
      options: {
        width?: number;
        height?: number;
        color?: string;
        padding?: number;
        handleRadius?: number;
        borderWidth?: number;
        borderColor?: string;
        layout?: Array<{ component: unknown; options?: object }>;
      },
    ) => {
      color: { hexString: string; set(v: string): void };
      on(event: string, callback: (color: { hexString: string }) => void): void;
    };
    ui: { Box: unknown; Slider: unknown };
  };

  const confetti: ((opts: object) => void) & {
    shapeFromText(opts: {
      text: string;
      scalar?: number;
      color?: string;
    }): unknown;
  };

  // CodeMirror 6 bundle (window.CM)
  const CM: typeof import("codemirror") &
    typeof import("@codemirror/lang-json") &
    typeof import("@codemirror/theme-one-dark") &
    typeof import("@codemirror/state") &
    typeof import("@codemirror/lint") &
    typeof import("@codemirror/language");

  // Globals exposed by the compiled bundles for Alpine x-data usage
  interface Window {
    formatTimeAgo(seconds: number): string;
    notifTimeAgo(timestamp: number, tick?: number): string;
    trialViewer(trialId: string, externalUrl: string): object;
    monitor(): object;
    mosaic(): object;
    sensai(): object;
    sensaiMsgData(role: string): object;
    downloadSensAIHistory(): void;
    renderMarkdown(text: string): string;
    initSensAICodeBlocks(container: HTMLElement): void;
    // Signal Lab - defined in _signal_lab.html, called from trial-viewer.ts
    mojoLabSelectNodeColumn?(nodeId: number, col: string): void;
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
