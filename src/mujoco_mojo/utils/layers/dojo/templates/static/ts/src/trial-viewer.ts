import { enumMapOf } from "./lib/enum-axes";
import {
  breakableLabel,
  formatNum,
  formatPercentile,
  formatSampled,
  formatSigFig,
  relativeTime,
} from "./lib/format";
import { evalMathExpr } from "./lib/math-expr";
import {
  filterColumns,
  isSearchSegmentActive,
  quatBases,
  rotatableColumns,
  searchActiveLevels,
  searchAvailableSuffixes,
  searchSegmentsAtDepth,
  smartSort,
  toggleSearchSegment,
} from "./lib/column-search";
import {
  refFrameActive,
  refFrameLabel,
  sameRefFrame,
  sanitizeRefFrame,
  withRefFrameFilter,
  type RefFrame,
} from "./lib/ref-frame";
import { jsonPathAt, jsonRangeForPath } from "./lib/json-editor";
import { decodeShareConfig, encodeShareConfig, extractShareBlob } from "./lib/share-link";
import {
  filterLogEntries,
  fittedLogColumnWidth,
  formatLogTime,
  logLevelClass,
  logLevelsOf,
  logSourceFull,
  logSourceShort,
  resizedLogColumnWidth,
} from "./lib/log-entries";
import { paddedRange, selectVsDatasets } from "./lib/plot-range";
import { validatePlotConfig } from "./lib/config-validate";
import { countInRange, countWithPinned, presetRange, togglePinned, trialBounds, trialNumber } from "./lib/vs-range";
import { pushSnapshot } from "./lib/history";
import { countBy, distinctSorted, filterDists, toggleFacet } from "./lib/dist-table";
import { highlightJson } from "./lib/json-highlight";
import {
  addFilter,
  duplicateFilter,
  effectiveUnit as unitAfterFilters,
  filterSummary,
  getUnitOptions,
  groupFilterSchemas,
  moveFilter,
  removeFilter,
  setFilterParam,
} from "./lib/filter-stack";
import { nextAvailableStyle as pickNextStyle } from "./lib/plot-style";
import {
  errorStep as trialErrorStep,
  stepDotClass as trialStepDotClass,
  stepTextClass as trialStepTextClass,
  trialOutcome,
  trialPollAction,
  type TrialStep,
} from "./lib/trial-status";
import { newYAxisConfig, reorderYAxes, usedStyles, withoutYAxis, yRangeToggles } from "./lib/y-axes";
import { applyRangeBound, rangeBoundText, resolveAxisRange as resolveRange } from "./lib/axis-range";
import {
  DEFAULT_CONFIG,
  hasPlotDefault,
  isPlotFieldDefault,
  plotDefaultCopy,
  shapeDefName,
  withDefaultNote,
} from "./lib/plot-defaults";
import { OPTIONS } from "./lib/options";
import {
  buildTreeRows,
  buildTreeRowsFromNames,
  visibleTreeRows,
  allTreeFolderPaths,
  sortTreeItems,
  type TreeRow,
  type TreeSortMode,
  type TreeSortDirection,
} from "./lib/tree";
import { themeColor, themeColorAlpha } from "./lib/theme-colors";
import {
  newTabId,
  loadTabsFromStorage,
  persistTabsToStorage,
  reorderTabs,
  pickNextActiveOnClose,
  selectRange,
  toggleSelection,
} from "./lib/tab-session";
import type { PlotProfile } from "./lib/plot-profile";
import {
  closedPlotTabEntry,
  duplicatePlotTab as copyPlotTab,
  isPlotTabDirty,
  loadClosedPlotTabs,
  makeBlankPlotTab,
  neededColumns,
  persistClosedPlotTabs,
  persistablePlotTabs,
  pushClosedPlotTabs,
  reopenPlotTab,
  type PlotTab,
} from "./lib/plot-tabs";
import {
  aspectRatio,
  framesVisible,
  frameInterval,
  frameMarkersPath,
  isScrubbable,
  knownDuration,
  loopedTime,
  mediaUrl,
  miniDragPosition,
  miniFrameReady,
  miniResizeSize,
  miniUsesVideo,
  overlayVisibility,
  pickSelectedMedia,
  shouldRunPlayback,
  snappedTime,
} from "./lib/media";
import { trialDataUrl, unseenFilterErrors } from "./lib/trial-data";
import {
  chunked,
  comparingNotice,
  missingColumns,
  orderedRange,
  parseStoredVs,
  vsActiveColumns,
  vsChipClass as chipClass,
  vsNeedsFetch,
  vsTargetIds,
} from "./lib/vs-sync";
import { parseRawConfig, parseSavedConfig, parseSavedHistory } from "./lib/config-storage";
import {
  distPlot,
  hasTooltipContent,
  paramsHtml,
  tooltipMinWidth,
  tooltipPosition,
  type DistColors,
} from "./lib/dist-plot";
import {
  csvFileName,
  csvText,
  configFileName,
  manifestFileName,
  plotExportFileName,
  plotExportSize,
  plotImageFormat,
} from "./lib/export";
import {
  activeColumns,
  needsRefFrameMigration,
  needsVsSync,
  planConfigChange,
} from "./lib/config-change";
import { paddingLength, sharedLinkDecision, withoutSharedParam } from "./lib/boot";
import { notifierText, popupCoords, relayoutRanges, scrubTime } from "./lib/plot-events";
import {
  anyPanelOpen,
  isTextInputTarget,
  shortcutsFor,
  stepPlaybackRate,
} from "./lib/shortcuts";
import {
  buildLayout,
  type LayoutColors,
} from "./lib/plot-layout";
import {
  enumContext,
  primaryTraces,
  vsTraces,
  type Series,
  type TraceContext,
} from "./lib/plot-traces";
import {
  annotationXRange,
  annotationYRange,
  isUsableText,
  placementLabel,
  plotlyAnnotations,
  plotlyShapes,
  shapeFromClick,
  upsertAt,
} from "./lib/overlays";
import {
  duplicateLabTab as copyLabTab,
  evictLabData,
  evictedPlottedColumns,
  isReusableLabTab,
  labTabFor,
  labUrl,
  legacyLabTabs,
  makeBlankLabTab,
  resolveLabSchemas,
  staleLabs,
  type LabSchema,
  type LabTab,
  type RawLabSchema,
} from "./lib/lab";
import {
  buildProfilePayload,
  profileActiveIndex,
  profileMissing,
  profileUrl,
  profileWarnings,
  saveProfileRequest,
  tabsFromProfile,
} from "./lib/profiles";
import { fetchWithTimeout, fetchWithRetry } from "./lib/fetch-timeout";
import {
  describeSchemaPath,
  describeEnumValue,
  describeDefField,
  describeFilterField,
  type JsonSchemaNode,
} from "./lib/json-schema";
import Plotly from "./lib/plotly";
import "./lib/color-picker";
import {
  EditorView,
  basicSetup,
  EditorState,
  json,
  jsonParseLinter,
  syntaxHighlighting,
  oneDarkHighlightStyle,
  defaultHighlightStyle,
  Compartment,
  linter,
  lintGutter,
  forceLinting,
  hoverTooltip,
  syntaxTree,
  type Tooltip,
  type Diagnostic,
} from "./lib/codemirror";
import { DASH_STYLE_VALUES } from "./lib/plot-config.generated";
import {
  attachVerticalResizeHandle,
  restorePersistedHeight,
} from "./lib/resize";
import { collectSchemaDiagnostics } from "./lib/schema-validate";
import { createToastMixin } from "./lib/toast";
import type { AlpineMagics } from "./types/global";
import type {
  Annotation,
  ColumnMeta,
  DashStyle,
  DistEntry,
  DistsResponse,
  DojoStore,
  FilterEntry,
  FilterSchema,
  JobStatus,
  LogEntry,
  PlotConfig,
  Shape,
  TrialDataResponse,
  TrialLogsResponse,
  TrialManifest,
  TrialMediaFile,
  TrialMediaResponse,
  TrialStatus,
  YAxisConfig,
} from "./models";

// ---------------------------------------------------------------------------
// CodeMirror editor state (kept outside Alpine to avoid proxy issues)
// ---------------------------------------------------------------------------
const _cm: {
  editor: EditorView | null;
  updating: boolean;
  debounce: ReturnType<typeof setTimeout> | null;
} = {
  editor: null,
  updating: false,
  debounce: null,
};

// the plot's element, which plotly gives a `_fullLayout` once it has drawn
interface PlotAreaEl extends HTMLElement {
  _fullLayout?: {
    xaxis: { l2p(v: number): number; range: [number, number] };
    margin: { l: number; r: number; t: number; b: number };
  };
}

function plotAreaEl(): PlotAreaEl | null {
  return document.getElementById("plot-area");
}

// miniplayer RAF state - kept outside Alpine to avoid proxy overhead
const _mini: { rafId: number | null } = { rafId: null };

// ---------------------------------------------------------------------------
// Lab tab state
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Component factory
// ---------------------------------------------------------------------------
function trialViewer(trialId: string, externalUrl: string, showQuickFilters: boolean) {
  // dojo.show_quick_filters (settings.py) - whether the X/Y-axis and
  // reference-frame dropdowns show their regex quick-filter chip rows.
  // Seeds $store.dojo.showQuickFilters (settings-panel.ts) from the
  // server-rendered initial value (routers/mosaic.py) the first time this
  // page constructs its component - templates read the store property
  // directly (not a local copy here), so if the settings panel is later
  // opened and saved in the same tab, every X/Y-axis/refFrame dropdown
  // picks up the change immediately instead of only on the next full
  // reload. Store.ts's `alpine:init` registration always runs before
  // Alpine processes this page's own x-data (see global.d.ts's comment on
  // the bare `Alpine` global), so the store already exists here.
  const _quickFiltersStore = Alpine.store("dojo") as { showQuickFilters?: boolean } | undefined;
  if (_quickFiltersStore && _quickFiltersStore.showQuickFilters === undefined) {
    _quickFiltersStore.showQuickFilters = showQuickFilters;
  }

  const self = {
    // Alpine magic (injected at runtime - declared here for TS)
    ...(null as unknown as AlpineMagics),

    // --- BASE STATE ---
    trialId,
    externalUrl,
    warpId: null as number | null,
    paddingLen: 2,
    loading: true,
    isMac: /Mac|iPhone|iPod|iPad/.test(navigator.platform),
    data: null as Record<string, number[]> | null,
    errorState: null as string | null,
    _renderedPlotType: null as string | null,

    // --- UI / MENU STATES ---
    theme: "dark",
    xMenuOpen: false,
    xSearch: "",
    yMenuOpen: false,
    ySearch: "",
    refFrameMenuOpen: false,
    refFrameSearch: "",
    refFrameOriginMenuOpen: false,
    refFrameOriginSearch: "",
    plotConfigOpen: false,
    downloadOpen: false,
    shareOpen: false,
    mergeLinkDraft: "" as string,
    activeFrame: null as string | null,
    dragCounter: 0,
    editorOpen: false,
    columns: [] as string[],
    rotateableVectors: [] as string[],
    columnMetadata: {} as Record<string, ColumnMeta>,
    discoveryId: 0,
    plotColors: [
      themeColor("accent-500"),
      themeColor("success"),
      themeColor("chart-blue"),
      themeColor("chart-violet"),
      themeColor("warning"),
      themeColor("danger"),
    ],
    dashStyles: DASH_STYLE_VALUES,

    // Toast (shared mixin)
    ...createToastMixin(),

    // Options - exposed so templates can use opts.lineMode, opts.interpLabel(...), etc.
    opts: OPTIONS,

    // --- PLOT CONFIGURATION ---
    config: JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as PlotConfig,

    // --- JSON EDITOR STATE ---
    configRaw: "",
    isValidJson: true,
    isValidConfig: true,
    configErrors: [] as string[],
    isEditingRaw: false,

    // --- PROFILES ---
    profiles: [] as Array<{ name: string; modified: number }>,
    profileWarnings: {} as Record<string, string[]>,
    profileSearch: localStorage.getItem("mojo:profile:search") ?? "",
    profilesOpen: false,
    // page-level (not a local x-data on the Profiles button) so the Ctrl+S
    // shortcut below can position the popup too, not just a direct click -
    // it lives in this component's own keydown handler, a different Alpine
    // scope than a button-local x-data could ever reach.
    profilesCoords: { top: 0, left: 0 },
    profileNameDraft: "",
    // folder-tree view (lib/tree.ts) over `profiles` - not persisted across
    // reloads, unlike settings-panel.ts's collapsed-sections map: profiles
    // are refetched fresh every time this panel opens, and their folder set
    // can change (renamed/deleted) between opens in a way settings.py's
    // fixed schema never does, so "start fully expanded" is a simpler,
    // always-correct default than tracking staleness in localStorage.
    profileTreeCollapsed: {} as Record<string, boolean>,
    // sort/filter preferences persist across reloads (like profileSearch
    // above), unlike the collapse map, since they're a standing preference
    // rather than session-local navigation state.
    profileSortMode: (localStorage.getItem("mojo:profile:sort") ??
      window.__mojoDefaultProfileSort ??
      "modified") as TreeSortMode,
    profileSortDir: (localStorage.getItem("mojo:profile:sortDir") ??
      window.__mojoDefaultProfileSortDir ??
      "desc") as TreeSortDirection,
    // falls back to dojo.hide_invalid_profiles (settings.py, seeded onto
    // window by base.html) only when the browser has never touched this
    // preference - once it has, that choice always wins, same pattern as
    // store.ts's isFullscreen.
    hideInvalidProfiles:
      localStorage.getItem("mojo:profile:hideInvalid") === null
        ? !!window.__mojoDefaultHideInvalidProfiles
        : localStorage.getItem("mojo:profile:hideInvalid") === "1",
    get profileTreeRows(): TreeRow<{ name: string; modified: number }>[] {
      // folders follow the same order as their contents in "modified" mode
      // (a folder holding the most/least recently changed profile bubbles
      // like that profile itself would) but stay alphabetical-by-name in
      // "name" mode - see buildTreeRows's own comment on folderOrder.
      return buildTreeRows(
        sortTreeItems(this.profiles, this.profileSortMode, this.profileSortDir),
        this.profileSortMode === "modified" ? "input" : "alpha",
      );
    },
    // a profile is invalid when loadProfiles() found it referencing columns/
    // frames not present in this trial (profileWarnings, populated there)
    get hasInvalidProfiles(): boolean {
      return this.profiles.some((p) => (this.profileWarnings[p.name]?.length ?? 0) > 0);
    },
    get profileVisibleRows(): TreeRow<{ name: string; modified: number }>[] {
      const q = this.profileSearch.toLowerCase();
      return visibleTreeRows(
        this.profileTreeRows,
        this.profileTreeCollapsed,
        this.profileSearch,
        (p) => p.name.toLowerCase().includes(q),
        undefined,
        (p) => (this.profileWarnings[p.name]?.length ?? 0) === 0,
        this.hideInvalidProfiles,
      );
    },
    // Re-clicking the already-active sort mode reverses its direction
    // instead of doing nothing; switching to the other mode resets to that
    // mode's own natural default direction (see sortTreeItems's comment).
    setProfileSortMode(mode: TreeSortMode) {
      if (this.profileSortMode === mode) {
        this.profileSortDir = this.profileSortDir === "asc" ? "desc" : "asc";
      } else {
        this.profileSortMode = mode;
        this.profileSortDir = mode === "name" ? "asc" : "desc";
      }
      try {
        localStorage.setItem("mojo:profile:sort", this.profileSortMode);
        localStorage.setItem("mojo:profile:sortDir", this.profileSortDir);
      } catch {}
    },
    toggleHideInvalidProfiles() {
      this.hideInvalidProfiles = !this.hideInvalidProfiles;
      try {
        localStorage.setItem(
          "mojo:profile:hideInvalid",
          this.hideInvalidProfiles ? "1" : "0",
        );
      } catch {}
    },
    toggleProfileFolder(path: string) {
      this.profileTreeCollapsed = { ...this.profileTreeCollapsed, [path]: !this.profileTreeCollapsed[path] };
    },
    expandAllProfileFolders() {
      this.profileTreeCollapsed = {};
    },
    collapseAllProfileFolders() {
      this.profileTreeCollapsed = Object.fromEntries(
        allTreeFolderPaths(this.profileTreeRows).map((p) => [p, true]),
      );
    },

    // --- FILTER SCHEMAS (loaded from /mosaic/api/filter-schema on init) ---
    filterSchemas: [] as FilterSchema[],
    // tracks the last filter fingerprint that was fetched for each col; used to detect
    // real filter changes without relying on Alpine.js's (unreliable) oldValue deep clone
    filterFingerprints: {} as Record<string, string>,
    xAxisFilterFingerprint: "[]" as string,
    // deduplicates filter error toasts so VS mode (N parallel fetches) shows each error once
    _shownFilterErrors: new Set<string>(),
    // in-progress signal editor edits that survive closing/reopening the panel
    signalDrafts: {} as Record<
      string,
      { draft: YAxisConfig; baseSnapshot: string }
    >,

    // --- PLOT CONFIG SCHEMA (loaded from /mosaic/api/plot-config-schema on
    // init) - PlotConfig's own JSON schema, Field descriptions included.
    // Single source of truth for the Plot Editor's hover-info icons
    // (_macros.html's field_help_icon, called from _chart.html) and the
    // JSON editor's CodeMirror hover tooltips (initCodeMirror below) -
    // both read this same schema via lib/json-schema.ts's
    // describeSchemaPath rather than each hand-maintaining their own copy
    // of what every field means.
    plotConfigSchema: null as JsonSchemaNode | null,
    // Most PlotConfig fields are *required* at the model level (a saved
    // profile must specify everything explicitly - see plot_config.py),
    // unlike MujocoMojoSettings where every field genuinely has a
    // permanent default - so GenerateJsonSchemaWithDefaults (settings.py)
    // has nothing to append to their description; only the handful of
    // truly-optional fields (maxPoints, displayUnitSystem, plotType) get a
    // "Default:" line from the schema itself. The real "what does a
    // brand-new plot start with" values live in this file's own
    // DEFAULT_CONFIG instead, so this falls back to that when the
    // schema's description doesn't already carry a default.
    plotFieldHelp(key: string): string {
      const description = describeSchemaPath(this.plotConfigSchema, [key]);
      return withDefaultNote(description, key);
    },
    // Same schema, but for one option within a dropdown (e.g. field "grid",
    // value "all" -> GridMode.ALL's own docstring) rather than the field as
    // a whole - see settings.py's GenerateJsonSchemaWithDefaults for where
    // per-option "x-enum-descriptions" comes from.
    plotEnumOptionHelp(key: string, value: string): string {
      return describeEnumValue(this.plotConfigSchema, [key], value);
    },
    // For the Notes (Annotation) and Shapes editors - fields on a nested
    // model rather than a top-level PlotConfig field, named directly (see
    // lib/json-schema.ts's describeDefField for why the Shape editor can't
    // just use plotFieldHelp's own path-walking here: the same field name
    // means different things across VlineShape/HlineShape/RectShape).
    plotDefFieldHelp(defName: string, fieldName: string): string {
      return describeDefField(this.plotConfigSchema, defName, fieldName);
    },
    // Same schema, for a filter-stack param (e.g. RotationFilter.originCol) -
    // named by the filter's own discriminator value ("rotation") rather than
    // its $defs class name, since that's all the filter-param editor
    // (_series_panel.html) has on hand at that point (f.type). See
    // describeFilterField for why the type -> class name mapping has to be
    // read from the schema instead of guessed.
    plotFilterFieldHelp(filterType: string, fieldName: string): string {
      return describeFilterField(this.plotConfigSchema, filterType, fieldName);
    },
    // Maps a shape's own "type" discriminator (ShapeType's values: "vline"/
    // "hline"/"rect") to its $defs name, for plotDefFieldHelp calls in the
    // Shape editor whose defName has to follow shapeDraft.type rather than
    // being fixed per call site (fields like x0/y0/dash/color are shared
    // across more than one shape type, each with its own description).
    shapeDefName,
    // --- PER-FIELD RESET (Plot Editor) ---
    // Whether config[key] currently matches DEFAULT_CONFIG[key] - drives
    // the per-field reset icon's x-show (_macros.html's field_reset_icon),
    // the same "only show a reset affordance once there's something to
    // reset" behavior the Dojo settings panel's own per-field reset icon
    // uses. JSON.stringify rather than === since a couple of these
    // (rangeX/rangeY) are small arrays, not primitives - reference
    // equality would never match even when the values are identical.
    plotFieldIsDefault(key: string): boolean {
      return isPlotFieldDefault(this.config, key);
    },
    resetPlotField(key: string) {
      if (!hasPlotDefault(key)) return;
      (this.config as unknown as Record<string, unknown>)[key] = plotDefaultCopy(key);
      this.saveAndRender();
    },

    // --- MATCHUP STATE ---
    // Page-level/workspace-wide, shared by every plot tab - which trials
    // you're comparing against isn't a single plot's concern (see
    // syncVsRange()). `vs` is the committed/applied setting; `vsDraft` below
    // is the header VS selector's own editable buffer, pushed into `vs` by
    // syncVsRange() when the user hits Apply.
    vs: {
      enabled: false,
      range: [0, 10] as [number, number],
      pinned: [] as number[],
    },
    vsDatasets: {} as Record<string, Record<string, number[]>>,
    allTrials: [] as string[],
    vsMenuOpen: false,
    vsLoading: false,
    vsDraft: {
      enabled: false,
      range: [0, 0] as [number, number],
      pinned: [] as number[],
    },
    discoveryTimeout: null as ReturnType<typeof setTimeout> | null,

    // --- HISTORY STATE ---
    historyStack: [] as string[],
    historyIndex: -1,
    isUndoing: false,
    maxHistory: 50,

    // --- ANNOTATIONS ---
    annotationsOpen: false,
    annDraft: null as Annotation | null,
    annEditIndex: null as number | null,
    // teleported (x-teleport) popup position -- lives at this top level
    // rather than in the sidebar button's own x-data, since the annotation
    // editor can also be opened by middle-clicking the chart (see the
    // mousedown listener below), which needs to set this itself rather than
    // going through the sidebar button's own @click handler.
    annCoords: { top: 0, left: 0 },

    // --- FILTER LAB ---
    labOpen: localStorage.getItem("mojo:lab:open") === "1",
    labGraph: null as object | null,
    labName: "" as string,
    labTabs: [] as LabTab[],
    labActiveTabId: null as string | null,
    // multi-select for bulk-closing/duplicating lab tabs - see the matching
    // selectedPlotTabIds fields below for the shared semantics.
    selectedLabTabIds: [] as string[],
    _labTabSelectionAnchorId: null as string | null,

    // --- PLOT TABS ---
    plotTabs: [] as PlotTab[],
    plotActiveTabId: null as string | null,
    // most-recently-closed first, capped at MAX_CLOSED_PLOT_TABS - lets any
    // close (confirmed-dirty or not) be undone via reopenLastClosedPlotTab()
    closedPlotTabs: [] as PlotTab[],
    // multi-select for bulk-closing plot tabs (shift/ctrl-click); cleared on
    // a plain click. Independent of plotActiveTabId - a tab can be selected
    // without being the one currently displayed, and vice versa.
    selectedPlotTabIds: [] as string[],
    _plotTabSelectionAnchorId: null as string | null,
    nodePickingColumn: null as number | null,
    nodeColSearch: "" as string,
    nodePickingQuat: null as number | null,
    nodeQuatSearch: "" as string,
    nodePickingOrigin: null as number | null,
    nodeOriginSearch: "" as string,
    nodePickingTemplate: null as number | null,
    labSchemas: [] as LabSchema[],
    // lifted out of the "load into new tab" dropdown's own local x-data
    // (where it lived before) up to top-level state - the tree getters
    // below need it for filtering, and getters can only close over this
    // component's own `this`, not a nested dropdown's separate scope.
    labSearch: localStorage.getItem("mojo:lab:search") ?? "",
    // folder-tree view (lib/tree.ts) over `labSchemas` - see
    // profileTreeCollapsed's comment above for why this isn't persisted.
    labTreeCollapsed: {} as Record<string, boolean>,
    // sort/filter preferences persist across reloads - see
    // profileSortMode's own comment above for why (a standing preference,
    // not session-local navigation state like the collapse map).
    labSortMode: (localStorage.getItem("mojo:lab:sort") ??
      window.__mojoDefaultLabSort ??
      "modified") as TreeSortMode,
    labSortDir: (localStorage.getItem("mojo:lab:sortDir") ??
      window.__mojoDefaultLabSortDir ??
      "desc") as TreeSortDirection,
    // see hideInvalidProfiles's own comment above
    hideInvalidLabs:
      localStorage.getItem("mojo:lab:hideInvalid") === null
        ? !!window.__mojoDefaultHideInvalidLabs
        : localStorage.getItem("mojo:lab:hideInvalid") === "1",
    get labTreeRows(): TreeRow<LabSchema>[] {
      // see profileTreeRows's own comment on folderOrder
      return buildTreeRows(
        sortTreeItems(this.labSchemas, this.labSortMode, this.labSortDir),
        this.labSortMode === "modified" ? "input" : "alpha",
      );
    },
    get hasInvalidLabs(): boolean {
      return this.labSchemas.some((l) => !l.valid);
    },
    get labVisibleRows(): TreeRow<LabSchema>[] {
      const q = this.labSearch.toLowerCase();
      return visibleTreeRows(
        this.labTreeRows,
        this.labTreeCollapsed,
        this.labSearch,
        (l) => l.name.toLowerCase().includes(q),
        undefined,
        (l) => l.valid,
        this.hideInvalidLabs,
      );
    },
    // see setProfileSortMode's own comment for the re-click-reverses rule
    setLabSortMode(mode: TreeSortMode) {
      if (this.labSortMode === mode) {
        this.labSortDir = this.labSortDir === "asc" ? "desc" : "asc";
      } else {
        this.labSortMode = mode;
        this.labSortDir = mode === "name" ? "asc" : "desc";
      }
      try {
        localStorage.setItem("mojo:lab:sort", this.labSortMode);
        localStorage.setItem("mojo:lab:sortDir", this.labSortDir);
      } catch {}
    },
    toggleHideInvalidLabs() {
      this.hideInvalidLabs = !this.hideInvalidLabs;
      try {
        localStorage.setItem("mojo:lab:hideInvalid", this.hideInvalidLabs ? "1" : "0");
      } catch {}
    },
    toggleLabFolder(path: string) {
      this.labTreeCollapsed = { ...this.labTreeCollapsed, [path]: !this.labTreeCollapsed[path] };
    },
    expandAllLabFolders() {
      this.labTreeCollapsed = {};
    },
    collapseAllLabFolders() {
      this.labTreeCollapsed = Object.fromEntries(allTreeFolderPaths(this.labTreeRows).map((p) => [p, true]));
    },

    // --- SHAPES ---
    shapesOpen: false,
    placementMode: null as "vline" | "hline" | "rect" | null,
    rectStart: null as { x: number; y: number } | null,
    shapeDraft: null as Shape | null,
    shapeEditIndex: null as number | null,

    // --- TRIAL STATUS ---
    trialStatus: null as TrialStatus | null,
    _trialStatusPoll: null as ReturnType<typeof setTimeout> | null,

    // --- DISTRIBUTIONS ---
    dists: [] as DistEntry[],
    _distTooltipEntry: null as DistEntry | null,
    distFilterName: ((): string => {
      try {
        return localStorage.getItem("mojo:dists:filter-name") ?? "";
      } catch {
        return "";
      }
    })(),
    // null = no filter applied (all pass); a (possibly empty) array is an
    // explicit selection, so deselecting every item shows zero rows instead
    // of silently falling back to "all"
    distFilterCategories: ((): string[] | null => {
      try {
        const v = localStorage.getItem("mojo:dists:filter-categories");
        return v === null ? null : (JSON.parse(v) as string[] | null);
      } catch {
        return null;
      }
    })(),
    distFilterTypes: ((): string[] | null => {
      try {
        const v = localStorage.getItem("mojo:dists:filter-types");
        return v === null ? null : (JSON.parse(v) as string[] | null);
      } catch {
        return null;
      }
    })(),
    distFilterUnits: ((): string[] | null => {
      try {
        const v = localStorage.getItem("mojo:dists:filter-units");
        return v === null ? null : (JSON.parse(v) as string[] | null);
      } catch {
        return null;
      }
    })(),
    distSortKey: "name" as
      | "name"
      | "category"
      | "dist_type"
      | "nominal"
      | "sampled_value"
      | "stat",
    distSortAsc: true,
    distColWidths: ((): Record<
      "name" | "category" | "dist_type" | "units" | "nominal" | "sampled",
      number
    > => {
      try {
        const saved = localStorage.getItem("mojo:dists:col-widths");
        if (saved) {
          return JSON.parse(saved) as Record<
            "name" | "category" | "dist_type" | "units" | "nominal" | "sampled",
            number
          >;
        }
      } catch {
        // ignore malformed storage
      }
      return {
        name: 180,
        category: 100,
        dist_type: 148,
        units: 70,
        nominal: 88,
        sampled: 88,
      };
    })(),

    // --- TRIAL LOGS ---
    logFilename: null as string | null,
    logEntries: [] as LogEntry[],
    logSortKey: "timestamp" as "timestamp" | "level",
    logSortAsc: true,
    logFilterLevels: [] as string[], // empty = all levels
    logLevelMenuOpen: false,
    logFilterMessage: "" as string,
    logFilterRegex: false,
    logColWidths: ((): Record<"time" | "level" | "source", number> => {
      try {
        const saved = localStorage.getItem("mojo:trial-logs:col-widths");
        if (saved) return JSON.parse(saved) as Record<"time" | "level" | "source", number>;
      } catch {
        // ignore malformed storage
      }
      return { time: 176, level: 96, source: 160 };
    })(),
    _logColResize: null as { col: "time" | "level" | "source" } | null,
    _logMeasureCanvas: null as HTMLCanvasElement | null,

    // --- MEDIA PLAYER ---
    mediaFiles: [] as string[],
    selectedMedia: null as string | null,
    mediaScrubMode: (localStorage.getItem("mojo:media:mode") ?? "play") as
      | "play"
      | "scrub",
    mediaShowLine: localStorage.getItem("mojo:media:show-line") === "1",
    mediaShowFrames: localStorage.getItem("mojo:media:show-frames") === "1",
    mediaPlaybackRate: Number(localStorage.getItem("mojo:media:rate")) || 1,
    mediaSpeedPresets: [0.2, 0.5, 1.0, 2.0, 4.0] as number[],
    mediaMiniplayerOpen: localStorage.getItem("mojo:media:mini") === "1",
    mediaIsScrubbable: false,
    _gifConvertStatus: "none" as "none" | "loading" | "ready" | "failed",
    _mediaRafId: null as number | null,
    _mediaFpsMap: {} as Record<string, number | null>,
    _mediaMtimeMap: {} as Record<string, number>,
    _mediaFrameInterval: null as number | null,

    // -----------------------------------------------------------------------
    // History
    // -----------------------------------------------------------------------
    pushHistory() {
      if (this.isUndoing) return;
      const next = pushSnapshot(
        { stack: this.historyStack, index: this.historyIndex },
        JSON.stringify(this.config),
        this.maxHistory,
      );
      if (!next) return;
      this.historyStack = next.stack;
      this.historyIndex = next.index;
      this.persistHistory();
    },

    undo() {
      if (this.historyIndex > 0) {
        this.isUndoing = true;
        this.historyIndex--;
        this.config = JSON.parse(
          this.historyStack[this.historyIndex] ?? "{}",
        ) as PlotConfig;
        this.persistHistory();
        void this.$nextTick(() => {
          this.isUndoing = false;
        });
        this.notify("Undo", "info");
      }
    },

    redo() {
      if (this.historyIndex < this.historyStack.length - 1) {
        this.isUndoing = true;
        this.historyIndex++;
        this.config = JSON.parse(
          this.historyStack[this.historyIndex] ?? "{}",
        ) as PlotConfig;
        this.persistHistory();
        void this.$nextTick(() => {
          this.isUndoing = false;
        });
        this.notify("Redo", "info");
      }
    },

    persistHistory() {
      localStorage.setItem(
        "mojo_mosaic_history",
        JSON.stringify({ stack: this.historyStack, index: this.historyIndex }),
      );
    },

    shiftY(index: number, direction: number, isWarp = false) {
      const reordered = reorderYAxes(this.config.yAxes, index, direction, isWarp);
      if (!reordered) return;
      this.config.yAxes = reordered;
      this.saveAndRender();
    },

    // -----------------------------------------------------------------------
    // Data fetching
    // -----------------------------------------------------------------------
    async fetchTrialData(
      id: string,
      requiredCols: string[] = [],
    ): Promise<TrialDataResponse> {
      const url = trialDataUrl(id, requiredCols, this.config, (c) =>
        this.isEnumCol(c),
      );
      // lab-virtual columns can change value for the same URL after an
      // in-place edit + save, so always bypass the browser HTTP cache
      const resp = await fetchWithRetry(url, { cache: "no-store" });
      if (!resp.ok) throw new Error(`Trial ${id} failed`);
      const result = (await resp.json()) as TrialDataResponse;
      if (result.filter_errors && result.filter_errors.length > 0) {
        for (const msg of unseenFilterErrors(
          result.filter_errors,
          this._shownFilterErrors,
        )) {
          (this._shownFilterErrors).add(msg);
          this.notify(msg, "error");
          // clear after 5 s so the same error can resurface if the user tries again
          setTimeout(
            () => (this._shownFilterErrors).delete(msg),
            5000,
          );
        }
      }
      return result;
    },

    async trickleFetch(
      id: string,
      columnList: string[],
      label: string,
      isVsDataset: boolean,
      loopId: number,
    ) {
      const CHUNK_SIZE = 10;
      const chunks = chunked(columnList, CHUNK_SIZE);
      for (let c = 0; c < chunks.length; c++) {
        const i = c * CHUNK_SIZE;
        if (loopId !== this.discoveryId) return;
        await new Promise((r) => setTimeout(r, 50));
        const chunk = chunks[c]!;
        try {
          const resp = await this.fetchTrialData(id, chunk);
          if (isVsDataset) {
            this.vsDatasets[id] = {
              ...(this.vsDatasets[id] ?? {}),
              ...resp.data,
            };
            this.vsDatasets = { ...this.vsDatasets };
          } else {
            this.data = { ...(this.data ?? {}), ...resp.data };
          }
          if (Object.keys(this.config.yAxes).some((y) => chunk.includes(y)))
            void this.renderPlot();
          console.debug(
            `[Dojo Hydration ${label}]: ${i + chunk.length}/${columnList.length}`,
          );
        } catch (e) {
          console.warn(`Hydration failed for ${id}`, e);
        }
      }
    },

    async fetchTrialStatus() {
      if (this.warpId === null) return;
      try {
        const resp = await fetch(`/monitor/api/status/trial/${this.warpId}`);
        if (!resp.ok) return;
        this.trialStatus = (await resp.json()) as TrialStatus;
      } catch {
        // dojo offline - leave existing status in place
      }
      const poll = trialPollAction(this.trialStatus, this._trialStatusPoll !== null);
      if (poll === "start") {
        this._trialStatusPoll = setInterval(() => {
          void this.fetchTrialStatus();
          void this.fetchTrialLogs();
        }, 3000);
      } else if (poll === "stop") {
        clearInterval(this._trialStatusPoll!);
        this._trialStatusPoll = null;
      }
    },

    // the step whose block was active when an ERROR trial's exception was
    // raised. record_step()'s `finally` always sets `elapsed`, even when the
    // wrapped code throws, so `elapsed !== null` alone can't tell "this step
    // finished cleanly" apart from "this step is where things broke". The
    // runner also resets `status.step` to "done" in its except handler, so
    // that can't be used either. `started` is reliable instead: generating
    // and solving run strictly sequentially, so whichever one has `started`
    // set *last* is the one that was in flight when the trial errored.
    errorStep(): TrialStep | null {
      return trialErrorStep(this.trialStatus);
    },

    stepDotClass(stepName: TrialStep): string {
      return trialStepDotClass(this.trialStatus, stepName);
    },

    stepTextClass(stepName: TrialStep): string {
      return trialStepTextClass(this.trialStatus, stepName);
    },

    async fetchTrialLogs() {
      try {
        const resp = await fetch(`/mosaic/${this.trialId}/logs`, {
          cache: "no-store",
        });
        if (!resp.ok) return;
        const result = (await resp.json()) as TrialLogsResponse;
        this.logFilename = result.filename;
        this.logEntries = result.entries;
      } catch {
        // dojo offline - leave existing logs in place
      }
    },

    // -----------------------------------------------------------------------
    // Distributions
    // -----------------------------------------------------------------------
    async fetchDists() {
      try {
        const resp = await fetch(`/mosaic/${this.trialId}/dists`, {
          cache: "no-store",
        });
        if (!resp.ok) return;
        const result = (await resp.json()) as DistsResponse;
        this.dists = result.entries;
      } catch {
        // stochas tables not written yet - silently skip
      }
    },

    showDistTooltip(event: MouseEvent, entry: DistEntry) {
      if (!hasTooltipContent(entry)) return;
      this._distTooltipEntry = entry;
      const tooltip = document.getElementById(
        "dist-pdf-tooltip",
      );
      if (!tooltip) return;
      const minW = tooltipMinWidth(entry.chart_type, entry.cat_labels.length);
      tooltip.style.minWidth = `${minW}px`;
      const pos = tooltipPosition(
        event.clientX,
        event.clientY,
        minW,
        window.innerWidth,
      );
      tooltip.style.left = `${pos.left}px`;
      tooltip.style.top = `${pos.top}px`;
      tooltip.style.display = "block";
      void this._renderDistTooltipPlot(entry);
    },

    hideDistTooltip() {
      this._distTooltipEntry = null;
      const tooltip = document.getElementById("dist-pdf-tooltip");
      if (tooltip) tooltip.style.display = "none";
    },

    async _renderDistTooltipPlot(entry: DistEntry) {
      const chartEl = document.getElementById(
        "dist-pdf-chart",
      );
      const paramsEl = document.getElementById("dist-pdf-params");
      if (!chartEl) return;

      const isDark = this.theme === "dark";
      const bg = themeColor("surface");
      const textColor = themeColor("ink-muted");
      const curveColor = isDark
        ? themeColor("accent-500")
        : themeColor("accent-600");
      const cdfColor = isDark
        ? themeColor("secondary-400")
        : themeColor("secondary-600");
      const fillColor = isDark
        ? themeColorAlpha("accent-500", 0.12)
        : themeColorAlpha("accent-600", 0.1);
      // matches the "sampled value" legend swatch in _distributions.html
      // (bg-danger-500): was a hardcoded true-red hex here previously, one
      // shade off from the rose the legend actually shows.
      const sampledColor = themeColor("danger");

      const colors: DistColors = {
        bg,
        text: textColor,
        curve: curveColor,
        cdf: cdfColor,
        fill: fillColor,
        sampled: sampledColor,
        nominal: themeColor("ink-muted"),
      };
      const plot = distPlot(entry, colors);
      if (!plot) {
        // no chart - hide the chart element so the tooltip is params-only
        chartEl.style.display = "none";
      } else {
        chartEl.style.display = "";
        await Plotly.react(chartEl, plot.traces, plot.layout, {
          displayModeBar: false,
          responsive: true,
        });
      }

      if (paramsEl) paramsEl.innerHTML = paramsHtml(entry);
    },

    get dataLength(): number {
      if (!this.data) return 0;
      const xCol = this.config.xAxis?.col;
      if (xCol && this.data[xCol]) return this.data[xCol].length;
      const first = Object.values(this.data).find((arr) => arr.length > 0);
      return first?.length ?? 0;
    },

    get currentTrialNum(): number {
      return parseInt(this.trialId.split("_").pop() ?? "0");
    },

    // same success/failure/error outcome classification vsChipClass() uses
    // ($store.dojo.failureTrialNums/errorTrialNums, populated from
    // applyJobOutcomes) - for the compact pip next to the warp input.
    // Tracks warpId (the draft trial number being typed/warped to), not
    // just the page's own trial, falling back to the page's trial once the
    // draft is cleared - see _header.html's pip.
    get warpOutcomeColor(): "success" | "warning" | "danger" {
      const store = Alpine.store("dojo") as DojoStore;
      const num = this.warpId ?? this.currentTrialNum;
      const outcome = trialOutcome(num, store.errorTrialNums, store.failureTrialNums);
      return outcome === "error" ? "warning" : outcome === "failure" ? "danger" : "success";
    },

    // -----------------------------------------------------------------------
    // Distributions: sorting, filtering & column resize
    // -----------------------------------------------------------------------
    get distCategories(): string[] {
      return distinctSorted(this.dists.map((d) => d.category));
    },

    get distTypes(): string[] {
      return distinctSorted(this.dists.map((d) => d.dist_type));
    },

    get distUnits(): string[] {
      return distinctSorted(this.dists.map((d) => d.units));
    },

    // signal counts per dropdown option, shown right-justified next to each
    // checkbox so users can see how many rows a filter choice covers
    get distCategoryCounts(): Record<string, number> {
      return countBy(this.dists.map((d) => d.category));
    },

    get distTypeCounts(): Record<string, number> {
      return countBy(this.dists.map((d) => d.dist_type));
    },

    get distUnitCounts(): Record<string, number> {
      return countBy(this.dists.map((d) => d.units));
    },

    // see toggleFacet for how a selection becomes (and stops being) "all"
    toggleDistCategoryFilter(cat: string) {
      this.distFilterCategories = toggleFacet(this.distFilterCategories, this.distCategories, cat);
    },

    selectAllDistCategories() {
      this.distFilterCategories = null;
    },

    deselectAllDistCategories() {
      this.distFilterCategories = [];
    },

    toggleDistTypeFilter(type: string) {
      this.distFilterTypes = toggleFacet(this.distFilterTypes, this.distTypes, type);
    },

    selectAllDistTypes() {
      this.distFilterTypes = null;
    },

    deselectAllDistTypes() {
      this.distFilterTypes = [];
    },

    toggleDistUnitFilter(unit: string) {
      this.distFilterUnits = toggleFacet(this.distFilterUnits, this.distUnits, unit);
    },

    selectAllDistUnits() {
      this.distFilterUnits = null;
    },

    deselectAllDistUnits() {
      this.distFilterUnits = [];
    },

    get filteredDists(): DistEntry[] {
      return filterDists(this.dists, {
        name: this.distFilterName,
        categories: this.distFilterCategories,
        types: this.distFilterTypes,
        units: this.distFilterUnits,
        sortKey: this.distSortKey,
        sortAsc: this.distSortAsc,
      });
    },

    toggleDistSort(
      key:
        | "name"
        | "category"
        | "dist_type"
        | "nominal"
        | "sampled_value"
        | "stat",
    ) {
      if (this.distSortKey === key) {
        this.distSortAsc = !this.distSortAsc;
      } else {
        this.distSortKey = key;
        this.distSortAsc = true;
      }
    },

    _persistDistColWidths() {
      try {
        localStorage.setItem(
          "mojo:dists:col-widths",
          JSON.stringify(this.distColWidths),
        );
      } catch {
        // ignore storage errors
      }
    },

    startDistColResize(
      e: MouseEvent,
      col: "name" | "category" | "dist_type" | "units" | "nominal" | "sampled",
    ) {
      e.preventDefault();
      const startX = e.clientX;
      const startWidth = this.distColWidths[col];
      const MIN: Record<typeof col, number> = {
        name: 80,
        category: 68,
        dist_type: 96,
        units: 48,
        nominal: 64,
        sampled: 64,
      };
      const onMove = (ev: MouseEvent) => {
        this.distColWidths[col] = Math.max(
          MIN[col],
          startWidth + (ev.clientX - startX),
        );
      };
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        this._persistDistColWidths();
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },

    autoFitDistColumn(
      col: "name" | "category" | "dist_type" | "units" | "nominal" | "sampled",
    ) {
      const container = this.$refs.distTable;
      if (!container) return;
      const headerEl = container.querySelector<HTMLElement>(
        `[data-distcol-header="${col}"]`,
      );
      if (!headerEl) return;
      // header: canvas-measure the label text + room for the sort chevron
      let width =
        this._measureTextWidth(headerEl.textContent?.trim() ?? "", headerEl) +
        20;
      // per-column total horizontal padding: outer cell px-3 = 24px;
      // dist_type badge adds its own px-1.5 (12px) on top, so 36px total
      const PADDING: Record<typeof col, number> = {
        name: 24,
        category: 24,
        dist_type: 36,
        units: 24,
        nominal: 24,
        sampled: 24,
      };
      const pad = PADDING[col];
      // read rendered text from every content cell — handles all formatting
      // (uppercase CSS, toPrecision, em-dash substitution) without a switch
      for (const cell of container.querySelectorAll<HTMLElement>(
        `[data-distcol-content="${col}"]`,
      )) {
        width = Math.max(
          width,
          this._measureTextWidth((cell.innerText ?? "").trim(), cell) + pad,
        );
      }
      this.distColWidths[col] = Math.ceil(width);
      this._persistDistColWidths();
    },

    // -----------------------------------------------------------------------
    // Logs: sorting, filtering & styling
    // -----------------------------------------------------------------------
    get filteredLogEntries(): LogEntry[] {
      return filterLogEntries(this.logEntries, {
        levels: this.logFilterLevels,
        message: this.logFilterMessage,
        regex: this.logFilterRegex,
        sortKey: this.logSortKey,
        sortAsc: this.logSortAsc,
      });
    },

    get logLevels(): string[] {
      return logLevelsOf(this.logEntries);
    },

    toggleLogSort(key: "timestamp" | "level") {
      if (this.logSortKey === key) {
        this.logSortAsc = !this.logSortAsc;
      } else {
        this.logSortKey = key;
        this.logSortAsc = true;
      }
    },

    toggleLogLevelFilter(level: string) {
      const idx = this.logFilterLevels.indexOf(level);
      if (idx === -1) this.logFilterLevels.push(level);
      else this.logFilterLevels.splice(idx, 1);
    },

    _persistLogColWidths() {
      try {
        localStorage.setItem(
          "mojo:trial-logs:col-widths",
          JSON.stringify(this.logColWidths),
        );
      } catch {
        // ignore storage errors
      }
    },

    startLogColResize(e: MouseEvent, col: "time" | "level" | "source") {
      e.preventDefault();
      const startX = e.clientX;
      const startWidth = this.logColWidths[col];
      const onMove = (ev: MouseEvent) => {
        this.logColWidths[col] = resizedLogColumnWidth(
          col,
          startWidth,
          ev.clientX - startX,
        );
      };
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        this._persistLogColWidths();
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },

    fmtSigFig: formatSigFig,
    fmtSampled: formatSampled,
    fmtPercentile: formatPercentile,

    _measureTextWidth(text: string, refEl: HTMLElement): number {
      const canvas = (this._logMeasureCanvas ??=
        document.createElement("canvas"));
      const ctx = canvas.getContext("2d");
      if (!ctx) return 0;
      ctx.font = getComputedStyle(refEl).font;
      return ctx.measureText(text).width;
    },

    autoFitLogColumn(col: "time" | "level" | "source") {
      const container = this.$refs.logTable;
      if (!container) return;

      // text-overflow:ellipsis cells report their box size (not content size)
      // via scrollWidth, so measure the actual text with a canvas instead.
      const headerEl = container.querySelector<HTMLElement>(
        `[data-logcol-header="${col}"]`,
      );
      if (!headerEl) return;
      const contentEl = container.querySelector<HTMLElement>(
        `[data-logcol-content="${col}"]`,
      );

      const headerWidth = this._measureTextWidth(
        headerEl.textContent?.trim() ?? "",
        headerEl,
      );
      const contentWidths: number[] = [];
      if (contentEl) {
        for (const entry of this.filteredLogEntries) {
          let text: string;
          switch (col) {
            case "time":
              text = this.formatLogTime(entry.timestamp);
              break;
            case "level":
              text = entry.level;
              break;
            case "source":
              text = this.logSourceShort(entry);
              break;
          }
          contentWidths.push(this._measureTextWidth(text, contentEl));
        }
      }

      this.logColWidths[col] = fittedLogColumnWidth(col, headerWidth, contentWidths);
      this._persistLogColWidths();
    },

    logSourceShort,

    logSourceFull,

    logLevelClass,

    formatLogTime,

    _updateIsScrubbable() {
      this.mediaIsScrubbable = isScrubbable(
        this.selectedMedia,
        this._gifConvertStatus,
      );
    },

    _syncOverlayVisibility() {
      const overlay = document.getElementById(
        "playback-line-overlay",
      );
      const lineEl = document.getElementById(
        "playback-line-el",
      );
      const vis = overlayVisibility({
        showLine: this.mediaShowLine,
        scrubMode: this.mediaScrubMode,
        isScrubbable: this.mediaIsScrubbable,
        showFrames: this.mediaShowFrames,
        frameInterval: this._mediaFrameInterval,
        xCol: this.config.xAxis?.col,
        hasYAxes: Object.keys(this.config.yAxes).length > 0,
      });
      if (overlay) overlay.style.display = vis.overlay;
      if (lineEl) lineEl.style.display = vis.line;
    },

    _renderFrameMarkers() {
      const framesPath = document.getElementById(
        "playback-frames-path",
      ) as SVGPathElement | null;
      if (!framesPath) return;
      this._syncOverlayVisibility();
      if (
        !framesVisible({
          showLine: this.mediaShowLine,
          scrubMode: this.mediaScrubMode,
          isScrubbable: this.mediaIsScrubbable,
          showFrames: this.mediaShowFrames,
          frameInterval: this._mediaFrameInterval,
          xCol: this.config.xAxis?.col,
          hasYAxes: Object.keys(this.config.yAxes).length > 0,
        })
      ) {
        framesPath.setAttribute("d", "");
        return;
      }
      const plotEl = plotAreaEl();
      const fullLayout = plotEl?._fullLayout;
      const rect = plotEl?.getBoundingClientRect();
      if (!plotEl || !fullLayout) return;
      const video = document.getElementById(
        "media-video-player",
      ) as HTMLVideoElement | null;
      framesPath.setAttribute(
        "d",
        frameMarkersPath({
          interval: this._mediaFrameInterval!,
          duration: knownDuration(video?.duration),
          height: rect!.height,
          marginB: fullLayout.margin.b,
          marginL: fullLayout.margin.l,
          range: fullLayout.xaxis.range,
          l2p: (v) => fullLayout.xaxis.l2p(v),
        }),
      );
    },

    _updatePlaybackLine() {
      // loop only runs on time axis: line, zoom-looping, and frame markers all require it
      const playback = (): boolean =>
        shouldRunPlayback({
          scrubMode: this.mediaScrubMode,
          fileCount: this.mediaFiles.length,
          isScrubbable: this.mediaIsScrubbable,
          isTimeAxis: this.config.xAxis?.col === "time",
          plotType: this.config.plotType,
        });
      if (!playback() || this._mediaRafId !== null) return;
      const tick = () => {
        // a polar plot's _fullLayout has polar.radialaxis/angularaxis, not
        // xaxis at all - reading fullLayout.xaxis.range below would throw
        if (!playback()) {
          this._mediaRafId = null;
          this._syncOverlayVisibility();
          return;
        }
        const video = document.getElementById(
          "media-video-player",
        ) as HTMLVideoElement | null;
        const plotEl = plotAreaEl();
        if (video && plotEl && video.duration > 0 && !isNaN(video.duration)) {
          const fullLayout = plotEl._fullLayout;
          if (fullLayout) {
            const [xMin, xMax] = fullLayout.xaxis.range;
            const next = loopedTime(video.currentTime, xMin, xMax, video.duration);
            if (next !== null) video.currentTime = next;
            this._syncOverlayVisibility();
            if (this.mediaShowLine) {
              const lineEl = document.getElementById(
                "playback-line-el",
              );
              if (lineEl) {
                lineEl.style.top = fullLayout.margin.t + "px";
                lineEl.style.bottom = fullLayout.margin.b + "px";
                const t = snappedTime(video.currentTime, this._mediaFrameInterval);
                lineEl.style.left =
                  fullLayout.margin.l + fullLayout.xaxis.l2p(t) + "px";
              }
            }
            if (this.mediaShowFrames) this._renderFrameMarkers();
          }
        }
        this._mediaRafId = requestAnimationFrame(tick);
      };
      this._mediaRafId = requestAnimationFrame(tick);
    },

    async fetchMediaFiles() {
      try {
        const resp = await fetch(`/mosaic/${this.trialId}/media`);
        if (!resp.ok) return;
        const data = (await resp.json()) as TrialMediaResponse;
        this._mediaFpsMap = Object.fromEntries(
          data.files.map((f: TrialMediaFile) => [f.name, f.fps]),
        );
        this._mediaMtimeMap = Object.fromEntries(
          data.files.map((f: TrialMediaFile) => [f.name, f.mtime]),
        );
        this.mediaFiles = data.files.map((f: TrialMediaFile) => f.name);
        if (this.mediaFiles.length > 0) {
          const saved = localStorage.getItem("mojo:media:file");
          this.selectedMedia = pickSelectedMedia(this.mediaFiles, saved)!;
        }
        this._applySelectedMediaFps();
        this._updateIsScrubbable();
      } catch {
        // dojo offline - no media available
      }
      this._updatePlaybackLine();
      this._renderFrameMarkers();
      if (this.mediaMiniplayerOpen && this.mediaFiles.length > 0)
        this._startMiniplayer();
    },

    // builds a media file URL with an mtime cache-buster, so a regenerated
    // file with the same name forces the browser to reload it instead of
    // reusing a stale cached video/image from before the rerun
    _mediaFileUrl(filename: string, suffix = ""): string {
      return mediaUrl(this.trialId, filename, suffix, this._mediaMtimeMap[filename]);
    },

    _applySelectedMediaFps() {
      const fps = this.selectedMedia
        ? (this._mediaFpsMap[this.selectedMedia] ?? null)
        : null;
      this._mediaFrameInterval = frameInterval(fps);
    },

    _onVideoLoaded() {
      const video = document.getElementById(
        "media-video-player",
      ) as HTMLVideoElement | null;
      if (video) video.playbackRate = this.mediaPlaybackRate;
      if (this.selectedMedia?.toLowerCase().endsWith(".gif")) {
        this._gifConvertStatus = "ready";
        // mirror the img's auto-play behaviour now that the video element takes over
        void video?.play();
      }
    },

    _onVideoError() {
      if (this.selectedMedia?.toLowerCase().endsWith(".gif")) {
        this._gifConvertStatus = "failed";
      }
    },

    _miniDragStart(e: MouseEvent) {
      const wrapper = document.getElementById(
        "mini-wrapper",
      );
      const canvas = document.getElementById(
        "mini-canvas",
      );
      if (!wrapper) return;
      const startX = e.clientX;
      const startY = e.clientY;
      const startLeft = parseInt(wrapper.style.left) || 8;
      const startTop = parseInt(wrapper.style.top) || 8;
      const card = wrapper.parentElement;
      if (canvas) canvas.style.cursor = "grabbing";
      const onMove = (ev: MouseEvent) => {
        const pos = miniDragPosition(
          startLeft,
          startTop,
          ev.clientX - startX,
          ev.clientY - startY,
          card
            ? {
                width: card.offsetWidth,
                height: card.offsetHeight,
                wrapperWidth: wrapper.offsetWidth,
                wrapperHeight: wrapper.offsetHeight,
              }
            : null,
        );
        wrapper.style.left = pos.left + "px";
        wrapper.style.top = pos.top + "px";
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        if (canvas) canvas.style.cursor = "grab";
        try {
          localStorage.setItem("mojo:media:mini:left", wrapper.style.left);
          localStorage.setItem("mojo:media:mini:top", wrapper.style.top);
        } catch {
          /* ignore */
        }
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },

    _miniResizeStart(e: MouseEvent) {
      const wrapper = document.getElementById(
        "mini-wrapper",
      );
      if (!wrapper) return;
      const startX = e.clientX;
      const startY = e.clientY;
      const startW = wrapper.offsetWidth;
      const startH = wrapper.offsetHeight;
      // use the video's natural aspect ratio for Shift-snap; fall back to 16:9
      const video = document.getElementById(
        "media-video-player",
      ) as HTMLVideoElement | null;
      const aspect = aspectRatio(video?.videoWidth, video?.videoHeight);
      const onMove = (ev: MouseEvent) => {
        const size = miniResizeSize(
          startW,
          startH,
          ev.clientX - startX,
          ev.clientY - startY,
          ev.shiftKey,
          aspect,
        );
        wrapper.style.width = size.width + "px";
        wrapper.style.height = size.height + "px";
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        try {
          localStorage.setItem("mojo:media:mini:w", wrapper.style.width);
          localStorage.setItem("mojo:media:mini:h", wrapper.style.height);
        } catch {
          /* ignore */
        }
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },

    _startMiniplayer() {
      const wrapper = document.getElementById(
        "mini-wrapper",
      );
      const canvas = document.getElementById(
        "mini-canvas",
      ) as HTMLCanvasElement | null;
      if (!wrapper || !canvas || _mini.rafId !== null) return;
      // restore saved position and size
      try {
        const sl = localStorage.getItem("mojo:media:mini:left");
        const st = localStorage.getItem("mojo:media:mini:top");
        const sw = localStorage.getItem("mojo:media:mini:w");
        const sh = localStorage.getItem("mojo:media:mini:h");
        if (sl) wrapper.style.left = sl;
        if (st) wrapper.style.top = st;
        if (sw) wrapper.style.width = sw;
        if (sh) wrapper.style.height = sh;
      } catch {
        /* ignore */
      }
      wrapper.style.display = "block";
      const paint = () => {
        const isGif =
          this.selectedMedia?.toLowerCase().endsWith(".gif") ?? false;
        const useVideo = miniUsesVideo(isGif, this._gifConvertStatus);
        const srcEl = useVideo
          ? (document.getElementById(
              "media-video-player",
            ) as HTMLVideoElement | null)
          : (document.getElementById(
              "media-gif-player",
            ) as HTMLImageElement | null);
        if (srcEl) {
          const ctx = canvas.getContext("2d");
          if (ctx) {
            const vEl = srcEl as HTMLVideoElement;
            if (miniFrameReady(isGif, vEl.readyState)) {
              ctx.drawImage(
                srcEl,
                0,
                0,
                canvas.width,
                canvas.height,
              );
            }
          }
        }
        _mini.rafId = requestAnimationFrame(paint);
      };
      _mini.rafId = requestAnimationFrame(paint);
    },

    _stopMiniplayer() {
      if (_mini.rafId !== null) {
        cancelAnimationFrame(_mini.rafId);
        _mini.rafId = null;
      }
      const wrapper = document.getElementById(
        "mini-wrapper",
      );
      if (wrapper) wrapper.style.display = "none";
    },

    async startBackgroundDiscovery() {
      const currentId = ++this.discoveryId;
      const pendingCols = missingColumns(this.columns, this.data);
      if (pendingCols.length > 0)
        await this.trickleFetch(
          this.trialId,
          pendingCols,
          "Current",
          false,
          currentId,
        );
      if (currentId !== this.discoveryId) return;

      const [start, end] = orderedRange(this.vsDraft.range);
      const activeCols = activeColumns(this.config);
      const draftIds = vsTargetIds(
        this.allTrials,
        start,
        end,
        this.vsDraft.pinned,
        (id) => id === this.trialId,
      );

      for (const id of draftIds) {
        if (currentId !== this.discoveryId) return;
        const existing = this.vsDatasets[id];
        if (vsNeedsFetch(existing, activeCols, false))
          await this.trickleFetch(
            id,
            activeCols,
            `Draft ${id}`,
            true,
            currentId,
          );
      }
    },

    // -----------------------------------------------------------------------
    // Shapes
    // -----------------------------------------------------------------------
    setPlacementMode(type: "vline" | "hline" | "rect") {
      this.placementMode = type;
      this.rectStart = null;
      this.shapeDraft = null;
      this.notify(`Mode: ${placementLabel(type)}. Click plot to place.`, "info");
    },

    deleteShape(index: number) {
      this.config.shapes.splice(index, 1);
      this.saveAndRender();
    },

    handlePlotClickForShapes(pt: { x: number; y: number }): boolean {
      if (!this.placementMode) return false;
      const defaultStyle = this.nextAvailableStyle(
        this.config.shapes.map((s) => ({
          color: s.color,
          dash: s.dash ?? "solid",
        })),
      );
      const placed = shapeFromClick(
        this.placementMode,
        this.rectStart,
        pt,
        defaultStyle,
      );
      this.rectStart = placed.rectStart;
      if (placed.shape) {
        this.config.shapes.push(placed.shape);
        this.placementMode = null;
        this.saveAndRender();
      }
      return true;
    },

    saveShape() {
      if (!this.shapeDraft) return;
      upsertAt(this.config.shapes, this.shapeDraft, this.shapeEditIndex);
      this.shapeDraft = null;
      this.shapeEditIndex = null;
      this.saveAndRender();
    },

    startShapeEdit(index: number) {
      this.shapeEditIndex = index;
      this.shapeDraft = { ...this.config.shapes[index]! };
      this.shapesOpen = true;
    },

    cancelShapeDraft() {
      this.shapeDraft = null;
      this.shapeEditIndex = null;
      this.rectStart = null;
    },

    // -----------------------------------------------------------------------
    // Annotations
    // -----------------------------------------------------------------------
    saveAnnotation() {
      if (!this.annDraft || !isUsableText(this.annDraft.text)) return;
      upsertAt(this.config.annotations, this.annDraft, this.annEditIndex);
      this.cancelAnnDraft();
      this.saveAndRender();
    },

    startAnnEdit(index: number) {
      this.annEditIndex = index;
      this.annDraft = { ...this.config.annotations[index]! };
      void this.$nextTick(() =>
        (this.$refs["annInput"] as HTMLInputElement | undefined)?.focus(),
      );
    },

    cancelAnnDraft() {
      this.annDraft = null;
      this.annEditIndex = null;
    },

    jumpToAnnotation(ann: Annotation) {
      const el = document.getElementById("plot-area");
      if (!el || !this.data) return;
      const newRangeX = annotationXRange(
        this.data[this.config.xAxis.col!] ?? [],
        ann.x,
      );

      // enum columns have axes of their own, so only the numeric ones set the y zoom;
      // with none, the primary axis is an enum axis and keeps its fixed range
      const numericY = Object.keys(this.config.yAxes).filter(
        (k) => !this.isEnumCol(k),
      );
      this.config.rangeX = newRangeX;
      if (numericY.length === 0) {
        void Plotly.relayout(el, {
          "xaxis.range": newRangeX,
          "xaxis.autorange": false,
        });
        this.saveAndRender();
        return;
      }

      const fullY = this.calculatePaddedRange(numericY, false);
      const newRangeY = annotationYRange(fullY, ann.y);

      this.config.rangeY = newRangeY;
      void Plotly.relayout(el, {
        "xaxis.range": newRangeX,
        "yaxis.range": newRangeY,
        "xaxis.autorange": false,
        "yaxis.autorange": false,
      });
      this.saveAndRender();
    },

    deleteAnnotation(index: number) {
      this.config.annotations.splice(index, 1);
      this.saveAndRender();
    },

    editAnnotation(index: number) {
      const ann = this.config.annotations[index]!;
      const newText = prompt("Update Annotation:", ann.text);
      if (isUsableText(newText)) {
        this.config.annotations[index]!.text = newText;
        this.saveAndRender();
      }
    },

    // -----------------------------------------------------------------------
    // Column accessors
    // -----------------------------------------------------------------------
    get selectableYColumns(): string[] {
      if (!this.columns) return [];
      if (!refFrameActive(this.config.refFrame)) return this.columns;
      return rotatableColumns(this.columns, this.rotateableVectors ?? [], (c) => this.isEnumCol(c));
    },

    get frameActive(): boolean {
      return refFrameActive(this.config.refFrame);
    },

    // whether a signal can be picked: any, in the world frame, else only the
    // vectors a frame can rotate, and enum signals (drawn as they are, with no
    // rotation filter)
    isFrameSelectable(col: string): boolean {
      return (
        !refFrameActive(this.config.refFrame) ||
        this.isEnumCol(col) ||
        (this.rotateableVectors ?? []).includes(col.split(":")[0]!)
      );
    },

    get availableQuats(): string[] {
      if (!this.columns || !Array.isArray(this.columns)) return [];
      return quatBases(this.columns);
    },

    // -----------------------------------------------------------------------
    // Init
    // -----------------------------------------------------------------------
    async init() {
      this.theme = document.documentElement.classList.contains("dark")
        ? "dark"
        : "light";
      const currentNum = trialNumber(this.trialId);
      this.warpId = isNaN(currentNum) ? null : currentNum;
      void this.fetchTrialStatus();
      void this.fetchTrialLogs();
      void this.fetchMediaFiles();
      void this.fetchDists();

      // initialize tab state (populates labTabs, labActiveTabId, labName, labGraph)
      this._initTabs();
      window.mojoLabOnDirtyChange = (dirty: boolean) => {
        const tab = this.labTabs.find((t) => t.id === this.labActiveTabId);
        if (tab) tab.dirty = dirty;
      };
      // LabTab.savedState is the single source of truth for "what does clean
      // look like for this tab" - _signal_lab.html never keeps its own copy,
      // it always asks for the active tab's baseline through these two bridges.
      // That structurally rules out the stale-copy bugs a locally-cached
      // baseline used to cause (forgotten syncs, baselines surviving a tab
      // switch, ordering footguns around when the cache had to be refreshed).
      window.mojoLabGetBaseline = () => {
        const tab = this.labTabs.find((t) => t.id === this.labActiveTabId);
        return tab?.savedState ?? null;
      };
      window.mojoLabSetBaseline = (state: string | null) => {
        const tab = this.labTabs.find((t) => t.id === this.labActiveTabId);
        if (tab) tab.savedState = state;
      };

      // bind video element handlers programmatically so `this` resolves to the
      // trialViewer component — template @event handlers in nested x-data scopes
      // lose the correct `this` binding when calling parent methods
      void this.$nextTick(() => {
        const video = document.getElementById(
          "media-video-player",
        ) as HTMLVideoElement | null;
        if (video) {
          video.onloadedmetadata = () => this._onVideoLoaded();
          video.onerror = () => this._onVideoError();
        }
      });

      const observer = new MutationObserver((mutations) => {
        if (mutations.some((m) => m.attributeName === "class")) {
          this.theme = document.documentElement.classList.contains("dark")
            ? "dark"
            : "light";
          if (this.data && Object.keys(this.config.yAxes).length > 0)
            void this.renderPlot();
        }
      });
      observer.observe(document.documentElement, { attributes: true });

      try {
        const schemaResp = await fetchWithTimeout("/mosaic/api/filter-schema");
        this.filterSchemas = (await schemaResp.json()) as FilterSchema[];
      } catch (e) {
        console.warn("Failed to load filter schemas", e);
      }

      try {
        const plotSchemaResp = await fetchWithTimeout("/mosaic/api/plot-config-schema");
        this.plotConfigSchema = (await plotSchemaResp.json()) as JsonSchemaNode;
        // the JSON editor's schema-diagnostics linter (initCodeMirror,
        // below) reads this same field via closure but only re-runs on
        // document edits - if the editor already mounted before this
        // fetch resolved (a real race: _json_editor.html's own x-init
        // fires independently of this async init()), force one lint pass
        // now so violations show up without the user needing to type
        // anything first.
        if (_cm.editor) forceLinting(_cm.editor);
      } catch (e) {
        console.warn("Failed to load plot config schema", e);
      }

      try {
        const statusResp = await fetchWithTimeout("/monitor/api/status/job");
        const statusData = (await statusResp.json()) as {
          error?: boolean;
          is_complete: boolean;
          padding_style: string;
        };
        if (statusData && !statusData.error) {
          (Alpine.store("dojo") as DojoStore).updateSync(
            Date.now(),
            statusData.is_complete,
          );
          this.paddingLen = paddingLength(statusData.padding_style);
        }
      } catch (e) {
        console.warn("Dojo offline", e);
      }

      try {
        const initialCols = activeColumns(this.config);
        const response = await this.fetchTrialData(this.trialId, initialCols);
        this.columns = response.columns.all.sort();
        this.rotateableVectors = response.columns.rotatable_vectors ?? [];
        this.columnMetadata = response.columns.column_metadata ?? {};
        this.data = response.data;
        void this.loadLabSchemas();

        const params = new URLSearchParams(window.location.search);
        const shared = params.get("v");
        let hasStoredTabs = false;
        if (shared) {
          try {
            hasStoredTabs = !!localStorage.getItem("mojo:plot:tabs");
          } catch {}
        }
        const decision = sharedLinkDecision(shared, hasStoredTabs);
        let useSharedLink = decision === "use";
        if (decision === "ask") {
          // A ?v= link left in the address bar survives a plain page
          // refresh - without asking first, every such refresh would
          // silently blow away whatever tab session is already saved in
          // this browser, which is exactly what happened here. Only
          // prompt when there's actually something to lose.
          const ok = await window.mojoConfirm?.({
            title: "Open shared link?",
            message:
              "This link will replace the plot tabs you already have open in this browser. Replace them, or keep what you have?",
            confirmLabel: "Replace my tabs",
            cancelLabel: "Keep my tabs",
            variant: "warning",
          });
          useSharedLink = ok ?? false;
        }
        if (shared) {
          // Strip ?v= from the address bar regardless of the choice above,
          // so a later refresh doesn't re-ask (or silently reapply it)
          // for a link that's already been handled once.
          window.history.replaceState(null, "", withoutSharedParam(window.location.href));
        }
        if (useSharedLink) {
          this.hydrateFromUrl(shared!);
        } else {
          this.loadConfig();
        }
        // VS is page-level now, not part of config/the shared-link payload -
        // same init path regardless of which branch above ran.
        this._initVsState();

        // Migrate old profiles: if refFrame is set but no series has a RotationFilter,
        // inject it now (before watchers are registered so this is a silent migration).
        if (needsRefFrameMigration(this.config)) {
          this.applyRefFrame(this.config.refFrame);
        }

        // Restores a previously-saved multi-tab session (mojo:plot:tabs),
        // superseding the single-config state the sequence above just
        // produced - unless a shared link was just hydrated (useSharedLink,
        // set above only after confirming it's OK to replace an existing
        // session). Awaited directly (not via $nextTick) so the fetch it
        // may need to run for a restored tab's uncached columns completes
        // before the render below ever starts.
        await this._initPlotTabs(useSharedLink);

        void this.$nextTick(() => {
          this.pushHistory();
        });

        void this.$nextTick(async () => {
          await this.renderPlot();
          // wait one layout pass before reading getBoundingClientRect for frame markers
          requestAnimationFrame(() => {
            const plotEl = plotAreaEl();
            console.debug(
              "[init RAF] _fullLayout present:",
              !!plotEl?._fullLayout,
              "rect:",
              plotEl?.getBoundingClientRect(),
            );
            this._renderFrameMarkers();
            this._syncOverlayVisibility();
          });
          const plotEl = document.getElementById("plot-area") as HTMLElement & {
            on(
              event: string,
              handler: (event: Record<string, unknown>) => void,
            ): void;
            _fullLayout?: {
              xaxis: {
                p2l(v: number): number;
                l2p(v: number): number;
                range: [number, number];
              };
              yaxis: { p2l(v: number): number };
              margin: { l: number; r: number; t: number; b: number };
            };
          };

          // re-render frame markers after every complete Plotly render so positions
          // always reflect the final settled layout (range, margins, dimensions)
          this._attachPlotEventHandlers();

          // placementMode uses normal click
          plotEl.addEventListener("click", (e) => {
            if (!this.placementMode) return;
            const target = e.target as HTMLElement;
            if (
              !target.classList.contains("nsewdrag") &&
              !target.classList.contains("drag")
            )
              return;
            const rect = plotEl.getBoundingClientRect();
            const fullLayout = plotEl._fullLayout;
            if (!fullLayout) return;
            this.handlePlotClickForShapes({
              x: fullLayout.xaxis.p2l(
                e.clientX - rect.left - fullLayout.margin.l,
              ),
              y: fullLayout.yaxis.p2l(
                e.clientY - rect.top - fullLayout.margin.t,
              ),
            });
          });

          // middle-click anywhere over the plot opens annotation editor.
          // Listening at document level so Plotly's stopPropagation on inner SVG elements
          // cannot block the event.
          document.addEventListener("mousedown", (e) => {
            if (e.button !== 1) return;
            const rect = plotEl.getBoundingClientRect();
            if (
              e.clientX < rect.left ||
              e.clientX > rect.right ||
              e.clientY < rect.top ||
              e.clientY > rect.bottom
            )
              return;
            e.preventDefault(); // suppress browser auto-scroll cursor
            const fullLayout = plotEl._fullLayout;
            if (!fullLayout) return;
            const xVal = fullLayout.xaxis.p2l(
              e.clientX - rect.left - fullLayout.margin.l,
            );
            const yVal = fullLayout.yaxis.p2l(
              e.clientY - rect.top - fullLayout.margin.t,
            );
            setTimeout(() => {
              this.annDraft = { x: xVal, y: yVal, text: "" };
              this.annEditIndex = null;
              // same position math as the sidebar Notes button's own
              // @click handler (_chart.html) -- popup width 288px (w-72) +
              // 16px gap, positioned document-relative since the popup is
              // x-teleport'd to <body>.
              const annBtn = document.querySelector<HTMLElement>(
                '[x-ref="annBtn"]',
              );
              if (annBtn) {
                this.annCoords = popupCoords(
                  annBtn.getBoundingClientRect(),
                  window.scrollX,
                  window.scrollY,
                );
              }
              this.annotationsOpen = true;
              void this.$nextTick(() => {
                document
                  .querySelector<HTMLInputElement>('[x-ref="annInput"]')
                  ?.focus();
              });
            }, 0);
          });

          // intercept Plotly's own notifier and route through our toast
          new MutationObserver((mutations) => {
            for (const { addedNodes } of mutations) {
              for (const node of addedNodes) {
                if (!(node instanceof HTMLElement)) continue;
                const notif = node.classList.contains("plotly-notifier")
                  ? node
                  : node.querySelector?.(".plotly-notifier");
                if (!notif) continue;
                const text = notifierText(notif.textContent);
                if (text) this.notify(text, "info");
                (notif as HTMLElement).style.display = "none";
              }
            }
          }).observe(document.body, { childList: true, subtree: true });

          // scrub video on mousemove: use axis time value when x-axis is "time",
          // otherwise fall back to pixel fraction so phase-space plots still work.
          plotEl.addEventListener("mousemove", (e: MouseEvent) => {
            if (this.mediaScrubMode !== "scrub") return;
            const video = document.getElementById(
              "media-video-player",
            ) as HTMLVideoElement | null;
            if (!video || !video.duration || isNaN(video.duration)) return;
            const fullLayout = plotEl._fullLayout;
            if (!fullLayout) return;
            const rect = plotEl.getBoundingClientRect();
            const relX = e.clientX - rect.left - fullLayout.margin.l;
            const xIsTime = this.config.xAxis?.col === "time";
            const t = scrubTime(
              video.duration,
              xIsTime ? fullLayout.xaxis.p2l(relX) : null,
              relX,
              rect.width - fullLayout.margin.l - fullLayout.margin.r,
            );
            if (t !== null) video.currentTime = t;
          });

          setTimeout(() => {
            if (plotEl?.offsetParent !== null) Plotly.Plots.resize(plotEl);
          }, 100);
        });
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        this.errorState = msg.includes("not found") ? "not_found" : "empty";
        this.notify(msg, "error");
      } finally {
        this.loading = false;
        (Alpine.store("dojo") as DojoStore).startGlobalSync();
        (Alpine.store("dojo") as DojoStore).setPageReady(true);
      }

      // Capture phase so this runs before Alpine's bubble-phase window listeners
      // (e.g. @keydown.escape.window in base.html). stopImmediatePropagation()
      // in the Escape branch then prevents those listeners from firing when a
      // panel was open.
      window.addEventListener(
        "keydown",
        (e) => {
          const dojoStore = Alpine.store("dojo") as DojoStore;
          const dialogOpen = !!dojoStore?.dialog?.show;
          const targetEl = e.target as HTMLElement;
          const isTextInput =
            e.repeat || dialogOpen ? false : isTextInputTarget(targetEl);

          for (const shortcut of shortcutsFor(e, {
            dialogOpen,
            isTextInput,
            labOpen: this.labOpen,
          })) {
            if (shortcut.preventDefault) e.preventDefault();
            if (shortcut.stopPropagation) e.stopPropagation();
            switch (shortcut.action) {
              case "dialog-cancel":
                dojoStore.dialog.cancel();
                break;
              case "dialog-confirm":
                dojoStore.dialog.confirm();
                break;
              case "focus-warp":
                document
                  .querySelector<HTMLElement>("input[data-warp-input]")
                  ?.focus();
                break;
              case "escape": {
                const anyOpen = anyPanelOpen({
                  placementMode: this.placementMode,
                  annotationsOpen: this.annotationsOpen,
                  shapesOpen: this.shapesOpen,
                  xMenuOpen: this.xMenuOpen,
                  yMenuOpen: this.yMenuOpen,
                  refFrameMenuOpen: this.refFrameMenuOpen,
                  refFrameOriginMenuOpen: this.refFrameOriginMenuOpen,
                  plotConfigOpen: this.plotConfigOpen,
                  downloadOpen: this.downloadOpen,
                  editorOpen: this.editorOpen,
                  profilesOpen: this.profilesOpen,
                  vsMenuOpen: this.vsMenuOpen,
                  shareOpen: this.shareOpen,
                  notifOpen: (Alpine.store("dojo") as DojoStore).notifOpen,
                  labOpen: this.labOpen,
                  overlayCount: (Alpine.store("dojo") as DojoStore).overlayCount,
                  isTextInput,
                });
                if (isTextInput) targetEl.blur();
                this.placementMode = null;
                this.rectStart = null;
                this.cancelAnnDraft();
                this.cancelShapeDraft();
                this.annotationsOpen = false;
                this.shapesOpen = false;
                this.xMenuOpen = this.yMenuOpen = this.refFrameMenuOpen = this.refFrameOriginMenuOpen = false;
                this.plotConfigOpen = this.downloadOpen = this.editorOpen = false;
                this.profilesOpen = this.vsMenuOpen = this.shareOpen = false;
                (Alpine.store("dojo") as DojoStore).notifOpen = false;
                this.profileSearch = "";
                if (!this.labOpen || !window.mojoLabHasUnsavedChanges?.()) {
                  this.labOpen = false;
                } else {
                  void (
                    window.mojoConfirm?.({
                      title: "Unsaved changes",
                      message: "Close the lab and discard unsaved changes?",
                      confirmLabel: "Discard",
                      cancelLabel: "Keep editing",
                      variant: "warning",
                    }) ?? Promise.resolve(false)
                  ).then((ok) => {
                    if (ok) {
                      window.mojoLabRevertToSaved?.();
                      this.labOpen = false;
                    }
                  });
                }
                window.dispatchEvent(new CustomEvent("mojo:escape"));
                // Stop immediate propagation when something was open so Alpine's
                // bubble-phase @keydown.escape.window handler doesn't also fire.
                // This prevents Escape from both closing the lab and exiting fullscreen.
                if (anyOpen) e.stopImmediatePropagation();
                break;
              }
              case "lab-clear":
                document.dispatchEvent(new CustomEvent("mojo:lab-clear"));
                break;
              case "lab-save": {
                const nameEl = document.getElementById(
                  "lab-name-input",
                ) as HTMLInputElement | null;
                const name = nameEl?.value.trim() ?? "";
                if (name) {
                  const graph = window.mojoLabSerialize?.();
                  if (graph) void this.saveLabGraph(name, graph);
                } else {
                  nameEl?.focus();
                  nameEl?.setSelectionRange(0, 0);
                }
                break;
              }
              case "open-profiles":
                this._computeProfilesCoords();
                this.profilesOpen = true;
                void this.loadProfiles();
                void this.$nextTick(() => {
                  const el = document.getElementById(
                    "profile-name-input",
                  ) as HTMLInputElement | null;
                  if (el) {
                    el.focus();
                    el.setSelectionRange(el.value.length, el.value.length);
                  }
                });
                break;
              case "nav-prev":
                document.getElementById("nav-prev")?.click();
                break;
              case "nav-next":
                document.getElementById("nav-next")?.click();
                break;
              case "rate-down": {
                const prev = stepPlaybackRate(
                  this.mediaSpeedPresets,
                  this.mediaPlaybackRate,
                  "down",
                );
                if (prev !== undefined) this.mediaPlaybackRate = prev;
                break;
              }
              case "rate-up": {
                const next = stepPlaybackRate(
                  this.mediaSpeedPresets,
                  this.mediaPlaybackRate,
                  "up",
                );
                if (next !== undefined) this.mediaPlaybackRate = next;
                break;
              }
              case "undo":
                this.undo();
                break;
              case "redo":
                this.redo();
                break;
              case "lab-undo":
                window.mojoLabUndo?.();
                break;
              case "lab-redo":
                window.mojoLabRedo?.();
                break;
              case "lab-arrange":
                window.mojoLabArrange?.();
                break;
              case "lab-fit":
                window.mojoLabFitView?.();
                break;
              case "none":
                break;
            }
          }
        },
        { capture: true },
      );

      const resp = await fetch("/mosaic/api/trials");
      const data = (await resp.json()) as TrialManifest;
      this.allTrials = data.trials ?? [];

      if (this.allTrials.length) {
        const bounds = trialBounds(this.allTrials);
        if (bounds && this.vs.range[0] === 0 && this.vs.range[1] === 0) {
          this.vs.range = [bounds.min, bounds.max];
          this.vsDraft.range = [bounds.min, bounds.max];
        }
      }

      this.$watch("vsDraft.range", () => {
        if (this.discoveryTimeout) clearTimeout(this.discoveryTimeout);
        this.discoveryTimeout = setTimeout(() => {
          if (this.vsDraft.enabled) void this.startBackgroundDiscovery();
        }, 500);
      });

      this.$watch("vsDraft.pinned", () => {
        if (this.discoveryTimeout) clearTimeout(this.discoveryTimeout);
        this.discoveryTimeout = setTimeout(() => {
          if (this.vsDraft.enabled) void this.startBackgroundDiscovery();
        }, 500);
      });

      this.$watch("profileSearch", (val: string) => {
        try {
          localStorage.setItem("mojo:profile:search", val);
        } catch {
          /* ignore */
        }
      });

      this.$watch("labSearch", (val: string) => {
        try {
          localStorage.setItem("mojo:lab:search", val);
        } catch {
          /* ignore */
        }
      });

      this.$watch("mediaScrubMode", (mode: string) => {
        if (mode === "scrub") {
          (
            document.getElementById(
              "media-video-player",
            ) as HTMLVideoElement | null
          )?.pause();
        }
        try {
          localStorage.setItem("mojo:media:mode", mode);
        } catch {
          /* ignore */
        }
        this._syncOverlayVisibility();
        this._updatePlaybackLine();
      });

      this.$watch("mediaShowLine", (val: boolean) => {
        try {
          localStorage.setItem("mojo:media:show-line", val ? "1" : "0");
        } catch {
          /* ignore */
        }
        this._syncOverlayVisibility();
        this._updatePlaybackLine();
      });

      this.$watch("mediaShowFrames", (val: boolean) => {
        try {
          localStorage.setItem("mojo:media:show-frames", val ? "1" : "0");
        } catch {
          /* ignore */
        }
        this._syncOverlayVisibility();
        this._renderFrameMarkers();
        this._updatePlaybackLine();
      });

      this.$watch("mediaPlaybackRate", (rate: number) => {
        try {
          localStorage.setItem("mojo:media:rate", String(rate));
        } catch {
          /* ignore */
        }
        const video = document.getElementById(
          "media-video-player",
        ) as HTMLVideoElement | null;
        if (video) video.playbackRate = rate;
      });

      this.$watch("config.rangeX", () => {
        requestAnimationFrame(() => this._renderFrameMarkers());
      });

      this.$watch("selectedMedia", (file: string | null) => {
        if (file)
          try {
            localStorage.setItem("mojo:media:file", file);
          } catch {
            /* ignore */
          }
        const sel = (file ?? "").toLowerCase();
        this._gifConvertStatus = sel.endsWith(".gif") ? "loading" : "none";
        this._applySelectedMediaFps();
        this._updateIsScrubbable();
        this._renderFrameMarkers();
        this._updatePlaybackLine();
        if (this.mediaMiniplayerOpen) {
          this._stopMiniplayer();
          void this.$nextTick(() => this._startMiniplayer());
        }
        // catch cache-hit: browser may have loaded metadata before @loadedmetadata bound
        if (sel.endsWith(".gif")) {
          void this.$nextTick(() => {
            const video = document.getElementById(
              "media-video-player",
            ) as HTMLVideoElement | null;
            if (video && video.readyState >= HTMLMediaElement.HAVE_METADATA) {
              this._onVideoLoaded();
            }
          });
        }
      });

      this.$watch("mediaMiniplayerOpen", (open: boolean) => {
        try {
          localStorage.setItem("mojo:media:mini", open ? "1" : "0");
        } catch {
          /* ignore */
        }
        if (open && this.mediaFiles.length > 0) this._startMiniplayer();
        else this._stopMiniplayer();
      });

      this.$watch("_gifConvertStatus", () => {
        this._updateIsScrubbable();
        this._syncOverlayVisibility();
        this._updatePlaybackLine();
      });

      this.$watch("config.xAxis.col", (newCol: string) => {
        if (
          newCol &&
          !Object.prototype.hasOwnProperty.call(this.data ?? {}, newCol)
        ) {
          void (async () => {
            try {
              const resp = await this.fetchTrialData(this.trialId, [newCol]);
              this.data = { ...(this.data ?? {}), ...resp.data };
              this.saveAndRender();
            } catch {
              // non-critical
            }
          })();
        }
        requestAnimationFrame(() => {
          this._syncOverlayVisibility();
          this._renderFrameMarkers();
          this._updatePlaybackLine();
        });
      });

      this.$watch(
        "config.refFrame",
        (newValue: RefFrame, oldValue: RefFrame) => {
          if (sameRefFrame(newValue, oldValue)) return;
          this.notify(`Frame: ${refFrameLabel(newValue)}`, "info");
          this.discoveryId++;
          this.applyRefFrame(newValue);
          // config watcher handles re-fetch and re-render when yAxes.filters change
        },
      );

      this.$watch("config", async (value: PlotConfig, oldValue: PlotConfig) => {
        // re-validate on every config change, not just raw-JSON edits, so fixes
        // made through the UI (column pickers, filters, etc.) clear a stale
        // Config Error banner instead of requiring a page refresh
        this.configErrors = this.validateConfig(value);
        this.isValidConfig = this.configErrors.length === 0;
        this.isValidJson = true;

        if (!this.isEditingRaw) {
          this.configRaw = JSON.stringify(value, null, 4);
          try {
            localStorage.removeItem("mojo:config:raw-draft");
          } catch {}
        }
        if (needsVsSync(this.vs.enabled, value, oldValue)) {
          await this.syncVsRange();
        }
        this.pushHistory();

        // detect filter changes by comparing against the last-fetched fingerprint rather
        // than oldValue, because Alpine.js $watch does not reliably deep-clone oldValue
        // for nested reactive objects - both value and oldValue may point to the same data
        const plan = planConfigChange(
          value,
          this.filterFingerprints,
          this.xAxisFilterFingerprint,
        );
        if (plan.xFilterChanged) {
          this.xAxisFilterFingerprint = plan.xFilterFingerprint;
          if (this.data) delete this.data[value.xAxis.col!];
        }

        if (plan.colsToRefetch.length > 0) {
          plan.changedFilterCols.forEach((col) => {
            this.filterFingerprints[col] = plan.filterFingerprints[col]!;
            if (this.data) delete this.data[col];
          });
          this.vsDatasets = {};
          const resp = await this.fetchTrialData(this.trialId, plan.colsToRefetch);
          this.data = { ...(this.data ?? {}), ...resp.data };
          if (this.vs.enabled) await this.syncVsRange();
        }

        this.saveAndRender();
        this._syncOverlayVisibility();
        requestAnimationFrame(() => this._renderFrameMarkers());

        // keep the active PlotTab's mirror (config/data/etc.) and its
        // localStorage copy continuously in sync - without this, a whole-
        // object reassignment of this.config (undo/redo, loadProfile,
        // hydrateFromUrl all do `this.config = {...}` rather than mutating
        // in place) would leave plotTabs[activeId].config pointing at the
        // stale pre-change object until the next tab switch, which the tab
        // strip's title (tab.config.title) would otherwise briefly show.
        // A no-op before plotTabs is initialized (_initPlotTabs runs later
        // in boot; _snapshotActivePlotTab just returns when there's no
        // active tab yet to find).
        this._snapshotActivePlotTab();
        if (this.plotTabs.length > 0) this._persistPlotTabs();
      });

      // re-fetch data and column manifest when display unit system changes so the
      // plot values and unit dropdowns reflect the new unit system immediately
      this.$watch(
        "config.displayUnitSystem",
        async (newVal: string | null, oldVal: string | null) => {
          if (newVal === oldVal) return;
          const activeCols = activeColumns(this.config);
          this.vsDatasets = {};
          try {
            const resp = await this.fetchTrialData(this.trialId, activeCols);
            this.columnMetadata = resp.columns.column_metadata ?? {};
            // replace entirely so background-hydrated columns with stale unit values
            // are not used; startBackgroundDiscovery re-hydrates the rest
            this.data = resp.data;
            void this.renderPlot();
            // re-index frame markers after the plot re-renders with the new unit scale
            requestAnimationFrame(() => {
              this._renderFrameMarkers();
              this._syncOverlayVisibility();
            });
            void this.startBackgroundDiscovery();
          } catch (e) {
            console.warn("Display unit system re-fetch failed", e);
          }
        },
      );

      // re-fetch all data when max_points changes; also clear VS cache since
      // all previously fetched comparison datasets used the old point limit
      this.$watch(
        "config.maxPoints",
        async (newVal: number | null, oldVal: number | null) => {
          if (newVal === oldVal) return;
          const activeCols = activeColumns(this.config);
          this.vsDatasets = {};
          try {
            const resp = await this.fetchTrialData(this.trialId, activeCols);
            this.data = resp.data;
            void this.renderPlot();
            void this.startBackgroundDiscovery();
          } catch (e) {
            console.warn("Max points re-fetch failed", e);
          }
        },
      );

      void this.startBackgroundDiscovery();
      this.configRaw =
        localStorage.getItem("mojo:config:raw-draft") ??
        JSON.stringify(this.config, null, 4);
      this.updateFromRaw();

      // persist dist filter state across page loads and trial navigation
      this.$watch("distFilterName", (v: string) => {
        try {
          localStorage.setItem("mojo:dists:filter-name", v);
        } catch {
          /* ignore */
        }
      });
      this.$watch("distFilterCategories", (v: string[] | null) => {
        try {
          localStorage.setItem(
            "mojo:dists:filter-categories",
            JSON.stringify(v),
          );
        } catch {
          /* ignore */
        }
      });
      this.$watch("distFilterTypes", (v: string[] | null) => {
        try {
          localStorage.setItem("mojo:dists:filter-types", JSON.stringify(v));
        } catch {
          /* ignore */
        }
      });
      this.$watch("distFilterUnits", (v: string[] | null) => {
        try {
          localStorage.setItem("mojo:dists:filter-units", JSON.stringify(v));
        } catch {
          /* ignore */
        }
      });

      // re-pull distribution metadata when new job data arrives
      // ($store.dojo's own SSE handler already applies trial outcomes for
      // this event -- see startGlobalSync() in store.ts)
      window.addEventListener("mojo-data-updated", () => {
        void this.fetchDists();
      });

      // bootstrap trial outcome hints so vs-mode chips are colored before the
      // first SSE sync tick arrives
      void fetch("/monitor/api/status/job")
        .then((r) => r.json())
        .then((data: JobStatus) => {
          if (data && !data.error)
            (Alpine.store("dojo") as DojoStore).applyJobOutcomes(data);
        })
        .catch(() => {});

      window.addEventListener("mojo-sensai-plot-config", (e) => {
        const detail = (e as CustomEvent<PlotConfig>).detail;
        if (detail && typeof detail === "object") {
          this.config = { ...detail };
        }
      });

      window.addEventListener("mojo-sensai-undo", () => {
        this.undo();
      });
    },

    // -----------------------------------------------------------------------
    // VS (comparison) mode
    // -----------------------------------------------------------------------
    // Restores a VS comparison range/pinned selection WITHOUT ever
    // auto-enabling comparison mode - this is intentional, not an
    // oversight: turning VS on can pull a large amount of trial data
    // (every trial in range × every active column), so re-enabling it is
    // always an explicit user action (toggle + Apply in the header), never
    // implied by restoring a remembered range - whether that range came
    // from localStorage on a fresh page load or from a saved profile that
    // happened to have comparison mode on when it was saved.
    _restoreVsRange(range: [number, number], pinned: number[]) {
      this.vs.enabled = false;
      this.vs.range = range;
      this.vs.pinned = pinned;
      this.vsDatasets = {};
      this.vsDraft.enabled = false;
      this.vsDraft.range = [...range];
      this.vsDraft.pinned = [...pinned];
    },

    _initVsState() {
      let raw: string | null = null;
      try {
        raw = localStorage.getItem("mojo:plot:vs");
      } catch {}
      const { range, pinned } = parseStoredVs(raw, {
        range: this.vs.range,
        pinned: this.vs.pinned,
      });
      this._restoreVsRange(range, pinned);
    },

    _persistVsState() {
      try {
        localStorage.setItem(
          "mojo:plot:vs",
          JSON.stringify({ range: this.vs.range, pinned: this.vs.pinned }),
        );
      } catch {}
    },

    // same coloring as monitor.html's success/failed/error trial badges
    // (badge-success/-failure/-error in main.css: a translucent tinted
    // background + colored border/text, not a solid fill) -- their exact
    // padding/rounding/hover-scale isn't reused here since this renders as
    // a compact 5-column grid with its own sizing (see the static class at
    // the _header.html call site), but the color treatment matches. Pinned
    // trials get the same outcome color plus a ring, rather than switching
    // to a different (previously accent) fill.
    vsChipClass(t: string): string {
      const store = Alpine.store("dojo") as DojoStore;
      return chipClass(
        t,
        this.trialId,
        this.vsDraft.pinned,
        store.errorTrialNums,
        store.failureTrialNums,
      );
    },

    async syncVsRange() {
      try {
        const resp = await fetch("/mosaic/api/trials");
        const data = (await resp.json()) as TrialManifest;
        this.allTrials = data.trials ?? [];
      } catch (e) {
        console.warn("Manifest sync failed", e);
      }

      if (!this.vsDraft.enabled) {
        this.vs.enabled = false;
        this.vsDatasets = {};
        this._persistVsState();
        return;
      }

      this.vsLoading = true;
      try {
        const [start, end] = orderedRange(this.vsDraft.range);
        const activeCols = vsActiveColumns(this.config);

        const currentNum = trialNumber(this.trialId);
        const targetIds = vsTargetIds(
          this.allTrials,
          start,
          end,
          this.vsDraft.pinned,
          (_id, n) => n === currentNum,
        );

        await Promise.all(
          targetIds.map(async (id) => {
            const existing = this.vsDatasets[id];
            const needsFetch = vsNeedsFetch(
              existing,
              activeCols,
              refFrameActive(this.config.refFrame),
            );
            if (needsFetch) {
              const response = await this.fetchTrialData(id, activeCols);
              this.vsDatasets[id] = {
                ...(this.vsDatasets[id] ?? {}),
                ...response.data,
              };
            }
          }),
        );

        this.vsDatasets = { ...this.vsDatasets };
        this.vs.range = [start, end];
        this.vs.pinned = [...this.vsDraft.pinned];
        this.vs.enabled = true;
        this._persistVsState();
        if (targetIds.length > 0) {
          this.notify(comparingNotice(targetIds.length), "info");
        }
      } finally {
        this.vsLoading = false;
      }
    },

    handleVsToggle() {
      if (!this.vsDraft.enabled) {
        this.vs.enabled = false;
        this.vsDatasets = {};
        this._persistVsState();
        void this.renderPlot();
      }
    },

    // shared by every vs-range preset below so "the actual set of trial
    // numbers that exist" has exactly one computation, not one hand-rolled
    // per caller (setVsAll/isVsAll used to each redo this independently,
    // and setVsPreset skipped it entirely - see its own comment).
    vsTrialBounds(): { min: number; max: number } | null {
      return trialBounds(this.allTrials);
    },

    setVsPreset(delta: number) {
      this.vsDraft.range = presetRange(this.trialId, delta, this.vsTrialBounds());
    },

    setVsAll() {
      const bounds = this.vsTrialBounds();
      if (!bounds) return;
      this.vsDraft.range = [bounds.min, bounds.max];
    },

    isVsPreset(delta: number): boolean {
      const [lo, hi] = presetRange(this.trialId, delta, this.vsTrialBounds());
      const [a, b] = this.vsDraft.range;
      return Math.min(a, b) === lo && Math.max(a, b) === hi;
    },

    isVsAll(): boolean {
      const bounds = this.vsTrialBounds();
      if (!bounds) return false;
      const [a, b] = this.vsDraft.range;
      return Math.min(a, b) === bounds.min && Math.max(a, b) === bounds.max;
    },

    vsInRangeCount(): number {
      return countInRange(this.allTrials, this.vsDraft.range, this.trialId);
    },

    vsTotalCount(): number {
      return countWithPinned(this.allTrials, this.vsDraft.range, this.vsDraft.pinned, this.trialId);
    },

    toggleVsPin(n: number) {
      this.vsDraft.pinned = togglePinned(this.vsDraft.pinned, n);
    },

    // -----------------------------------------------------------------------
    // Column filtering & search
    // -----------------------------------------------------------------------
    smartSort,

    getFilteredCols(field: string): string[] {
      if (!this.columns || !Array.isArray(this.columns)) return [];
      const base =
        field === "x" || field === "nodeCol"
          ? this.columns
          : field === "nodeQuat" || field === "refFrame"
            ? this.availableQuats
            : field === "nodeOrigin" || field === "refFrameOrigin"
              ? this.rotateableVectors
              : this.selectableYColumns;
      const search =
        (this as unknown as Record<string, string>)[field + "Search"] ?? "";
      return filterColumns(base, search);
    },

    // Folder-tree view (lib/tree.ts) over getFilteredCols(field) - a second,
    // orthogonal way to browse the *already* quick-filter/chip-narrowed
    // result set into "/"-delimited groups, not a replacement for the chips
    // above (which keep doing exactly what they did before). One flat map
    // keyed by "field:path" covers every field this dropdown pattern is
    // used for (x, y, nodeCol, nodeQuat) rather than one Record per field.
    // Unlike profileTreeCollapsed/labTreeCollapsed, folders here default to
    // COLLAPSED, not expanded: a column list can run into the hundreds
    // across many folders, where profiles/labs are typically few - starting
    // collapsed is what actually declutters that case, so an absent entry
    // here means "collapsed" instead of the opposite default those two use.
    columnTreeCollapsed: {} as Record<string, boolean>,
    // Caches getColumnTreeRows' result per field, keyed on the few things
    // that actually change it (the underlying columns array's identity,
    // config.refFrame for the y field's rotatable-vector restriction, and
    // that field's own search string) - NOT columnTreeCollapsed, which is
    // deliberately excluded so a plain folder toggle can't invalidate it.
    // Before this, every toggle re-ran getFilteredCols (regex filter +
    // sort) and rebuilt the whole tree from scratch even though neither
    // actually depends on which folders happen to be open - free for
    // Profiles' handful of entries, but real, repeated O(n log n) work on
    // a signal tree with hundreds of columns, which is what made folder
    // expansion feel slow there specifically while staying instant on
    // Profiles. selectableYColumns/availableQuats are getters that build a
    // fresh array on every access, so their own reference can't be used to
    // detect "did the underlying data actually change" - comparing
    // this.columns (a plain, only-reassigned-not-mutated property) plus
    // refFrame instead sidesteps that without needing to materialize
    // either getter just to check the cache.
    _columnTreeRowsCache: {} as Record<
      string,
      { colsRef: string[]; refFrame: string; search: string; rows: TreeRow<string>[] }
    >,
    // extraFilter: an additional per-column predicate beyond
    // getFilteredCols(field) itself - the Y-axis dropdown also excludes
    // non-rotateable columns while a reference frame is active, a
    // condition specific to that one call site rather than something
    // getFilteredCols itself should know about.
    getColumnTreeRows(field: string, extraFilter?: (col: string) => boolean): TreeRow<string>[] {
      // 'y' is called both without extraFilter (the has-folders check
      // driving tree_expand_collapse_buttons' x-show) and with it (actual
      // row rendering) - two different result sets for the same field, so
      // they need their own cache slots or one call would silently return
      // the other's (stale, wrongly filtered or wrongly unfiltered) rows.
      const cacheKey = extraFilter ? `${field}:filtered` : field;
      const search = (this as unknown as Record<string, string>)[field + "Search"] ?? "";
      const refFrame = this.config.refFrame.join("|");
      const cached = this._columnTreeRowsCache[cacheKey];
      if (
        cached &&
        cached.colsRef === this.columns &&
        cached.refFrame === refFrame &&
        cached.search === search
      ) {
        return cached.rows;
      }
      const cols = this.getFilteredCols(field);
      const rows = buildTreeRowsFromNames(extraFilter ? cols.filter(extraFilter) : cols);
      this._columnTreeRowsCache[cacheKey] = { colsRef: this.columns, refFrame, search, rows };
      return rows;
    },
    // Single source of truth for "is this column-tree folder currently
    // collapsed" (default true, absent an explicit entry) - used by the
    // chevron's own rotation in the template as well as the two call sites
    // below, so the chevron can never again show "open" for a folder
    // getColumnVisibleRows is actually treating as collapsed (or vice
    // versa) the way two separately-duplicated copies of this same
    // true-when-absent fallback drifting apart once already caused.
    isColumnFolderCollapsed(field: string, path: string): boolean {
      const key = field + ":" + path;
      return key in this.columnTreeCollapsed ? !!this.columnTreeCollapsed[key] : true;
    },
    // Last output of getColumnVisibleRows per field (same field:filtered
    // keying as _columnTreeRowsCache, for the same reason) - fed back into
    // visibleTreeRows as `previous` so it can hand back the exact same row
    // reference for anything whose hidden state didn't change on this
    // call, rather than a fresh spread copy of every row every time. See
    // visibleTreeRows' own comment in lib/tree.ts for why that reference
    // stability is what actually lets Alpine skip re-evaluating most of
    // the tree's bindings on a single folder toggle.
    _columnVisibleRowsCache: {} as Record<string, TreeRow<string>[]>,
    getColumnVisibleRows(field: string, extraFilter?: (col: string) => boolean): TreeRow<string>[] {
      const cacheKey = extraFilter ? `${field}:filtered` : field;
      const rows = this.getColumnTreeRows(field, extraFilter);
      const collapsed: Record<string, boolean> = {};
      for (const row of rows) {
        if (row.type !== "folder") continue;
        collapsed[row.path] = this.isColumnFolderCollapsed(field, row.path);
      }
      const result = visibleTreeRows(
        rows,
        collapsed,
        "",
        () => true,
        this._columnVisibleRowsCache[cacheKey],
      );
      this._columnVisibleRowsCache[cacheKey] = result;
      return result;
    },
    toggleColumnFolder(field: string, path: string) {
      const key = field + ":" + path;
      this.columnTreeCollapsed = { ...this.columnTreeCollapsed, [key]: !this.isColumnFolderCollapsed(field, path) };
    },
    expandAllColumnFolders(field: string) {
      const prefix = field + ":";
      const next = { ...this.columnTreeCollapsed };
      for (const path of allTreeFolderPaths(this.getColumnTreeRows(field))) next[prefix + path] = false;
      this.columnTreeCollapsed = next;
    },
    collapseAllColumnFolders(field: string) {
      const prefix = field + ":";
      const next = { ...this.columnTreeCollapsed };
      for (const path of allTreeFolderPaths(this.getColumnTreeRows(field))) next[prefix + path] = true;
      this.columnTreeCollapsed = next;
    },

    toggleRegexSegment(
      field: string,
      segment: string,
      depth: number | "suffix",
    ) {
      const key = field + "Search";
      const self = this as unknown as Record<string, string>;
      self[key] = toggleSearchSegment(self[key] ?? "", segment, depth, this.columns);
    },

    getSegmentsAtDepth(field: string, depth: number): string[] {
      const base =
        field === "x" || field === "nodeCol"
          ? this.columns
          : field === "nodeQuat" || field === "refFrame"
            ? this.availableQuats
            : field === "nodeOrigin" || field === "refFrameOrigin"
              ? this.rotateableVectors
              : this.selectableYColumns;
      const search =
        (this as unknown as Record<string, string>)[field + "Search"] ?? "";
      return searchSegmentsAtDepth(base, search, depth);
    },

    getAvailableSuffixes(field: string): string[] {
      const base =
        field === "x" || field === "nodeCol"
          ? this.columns
          : field === "nodeQuat" || field === "refFrame"
            ? this.availableQuats
            : field === "nodeOrigin" || field === "refFrameOrigin"
              ? this.rotateableVectors
              : this.selectableYColumns;
      const search =
        (this as unknown as Record<string, string>)[field + "Search"] ?? "";
      return searchAvailableSuffixes(base, search);
    },

    isSegmentActive(
      field: string,
      seg: string,
      depth: number | "suffix",
    ): boolean {
      const search =
        (this as unknown as Record<string, string>)[field + "Search"] ?? "";
      return isSearchSegmentActive(search, seg, depth);
    },

    getActiveLevels(field: string): number[] {
      const search =
        (this as unknown as Record<string, string>)[field + "Search"] ?? "";
      return searchActiveLevels(search);
    },

    // -----------------------------------------------------------------------
    // JSON editor
    // -----------------------------------------------------------------------
    get highlightedJson(): string {
      return highlightJson(this.configRaw);
    },

    validateConfig(cfg: PlotConfig): string[] {
      // the cast bridges two structurally-equivalent-but-nominally-different
      // JsonSchemaNode types (this file's own, from lib/json-schema.ts, and the
      // looser Record<string, unknown> lib/schema-validate.ts takes): both are
      // the same arbitrary JSON Schema object at different strictness levels
      return validatePlotConfig(cfg, {
        schema: this.plotConfigSchema as Record<string, unknown> | null,
        labSchemas: this.labSchemas,
        columns: this.columns,
      });
    },

    updateFromRaw() {
      try {
        localStorage.setItem("mojo:config:raw-draft", this.configRaw);
      } catch {}
      const raw = parseRawConfig(this.configRaw);
      if (!raw.json) {
        this.isValidJson = false;
        this.isValidConfig = false;
        return;
      }
      try {
        const parsed = raw.config;
        this.isValidJson = true;
        if (parsed) {
          this.configErrors = this.validateConfig(parsed);
          this.isValidConfig = this.configErrors.length === 0;
          if (this.isValidConfig) {
            const prevRefFrame = this.config.refFrame;
            this.isEditingRaw = true;
            this.config = { ...this.config, ...parsed };
            // Apply rotation filters synchronously. $watch("config.refFrame") fires
            // asynchronously after the whole config object is replaced, so filters
            // would be wrong during the first render if we relied solely on the watch.
            const nextRefFrame = this.config.refFrame;
            if (!sameRefFrame(nextRefFrame, prevRefFrame)) {
              this.applyRefFrame(nextRefFrame);
            }
            void this.$nextTick(() => {
              this.isEditingRaw = false;
            });
          }
        }
      } catch {
        this.isValidJson = false;
        this.isValidConfig = false;
      }
    },

    // -----------------------------------------------------------------------
    // Config persistence
    // -----------------------------------------------------------------------
    loadConfig() {
      const saved = localStorage.getItem("mojo_mosaic_config");
      if (saved) {
        const parsed = parseSavedConfig(saved);
        if (parsed !== null) this.config = { ...this.config, ...parsed };
        else console.error("Stored config corrupt");
      } else {
        if (this.columns.includes("time")) this.config.xAxis.col = "time";
      }

      const savedHistory = localStorage.getItem("mojo_mosaic_history");
      if (savedHistory) {
        const history = parseSavedHistory(savedHistory);
        if (history) {
          this.historyStack = history.stack;
          this.historyIndex = history.index;
        } else {
          console.warn("History recovery failed.");
          this.pushHistory();
        }
      } else {
        this.pushHistory();
      }
      this.configRaw = JSON.stringify(this.config, null, 4);
    },

    saveAndRender() {
      localStorage.setItem("mojo_mosaic_config", JSON.stringify(this.config));
      this.persistHistory();
      void this.renderPlot();
      void this.$nextTick(() => {
        const el = document.getElementById("plot-area");
        if (el && el.offsetParent !== null) Plotly.Plots.resize(el);
      });
    },

    hydrateFromUrl(blob: string) {
      try {
        const parsed = decodeShareConfig(blob);
        this.config = { ...this.config, ...parsed };
        this.notify("Shared view loaded", "success");
      } catch {
        this.notify("Failed to decode shared link", "error");
        this.loadConfig();
      }
    },

    // -----------------------------------------------------------------------
    // Exports / clipboard
    // -----------------------------------------------------------------------
    copyShareLink() {
      try {
        const encoded = encodeShareConfig(this.config);
        const shareBase = this.externalUrl + window.location.pathname;
        void this.copyToClipboard(
          `${shareBase}?v=${encoded}`,
          "Shareable link copied!",
        );
      } catch {
        this.notify("Link generation failed", "error");
      }
    },

    copyRawConfig() {
      void this.copyToClipboard(this.configRaw, "JSON Config copied!");
    },

    // Accepts either a bare shared-link code (the ?v= value alone) or a
    // full URL containing one, so pasting the whole copied link just
    // works without the user having to trim it down themselves.
    _extractShareBlob: extractShareBlob,

    // Adds a shared link as a NEW tab instead of replacing the session the
    // way opening a ?v= link in a fresh page load does (hydrateFromUrl) -
    // lets several links get combined into one browser window one at a
    // time, e.g. pasting a colleague's link alongside your own tabs.
    async addTabFromShareLink(input: string) {
      const blob = this._extractShareBlob(input);
      if (!blob) {
        this.notify("Paste a shared link first", "error");
        return;
      }
      try {
        const parsed = decodeShareConfig(blob);
        const config = {
          ...(JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as PlotConfig),
          ...parsed,
        };
        this._snapshotActivePlotTab();
        const newTab: PlotTab = {
          id: newTabId(),
          config,
          data: null,
          filterFingerprints: {},
          xAxisFilterFingerprint: "[]",
          historyStack: [],
          historyIndex: -1,
          savedSnapshot: null,
        };
        this.plotTabs.push(newTab);
        await this._activatePlotTab(newTab.id);
        this._persistPlotTabs();
        this.mergeLinkDraft = "";
        this.shareOpen = false;
        this.notify("Tab added from shared link", "success");
      } catch {
        this.notify("Failed to decode shared link", "error");
      }
    },

    // Forces an immediate Plotly resize of the main chart. initChartResize's
    // own resize handling only fires from its drag handle (a height change);
    // this covers width changes from elsewhere, e.g. _chart.html's x-init
    // watches $store.dojo.isFullscreen and calls this, since that toggle
    // changes the page's own max-width rather than anything the drag handle
    // observes. Referenced by name (not a bare `Plotly` global) because
    // that inline Alpine expression isn't bundled TS and can't reach the
    // module-scoped Plotly import in lib/plotly.ts.
    resizeMainPlot() {
      const plotEl = document.getElementById("plot-area");
      if (plotEl && plotEl.offsetParent !== null) Plotly.Plots.resize(plotEl);
    },

    initChartResize(hostEl: HTMLElement | undefined) {
      if (!hostEl || hostEl.dataset.resizeAttached) return;
      hostEl.dataset.resizeAttached = "true";

      restorePersistedHeight(hostEl, "mojo:chart:height");

      // Plotly.Plots.resize() can take longer than a single frame, so a
      // simple rAF throttle would drop requests that arrive mid-resize and
      // leave the plot visibly lagging behind the cursor. Instead, queue at
      // most one follow-up resize so it keeps catching up to the latest size.
      let resizeRaf: number | null = null;
      let resizeQueued = false;
      const doResize = () => {
        resizeRaf = null;
        const plotEl = document.getElementById("plot-area");
        if (plotEl && plotEl.offsetParent !== null) Plotly.Plots.resize(plotEl);
        if (resizeQueued) {
          resizeQueued = false;
          resizeRaf = requestAnimationFrame(doResize);
        }
      };
      const resizePlot = () => {
        if (resizeRaf !== null) {
          resizeQueued = true;
          return;
        }
        resizeRaf = requestAnimationFrame(doResize);
      };

      attachVerticalResizeHandle(hostEl, {
        storageKey: "mojo:chart:height",
        minHeight: 300,
        onResize: resizePlot,
        getResetHeight: () => "521.133px",
      });

      // Fill (or shrink to) the restored height once the plot has rendered.
      resizePlot();
    },

    initCodeMirror(hostEl: HTMLElement) {
      if (!hostEl || _cm.editor) return;

      // Restore persisted height before creating the editor so it sizes correctly.
      restorePersistedHeight(hostEl, "mojo:json-editor:height");

      // --- themes (base chrome only; highlight handled separately) ---
      const darkTheme = EditorView.theme(
        {
          "&": {
            backgroundColor: themeColor("slate-950"),
            color: themeColor("slate-300"),
            height: "100%",
          },
          ".cm-scroller": {
            overflow: "auto",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: "0.875rem",
            lineHeight: "1.625",
          },
          ".cm-content": {
            padding: "1rem",
            caretColor: themeColor("accent-500"),
          },
          ".cm-cursor": { borderLeftColor: themeColor("accent-500") },
          ".cm-gutters": {
            backgroundColor: themeColor("slate-900"),
            color: themeColor("slate-600"),
            borderRight: `1px solid ${themeColor("slate-800")}`,
          },
          ".cm-activeLineGutter": {
            backgroundColor: themeColorAlpha("slate-900", 0.6),
          },
          ".cm-activeLine": {
            backgroundColor: themeColorAlpha("slate-900", 0.4),
          },
          ".cm-selectionBackground": {
            backgroundColor: `${themeColorAlpha("accent-500", 0.4)} !important`,
          },
          "&.cm-focused .cm-selectionBackground": {
            backgroundColor: `${themeColorAlpha("accent-500", 0.4)} !important`,
          },
          ".cm-matchingBracket": {
            color: themeColor("accent-400"),
            fontWeight: "bold",
          },
          ".cm-tooltip": {
            backgroundColor: themeColor("slate-800"),
            border: `1px solid ${themeColor("slate-700")}`,
            color: themeColor("slate-300"),
          },
          ".cm-panels": {
            backgroundColor: themeColor("slate-900"),
            borderColor: themeColor("slate-800"),
            color: themeColor("slate-300"),
          },
          ".cm-searchMatch": {
            backgroundColor: themeColorAlpha("accent-400", 0.18),
          },
          ".cm-searchMatch.cm-searchMatch-selected": {
            backgroundColor: themeColorAlpha("accent-400", 0.35),
          },
          ".cm-lintRange-error": {
            backgroundImage: "none",
            textDecoration: `underline wavy ${themeColor("danger")} 1.5px`,
            textUnderlineOffset: "3px",
          },
          ".cm-lintRange-warning": {
            backgroundImage: "none",
            textDecoration: `underline wavy ${themeColor("warning")} 1.5px`,
            textUnderlineOffset: "3px",
          },
          ".cm-diagnostic-error": {
            borderLeft: `3px solid ${themeColor("danger")}`,
          },
        },
        { dark: true },
      );

      const lightTheme = EditorView.theme(
        {
          "&": {
            backgroundColor: themeColor("white"),
            color: themeColor("slate-900"),
            height: "100%",
          },
          ".cm-scroller": {
            overflow: "auto",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: "0.875rem",
            lineHeight: "1.625",
          },
          ".cm-content": {
            padding: "1rem",
            caretColor: themeColor("accent-600"),
          },
          ".cm-cursor": { borderLeftColor: themeColor("accent-600") },
          ".cm-gutters": {
            backgroundColor: themeColor("slate-50"),
            color: themeColor("slate-400"),
            borderRight: `1px solid ${themeColor("slate-200")}`,
          },
          ".cm-activeLineGutter": {
            backgroundColor: themeColorAlpha("slate-100", 0.6),
          },
          ".cm-activeLine": {
            backgroundColor: themeColorAlpha("slate-100", 0.5),
          },
          ".cm-selectionBackground": {
            backgroundColor: `${themeColorAlpha("accent-500", 0.4)} !important`,
          },
          "&.cm-focused .cm-selectionBackground": {
            backgroundColor: `${themeColorAlpha("accent-500", 0.4)} !important`,
          },
          ".cm-matchingBracket": {
            color: themeColor("accent-600"),
            fontWeight: "bold",
          },
          ".cm-tooltip": {
            backgroundColor: themeColor("slate-50"),
            border: `1px solid ${themeColor("slate-200")}`,
            color: themeColor("slate-900"),
          },
          ".cm-panels": {
            backgroundColor: themeColor("slate-50"),
            borderColor: themeColor("slate-200"),
          },
          ".cm-searchMatch": {
            backgroundColor: themeColorAlpha("accent-600", 0.15),
          },
          ".cm-searchMatch.cm-searchMatch-selected": {
            backgroundColor: themeColorAlpha("accent-600", 0.3),
          },
          ".cm-lintRange-error": {
            backgroundImage: "none",
            textDecoration: `underline wavy ${themeColor("danger")} 1.5px`,
            textUnderlineOffset: "3px",
          },
          ".cm-lintRange-warning": {
            backgroundImage: "none",
            textDecoration: `underline wavy ${themeColor("warning")} 1.5px`,
            textUnderlineOffset: "3px",
          },
          ".cm-diagnostic-error": {
            borderLeft: `3px solid ${themeColor("danger")}`,
          },
        },
        { dark: false },
      );

      const isDark = () => document.documentElement.classList.contains("dark");
      const themeComp = new Compartment();
      const highlightComp = new Compartment();
      const makeTheme = (dark: boolean) => (dark ? darkTheme : lightTheme);
      const makeHighlight = (dark: boolean) =>
        syntaxHighlighting(
          dark ? oneDarkHighlightStyle : defaultHighlightStyle,
        );

      // Base (theme-independent) styling for the hover tooltip's own DOM
      // below - the surrounding .cm-tooltip chrome (background/border/text
      // color) already comes from darkTheme/lightTheme above for free,
      // since hoverTooltip wraps whatever create() returns in that same
      // .cm-tooltip container; this only needs to add what's specific to
      // this content (a readable prose font instead of the editor's own
      // monospace, and a width cap so a long description wraps instead of
      // stretching across the whole document).
      const plotFieldTooltipBaseTheme = EditorView.baseTheme({
        ".cm-plot-field-tooltip": {
          maxWidth: "260px",
          padding: "0.5rem 0.625rem",
          fontSize: "0.75rem",
          lineHeight: "1.4",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
        },
      });

      // Shows a PlotConfig field's Field(description=...) (via
      // plotConfigSchema, /mosaic/api/plot-config-schema) when hovering
      // any JSON key or value in the document - jsonPathAt (module scope,
      // above) walks CodeMirror's own parse tree to find which field
      // that position is inside, including nested ones (e.g. a signal's
      // own "color" key under "yAxes"), the same schema-path resolution
      // the Plot Editor's own field_help_icon tooltips use
      // (_macros.html/plotFieldHelp) - one schema, one field/description
      // relationship, read by both UIs instead of each hand-maintaining
      // its own copy of what a field means.
      const plotFieldHoverTooltip = hoverTooltip((view, pos): Tooltip | null => {
        const path = jsonPathAt(view.state, pos);
        if (path.length === 0) return null;
        const description = describeSchemaPath(this.plotConfigSchema, path);
        if (!description) return null;
        const node = syntaxTree(view.state).resolveInner(pos, -1);
        return {
          pos: node.from,
          end: node.to,
          above: true,
          create: () => {
            const dom = document.createElement("div");
            dom.className = "cm-plot-field-tooltip";
            dom.textContent = description;
            return { dom };
          },
        };
      });

      // Underlines the exact JSON range for each schema violation
      // collectSchemaDiagnostics finds (type mismatches, discriminated-
      // union mismatches, and unknown/"extra" keys - the same
      // extra_forbidden error the server raises for e.g. a stray leftover
      // filter param left over from switching that filter's type). Runs
      // alongside jsonParseLinter (which only ever catches malformed JSON
      // text, not schema violations) rather than replacing it - CM6
      // supports multiple linter() sources side by side. Skips entirely
      // when the document isn't valid JSON yet (jsonParseLinter already
      // covers that) or before plotConfigSchema has loaded (see the
      // forceLinting call in init(), which re-runs this once it has).
      const plotConfigSchemaLinter = linter((view): Diagnostic[] => {
        if (!this.plotConfigSchema) return [];
        let parsed: unknown;
        try {
          parsed = JSON.parse(view.state.doc.toString());
        } catch {
          return [];
        }
        return collectSchemaDiagnostics(parsed, this.plotConfigSchema as Record<string, unknown>)
          .map(({ path, message }): Diagnostic | null => {
            const range = jsonRangeForPath(view.state, path);
            return range ? { ...range, severity: "error", message } : null;
          })
          .filter((d): d is Diagnostic => d !== null);
      });

      const startState = EditorState.create({
        doc: this.configRaw,
        extensions: [
          basicSetup,
          json(),
          lintGutter(),
          linter(jsonParseLinter()),
          plotConfigSchemaLinter,
          themeComp.of(makeTheme(isDark())),
          highlightComp.of(makeHighlight(isDark())),
          plotFieldTooltipBaseTheme,
          plotFieldHoverTooltip,
          EditorView.updateListener.of((update) => {
            if (update.docChanged && !_cm.updating) {
              const text = update.state.doc.toString();
              _cm.updating = true;
              this.configRaw = text;
              if (_cm.debounce !== null) clearTimeout(_cm.debounce);
              _cm.debounce = setTimeout(() => {
                this.updateFromRaw();
                _cm.debounce = null;
              }, 500);
              _cm.updating = false;
            }
          }),
        ],
      });

      _cm.editor = new EditorView({ state: startState, parent: hostEl });

      // Custom resize handle
      attachVerticalResizeHandle(hostEl, {
        storageKey: "mojo:json-editor:height",
        minHeight: 128,
        getResetHeight: () => {
          // .cm-scroller fills the host at 100% height, so its scrollHeight
          // equals the panel height when content is shorter (useless for
          // shrinking). .cm-content has natural height matching actual content.
          const content = hostEl.querySelector<HTMLElement>(".cm-content");
          if (!content) return undefined;
          return Math.max(128, content.offsetHeight) + "px";
        },
      });

      // Swap theme when dark mode toggles.
      new MutationObserver(() => {
        const dark = isDark();
        _cm.editor?.dispatch({
          effects: [
            themeComp.reconfigure(makeTheme(dark)),
            highlightComp.reconfigure(makeHighlight(dark)),
          ],
        });
      }).observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["class"],
      });

      // Sync external configRaw changes into CM.
      this.$watch("configRaw", (val: string) => {
        if (!_cm.updating && _cm.editor) {
          const current = _cm.editor.state.doc.toString();
          if (current !== val) {
            _cm.updating = true;
            _cm.editor.dispatch({
              changes: { from: 0, to: current.length, insert: val },
            });
            _cm.updating = false;
          }
        }
      });
    },

    initMetadataViewer(hostEl: HTMLElement, jsonText: string): object | null {
      if (!hostEl) return null;
      const isDark = document.documentElement.classList.contains("dark");
      const darkTheme = EditorView.theme(
        {
          "&": {
            backgroundColor: themeColor("slate-950"),
            color: themeColor("slate-300"),
          },
          ".cm-scroller": {
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: "0.8rem",
            lineHeight: "1.625",
          },
          ".cm-content": {
            padding: "0.6rem 0.75rem",
            caretColor: themeColor("accent-500"),
          },
          ".cm-gutters": { display: "none" },
          ".cm-cursor, .cm-dropCursor": { display: "none" },
          ".cm-activeLine": { backgroundColor: "transparent" },
          ".cm-selectionBackground": {
            backgroundColor: `${themeColorAlpha("accent-500", 0.4)} !important`,
          },
          "&.cm-focused .cm-selectionBackground": {
            backgroundColor: `${themeColorAlpha("accent-500", 0.4)} !important`,
          },
        },
        { dark: true },
      );
      const lightTheme = EditorView.theme(
        {
          "&": {
            backgroundColor: themeColor("white"),
            color: themeColor("slate-900"),
          },
          ".cm-scroller": {
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: "0.8rem",
            lineHeight: "1.625",
          },
          ".cm-content": {
            padding: "0.6rem 0.75rem",
            caretColor: themeColor("accent-600"),
          },
          ".cm-gutters": { display: "none" },
          ".cm-cursor, .cm-dropCursor": { display: "none" },
          ".cm-activeLine": { backgroundColor: "transparent" },
          ".cm-selectionBackground": {
            backgroundColor: `${themeColorAlpha("accent-500", 0.4)} !important`,
          },
          "&.cm-focused .cm-selectionBackground": {
            backgroundColor: `${themeColorAlpha("accent-500", 0.4)} !important`,
          },
        },
        { dark: false },
      );
      const state = EditorState.create({
        doc: jsonText,
        extensions: [
          EditorState.readOnly.of(true),
          json(),
          isDark ? darkTheme : lightTheme,
          syntaxHighlighting(
            isDark ? oneDarkHighlightStyle : defaultHighlightStyle,
          ),
        ],
      });
      return new EditorView({ state, parent: hostEl });
    },

    async resetConfig() {
      const ok = await window.mojoConfirm?.({
        title: "Reset settings",
        message:
          "Reset plot to factory defaults? This will clear your current view.",
        confirmLabel: "Reset",
        cancelLabel: "Cancel",
        variant: "danger",
      });
      if (ok) {
        localStorage.removeItem("mojo_mosaic_config");
        this.config = JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as PlotConfig;
        if (this.columns.includes("time")) this.config.xAxis.col = "time";
        this.notify("Settings Reset", "info");
        this.configRaw = JSON.stringify(this.config, null, 4);
      }
    },

    async copyToClipboard(text: string, successMsg = "Copied to clipboard!") {
      if (navigator.clipboard && window.isSecureContext) {
        try {
          await navigator.clipboard.writeText(text);
          this.notify(successMsg, "success");
          return;
        } catch (err) {
          console.warn("Modern clipboard failed, falling back...", err);
        }
      }
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.cssText = "position:fixed;left:-9999px;top:0";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        if (document.execCommand("copy")) {
          this.notify(successMsg, "success");
        } else throw new Error("execCommand returned false");
      } catch {
        this.notify("Failed to copy to clipboard", "error");
      }
      document.body.removeChild(textArea);
    },

    async downloadPlot(format: string, scale = 1) {
      const el = document.getElementById("plot-area") as HTMLElement & {
        layout: { paper_bgcolor: string; plot_bgcolor: string };
      };
      if (!el) return;
      const plotlyFormat = plotImageFormat(format);
      const bgColor = themeColor("surface");
      const { width: resW, height: resH } = plotExportSize(scale);
      this.notify(
        `Exporting ${resW}x${resH} ${format.toUpperCase()}...`,
        "info",
      );
      try {
        const origPaper = el.layout.paper_bgcolor;
        const origPlot = el.layout.plot_bgcolor;
        await Plotly.relayout(el, {
          paper_bgcolor: bgColor,
          plot_bgcolor: bgColor,
        });
        const dataUrl = await Plotly.toImage(el, {
          format: plotlyFormat,
          width: 1280,
          height: 720,
          scale,
        });
        await Plotly.relayout(el, {
          paper_bgcolor: origPaper,
          plot_bgcolor: origPlot,
        });
        const link = document.createElement("a");
        link.href = dataUrl;
        link.download = plotExportFileName(this.trialId, resW, format);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        this.notify(
          `${format.toUpperCase()} saved (${resW}×${resH})`,
          "success",
        );
      } catch (e) {
        console.error("Export failed", e);
        this.notify("Export failed", "error");
      } finally {
        this.downloadOpen = false;
      }
    },

    downloadCSV() {
      if (!this.data || Object.keys(this.config.yAxes).length === 0) return;
      const csv = csvText(
        this.data,
        this.config.xAxis.col!,
        Object.keys(this.config.yAxes),
      );
      const link = document.createElement("a");
      link.href = URL.createObjectURL(
        new Blob([csv], { type: "text/csv;charset=utf-8;" }),
      );
      link.setAttribute("download", csvFileName(this.trialId));
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      this.downloadOpen = false;
      this.notify("Filtered CSV Exported", "success");
    },

    downloadJSON() {
      const link = document.createElement("a");
      link.href = URL.createObjectURL(
        new Blob([JSON.stringify(this.config)], {
          type: "application/json",
        }),
      );
      link.setAttribute("download", configFileName(this.trialId));
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      this.downloadOpen = false;
      this.notify("Configuration JSON Exported", "success");
    },

    // fetched fresh rather than assembled from local state, so it matches what
    // the server reports for this trial right now: Lab columns and their
    // metadata, and units in the selected display unit system
    async downloadColumnManifest() {
      this.downloadOpen = false;
      try {
        const { columns } = await this.fetchTrialData(this.trialId, []);
        const link = document.createElement("a");
        link.href = URL.createObjectURL(
          new Blob([JSON.stringify(columns, null, 2)], {
            type: "application/json",
          }),
        );
        link.setAttribute("download", manifestFileName(this.trialId));
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        this.notify("Column Manifest Exported", "success");
      } catch (e) {
        console.error("Column manifest export failed", e);
        this.notify("Column manifest export failed", "error");
      }
    },

    handleDrop(e: DragEvent) {
      const file = e.dataTransfer?.files[0];
      if (!file) return; // not a file drop (e.g. internal tab reorder) — ignore silently
      if (file.type !== "application/json" && !file.name.endsWith(".json")) {
        this.notify("Please drop a .json file", "error");
        return;
      }
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const imported = JSON.parse(
            event.target?.result as string,
          ) as Partial<PlotConfig>;
          this.config = { ...this.config, ...imported };
          this.notify("Configuration restored!", "success");
          this.configRaw = JSON.stringify(this.config, null, 4);
        } catch {
          this.notify("Invalid Config File", "error");
        }
      };
      reader.readAsText(file);
    },

    // -----------------------------------------------------------------------
    // Y-axis management
    // -----------------------------------------------------------------------
    // anchor for shift-click range-select in the Y-axis tree, below.
    lastYRangeClick: null as string | null,
    // Shift-click toggles every file row between the last-clicked row and
    // this one (in the tree's current visible order) to match this click's
    // own resulting state, the common file-manager range-select
    // convention - not something that existed here before, but a
    // reasonable one to add now that the flat list is a browsable tree
    // rather than a single short column.
    toggleYRange(row: TreeRow<string>, shiftKey: boolean) {
      const col = row.item;
      if (col === null) return;
      if (shiftKey && this.lastYRangeClick !== null) {
        const rows = this.getColumnVisibleRows("y", (c) => this.isFrameSelectable(c)).filter((r) => r.type === "file" && !r.hidden);
        const toggles = yRangeToggles(
          rows.map((r) => ({ path: r.path, item: r.item! })),
          this.lastYRangeClick,
          row.path,
          !!this.config.yAxes[col],
          (c) => !!this.config.yAxes[c],
        );
        if (toggles) {
          for (const c of toggles) this.toggleY(c);
          this.lastYRangeClick = row.path;
          return;
        }
      }
      this.toggleY(col);
      this.lastYRangeClick = row.path;
    },
    toggleY(col: string) {
      if (this.config.yAxes[col]) {
        this.config.yAxes = withoutYAxis(this.config.yAxes, col);
      } else {
        const nextStyle = this.nextAvailableStyle(usedStyles(this.config.yAxes));
        this.config.yAxes[col] = newYAxisConfig(
          nextStyle,
          this.config.refFrame,
          this.isEnumCol(col),
        );
        // eagerly fetch if this column has no cached data yet
        if (!Object.prototype.hasOwnProperty.call(this.data ?? {}, col)) {
          void (async () => {
            try {
              const resp = await this.fetchTrialData(this.trialId, [col]);
              this.data = { ...(this.data ?? {}), ...resp.data };
              this.saveAndRender();
            } catch {
              // non-critical - empty trace shown until data arrives
            }
          })();
        }
      }
      this.saveAndRender();
    },

    clearYAxes() {
      if (Object.keys(this.config.yAxes).length === 0) return;
      this.config.yAxes = {};
      this.saveAndRender();
      this.configRaw = JSON.stringify(this.config, null, 4);
      this.notify("Signals Cleared", "info");
    },

    applyRefFrame(frame: RefFrame) {
      for (const col of Object.keys(this.config.yAxes)) {
        const yConfig = this.config.yAxes[col];
        if (!yConfig || this.isEnumCol(col)) continue;
        yConfig.filters ??= [];
        const next = withRefFrameFilter(yConfig.filters, frame);
        if (next !== yConfig.filters) yConfig.filters = next;
      }
    },

    // either half may be null (a quaternion alone only rotates, an origin
    // alone only translates); both null is the world frame.
    setRefFrame(quat: string | null, origin: string | null) {
      this.config.refFrame = [quat, origin];
    },

    setRefFrameQuat(quat: string) {
      this.setRefFrame(quat, this.config.refFrame[1]);
    },

    setRefFrameOrigin(origin: string) {
      this.setRefFrame(this.config.refFrame[0], origin);
    },

    warpToTrial() {
      if (
        this.warpId === null ||
        this.warpId === undefined ||
        this.warpId === ("" as unknown)
      )
        return;
      const paddedNum = String(this.warpId).padStart(this.paddingLen, "0");
      window.location.href = `/mosaic/trial_${paddedNum}`;
    },

    getSignalColor(index: number): string {
      return (
        this.plotColors[index % this.plotColors.length] ??
        themeColor("accent-500")
      );
    },

    // picks the lowest-index (color, dash) pair not already in use by `used`,
    // so removing an earlier item in the cycle and adding a new one doesn't
    // collide with a pair still in use. Cycles through every color before
    // advancing to the next dash style, and falls back to round-robin by
    // count once every color/dash combination is taken.
    nextAvailableStyle(used: { color: string; dash: DashStyle }[]): {
      color: string;
      dash: DashStyle;
    } {
      return pickNextStyle(used, this.plotColors.length, (i) => this.getSignalColor(i), this.dashStyles);
    },

    // true for an integer-coded column (one with an enumeration_map), which is
    // drawn on its own labeled axis and never filtered
    isEnumCol(col: string): boolean {
      return enumMapOf(this.columnMetadata[col]) !== null;
    },

    getYProps(axis: string, index: number) {
      const obj = this.config.yAxes[axis] ?? ({} as Partial<YAxisConfig>);
      return {
        name: axis,
        label: obj.label || axis,
        color: obj.color || this.getSignalColor(index),
        width: obj.width ?? 3,
        opacity: obj.opacity ?? 1.0,
        dash: obj.dash ?? "solid",
        marker: obj.marker ?? "none",
      };
    },

    // -----------------------------------------------------------------------
    // Filter stack management
    // -----------------------------------------------------------------------
    getFilterSchema(filterType: string): FilterSchema | undefined {
      return this.filterSchemas.find((s) => s.type === filterType);
    },

    get groupedFilterSchemas(): {
      category: string;
      schemas: FilterSchema[];
    }[] {
      return groupFilterSchemas(this.filterSchemas);
    },

    evalMathExpr,

    getUnitOptions,

    // returns the concrete unit of col after walking its active filter stack;
    // starts from column_metadata and updates when a unit filter's toUnit changes it;
    // pass filtersOverride for axes (e.g. x-axis) that store filters outside config.yAxes
    effectiveUnit(col: string, filtersOverride?: FilterEntry[]): string | null {
      return unitAfterFilters(
        this.columnMetadata[col]?.unit ?? null,
        filtersOverride ?? this.config.yAxes[col]?.filters ?? [],
      );
    },

    getFilterSummary(entry: FilterEntry): string {
      return filterSummary(entry, this.filterSchemas.find((s) => s.type === entry.type));
    },

    addFilterToTemp(temp: YAxisConfig, filterType: string, col?: string) {
      const schema = this.filterSchemas.find((s) => s.type === filterType);
      const meta = col ? this.columnMetadata[col] : undefined;
      addFilter(temp, schema, filterType, meta?.group_unit ?? meta?.unit);
    },

    removeFilterFromTemp: removeFilter,

    moveFilterInTemp: moveFilter,

    setFilterParamOnTemp: setFilterParam,

    duplicateFilterInTemp: duplicateFilter,

    // -----------------------------------------------------------------------
    // Profiles
    _profileUrl(name: string): string {
      return profileUrl(name);
    },

    // ── Lab ──────────────────────────────────────────────────────────────────
    relTime: relativeTime,

    async loadLabSchemas() {
      try {
        const resp = await fetch("/mosaic/api/lab");
        if (!resp.ok) return;
        const all = (await resp.json()) as RawLabSchema[];
        const resolved = resolveLabSchemas(all, this.columns);
        this.labSchemas = resolved.schemas;
        this.columns = resolved.columns;
      } catch {
        // Lab endpoint unavailable - silently ignore
      }
    },

    async refreshLabValidation() {
      await this.loadLabSchemas();
      void this.loadProfiles();
    },

    // ── tab helpers ──────────────────────────────────────────────────────────

    _makeBlankLabTab(): LabTab {
      return makeBlankLabTab();
    },

    _initTabs() {
      const { tabs, activeId } = loadTabsFromStorage<LabTab>(
        "mojo:lab:tabs",
        "mojo:lab:activeTab",
        legacyLabTabs,
      );
      this.labTabs = tabs;
      this.labActiveTabId = activeId;
      const active = tabs.find((t) => t.id === activeId)!;
      this.labName = active.name;
      this.labGraph = active.graph;
    },

    _snapshotActiveTab() {
      if (!this.labActiveTabId) return;
      const tab = this.labTabs.find((t) => t.id === this.labActiveTabId);
      if (!tab) return;
      // run any pending debounced undo-history snapshot first so the stack's
      // top entry matches exactly what we persist onto the tab
      window.mojoLabFlushSnapshot?.();
      tab.graph = window.mojoLabSerialize?.() ?? tab.graph;
      tab.name = this.labName;
      // tab.savedState is NOT touched here - it's the tab's own baseline,
      // owned exclusively by this LabTab object (see mojoLabGetBaseline /
      // mojoLabSetBaseline) and never derived from a transient local copy.
      tab.viewport = window.mojoLabGetViewport?.() ?? tab.viewport;
      // keep labGraph (the value mojoLabInit reloads from on reopen) in sync,
      // otherwise closing and reopening the lab restores the pre-edit graph
      this.labGraph = tab.graph;
    },

    _persistTabs() {
      // persist tab list to localStorage WITHOUT snapshotting the live canvas —
      // safe to call immediately after _activateTab() before mojoLabInit fires
      persistTabsToStorage(
        "mojo:lab:tabs",
        "mojo:lab:activeTab",
        this.labTabs,
        this.labActiveTabId ?? "",
      );
    },

    _saveTabs() {
      this._snapshotActiveTab();
      this._persistTabs();
    },

    reorderLabTabs(draggedId: string, dropIndex: number) {
      this.labTabs = reorderTabs(this.labTabs, draggedId, dropIndex);
      this._saveTabs();
    },

    async _activateTab(tabId: string) {
      this.labActiveTabId = tabId;
      const tab = this.labTabs.find((t) => t.id === tabId);
      if (!tab) return;
      this.labName = tab.name;
      this.labGraph = tab.graph;
      if (this.labOpen) {
        await this.$nextTick();
        document.dispatchEvent(new CustomEvent("mojo:lab-activate-tab"));
      }
    },

    async switchTab(tabId: string) {
      if (tabId === this.labActiveTabId) return;
      this._snapshotActiveTab();
      await this._activateTab(tabId);
      // persist only - the canvas hasn't reloaded the new tab's graph yet
      // (mojoLabInit fires async via the mojo:lab-activate-tab event), so
      // re-snapshotting here would serialize the still-displayed old graph
      // onto the newly active tab and clobber it
      this._persistTabs();
    },

    async newTab() {
      this._snapshotActiveTab();
      const blank = this._makeBlankLabTab();
      this.labTabs.push(blank);
      await this._activateTab(blank.id);
      this._persistTabs();
    },

    async duplicateLabTab(tabId: string) {
      const tabIdx = this.labTabs.findIndex((t) => t.id === tabId);
      if (tabIdx === -1) return;
      if (tabId === this.labActiveTabId) this._snapshotActiveTab();
      const duplicate = copyLabTab(this.labTabs[tabIdx]!);
      this.labTabs.splice(tabIdx + 1, 0, duplicate);
      await this._activateTab(duplicate.id);
      this._persistTabs();
    },

    // See selectPlotTab's own comment for the shared shift/ctrl-click
    // semantics - identical here, just against labTabs/labActiveTabId.
    selectLabTab(tabId: string, event: MouseEvent) {
      if (event.shiftKey && this._labTabSelectionAnchorId) {
        this.selectedLabTabIds = selectRange(
          this.labTabs,
          this._labTabSelectionAnchorId,
          tabId,
        );
        return;
      }
      if (event.metaKey || event.ctrlKey) {
        this.selectedLabTabIds = toggleSelection(
          this.selectedLabTabIds,
          tabId,
        );
        this._labTabSelectionAnchorId = tabId;
        return;
      }
      this.selectedLabTabIds = [];
      this._labTabSelectionAnchorId = tabId;
      void this.switchTab(tabId);
    },

    async closeTab(tabId: string) {
      if (
        this.selectedLabTabIds.length > 1 &&
        this.selectedLabTabIds.includes(tabId)
      ) {
        await this.closeMultipleLabTabs(this.selectedLabTabIds);
        return;
      }
      const tabIdx = this.labTabs.findIndex((t) => t.id === tabId);
      if (tabIdx === -1) return;
      const tab = this.labTabs[tabIdx]!;
      if (tabId === this.labActiveTabId) this._snapshotActiveTab();
      const isDirty =
        tabId === this.labActiveTabId
          ? (window.mojoLabHasUnsavedChanges?.() ?? false)
          : tab.dirty;
      if (isDirty) {
        const ok = await window.mojoConfirm?.({
          title: "Unsaved changes",
          message: tab.name
            ? `Close "${tab.name}" and discard unsaved changes?`
            : "Close this tab and discard unsaved changes?",
          confirmLabel: "Close",
          cancelLabel: "Keep editing",
          variant: "warning",
        });
        if (!ok) return;
      }
      const { tabs, nextActiveId, activeChanged } = pickNextActiveOnClose(
        this.labTabs,
        tabIdx,
        this.labActiveTabId ?? "",
        () => this._makeBlankLabTab(),
      );
      this.labTabs = tabs;
      window.mojoLabDiscardHistory?.(tabId);
      if (activeChanged) {
        await this._activateTab(nextActiveId);
      }
      // persist only - see switchTab for why we must not re-snapshot here
      this._persistTabs();
    },

    // Bulk-close path for a multi-selection - one confirm dialog covering
    // the whole group rather than one per tab, mirroring
    // closeMultiplePlotTabs()'s dirty-count message.
    async closeMultipleLabTabs(tabIds: string[]) {
      const idSet = new Set(tabIds);
      const toClose = this.labTabs.filter((t) => idSet.has(t.id));
      if (toClose.length === 0) return;
      const activeWasClosed = idSet.has(this.labActiveTabId ?? "");
      if (activeWasClosed) this._snapshotActiveTab();
      const dirtyCount = toClose.filter((t) =>
        t.id === this.labActiveTabId
          ? (window.mojoLabHasUnsavedChanges?.() ?? false)
          : t.dirty,
      ).length;
      if (dirtyCount > 0) {
        const ok = await window.mojoConfirm?.({
          title: "Unsaved changes",
          message: `Close ${toClose.length} tabs and discard unsaved changes in ${dirtyCount} of them?`,
          confirmLabel: "Close",
          cancelLabel: "Keep editing",
          variant: "warning",
        });
        if (!ok) return;
      }
      const remaining = this.labTabs.filter((t) => !idSet.has(t.id));
      toClose.forEach((t) => window.mojoLabDiscardHistory?.(t.id));
      this.selectedLabTabIds = [];
      if (remaining.length === 0) {
        const blank = this._makeBlankLabTab();
        this.labTabs = [blank];
        await this._activateTab(blank.id);
      } else {
        this.labTabs = remaining;
        if (activeWasClosed) await this._activateTab(remaining[0]!.id);
      }
      this._persistTabs();
    },

    async loadLabInNewTab(labName: string) {
      // if this lab is already open in a tab, switch to it rather than
      // duplicating it (and preserve any unsaved edits already in that tab)
      const existing = this.labTabs.find((t) => t.name === labName);
      if (existing) {
        if (existing.id !== this.labActiveTabId) {
          this._snapshotActiveTab();
          await this._activateTab(existing.id);
          this._persistTabs();
        }
        return;
      }
      try {
        const resp = await fetch(labUrl(labName));
        if (!resp.ok) throw new Error(resp.statusText);
        const graph = (await resp.json()) as object;

        // reuse the current tab if it is blank (untitled + no unsaved changes)
        const activeTab = this.labTabs.find(
          (t) => t.id === this.labActiveTabId,
        );
        if (activeTab && isReusableLabTab(activeTab)) {
          activeTab.name = labName;
          activeTab.graph = graph;
          activeTab.savedState = null;
          activeTab.dirty = false;
          this.labName = labName;
          this.labGraph = graph;
          if (this.labOpen) {
            await this.$nextTick();
            document.dispatchEvent(new CustomEvent("mojo:lab-activate-tab"));
          }
        } else {
          this._snapshotActiveTab();
          const tab = labTabFor(labName, graph);
          this.labTabs.push(tab);
          await this._activateTab(tab.id);
        }
        // persist without snapshotting — mojoLabInit hasn't fired yet, so the
        // canvas is still showing the previous tab's graph; re-snapshotting
        // here would serialize that stale content onto the new tab
        this._persistTabs();
      } catch (err) {
        this.notify(`Failed to load "${labName}": ${String(err)}`, "error");
      }
    },

    async saveLabGraph(name: string, graph: object) {
      const trimmed = name.trim();
      if (!trimmed) return;
      const exists = this.labSchemas.some((s) => s.name === trimmed);
      if (exists) {
        const ok = await window.mojoConfirm?.({
          title: "Overwrite lab",
          message: `"${trimmed}" already exists. Replace it with the current graph?`,
          confirmLabel: "Overwrite",
          cancelLabel: "Cancel",
          variant: "warning",
        });
        if (!ok) return;
      }
      try {
        const resp = await fetch(labUrl(trimmed), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(graph),
        });
        if (!resp.ok) {
          const detail = await resp.text().catch(() => resp.statusText);
          this.notify(`Save failed: ${detail}`, "error");
          return;
        }
        this.notify(`Lab "${trimmed}" saved`, "success");
        // the just-saved content is the new clean baseline for the active tab
        window.mojoLabRebaseline?.();
        this.labName = trimmed;
        const activeTab = this.labTabs.find(
          (t) => t.id === this.labActiveTabId,
        );
        if (activeTab) {
          activeTab.name = trimmed;
          activeTab.dirty = false;
        }
        this._saveTabs();
        await this.refreshLabValidation();
        // compute the transitive closure of labs whose outputs may now be stale:
        // the saved lab itself, plus any lab that (directly or transitively) reads from it
        const toInvalidate = staleLabs(this.labSchemas, trimmed);
        // evict all stale entries from the client-side data cache
        const eviction = evictLabData(this.data, toInvalidate);
        if (eviction.evicted) this.data = eviction.data;
        // re-fetch currently plotted cols that were just evicted
        const activeCols = evictedPlottedColumns(
          Object.keys(this.config.yAxes),
          this.config.xAxis?.col ?? "",
          toInvalidate,
          this.data,
        );
        // also refreshes the column metadata (a Signal Out's unit and tags come
        // from the saved graph); with nothing to refetch the server just returns
        // the manifest
        try {
          const refetch = await this.fetchTrialData(this.trialId, activeCols);
          this.columnMetadata = {
            ...this.columnMetadata,
            ...(refetch.columns.column_metadata ?? {}),
          };
          if (activeCols.length > 0) {
            this.data = { ...(this.data ?? {}), ...refetch.data };
            this.saveAndRender();
          }
        } catch {
          // non-critical: plot drops stale trace until background discovery refetches
        }
      } catch (err) {
        this.notify(`Save failed: ${String(err)}`, "error");
      }
    },

    selectNodeColumn(col: string) {
      if (this.nodePickingColumn !== null) {
        // Defined in _signal_lab.html - updates the LiteGraph node property
        if (typeof window.mojoLabSelectNodeColumn === "function") {
          window.mojoLabSelectNodeColumn(this.nodePickingColumn, col);
        }
      }
      this.nodePickingColumn = null;
      this.nodeColSearch = "";
    },

    selectNodeQuat(base: string) {
      if (this.nodePickingQuat !== null) {
        // Defined in _signal_lab.html - updates the LiteGraph node property
        if (typeof window.mojoLabSelectNodeQuat === "function") {
          window.mojoLabSelectNodeQuat(this.nodePickingQuat, base);
        }
      }
      this.nodePickingQuat = null;
      this.nodeQuatSearch = "";
    },

    selectNodeOrigin(base: string) {
      if (this.nodePickingOrigin !== null) {
        // Defined in _signal_lab.html - updates the LiteGraph node property
        if (typeof window.mojoLabSelectNodeOrigin === "function") {
          window.mojoLabSelectNodeOrigin(this.nodePickingOrigin, base);
        }
      }
      this.nodePickingOrigin = null;
      this.nodeOriginSearch = "";
    },

    selectNodeTemplate(name: string) {
      if (this.nodePickingTemplate !== null) {
        if (typeof window.mojoLabSelectNodeTemplate === "function") {
          window.mojoLabSelectNodeTemplate(this.nodePickingTemplate, name);
        }
      }
      this.nodePickingTemplate = null;
    },

    async deleteLabGraph(name: string) {
      await fetch(labUrl(name), {
        method: "DELETE",
      });
      this.notify(`Lab "${name}" deleted`, "info");
      await this.refreshLabValidation();
    },

    // ── plot tab helpers ─────────────────────────────────────────────────────
    // config/data/filterFingerprints/xAxisFilterFingerprint/historyStack/
    // historyIndex are all mirrors of the *active* PlotTab's own fields - the
    // same pattern labName/labGraph use for Lab tabs above. This means
    // renderPlot(), the JSON editor, undo/redo, and every axis/filter picker
    // keep reading/writing `this.config` etc. completely unchanged; only tab
    // switching needs to know these are mirrors at all. vsDatasets is NOT
    // part of this mirror set - VS (comparison-trial) settings and their
    // fetched data are page-level/shared across every tab (see the `vs`
    // field and syncVsRange()), not per-tab.

    _makeBlankPlotTab(): PlotTab {
      return makeBlankPlotTab(DEFAULT_CONFIG);
    },

    // Shared by the tab strip's dirty dot (_plot_tabs.html) and
    // closePlotTab()'s confirm-before-discard check, so the two can't drift.
    _isPlotTabDirty(tab: PlotTab): boolean {
      return isPlotTabDirty(tab);
    },

    // Called once at the end of init()'s existing config-loading sequence
    // (after hydrateFromUrl/loadConfig and the ref-frame migration have
    // settled this.config). Tries to restore a previously-saved multi-tab
    // session from mojo:plot:tabs first; only when there isn't one yet does
    // it fall back to wrapping whatever this.config/data/etc. the sequence
    // above already produced into a single starting tab - the same
    // legacy-format-fallback shape _initTabs() uses for Signal Lab.
    // `skipStoredTabs` is true when a shared link (?v=) was just hydrated
    // AND the caller confirmed it's OK to replace whatever tabs happen to
    // be saved on this browser (see init()'s useSharedLink) - a link left
    // in the address bar shouldn't silently wipe an existing session on
    // every plain page refresh.
    async _initPlotTabs(skipStoredTabs: boolean) {
      const wrapCurrentAsTab = (): { tabs: PlotTab[]; activeId: string } => {
        const tab: PlotTab = {
          id: newTabId(),
          config: this.config,
          data: this.data,
          filterFingerprints: this.filterFingerprints,
          xAxisFilterFingerprint: this.xAxisFilterFingerprint,
          historyStack: this.historyStack,
          historyIndex: this.historyIndex,
          // baselined against whatever boot already produced, not dirty by
          // default - same reasoning as _makeBlankPlotTab()'s own baseline.
          savedSnapshot: JSON.stringify(this.config),
        };
        return { tabs: [tab], activeId: tab.id };
      };
      const { tabs, activeId } = skipStoredTabs
        ? wrapCurrentAsTab()
        : loadTabsFromStorage<PlotTab>(
            "mojo:plot:tabs",
            "mojo:plot:activeTab",
            wrapCurrentAsTab,
          );
      this.plotTabs = tabs;
      this.plotActiveTabId = activeId;
      this.closedPlotTabs = loadClosedPlotTabs();
      const active = tabs.find((t) => t.id === activeId)!;
      // active tab's fields become the live mirrors - when tabs came from
      // storage rather than wrapCurrentAsTab(), this replaces whatever
      // hydrateFromUrl()/loadConfig() set up above with the restored
      // session's own state instead.
      this.config = sanitizeRefFrame(active.config);
      this.data = active.data;
      this.filterFingerprints = active.filterFingerprints;
      this.xAxisFilterFingerprint = active.xAxisFilterFingerprint;
      this.historyStack = active.historyStack;
      this.historyIndex = active.historyIndex;
      // data is never persisted (see _persistPlotTabs), so a tab restored
      // from storage always needs its columns re-fetched here.
      const needed = this._neededColumns(active.config, active.data);
      if (needed.length > 0) {
        const fetched = await this.fetchTrialData(this.trialId, needed);
        this.data = { ...(this.data ?? {}), ...fetched.data };
      }
    },

    _snapshotActivePlotTab() {
      const tab = this.plotTabs.find((t) => t.id === this.plotActiveTabId);
      if (!tab) return;
      tab.config = this.config;
      tab.data = this.data;
      tab.filterFingerprints = this.filterFingerprints;
      tab.xAxisFilterFingerprint = this.xAxisFilterFingerprint;
      tab.historyStack = this.historyStack;
      tab.historyIndex = this.historyIndex;
    },

    // Persists the tab list WITHOUT the large, always-refetchable data cache
    // (see persistablePlotTabs).
    _persistPlotTabs() {
      persistTabsToStorage(
        "mojo:plot:tabs",
        "mojo:plot:activeTab",
        persistablePlotTabs(this.plotTabs),
        this.plotActiveTabId ?? "",
      );
    },

    _neededColumns(
      cfg: PlotConfig,
      cache: Record<string, number[]> | null,
    ): string[] {
      return neededColumns(cfg, cache);
    },

    async _activatePlotTab(tabId: string) {
      const tab = this.plotTabs.find((t) => t.id === tabId);
      if (!tab) return;
      this.plotActiveTabId = tabId;
      // order matters: data/fingerprints/history must be in place before
      // `config` is reassigned, since the central config watcher (below)
      // reads them synchronously and must not diff the new tab's filters
      // against the previous tab's fingerprints.
      this.data = tab.data;
      this.filterFingerprints = tab.filterFingerprints;
      this.xAxisFilterFingerprint = tab.xAxisFilterFingerprint;
      this.historyStack = tab.historyStack;
      this.historyIndex = tab.historyIndex;
      this.config = tab.config; // fires $watch("config", ...): validates,
      // pushes history (a no-op if unchanged), and re-fetches any columns
      // this tab's own fingerprints mark as stale - no explicit renderPlot()
      // call needed here for that part, exactly like undo()/redo() already
      // rely on this watcher instead of calling it directly.
      const needed = this._neededColumns(tab.config, tab.data);
      if (needed.length > 0) {
        const fetched = await this.fetchTrialData(this.trialId, needed);
        this.data = { ...(this.data ?? {}), ...fetched.data };
        void this.renderPlot();
      }
    },

    async switchPlotTab(tabId: string) {
      if (tabId === this.plotActiveTabId) return;
      this._snapshotActivePlotTab();
      await this._activatePlotTab(tabId);
      this._persistPlotTabs();
    },

    async newPlotTab() {
      this._snapshotActivePlotTab();
      const blank = this._makeBlankPlotTab();
      this.plotTabs.push(blank);
      await this._activatePlotTab(blank.id);
      this._persistPlotTabs();
    },

    async duplicatePlotTab(tabId: string) {
      const tabIdx = this.plotTabs.findIndex((t) => t.id === tabId);
      if (tabIdx === -1) return;
      if (tabId === this.plotActiveTabId) this._snapshotActivePlotTab();
      const duplicate = copyPlotTab(this.plotTabs[tabIdx]!);
      this.plotTabs.splice(tabIdx + 1, 0, duplicate);
      await this._activatePlotTab(duplicate.id);
      this._persistPlotTabs();
    },

    // Plain click switches tabs and clears any multi-selection. Shift-click
    // selects the inclusive range from the last anchor to this tab
    // (matching file-manager/list conventions); ctrl/cmd-click toggles this
    // one tab without touching the rest. Selection only exists to drive
    // closePlotTab()'s bulk-close check below - it's independent of which
    // tab is active/displayed.
    selectPlotTab(tabId: string, event: MouseEvent) {
      if (event.shiftKey && this._plotTabSelectionAnchorId) {
        this.selectedPlotTabIds = selectRange(
          this.plotTabs,
          this._plotTabSelectionAnchorId,
          tabId,
        );
        return;
      }
      if (event.metaKey || event.ctrlKey) {
        this.selectedPlotTabIds = toggleSelection(
          this.selectedPlotTabIds,
          tabId,
        );
        this._plotTabSelectionAnchorId = tabId;
        return;
      }
      this.selectedPlotTabIds = [];
      this._plotTabSelectionAnchorId = tabId;
      void this.switchPlotTab(tabId);
    },

    // Confirms before discarding a dirty tab, same as Lab tabs
    // (window.mojoConfirm) - and any close (confirmed-dirty or not) is
    // additionally always recoverable via reopenLastClosedPlotTab(), since
    // every closed tab is pushed onto closedPlotTabs regardless of how it
    // was closed. When tabId is part of a 2+ multi-selection (shift/ctrl-
    // click via selectPlotTab, or the tab_strip's own middle-click
    // listener), closes the whole selection instead of just this one tab -
    // both the close button and a middle-click go through this same method.
    async closePlotTab(tabId: string) {
      if (
        this.selectedPlotTabIds.length > 1 &&
        this.selectedPlotTabIds.includes(tabId)
      ) {
        await this.closeMultiplePlotTabs(this.selectedPlotTabIds);
        return;
      }
      const tabIdx = this.plotTabs.findIndex((t) => t.id === tabId);
      if (tabIdx === -1) return;
      if (tabId === this.plotActiveTabId) this._snapshotActivePlotTab();
      const closedTab = this.plotTabs[tabIdx]!;
      if (this._isPlotTabDirty(closedTab)) {
        const ok = await window.mojoConfirm?.({
          title: "Unsaved changes",
          message: closedTab.config.title
            ? `Close "${closedTab.config.title}" and discard unsaved changes?`
            : "Close this tab and discard unsaved changes?",
          confirmLabel: "Close",
          cancelLabel: "Keep editing",
          variant: "warning",
        });
        if (!ok) return;
      }
      const { tabs, nextActiveId, activeChanged } = pickNextActiveOnClose(
        this.plotTabs,
        tabIdx,
        this.plotActiveTabId ?? "",
        () => this._makeBlankPlotTab(),
      );
      this.plotTabs = tabs;
      // closedAtIndex is this tab's position before the splice above, so
      // reopenLastClosedPlotTab() can reinsert it back where it was.
      this.closedPlotTabs = pushClosedPlotTabs(this.closedPlotTabs, [
        closedPlotTabEntry(closedTab, tabIdx),
      ]);
      this._persistClosedPlotTabs();
      if (activeChanged) {
        await this._activatePlotTab(nextActiveId);
      }
      this._persistPlotTabs();
    },

    // Bulk-close path for a bulk selection (see closePlotTab above) - one
    // confirm dialog covering the whole group rather than one per tab, and
    // each closed tab still lands on closedPlotTabs individually (with its
    // own pre-close index) so reopenLastClosedPlotTab() can bring them back
    // one at a time, each near where it was.
    async closeMultiplePlotTabs(tabIds: string[]) {
      const idSet = new Set(tabIds);
      const indexById = new Map(this.plotTabs.map((t, i) => [t.id, i]));
      const toClose = this.plotTabs.filter((t) => idSet.has(t.id));
      if (toClose.length === 0) return;
      const activeWasClosed = idSet.has(this.plotActiveTabId ?? "");
      if (activeWasClosed) this._snapshotActivePlotTab();
      const dirtyCount = toClose.filter((t) =>
        this._isPlotTabDirty(t),
      ).length;
      if (dirtyCount > 0) {
        const ok = await window.mojoConfirm?.({
          title: "Unsaved changes",
          message: `Close ${toClose.length} tabs and discard unsaved changes in ${dirtyCount} of them?`,
          confirmLabel: "Close",
          cancelLabel: "Keep editing",
          variant: "warning",
        });
        if (!ok) return;
      }
      const remaining = this.plotTabs.filter((t) => !idSet.has(t.id));
      this.closedPlotTabs = pushClosedPlotTabs(
        this.closedPlotTabs,
        toClose.map((t) => closedPlotTabEntry(t, indexById.get(t.id))),
      );
      this._persistClosedPlotTabs();
      this.selectedPlotTabIds = [];
      if (remaining.length === 0) {
        const blank = this._makeBlankPlotTab();
        this.plotTabs = [blank];
        await this._activatePlotTab(blank.id);
      } else {
        this.plotTabs = remaining;
        if (activeWasClosed) await this._activatePlotTab(remaining[0]!.id);
      }
      this._persistPlotTabs();
    },

    async reopenLastClosedPlotTab() {
      const [mostRecent, ...rest] = this.closedPlotTabs;
      if (!mostRecent) return;
      this.closedPlotTabs = rest;
      this._persistClosedPlotTabs();
      this._snapshotActivePlotTab();
      const { tab: reopened, insertAt } = reopenPlotTab(
        mostRecent,
        this.plotTabs.length,
      );
      this.plotTabs.splice(insertAt, 0, reopened);
      await this._activatePlotTab(reopened.id);
      this._persistPlotTabs();
    },

    _persistClosedPlotTabs() {
      persistClosedPlotTabs(this.closedPlotTabs);
    },

    reorderPlotTabs(draggedId: string, dropIndex: number) {
      this.plotTabs = reorderTabs(this.plotTabs, draggedId, dropIndex);
      this._persistPlotTabs();
    },

    // Shared by the Profiles button's own @click (_chart.html) and the
    // Ctrl+S shortcut below, so the popup lands in the right place
    // regardless of which one opened it - both need this, since Ctrl+S
    // can't reach a coords value scoped to the button's own local x-data.
    _computeProfilesCoords() {
      const btn = document.getElementById("profiles-btn");
      if (!btn) return;
      this.profilesCoords = popupCoords(
        btn.getBoundingClientRect(),
        window.scrollX,
        window.scrollY,
      );
    },

    // -----------------------------------------------------------------------
    async loadProfiles() {
      try {
        const resp = await fetch("/mosaic/api/profiles");
        this.profiles = (await resp.json()) as Array<{
          name: string;
          modified: number;
        }>;

        const warnings: Record<string, string[]> = {};
        await Promise.all(
          this.profiles.map(async (p) => {
            try {
              const pr = await fetch(this._profileUrl(p.name));
              if (!pr.ok) return;
              const profile = (await pr.json()) as Partial<PlotProfile>;
              const w = profileWarnings(profile, this.columns);
              if (w.length) warnings[p.name] = w;
            } catch {
              /* skip */
            }
          }),
        );
        this.profileWarnings = warnings;
      } catch (e) {
        console.warn("[mojo] Failed to load profiles", e);
      }
    },

    async saveProfile() {
      const name = this.profileNameDraft.trim();
      if (!name) {
        this.notify("Enter a profile name", "error");
        return;
      }
      // a profile saves every open tab, not just the active one
      this._snapshotActivePlotTab();
      const payload = buildProfilePayload(
        this.plotTabs,
        this.plotActiveTabId,
        this.vs,
      );
      try {
        const result = await saveProfileRequest(name, payload, async (existingName) =>
          !!(await window.mojoConfirm?.({
            title: "Overwrite profile",
            message: `"${existingName}" already exists. Replace it with the current set of plot tabs?`,
            confirmLabel: "Overwrite",
            cancelLabel: "Cancel",
            variant: "warning",
          })),
        );
        if (!result.saved) return;
        this.profileNameDraft = "";
        // the just-saved content is every tab's new clean baseline
        this.plotTabs.forEach((t) => {
          t.savedSnapshot = JSON.stringify(t.config);
        });
        this._persistPlotTabs();
        await this.loadProfiles();
        this.notify(`Profile "${result.name}" saved`, "success");
      } catch {
        this.notify("Failed to save profile", "error");
      }
    },

    async loadProfile(name: string) {
      try {
        const resp = await fetch(this._profileUrl(name));
        if (!resp.ok) {
          const body = (await resp.json().catch(() => ({}))) as {
            detail?: string;
          };
          throw new Error(body.detail ?? `HTTP ${resp.status}`);
        }
        const profile = (await resp.json()) as PlotProfile;

        const missing = profileMissing(profile, this.columns);
        const newTabs = tabsFromProfile(profile);
        const activeIndex = profileActiveIndex(profile, newTabs.length);
        this.plotTabs = newTabs;
        await this._activatePlotTab(newTabs[activeIndex]!.id);
        this._persistPlotTabs();
        // a profile's saved comparison range/pinned trials carry over, but
        // (like page load) VS mode itself never auto-enables from this -
        // pulling comparison data is only ever a deliberate toggle+Apply,
        // even if the profile happened to be saved with it on.
        this._restoreVsRange(profile.vsRange ?? [0, 10], profile.vsPinned ?? []);
        this._persistVsState();

        if (missing.length) {
          this.notify(
            `Profile "${name}" loaded, but won't plot until added to this trial: ${missing.join(", ")}`,
            "info",
          );
        } else {
          this.notify(`Profile "${name}" loaded`, "success");
        }
      } catch (e) {
        this.notify(
          `Failed to load "${name}": ${(e as Error).message}`,
          "error",
        );
      }
    },

    async deleteProfile(name: string) {
      const ok = await window.mojoConfirm?.({
        title: "Delete profile",
        message: `Delete "${name}"? This cannot be undone.`,
        confirmLabel: "Delete",
        cancelLabel: "Cancel",
        variant: "danger",
      });
      if (!ok) return;
      try {
        const resp = await fetch(this._profileUrl(name), { method: "DELETE" });
        if (!resp.ok) throw new Error("Delete failed");
        await this.loadProfiles();
        this.notify(`Profile "${name}" deleted`, "info");
      } catch {
        this.notify(`Failed to delete "${name}"`, "error");
      }
    },

    applySignalConfig(col: string, temp: YAxisConfig) {
      // deep copy prevents temp.filters from sharing a reference with config.yAxes[col].filters
      this.config.yAxes[col] = JSON.parse(JSON.stringify(temp)) as YAxisConfig;
      delete this.signalDrafts[col];
      // config watcher handles pushHistory + filter re-fetch + saveAndRender
    },

    getDraft(col: string): { draft: YAxisConfig; baseSnapshot: string } | null {
      return (
        (
          this.signalDrafts as Record<
            string,
            { draft: YAxisConfig; baseSnapshot: string }
          >
        )[col] ?? null
      );
    },

    saveDraft(col: string, draft: YAxisConfig, baseSnapshot: string) {
      (
        this.signalDrafts as Record<
          string,
          { draft: YAxisConfig; baseSnapshot: string }
        >
      )[col] = { draft, baseSnapshot };
    },

    clearDraft(col: string) {
      delete (
        this.signalDrafts as Record<
          string,
          { draft: YAxisConfig; baseSnapshot: string }
        >
      )[col];
    },

    // -----------------------------------------------------------------------
    // Range helpers
    // -----------------------------------------------------------------------
    calculatePaddedRange(keys: string[], padding = true): [number, number] {
      const datasets: Array<Record<string, number[]>> = [this.data ?? {}];
      if (this.vs.enabled) {
        datasets.push(...selectVsDatasets(this.vsDatasets, this.vs.range, this.vs.pinned ?? []));
      }
      return paddedRange(datasets, keys, padding);
    },

    formatNum,
    breakableLabel,

    // reads the manual x/y axis min/max fields as strings for display; empty means autoscale
    rangeBoundValue(axis: "x" | "y", bound: "min" | "max"): string {
      return rangeBoundText(axis === "x" ? this.config.rangeX : this.config.rangeY, bound);
    },

    // sets a single x/y axis min/max field; an empty value reverts that side to autoscale
    setRangeBound(axis: "x" | "y", bound: "min" | "max", value: string) {
      const current = axis === "x" ? this.config.rangeX : this.config.rangeY;
      const applied = applyRangeBound(current, bound, value);
      if (!applied) return;
      if (axis === "x") this.config.rangeX = applied.range;
      else this.config.rangeY = applied.range;
      void this.saveAndRender();
    },

    // resolves a possibly-partial axis range into a concrete [min, max], falling back
    // to the padded data range for whichever side is unset
    resolveAxisRange(
      configRange: [number | null, number | null] | null,
      keys: string[],
    ): [number, number] | null {
      return resolveRange(configRange, () => this.calculatePaddedRange(keys));
    },

    // (re)attaches the Plotly event handlers that drive zoom/pan range tracking,
    // double-click-to-reset, and frame-marker syncing. Plotly.purge clears the plot
    // element's internal event emitter, so this must be called again after every
    // Plotly.newPlot (not just once during init).
    _attachPlotEventHandlers() {
      const plotEl = document.getElementById("plot-area") as
        | (HTMLElement & {
            on(
              event: string,
              handler: (event: Record<string, unknown>) => void,
            ): void;
          })
        | null;
      if (!plotEl) return;

      plotEl.on("plotly_afterplot", () => {
        requestAnimationFrame(() => {
          this._renderFrameMarkers();
          this._syncOverlayVisibility();
        });
      });

      plotEl.on("plotly_doubleclick", () => {
        this.config.rangeX = null;
        this.config.rangeY = null;
        void this.renderPlot();
      });

      plotEl.on("plotly_relayout", (event) => {
        const ranges = relayoutRanges(event);
        if (ranges.reset) {
          this.config.rangeX = null;
          this.config.rangeY = null;
          void this.renderPlot();
          return;
        }
        if (ranges.rangeX) this.config.rangeX = ranges.rangeX;
        if (ranges.rangeY) this.config.rangeY = ranges.rangeY;
      });
    },

    // -----------------------------------------------------------------------
    // Plotly render
    // -----------------------------------------------------------------------
    renderPlot() {
      if (!this.data) return;

      const isDark = document.documentElement.classList.contains("dark");
      const colors: LayoutColors = {
        text: themeColor("chart-text"),
        majorGrid: themeColor("chart-grid-major"),
        minorGrid: themeColor("chart-grid-minor"),
        tooltipBg: themeColor("chart-tooltip-bg"),
        tooltipFont: themeColor("chart-tooltip-font"),
        tooltipBorder: themeColor("accent-500"),
        spike: themeColor("accent-500"),
        title: themeColor("chart-title"),
      };

      const isPolar = this.config.plotType === "polar";
      const yKeys = Object.keys(this.config.yAxes);
      const xCol = this.config.xAxis.col!;

      // integer-coded columns sit on right-hand axes of their own, see lib/enum-axes.ts
      const enumCtx = enumContext(yKeys, this.data, this.columnMetadata, isPolar);
      const traceCtx: TraceContext = {
        isPolar,
        interp: this.config.interp,
        lineMode: this.config.lineMode,
        enum: enumCtx,
      };
      const series: Series[] = yKeys.map((key, i) => ({
        key,
        props: this.getYProps(key, i),
        unit: this.effectiveUnit(key),
      }));

      let traces = primaryTraces(series, this.data, xCol, traceCtx, colors);
      if (this.vs.enabled) {
        traces = [
          ...traces,
          ...vsTraces(series, this.vsDatasets, this.vs, this.trialId, xCol, traceCtx),
        ];
      }

      const layout = buildLayout({
        trialId: this.trialId,
        config: this.config,
        isPolar,
        enum: enumCtx,
        resolvedRangeX: this.resolveAxisRange(this.config.rangeX, [xCol]),
        // a manual y range means nothing once the primary slot is an enum axis
        resolvedRangeY: enumCtx.enumPromoted
          ? null
          : this.resolveAxisRange(this.config.rangeY, enumCtx.numericKeys),
        xUnit: this.effectiveUnit(xCol, this.config.xAxis?.filters ?? []),
        yUnitList: enumCtx.numericKeys.map((c) => this.effectiveUnit(c)),
        labelOf: (col) => this.getYProps(col, yKeys.indexOf(col)).label,
        data: this.data,
        colors,
        overlays: {
          annotations: isPolar
            ? []
            : plotlyAnnotations(
                this.config.annotations ?? [],
                this.config.shapes ?? [],
                {
                  tooltipFont: themeColor("chart-tooltip-font"),
                  annotationBg: themeColor("chart-annotation-bg"),
                  accent: themeColor("accent-500"),
                  shapeLabelBg: themeColorAlpha("chart-shape-label-bg", 0xb3 / 255),
                },
              ),
          shapes: isPolar
            ? []
            : plotlyShapes(
                this.config.shapes ?? [],
                isDark,
                themeColor("accent-500"),
              ),
        },
      });

      const config = {
        responsive: true,
        displaylogo: false,
        displayModeBar: true,
        modeBarButtonsToRemove: ["toImage"],
        // plotly.js defaults this to true, adding a "Share chart..." modebar
        // button (cloud-upload icon) that's easily confused with the
        // sidebar's own Share button -- it also does nothing useful here
        // since no plotlyServerURL/Chart Studio is configured.
        showSendToCloud: false,
        doubleClick: false as const,
      };
      const plotEl = document.getElementById("plot-area");
      if (plotEl && this._renderedPlotType !== this.config.plotType) {
        Plotly.purge(plotEl);
        this._renderedPlotType = this.config.plotType ?? null;
        // Plotly.purge clears the plot element's event emitter, so the
        // zoom/relayout/doubleclick handlers must be re-attached after recreating it.
        return Plotly.newPlot("plot-area", traces, layout, config).then(() =>
          this._attachPlotEventHandlers(),
        );
      }
      return Plotly.react("plot-area", traces, layout, config);
    },
  };
  return self;
}

window.trialViewer = trialViewer;
