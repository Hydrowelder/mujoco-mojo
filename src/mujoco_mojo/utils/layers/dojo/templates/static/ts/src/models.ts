export type {
  Annotation,
  DashStyle,
  FilterEntry,
  GridMode,
  HoverMode,
  InterpMode,
  LegendPos,
  LineMode,
  MarkerSymbol,
  PlotConfig,
  ScaleType,
  Shape,
  YAxisConfig,
} from "./lib/plot-config.generated";

// ---------------------------------------------------------------------------
// Backend API shapes
// ---------------------------------------------------------------------------

export interface TimelineBin {
  t: number;
  label: string;
  n_success: number;
  n_failed: number;
  n_error: number;
  n_running: number;
  n_pending: number;
}

export interface JobStatus {
  n_done: number;
  n_success: number;
  n_failed: number;
  n_error: number;
  n_remaining: number;
  n_trial: number;
  progress: number;
  success_tns: string[];
  failure_tns: string[];
  error_tns: string[];
  failure_tns_with_db: string[];
  error_tns_with_db: string[];
  last_success_tn: number | null;
  last_failure_tn: number | null;
  last_error_tn: number | null;
  padding_style: string;
  throughput: string;
  avg_duration: string;
  elapsed: string;
  start_time: string;
  time_remaining: string;
  end_time: string;
  is_complete: boolean;
  timeline?: TimelineBin[];
  error?: string;
}

export interface StepStatus {
  started: string | null;
  elapsed: number | null;
}

export interface RequirementResult {
  name: string;
  passed: boolean;
  message: string;
  decided_at: number;
  every: number | null;
  terminate_on_fail: boolean;
  terminate_on_pass: boolean;
  latch_on_fail: boolean;
  latch_on_pass: boolean;
}

export interface TrialStatus {
  trial_num: number;
  step: "pending" | "generating" | "solving" | "done";
  completion: "incomplete" | "success" | "failure" | "terminated" | "error";
  pending: StepStatus;
  generating: StepStatus;
  solving: StepStatus;
  requirements: RequirementResult[];
  requirements_passed: boolean | null;
}

export interface TrialManifest {
  trials: string[];
}

export interface TrialMediaFile {
  name: string;
  fps: number | null;
  mtime: number;
}

export interface TrialMediaResponse {
  files: TrialMediaFile[];
}

export interface LogEntry {
  timestamp: number; // ms epoch
  level: string;
  pathname: string;
  lineno: number | null;
  message: string;
}

export interface TrialLogsResponse {
  filename: string | null;
  entries: LogEntry[];
}

export interface TrialDataResponse {
  columns: {
    all: string[];
    rotatable_vectors: string[];
    available_quats: string[];
    column_metadata: Record<string, Record<string, string>>;
  };
  data: Record<string, number[]>;
  filter_errors?: string[];
}

// ---------------------------------------------------------------------------
// Filter stack (per-signal server-side transformations)
// ---------------------------------------------------------------------------

export interface FilterParamSchema {
  name: string;
  type: "float" | "int" | "bool" | "string" | "col" | "select";
  default: number | boolean | string | null;
  options?: string[];
  min?: number;
  max?: number;
  exclusive_min?: number;
  exclusive_max?: number;
}

export interface UnitGroup {
  label: string;
  units: string[];
  dimension?: string;
}

export interface FilterSchema {
  type: string;
  label: string;
  description: string;
  category?: string;
  params: FilterParamSchema[];
  unit_groups?: UnitGroup[];
}

// ---------------------------------------------------------------------------
// Distribution viewer
// ---------------------------------------------------------------------------

export type DistChartType =
  | "continuous"
  | "discrete"
  | "categorical"
  | "permutation"
  | "none";

export interface DistEntry {
  name: string;
  dist_type: string;
  category: string;
  units: string;
  nominal: number | null;
  nominal_label: string | null;
  sampled_value: number | null;
  sampled_values: number[] | null;
  sampled_labels: string[] | null;
  sampled_permutations: (string | number)[][] | null;
  z_score: number | null;
  percentile: number | null;
  is_discrete: boolean;
  chart_type: DistChartType;
  pdf_x: number[];
  pdf_y: number[];
  cdf_x: number[];
  cdf_y: number[];
  cat_labels: string[];
  cat_probs: number[];
  params: Record<string, string | number | boolean>;
}

export interface DistsResponse {
  entries: DistEntry[];
}

// PlotConfig and related types are generated from plot_config.py - see the
// re-exports at the top of this file and lib/plot-config.generated.ts.

// ---------------------------------------------------------------------------
// Notification history
// ---------------------------------------------------------------------------

export interface NotificationEntry {
  id: number;
  message: string;
  type: "success" | "error" | "info";
  timestamp: number;
  read: boolean;
}

// ---------------------------------------------------------------------------
// Alpine store shape (used for typed store access across components)
// ---------------------------------------------------------------------------

export interface DojoStore {
  isPageReady: boolean;
  isFullscreen: boolean;
  overlayCount: number;
  isComplete: boolean;
  isMuted: boolean;
  isAutoRefresh: boolean;
  isConnected: boolean;
  _wasConnected: boolean | null;
  globalToast: {
    show: boolean;
    message: string;
    type: "success" | "error" | "info";
  };
  isSyncing: boolean;
  syncProgress: number;
  secondsSinceUpdate: number;
  lastUpdate: number | null;
  source: EventSource | null;
  notifications: NotificationEntry[];
  unreadCount: number;
  notifOpen: boolean;
  notifTick: number;
  toast(message: string, type?: "success" | "error" | "info"): void;
  copyText(text: string, successMsg?: string): Promise<void>;
  _installPlotlyLogCapture(): void;
  _setConnected(connected: boolean): void;
  startGlobalSync(): void;
  stopGlobalSync(): void;
  setPageReady(val: boolean, force?: boolean): void;
  updateSync(timestamp: number, isComplete?: boolean): void;
  addNotification(message: string, type: "success" | "error" | "info"): void;
  openNotifications(): void;
  clearNotifications(): void;
  dialog: {
    show: boolean;
    title: string;
    message: string;
    confirmLabel: string;
    cancelLabel: string;
    variant: "danger" | "warning" | "info";
    open(opts: {
      title: string;
      message: string;
      confirmLabel?: string;
      cancelLabel?: string;
      variant?: "danger" | "warning" | "info";
    }): Promise<boolean>;
    confirm(): void;
    cancel(): void;
  };
}
