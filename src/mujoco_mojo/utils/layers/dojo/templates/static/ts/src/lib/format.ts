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
