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
    // Signal Lab - defined in _signal_lab.html, called from trial-viewer.ts
    mojoLabSelectNodeColumn?(nodeId: number, col: string): void;
    mojoLabUndo?(): void;
    mojoLabRedo?(): void;
  }
}

// Alpine magic properties injected at runtime into component `this`
export interface AlpineMagics {
  $nextTick(callback?: () => void): Promise<void>;
  $watch<T>(
    expr: string,
    callback: (value: T, oldValue: T) => void,
  ): () => void;
  $refs: Readonly<Record<string, HTMLElement | undefined>>;
}
