// reads Dojo's design tokens (theme.css) at runtime, resolving each
// `--color-*` custom property to a plain hex string. Canvas/SVG consumers
// (Plotly, LiteGraph, raw style strings) can't parse `var(--color-x)`
// directly, so this is the one place they resolve a token instead of each
// re-typing the palette's hex values independently.

// theme.css's tokens mostly alias Tailwind's own default palette (e.g.
// --color-accent-500: var(--color-cyan-500)), and Tailwind v4 defines that
// palette with progressively-enhanced hex / color(display-p3 ...) / lab()
// declarations for the same custom property gated behind @supports -- every
// evergreen browser matches the lab() one, so getComputedStyle() resolves
// to a string like "lab(67.8% -35.4 -30.2)", not hex, despite this file's
// own contract above. That's harmless for consumers that just hand the
// string to a CSS-color-aware API (Plotly/culori, canvas fillStyle), but it
// broke anything that stores or re-parses the raw string as "the color":
// plotColors (persisted as shape/annotation/series colors in PlotConfig)
// and the swatch color picker (iro.js doesn't understand lab() and falls
// back to black; the hex text field showed the lab() string verbatim).
// Routing every value through a 1x1 canvas forces a real hex string
// regardless of what format the browser resolved the custom property to --
// canvas fillStyle accepts any valid CSS color and getImageData always
// reads back plain sRGB bytes.
let hexCanvasCtx: CanvasRenderingContext2D | null | undefined;

function resolveToHex(cssColor: string): string {
  if (!cssColor) return cssColor;
  if (hexCanvasCtx === undefined) {
    const canvas = document.createElement("canvas");
    canvas.width = 1;
    canvas.height = 1;
    hexCanvasCtx = canvas.getContext("2d", { willReadFrequently: true });
  }
  if (!hexCanvasCtx) return cssColor;
  hexCanvasCtx.fillStyle = cssColor;
  hexCanvasCtx.fillRect(0, 0, 1, 1);
  const [r, g, b] = hexCanvasCtx.getImageData(0, 0, 1, 1).data;
  const toHex = (n: number) => n.toString(16).padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

/**
 * resolve `--color-{name}` from `theme.css` (e.g. "accent-500" ->
 * "#06b6d4"). Not cached: cheap enough to call per redraw, and a live read
 * means callers automatically pick up a light/dark theme toggle without
 * needing their own invalidation logic.
 */
export function themeColor(name: string): string {
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(`--color-${name}`)
    .trim();
  return resolveToHex(raw);
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
