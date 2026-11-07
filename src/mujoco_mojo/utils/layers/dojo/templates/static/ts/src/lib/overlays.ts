// the shapes (vertical and horizontal lines, rectangles) and annotations a
// trial viewer plot can carry, moved out of trial-viewer.ts so they can be
// tested without an alpine component: placing a shape from clicks, saving a
// draft into the config, where an annotation jump zooms to, and the plotly
// annotation and shape objects a plot is drawn with.

import type { Annotation, DashStyle, Shape } from "./plot-config.generated";

export type PlacementMode = "vline" | "hline" | "rect";

export interface ShapeStyle {
  color: string;
  dash: DashStyle;
}

export function placementLabel(type: PlacementMode): string {
  return type === "vline"
    ? "Vertical Line"
    : type === "hline"
      ? "Horizontal Line"
      : "Area Rectangle";
}

// what a click on the plot does while a shape is being placed. A line is
// placed by one click. A rectangle takes two: the first click only remembers
// its corner (no shape yet), the second completes it and forgets the corner.
// `rectStart` is the corner remembered so far, and the result's `rectStart`
// is the corner to remember now.
export function shapeFromClick(
  mode: PlacementMode,
  rectStart: { x: number; y: number } | null,
  pt: { x: number; y: number },
  style: ShapeStyle,
): { shape: Shape | null; rectStart: { x: number; y: number } | null } {
  let newShape: Shape | null = null;

  if (mode === "vline") {
    newShape = {
      type: "vline",
      x0: pt.x,
      color: style.color,
      dash: style.dash,
      label: "",
    };
  } else if (mode === "hline") {
    newShape = {
      type: "hline",
      y0: pt.y,
      color: style.color,
      dash: style.dash,
      label: "",
    };
  } else if (mode === "rect") {
    if (!rectStart) {
      return { shape: null, rectStart: { x: pt.x, y: pt.y } };
    }
    newShape = {
      type: "rect",
      x0: rectStart.x,
      x1: pt.x,
      y0: rectStart.y,
      y1: pt.y,
      color: style.color,
      dash: style.dash,
      label: "",
    };
    return { shape: newShape, rectStart: null };
  }
  return { shape: newShape, rectStart };
}

// saves a draft into a list in place: over the item being edited, or at the
// end for a new one. the list is changed in place because the component's own
// config array is reactive; the draft is stored as a copy.
export function upsertAt<T extends object>(
  list: T[],
  draft: T,
  editIndex: number | null,
): void {
  if (editIndex !== null) {
    list[editIndex] = { ...draft };
  } else {
    list.push({ ...draft });
  }
}

// text a user typed is worth keeping when it is not only whitespace; null is
// a cancelled prompt
export function isUsableText(text: string | null): text is string {
  return text !== null && text.trim() !== "";
}

// the x range an annotation jump zooms to: a tenth of the data's x extent,
// centered on the annotation and slid back inside the data when it would
// stick out past either end.
export function annotationXRange(xValues: number[], annX: number): [number, number] {
  const xMin = xValues[0] ?? 0;
  const xMax = xValues[xValues.length - 1] ?? 100;
  const xSpan = (xMax - xMin) * 0.1;
  const newRangeX: [number, number] = [annX - xSpan / 2, annX + xSpan / 2];
  if (newRangeX[0] < xMin) {
    newRangeX[1] += xMin - newRangeX[0];
    newRangeX[0] = xMin;
  }
  if (newRangeX[1] > xMax) {
    newRangeX[0] -= newRangeX[1] - xMax;
    newRangeX[1] = xMax;
  }
  return newRangeX;
}

// the y range an annotation jump zooms to: a fifth of the full y range,
// centered on the annotation
export function annotationYRange(fullY: [number, number], annY: number): [number, number] {
  const ySpan = Math.abs(fullY[1] - fullY[0]) * 0.2;
  return [annY - ySpan / 2, annY + ySpan / 2];
}

// the theme colors the plotly overlays use, resolved by the caller
export interface OverlayColors {
  tooltipFont: string;
  annotationBg: string;
  accent: string;
  shapeLabelBg: string;
}

// the plotly annotations of a plot: the user's notes, then a label for each
// shape that has one, placed at its line or at the top-left corner of its
// rectangle.
export function plotlyAnnotations(
  annotations: Annotation[],
  shapes: Shape[],
  colors: OverlayColors,
): object[] {
  return [
    ...annotations.map((ann) => ({
      x: ann.x,
      y: ann.y,
      text: ann.text,
      showarrow: true,
      arrowhead: 2,
      ax: 0,
      ay: -40,
      font: {
        family: "monospace",
        size: 12,
        color: colors.tooltipFont,
      },
      bgcolor: colors.annotationBg,
      bordercolor: colors.accent,
      borderwidth: 1,
      borderpad: 4,
    })),
    ...shapes
      .filter((s) => s.label)
      .map((s) => {
        let x = 0,
          y = 0,
          xanchor = "left",
          yanchor = "bottom",
          xref = "x",
          yref = "y";
        if (s.type === "vline") {
          x = s.x0;
          y = 1;
          yref = "paper";
        } else if (s.type === "hline") {
          x = 1;
          y = s.y0;
          xref = "paper";
          xanchor = "right";
        } else if (s.type === "rect") {
          x = s.x0;
          y = s.y1;
        }
        return {
          x,
          y,
          xref,
          yref,
          text: `<b>${s.label}</b>`,
          showarrow: false,
          xanchor,
          yanchor,
          font: {
            size: 10,
            color: s.color || colors.accent,
            family: "monospace",
          },
          bgcolor: colors.shapeLabelBg,
          borderpad: 2,
        };
      }),
  ];
}

// the plotly shapes of a plot: lines span the whole plot (in paper
// coordinates) across their other axis, rectangles are tinted a little more
// in light mode than dark
export function plotlyShapes(shapes: Shape[], isDark: boolean, accent: string): object[] {
  return shapes.map((s) => {
    const shapeColor = s.color || accent;
    const base = {
      line: { color: shapeColor, width: 2, dash: s.dash ?? "solid" },
      layer: "below",
    };
    if (s.type === "vline")
      return {
        ...base,
        type: "line",
        x0: s.x0,
        x1: s.x0,
        y0: 0,
        y1: 1,
        yref: "paper",
      };
    if (s.type === "hline")
      return {
        ...base,
        type: "line",
        y0: s.y0,
        y1: s.y0,
        x0: 0,
        x1: 1,
        xref: "paper",
      };
    if (s.type === "rect")
      return {
        ...base,
        type: "rect",
        x0: s.x0,
        x1: s.x1,
        y0: s.y0,
        y1: s.y1,
        fillcolor: isDark ? `${shapeColor}1A` : `${shapeColor}26`,
        line: { ...base.line, width: 1 },
      };
    return base;
  });
}
