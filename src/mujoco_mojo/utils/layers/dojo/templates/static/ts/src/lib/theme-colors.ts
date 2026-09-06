// reads Dojo's design tokens (theme.css) at runtime, resolving each
// `--color-*` custom property to a plain hex string. Canvas/SVG consumers
// (Plotly, LiteGraph, raw style strings) can't parse `var(--color-x)`
// directly, so this is the one place they resolve a token instead of each
// re-typing the palette's hex values independently.

/**
 * resolve `--color-{name}` from `theme.css` (e.g. "accent-500" ->
 * "#06b6d4"). Not cached: cheap enough to call per redraw, and a live read
 * means callers automatically pick up a light/dark theme toggle without
 * needing their own invalidation logic.
 */
export function themeColor(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(`--color-${name}`).trim();
}

/**
 * same as {@link themeColor}, with an alpha channel appended as an 8-digit
 * hex color (`#rrggbbaa`) rather than `rgba(...)`: tokens are already plain
 * hex, so this avoids re-parsing them into R/G/B components, and 8-digit
 * hex is well supported everywhere this is used (Plotly, SVG, canvas).
 */
export function themeColorAlpha(name: string, alpha: number): string {
  const alphaHex = Math.round(alpha * 255)
    .toString(16)
    .padStart(2, "0");
  return `${themeColor(name)}${alphaHex}`;
}
