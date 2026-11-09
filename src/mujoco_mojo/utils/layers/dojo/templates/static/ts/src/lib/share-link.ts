// the plot config as a shareable link: the whole config, JSON-stringified,
// compressed with lz-string into URL-safe text, carried in the page's `?v=`
// parameter

import LZString from "lz-string";

import type { PlotConfig } from "../models";
import { sanitizeRefFrame } from "./ref-frame";

export function encodeShareConfig(config: PlotConfig): string {
  return LZString.compressToEncodedURIComponent(JSON.stringify(config));
}

// throws if the text isn't something encodeShareConfig could have produced.
// a config saved before the reference frame became a pair comes back with the
// frame reset to the world frame
export function decodeShareConfig(blob: string): Partial<PlotConfig> {
  const decoded = LZString.decompressFromEncodedURIComponent(blob);
  if (!decoded) throw new Error("Decompression failed");
  return sanitizeRefFrame(JSON.parse(decoded) as Partial<PlotConfig>);
}

// Accepts either a bare shared-link code (the ?v= value alone) or a
// full URL containing one, so pasting the whole copied link just
// works without the user having to trim it down themselves.
export function extractShareBlob(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  try {
    const url = new URL(trimmed);
    const v = url.searchParams.get("v");
    if (v) return v;
  } catch {
    // not a parseable URL - fall through and treat it as a bare code
  }
  return trimmed;
}
