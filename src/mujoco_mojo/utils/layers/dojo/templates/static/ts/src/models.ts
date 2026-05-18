import type {
  DashStyle,
  GridMode,
  HoverMode,
  InterpMode,
  LegendPos,
  LineMode,
  MarkerSymbol,
  ScaleType,
} from './lib/options';

// ---------------------------------------------------------------------------
// Backend API shapes
// ---------------------------------------------------------------------------

export interface JobStatus {
  n_done: number;
  n_success: number;
  n_failed: number;
  n_remaining: number;
  n_trial: number;
  progress: number;
  success_tns: string[];
  failure_tns: string[];
  padding_style: string;
  throughput: string;
  avg_duration: string;
  elapsed: string;
  start_time: string;
  time_remaining: string;
  end_time: string;
  is_complete: boolean;
  error?: string;
}

export interface TrialManifest {
  trials: string[];
}

export interface TrialDataResponse {
  columns: {
    all: string[];
    rotateable_vectors: string[];
  };
  data: Record<string, number[]>;
}

// ---------------------------------------------------------------------------
// Plot configuration (the serialized state stored in localStorage / URL)
// ---------------------------------------------------------------------------

export interface YAxisConfig {
  label: string;
  color: string;
  width: number;
  opacity: number;
  scale: string;
  dash: DashStyle;
  marker: MarkerSymbol;
}

export interface Annotation {
  x: number;
  y: number;
  text: string;
}

export interface Shape {
  type: 'vline' | 'hline' | 'rect';
  x0: number;
  x1?: number;
  y0?: number;
  y1?: number;
  color: string;
  dash?: DashStyle;
  label: string;
}

export interface PlotConfig {
  xAxis: string;
  yAxes: Record<string, YAxisConfig>;
  refFrame: string | null;
  grid: GridMode;
  linemode: LineMode;
  interp: InterpMode;
  hover: HoverMode;
  title: string;
  xAxisTitle: string;
  yAxisTitle: string;
  showSpike: boolean;
  legendPos: LegendPos;
  rangeX: [number, number] | null;
  rangeY: [number, number] | null;
  xScale: ScaleType;
  yScale: ScaleType;
  xLogBase?: number;
  yLogBase?: number;
  vsEnabled: boolean;
  vsRange: [number, number];
  annotations: Annotation[];
  shapes: Shape[];
}

// ---------------------------------------------------------------------------
// Alpine store shape (used for typed store access across components)
// ---------------------------------------------------------------------------

export interface DojoStore {
  isPageReady: boolean;
  isFullscreen: boolean;
  isComplete: boolean;
  isMuted: boolean;
  isAutoRefresh: boolean;
  isConnected: boolean;
  isSyncing: boolean;
  syncProgress: number;
  secondsSinceUpdate: number;
  lastUpdate: number | null;
  source: EventSource | null;
  startGlobalSync(): void;
  stopGlobalSync(): void;
  setPageReady(val: boolean, force?: boolean): void;
  updateSync(timestamp: number, isComplete?: boolean): void;
}
