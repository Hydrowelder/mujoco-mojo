import type { DistEntry } from "../models";

// Formats a number like Python's `g` format: regular decimal notation for
// "normal" magnitudes, scientific notation for very small/large values, with
// trailing zeros trimmed.
export function formatNum(value: number | null | undefined, sigDigits = 4): string {
  if (value == null) return "-";
  if (!Number.isFinite(value)) return String(value);
  if (value === 0) return "0";

  const abs = Math.abs(value);
  if (abs < 1e-4 || abs >= 10 ** sigDigits) {
    return value
      .toExponential(Math.max(sigDigits - 1, 0))
      .replace(/\.?0+e/, "e");
  }
  return parseFloat(value.toPrecision(sigDigits)).toString();
}

// Inserts a zero-width space after every "/" and ":" so long signal/frame
// names wrap only at those separators instead of mid-word or not at all.
export function breakableLabel(text: string): string {
  return text.replace(/([/:])/g, "$1​");
}

export function formatTimeAgo(seconds: number): string {
  if (!seconds || seconds < 60) return `${seconds || 0}s ago`;
  const mins = Math.floor(seconds / 60);
  return mins < 60 ? `${mins}m ago` : `${Math.floor(mins / 60)}h ago`;
}

// Takes an absolute ms timestamp + an optional tick value (ignored, but its
// presence in the Alpine expression causes the template to re-evaluate when
// $store.dojo.notifTick changes every minute).
export function notifTimeAgo(timestamp: number, _tick?: number): string {
  const diff = Math.floor((Date.now() - timestamp) / 1000);
  if (diff < 60) return 'Just now';
  const mins = Math.floor(diff / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

// format a number with 4 significant figures, switching to exponential
// notation when the exponent is < -4 or >= 4 (matches Python's g format)
export function formatSigFig(v: number | null): string {
  if (v === null) return "—";
  if (v === 0) return "0";
  const abs = Math.abs(v);
  const exp = Math.floor(Math.log10(abs));
  if (exp < -4 || exp >= 4) return v.toExponential(3);
  return parseFloat(v.toPrecision(4)).toString();
}

// formats every drawn value for a dist table row, regardless of whether it
// sampled numbers, labels, or (for permutations) a list of items per draw
export function formatSampled(entry: DistEntry): string {
  if (entry.sampled_permutations && entry.sampled_permutations.length > 0) {
    return entry.sampled_permutations
      .map((perm) => `[${perm.join(", ")}]`)
      .join("; ");
  }
  if (entry.sampled_values && entry.sampled_values.length > 0) {
    return entry.sampled_values.map((v) => formatSigFig(v)).join(", ");
  }
  if (entry.sampled_labels && entry.sampled_labels.length > 0) {
    return entry.sampled_labels.join(", ");
  }
  return "—";
}

// formats a percentile in the standard P{x} notation (e.g. P95.7) rather
// than the nonstandard "%ile" shorthand
export function formatPercentile(p: number): string {
  return `P${p.toFixed(1)}`;
}

// Renders one DEFAULT_CONFIG value for a "Default: `X`." tooltip line
// (plotFieldHelp above), matching the exact rendering
// GenerateJsonSchemaWithDefaults (settings.py) uses server-side for
// Pydantic-level defaults - "true"/"false" for booleans, str(x) otherwise,
// which for Python's None is the literal text "None" - so a
// frontend-sourced default reads identically to a schema-sourced one
// rather than looking like a different kind of value. Empty string
// (title/xAxisTitle/yAxisTitle's actual default) renders as "(empty)"
// instead of nothing visibly between the backticks.
export function formatDefaultValue(value: unknown): string {
  if (value === null || value === undefined) return "None";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return value === "" ? "(empty)" : value;
  return JSON.stringify(value);
}

// "just now", "5m ago", "3h ago", "yesterday", "4d ago": how long before `now`
// the timestamp (ms) was
export function relativeTime(ms: number, now = Date.now()): string {
  const diff = now - ms;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return d === 1 ? "yesterday" : `${d}d ago`;
}
