// Drives the global Dojo settings panel ($store.dojo, merged in by store.ts)
// by walking the JSON Schema returned from GET /settings at runtime, rather
// than hand-listing fields here - see settings.py's MujocoMojoSettings for
// the single source of truth. A field only needs a widget hint here
// (`x-widget`) when a validator enforces something the JSON Schema type
// system can't express on its own (currently just the Color-enum fields);
// everything else is inferred from plain schema shape (type/enum/writeOnly/anyOf).

import { Marked } from "marked";

// a dedicated instance, not the shared `marked` singleton import - Vite
// factors `marked` into one chunk shared between this bundle (main.js) and
// sensai.ts's (marked.use({renderer: {code, codespan}}), rendering fenced
// code blocks as embedded CodeMirror editors for chat responses). Sharing
// the singleton would mean these tooltips silently inherited that renderer
// too, on any page where both happened to load. An instance of its own
// can't be affected by another module's marked.use() call regardless of
// chunking. Named for its role (rendering any Field(description=...) text
// this store's callers hand it), not "settings" specifically - main.js
// loads on every Dojo page, so renderMarkdown() below is already globally
// available via $store.dojo wherever a tooltip needs it (e.g. the Plot
// Editor/Line Config panels' field_help_icon macro, _macros.html), not
// just this file's own settings-panel tooltip.
const dojoMarked = new Marked();

export type SettingsWidget =
  | "toggle"
  | "select"
  | "secret"
  | "number"
  | "color"
  | "url"
  | "text";

export interface SettingsField {
  path: string;
  key: string;
  title: string;
  description: string;
  widget: SettingsWidget;
  default: string | number | boolean | null;
  value: string | number | boolean | null;
  enumOptions?: string[];
  minimum?: number;
  maximum?: number;
  nullable: boolean;
  // for a "url" field, whether the *current* value should show the
  // clickable-globe affordance. Seeded from the backend's value_meta
  // (computed from the real validated HttpUrl/Path object - see
  // routers/settings.py) and recomputed client-side as the user types.
  isUrl: boolean;
  // for a "secret" field only: the masked placeholder as loaded from the
  // last GET, resent verbatim on save when the user leaves the (blanked)
  // input untouched, so the backend's masked-value check preserves the
  // real secret instead of overwriting it with the mask string.
  secretOriginal?: string;
}

export interface SettingsDictEntry {
  key: string;
  valueType: "string" | "number" | "boolean";
  value: string | number | boolean;
}

export interface SettingsDictField {
  path: string;
  key: string;
  title: string;
  description: string;
  entries: SettingsDictEntry[];
}

export interface SettingsGroup {
  path: string;
  key: string;
  title: string;
  description: string;
  fields: SettingsField[];
  subgroups: SettingsGroup[];
  dictField: SettingsDictField | null;
  // inner SVG markup (<path>/<rect>/<circle> elements, no outer <svg> tag)
  // shown next to the section title. Sourced from the schema's own
  // x-icon (model_config's json_schema_extra, settings.py), the same
  // mechanism x-widget uses below for color fields - the schema stays the
  // single source of truth for this kind of metadata rather than a second,
  // hand-maintained map here that could drift from it. Empty string for
  // any section that doesn't set one, so a new section never breaks - it
  // just renders with no icon.
  icon: string;
}

export interface SettingsSchemaNode {
  $ref?: string;
  type?: string;
  anyOf?: SettingsSchemaNode[];
  properties?: Record<string, SettingsSchemaNode>;
  additionalProperties?: SettingsSchemaNode | boolean;
  enum?: (string | number)[];
  description?: string;
  title?: string;
  default?: unknown;
  minimum?: number;
  maximum?: number;
  writeOnly?: boolean;
  format?: string;
  "x-widget"?: string;
  "x-icon"?: string;
}

export interface SettingsSchema extends SettingsSchemaNode {
  $defs?: Record<string, SettingsSchemaNode>;
}

export interface SettingsValueMetaEntry {
  is_url?: boolean;
}

export interface SettingsGetResponse {
  schema: SettingsSchema;
  values: Record<string, unknown>;
  value_meta: Record<string, SettingsValueMetaEntry>;
  color_choices: Record<string, string>;
  is_localhost: boolean;
}

export interface SettingsWriteResponse {
  values: Record<string, unknown>;
  value_meta: Record<string, SettingsValueMetaEntry>;
}

export interface SettingsPanelState {
  settingsOpen: boolean;
  settingsLoading: boolean;
  settingsSaving: boolean;
  settingsError: string;
  settingsIsLocalhost: boolean;
  settingsSections: SettingsGroup[];
  settingsColorChoices: Record<string, string>;
  settingsCollapsed: Record<string, boolean>;
  settingsSearchQuery: string;
  // a single shared tooltip, teleported to <body> (see _settings_panel.html)
  // rather than one absolutely-positioned node per field/section - overflow
  // scroll containers still count an absolutely-positioned descendant's box
  // toward their scrollable content size even while invisible/opacity-0, so
  // a per-field tooltip living *inside* the settings panel's scrollable
  // list inflated its height by however tall the longest one was (most
  // visible on the one-field Assets section, whose "symlink" tooltip is one
  // of the longest descriptions in the whole model). Teleporting removes it
  // from that scroll container's DOM subtree entirely.
  settingsTooltip: { show: boolean; text: string; top: number; left: number };
  _settingsSchema: SettingsSchema | null;
  // dojo.show_quick_filters (settings.py), mirrored onto the store so
  // trial-viewer.ts's X/Y-axis and reference-frame trees can read it live
  // rather than only the value baked into the page at initial server
  // render - without this, toggling the setting here while a trial-viewer
  // tab is already open would only take effect on that tab's next full
  // reload. Starts undefined (this store slice loads before trial-viewer.ts
  // has had a chance to seed it with the page's own initial value) and is
  // refreshed on every settings fetch/save/reset below.
  showQuickFilters?: boolean;

  // Both methods, not getters: this whole state slice gets merged into the
  // wider dojoStore object via `{ ...createSettingsPanelState(), ... }`
  // (store.ts), and object-spread reads a getter's CURRENT value once at
  // spread time and copies that as a plain, permanently-frozen data
  // property - it does not preserve live accessor semantics. A getter here
  // would eval to `[]`/`false` at store construction (before any settings
  // have loaded) and never recompute again, no matter how settingsSections
  // or settingsSearchQuery later change. A method survives the spread
  // (spread copies function values by reference just fine) and simply
  // recomputes on every call.
  settingsFilteredSections(): SettingsGroup[];
  settingsHasInvalidFields(): boolean;

  openSettings(): Promise<void>;
  closeSettings(): void;
  updateField(path: string, value: string | number | boolean | null): void;
  resetField(path: string): void;
  resetAllToDefaults(): Promise<void>;
  saveSettings(): Promise<void>;
  toggleSettingsSection(path: string): void;
  openOnLocalhost(): void;
  addDictEntry(groupPath: string): void;
  removeDictEntry(groupPath: string, index: number): void;
  showSettingsTooltip(el: HTMLElement, text: string): void;
  hideSettingsTooltip(): void;
  settingsFieldOutOfRange(field: SettingsField): boolean;
  settingsFieldRangeMessage(field: SettingsField): string;
  renderMarkdown(text: string): string;
  _applySettingsResponse(data: SettingsGetResponse): void;
  _applySettingsWrite(data: SettingsWriteResponse): void;
}

// ---------------------------------------------------------------------------
// schema walking
// ---------------------------------------------------------------------------

function resolveRef(
  schema: SettingsSchema,
  node: SettingsSchemaNode,
): SettingsSchemaNode {
  if (!node.$ref) return node;
  const refName = node.$ref.replace("#/$defs/", "");
  const target = schema.$defs?.[refName];
  if (!target) return node;
  const { $ref: _ref, ...override } = node;
  return { ...target, ...override };
}

function isDictNode(node: SettingsSchemaNode): boolean {
  return node.type === "object" && !node.properties && !!node.additionalProperties;
}

function isObjectNode(node: SettingsSchemaNode): boolean {
  return node.type === "object" && !!node.properties;
}

interface LeafDescription {
  widget: SettingsWidget;
  nullable: boolean;
  minimum?: number;
  maximum?: number;
  enumOptions?: string[];
}

function describeLeaf(node: SettingsSchemaNode): LeafDescription {
  if (node["x-widget"] === "color") return { widget: "color", nullable: true };
  if (node.type === "boolean") return { widget: "toggle", nullable: false };
  if (node.writeOnly) return { widget: "secret", nullable: false };
  if (node.enum) return { widget: "select", nullable: false, enumOptions: node.enum.map(String) };

  const branches = node.anyOf ?? [node];
  const nonNull = branches.filter((b) => b.type !== "null");
  const nullable = nonNull.length !== branches.length;
  const primary = nonNull[0] ?? node;

  if (nonNull.some((b) => b.format === "uri")) return { widget: "url", nullable };
  if (primary.type === "integer" || primary.type === "number") {
    return {
      widget: "number",
      nullable,
      minimum: primary.minimum ?? node.minimum,
      maximum: primary.maximum ?? node.maximum,
    };
  }
  return { widget: "text", nullable };
}

function buildField(
  schema: SettingsSchema,
  path: string,
  key: string,
  rawNode: SettingsSchemaNode,
  value: unknown,
  valueMeta: Record<string, SettingsValueMetaEntry>,
): SettingsField {
  const node = resolveRef(schema, rawNode);
  const { widget, nullable, minimum, maximum, enumOptions } = describeLeaf(node);
  const isSecret = widget === "secret";
  const rawValue = value as string | number | boolean | null | undefined;

  return {
    path,
    key,
    title: node.title ?? key,
    description: node.description ?? "",
    widget,
    default: (node.default ?? null) as string | number | boolean | null,
    value: isSecret ? "" : (rawValue ?? null),
    enumOptions,
    minimum,
    maximum,
    nullable,
    isUrl: widget === "url" ? !!valueMeta[path]?.is_url : false,
    secretOriginal: isSecret ? String(rawValue ?? "") : undefined,
  };
}

function inferScalarType(v: unknown): "string" | "number" | "boolean" {
  if (typeof v === "boolean") return "boolean";
  if (typeof v === "number") return "number";
  return "string";
}

function buildDictField(
  path: string,
  key: string,
  node: SettingsSchemaNode,
  value: unknown,
): SettingsDictField {
  const raw = (value ?? {}) as Record<string, string | number | boolean>;
  return {
    path,
    key,
    title: node.title ?? key,
    description: node.description ?? "",
    entries: Object.entries(raw).map(([k, v]) => ({
      key: k,
      valueType: inferScalarType(v),
      value: v,
    })),
  };
}

function buildGroup(
  schema: SettingsSchema,
  path: string,
  key: string,
  rawNode: SettingsSchemaNode,
  value: unknown,
  valueMeta: Record<string, SettingsValueMetaEntry>,
): SettingsGroup {
  const node = resolveRef(schema, rawNode);
  const objectValue = (value ?? {}) as Record<string, unknown>;
  const fields: SettingsField[] = [];
  const subgroups: SettingsGroup[] = [];
  let dictField: SettingsDictField | null = null;

  for (const [propKey, propRawNode] of Object.entries(node.properties ?? {})) {
    const propPath = `${path}.${propKey}`;
    const propNode = resolveRef(schema, propRawNode);
    const propValue = objectValue[propKey];
    if (isDictNode(propNode)) {
      dictField = buildDictField(propPath, propKey, propNode, propValue);
    } else if (isObjectNode(propNode)) {
      subgroups.push(buildGroup(schema, propPath, propKey, propRawNode, propValue, valueMeta));
    } else {
      fields.push(buildField(schema, propPath, propKey, propRawNode, propValue, valueMeta));
    }
  }

  return {
    path,
    key,
    title: node.title ?? key,
    description: node.description ?? "",
    fields,
    subgroups,
    dictField,
    icon: node["x-icon"] ?? "",
  };
}

export function parseSettingsSchema(
  schema: SettingsSchema,
  values: Record<string, unknown>,
  valueMeta: Record<string, SettingsValueMetaEntry>,
): SettingsGroup[] {
  const groups: SettingsGroup[] = [];
  for (const [key, rawNode] of Object.entries(schema.properties ?? {})) {
    const node = resolveRef(schema, rawNode);
    const value = values[key];
    if (isDictNode(node)) {
      groups.push({
        path: key,
        key,
        title: node.title ?? key,
        description: node.description ?? "",
        fields: [],
        subgroups: [],
        dictField: buildDictField(key, key, node, value),
        icon: node["x-icon"] ?? "",
      });
    } else {
      groups.push(buildGroup(schema, key, key, rawNode, value, valueMeta));
    }
  }
  return groups;
}

// ---------------------------------------------------------------------------
// lookup / serialization
// ---------------------------------------------------------------------------

export function findSettingsField(groups: SettingsGroup[], path: string): SettingsField | null {
  for (const g of groups) {
    const direct = g.fields.find((f) => f.path === path);
    if (direct) return direct;
    const nested = findSettingsField(g.subgroups, path);
    if (nested) return nested;
  }
  return null;
}

export function findSettingsGroup(groups: SettingsGroup[], path: string): SettingsGroup | null {
  for (const g of groups) {
    if (g.path === path) return g;
    const nested = findSettingsGroup(g.subgroups, path);
    if (nested) return nested;
  }
  return null;
}

function collectSettingsFields(groups: SettingsGroup[]): SettingsField[] {
  const out: SettingsField[] = [];
  for (const g of groups) {
    out.push(...g.fields);
    out.push(...collectSettingsFields(g.subgroups));
  }
  return out;
}

/** Whether a number field's current value violates the schema's minimum/maximum (e.g. VisualizationSettings' `ge=0` width scales) - guards against posting a value the backend would reject anyway, surfacing it inline instead of only after a failed save. */
export function isFieldOutOfRange(field: SettingsField): boolean {
  if (field.widget !== "number" || typeof field.value !== "number") return false;
  if (field.minimum !== undefined && field.value < field.minimum) return true;
  if (field.maximum !== undefined && field.value > field.maximum) return true;
  return false;
}

export function fieldRangeMessage(field: SettingsField): string {
  if (field.minimum !== undefined && field.maximum !== undefined) {
    return `Must be between ${field.minimum} and ${field.maximum}`;
  }
  if (field.minimum !== undefined) return `Must be at least ${field.minimum}`;
  if (field.maximum !== undefined) return `Must be at most ${field.maximum}`;
  return "";
}

function dictFieldValue(dictField: SettingsDictField): Record<string, unknown> {
  return Object.fromEntries(dictField.entries.map((e) => [e.key, e.value]));
}

function serializeFieldValue(field: SettingsField): unknown {
  if (field.widget === "secret") return field.value ? field.value : (field.secretOriginal ?? "");
  if (field.nullable && field.value === "") return null;
  return field.value;
}

function groupValue(group: SettingsGroup): unknown {
  if (
    group.dictField &&
    group.dictField.key === group.key &&
    group.fields.length === 0 &&
    group.subgroups.length === 0
  ) {
    return dictFieldValue(group.dictField);
  }
  const out: Record<string, unknown> = {};
  for (const field of group.fields) out[field.key] = serializeFieldValue(field);
  for (const sub of group.subgroups) out[sub.key] = groupValue(sub);
  if (group.dictField) out[group.dictField.key] = dictFieldValue(group.dictField);
  return out;
}

export function serializeSettings(groups: SettingsGroup[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const group of groups) out[group.key] = groupValue(group);
  return out;
}

// ---------------------------------------------------------------------------
// search / filter
// ---------------------------------------------------------------------------

function fieldMatchesQuery(field: SettingsField, query: string): boolean {
  return (
    field.title.toLowerCase().includes(query) ||
    field.description.toLowerCase().includes(query) ||
    field.key.toLowerCase().includes(query)
  );
}

/**
 * Filters one group to only the fields/subgroups matching `query` (already
 * lowercased). A group whose own title/description matches is returned
 * whole (unfiltered) - searching "sensai" should show the entire SensAI
 * subgroup, not an empty shell with nothing under it. A group with no
 * matching title and no matching descendants (leaf fields or a dict field,
 * which has no per-entry title/description to search) is dropped entirely
 * rather than shown empty.
 */
function filterGroup(group: SettingsGroup, query: string): SettingsGroup | null {
  const titleMatches =
    group.title.toLowerCase().includes(query) || group.description.toLowerCase().includes(query);
  if (titleMatches) return group;

  const fields = group.fields.filter((f) => fieldMatchesQuery(f, query));
  const subgroups = group.subgroups
    .map((s) => filterGroup(s, query))
    .filter((s): s is SettingsGroup => s !== null);

  if (fields.length === 0 && subgroups.length === 0) return null;
  return { ...group, fields, subgroups };
}

/** Empty query is a no-op pass-through - the panel's normal, unfiltered section list. */
export function filterSettingsSections(groups: SettingsGroup[], query: string): SettingsGroup[] {
  const q = query.trim().toLowerCase();
  if (!q) return groups;
  const out: SettingsGroup[] = [];
  for (const group of groups) {
    const filtered = filterGroup(group, q);
    if (filtered) out.push(filtered);
  }
  return out;
}

// ---------------------------------------------------------------------------
// color (visualization.* fields, x-widget: "color")
// ---------------------------------------------------------------------------
// settings.py's color-widget fields accept either a Color enum member name
// (e.g. "EMERALD_500", matched case-insensitively) or a raw "#rrggbb" hex
// code - see parse_color_value, also reachable directly via
// GET /settings/color/resolve for a color picker that isn't this settings
// panel. The frontend mirrors that: a text input takes either form
// directly, and the wheel picker sets whatever hex was picked verbatim, no
// forced snapping to a named swatch. nearestColorName is kept only as an
// informational "closest named color" hint for a value that's a hex the
// user typed/picked rather than one of the named swatches.

const HEX_COLOR_RE = /^#[0-9A-Fa-f]{6}$/;

export function isHexColor(value: unknown): value is string {
  return typeof value === "string" && HEX_COLOR_RE.test(value);
}

/** Resolves a color field's current value (a Color name in any case, or a hex code) to a hex string for swatch/wheel display, or null if it's neither (e.g. hidden, or a still-being-typed value). Name matching is case-insensitive to mirror Color.parse - without this, typing a name in anything but the exact stored case (e.g. lowercase) looked up nothing and left the wheel stale. */
export function resolveColorHex(
  value: string | null | undefined,
  choices: Record<string, string>,
): string | null {
  if (!value) return null;
  const upper = value.toUpperCase();
  return isHexColor(upper) ? upper : (choices[upper] ?? null);
}

/** Collapses a hex value that exactly matches a named swatch to that name, mirroring Color.parse's own alias-collapsing (settings.py, via the model validator on save) so the wheel/text input reflect it immediately rather than only after a save+reload round trip. A name, an unmatched hex, or anything not yet a complete valid value passes through unchanged. */
export function collapseColorAlias(
  value: string | null | undefined,
  choices: Record<string, string>,
): string | null | undefined {
  if (!isHexColor(value)) return value;
  const upper = value.toUpperCase();
  for (const [name, hex] of Object.entries(choices)) {
    if (hex.toUpperCase() === upper) return name;
  }
  return upper;
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const clean = hex.replace("#", "");
  return {
    r: parseInt(clean.substring(0, 2), 16) || 0,
    g: parseInt(clean.substring(2, 4), 16) || 0,
    b: parseInt(clean.substring(4, 6), 16) || 0,
  };
}

/** Closest named entry in `choices` (e.g. settingsColorChoices) to an arbitrary hex, by simple RGB distance - good enough given how densely Color's ~200 swatches cover the space. Purely informational (see above); never overwrites what the user picked/typed. */
export function nearestColorName(hex: string, choices: Record<string, string>): string {
  const target = hexToRgb(hex);
  let bestName = "";
  let bestDist = Infinity;
  for (const [name, choiceHex] of Object.entries(choices)) {
    const rgb = hexToRgb(choiceHex);
    const dist = (rgb.r - target.r) ** 2 + (rgb.g - target.g) ** 2 + (rgb.b - target.b) ** 2;
    if (dist < bestDist) {
      bestDist = dist;
      bestName = name;
    }
  }
  return bestName;
}

// ---------------------------------------------------------------------------
// url detection (dojo.chime and any future url-or-path field)
// ---------------------------------------------------------------------------

/**
 * Live, client-side check used only while the user is typing an unsaved
 * edit - never the source of truth for what gets stored (POST /settings
 * re-validates through the real HttpUrl | Path union server-side
 * regardless). For a value already loaded from GET /settings, the
 * authoritative signal is value_meta[path].is_url instead, computed
 * server-side from the real validated Python object.
 */
export function looksLikeHttpUrl(value: unknown): boolean {
  if (typeof value !== "string" || !value) return false;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// store slice
// ---------------------------------------------------------------------------

function loadCollapsedSections(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem("mojo:settings:collapsed-sections");
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

async function settingsErrorDetail(resp: Response): Promise<string> {
  try {
    const data = (await resp.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((e) =>
          e && typeof e === "object" && "msg" in e
            ? String((e as { msg: unknown }).msg)
            : JSON.stringify(e),
        )
        .join("; ");
    }
  } catch {
    /* not JSON */
  }
  return `Request failed (${resp.status})`;
}

// cross-slice calls (toast/notifications) go through Alpine.store('dojo')
// rather than `this`, matching lib/toast.ts's createToastMixin() - `this`
// inside these methods is typed as SettingsPanelState only, which doesn't
// itself declare toast()/addNotification() (those live on the wider
// DojoStore this state gets spread into by store.ts).
function notifyDojo(message: string, type: "success" | "error" | "info") {
  (Alpine.store("dojo") as { toast?: (m: string, t?: string) => void }).toast?.(message, type);
}

// Pulls dojo.show_quick_filters back out of a /settings response's raw
// `values` tree (typed as Record<string, unknown> since it's the live
// MujocoMojoSettings dump, not a shape this module otherwise needs to know)
// - returns undefined rather than throwing if the shape isn't what's
// expected, so a malformed/older response degrades to "leave the store
// value alone" instead of clobbering it with undefined.
function extractShowQuickFilters(values: Record<string, unknown>): boolean | undefined {
  const dojo = values.dojo;
  if (!dojo || typeof dojo !== "object") return undefined;
  const v = (dojo as Record<string, unknown>).show_quick_filters;
  return typeof v === "boolean" ? v : undefined;
}

export function createSettingsPanelState(): SettingsPanelState {
  return {
    settingsOpen: false,
    settingsLoading: false,
    settingsSaving: false,
    settingsError: "",
    settingsIsLocalhost: false,
    settingsSections: [],
    settingsColorChoices: {},
    settingsCollapsed: loadCollapsedSections(),
    settingsSearchQuery: "",
    settingsTooltip: { show: false, text: "", top: 0, left: 0 },
    _settingsSchema: null,
    showQuickFilters: undefined,

    settingsHasInvalidFields() {
      return collectSettingsFields(this.settingsSections).some(isFieldOutOfRange);
    },

    settingsFilteredSections() {
      return filterSettingsSections(this.settingsSections, this.settingsSearchQuery);
    },

    settingsFieldOutOfRange(field) {
      return isFieldOutOfRange(field);
    },

    settingsFieldRangeMessage(field) {
      return fieldRangeMessage(field);
    },

    renderMarkdown(text) {
      try {
        return dojoMarked.parse(text, { async: false }) as string;
      } catch {
        return text;
      }
    },

    async openSettings() {
      this.settingsOpen = true;
      // guard scrolling to the settings panel itself while it's open,
      // rather than letting wheel/touch input also scroll the Dojo page
      // sitting behind the backdrop
      document.body.style.overflow = "hidden";
      this.settingsLoading = true;
      this.settingsError = "";
      try {
        const resp = await fetch("/settings");
        if (!resp.ok) throw new Error(await settingsErrorDetail(resp));
        const data = (await resp.json()) as SettingsGetResponse;
        this._applySettingsResponse(data);
      } catch (err) {
        this.settingsError = err instanceof Error ? err.message : "Failed to load settings";
      } finally {
        this.settingsLoading = false;
      }
    },

    closeSettings() {
      this.settingsOpen = false;
      document.body.style.overflow = "";
      this.hideSettingsTooltip();
      this.settingsSearchQuery = "";
    },

    showSettingsTooltip(el, text) {
      // the panel's own closing transition keeps its content visible (and
      // hoverable) for ~100ms after settingsOpen flips false, so a
      // mouseenter can still land on an info icon mid-fade - closeSettings()
      // already hides any currently-open tooltip synchronously, but that
      // can't stop a *later* mouseenter from reopening one afterward, and
      // nothing would then be left to hide it again. Guarding here (rather
      // than only reacting to the close) closes that race outright: no
      // tooltip can newly open once the panel isn't.
      if (!text || !this.settingsOpen) return;
      const rect = el.getBoundingClientRect();
      const tooltipWidth = 288; // matches the tooltip's w-72
      this.settingsTooltip = {
        show: true,
        text,
        top: rect.bottom + 8,
        left: Math.min(rect.left, window.innerWidth - tooltipWidth - 16),
      };
    },

    hideSettingsTooltip() {
      this.settingsTooltip = { ...this.settingsTooltip, show: false };
    },

    updateField(path, value) {
      const field = findSettingsField(this.settingsSections, path);
      if (!field) return;
      field.value = value;
      if (field.widget === "url") field.isUrl = looksLikeHttpUrl(value);
    },

    resetField(path) {
      const field = findSettingsField(this.settingsSections, path);
      if (!field) return;
      field.value = field.default;
      if (field.widget === "url") field.isUrl = looksLikeHttpUrl(field.default);
    },

    async resetAllToDefaults() {
      const ok = await window.mojoConfirm?.({
        title: "Restore default settings?",
        message: "Every setting will be reset to its built-in default. This cannot be undone.",
        confirmLabel: "Restore Defaults",
        variant: "danger",
      });
      if (!ok) return;
      this.settingsSaving = true;
      try {
        const resp = await fetch("/settings/reset", { method: "POST" });
        if (!resp.ok) throw new Error(await settingsErrorDetail(resp));
        const data = (await resp.json()) as SettingsWriteResponse;
        this._applySettingsWrite(data);
        notifyDojo("Settings restored to defaults", "success");
      } catch (err) {
        notifyDojo(err instanceof Error ? err.message : "Failed to restore defaults", "error");
      } finally {
        this.settingsSaving = false;
      }
    },

    async saveSettings() {
      if (this.settingsHasInvalidFields()) {
        this.settingsError = "Fix the highlighted field(s) before saving.";
        return;
      }
      this.settingsSaving = true;
      this.settingsError = "";
      try {
        const body = serializeSettings(this.settingsSections);
        const resp = await fetch("/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!resp.ok) throw new Error(await settingsErrorDetail(resp));
        const data = (await resp.json()) as SettingsWriteResponse;
        this._applySettingsWrite(data);
        notifyDojo("Settings saved", "success");
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to save settings";
        this.settingsError = message;
        notifyDojo(message, "error");
      } finally {
        this.settingsSaving = false;
      }
    },

    toggleSettingsSection(path) {
      this.settingsCollapsed = {
        ...this.settingsCollapsed,
        [path]: !this.settingsCollapsed[path],
      };
      try {
        localStorage.setItem(
          "mojo:settings:collapsed-sections",
          JSON.stringify(this.settingsCollapsed),
        );
      } catch {
        /* quota exceeded - ignore */
      }
    },

    openOnLocalhost() {
      const url = new URL(window.location.href);
      url.hostname = "127.0.0.1";
      window.open(url.toString(), "_blank", "noopener");
    },

    addDictEntry(groupPath) {
      const group = findSettingsGroup(this.settingsSections, groupPath);
      if (!group?.dictField) return;
      group.dictField.entries.push({ key: "", valueType: "string", value: "" });
    },

    removeDictEntry(groupPath, index) {
      const group = findSettingsGroup(this.settingsSections, groupPath);
      group?.dictField?.entries.splice(index, 1);
    },

    _applySettingsResponse(data) {
      this._settingsSchema = data.schema;
      this.settingsColorChoices = data.color_choices;
      this.settingsIsLocalhost = data.is_localhost;
      this.settingsSections = parseSettingsSchema(data.schema, data.values, data.value_meta);
      this.showQuickFilters = extractShowQuickFilters(data.values) ?? this.showQuickFilters;
    },

    _applySettingsWrite(data) {
      if (!this._settingsSchema) return;
      this.settingsSections = parseSettingsSchema(
        this._settingsSchema,
        data.values,
        data.value_meta,
      );
      this.showQuickFilters = extractShowQuickFilters(data.values) ?? this.showQuickFilters;
    },
  };
}
