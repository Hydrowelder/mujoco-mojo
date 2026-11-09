import { describe, expect, it } from "vitest";

import {
  annotationXRange,
  annotationYRange,
  isUsableText,
  placementLabel,
  plotlyAnnotations,
  plotlyShapes,
  shapeFromClick,
  upsertAt,
  type OverlayColors,
  type ShapeStyle,
} from "./overlays";
import type { Annotation, Shape } from "./plot-config.generated";

const STYLE: ShapeStyle = { color: "#ff0000", dash: "dash" };
const COLORS: OverlayColors = {
  tooltipFont: "#111111",
  annotationBg: "#222222",
  accent: "#333333",
  shapeLabelBg: "#444444b3",
};

describe("placementLabel", () => {
  it("names each placement mode", () => {
    expect(placementLabel("vline")).toBe("Vertical Line");
    expect(placementLabel("hline")).toBe("Horizontal Line");
    expect(placementLabel("rect")).toBe("Area Rectangle");
  });
});

describe("shapeFromClick", () => {
  it("places a vertical line at the clicked x", () => {
    expect(shapeFromClick("vline", null, { x: 1.5, y: 9 }, STYLE)).toEqual({
      shape: { type: "vline", x0: 1.5, color: "#ff0000", dash: "dash", label: "" },
      rectStart: null,
    });
  });

  it("places a horizontal line at the clicked y", () => {
    expect(shapeFromClick("hline", null, { x: 9, y: 2.5 }, STYLE)).toEqual({
      shape: { type: "hline", y0: 2.5, color: "#ff0000", dash: "dash", label: "" },
      rectStart: null,
    });
  });

  it("only remembers the corner on a rectangle's first click", () => {
    expect(shapeFromClick("rect", null, { x: 1, y: 2 }, STYLE)).toEqual({
      shape: null,
      rectStart: { x: 1, y: 2 },
    });
  });

  it("completes the rectangle on the second click and forgets the corner", () => {
    expect(shapeFromClick("rect", { x: 1, y: 2 }, { x: 3, y: 4 }, STYLE)).toEqual({
      shape: { type: "rect", x0: 1, x1: 3, y0: 2, y1: 4, color: "#ff0000", dash: "dash", label: "" },
      rectStart: null,
    });
  });

  it("keeps the corners in the order they were clicked, even when dragged backwards", () => {
    const { shape } = shapeFromClick("rect", { x: 5, y: 6 }, { x: -1, y: -2 }, STYLE);
    expect(shape).toMatchObject({ x0: 5, x1: -1, y0: 6, y1: -2 });
  });

  it("leaves a remembered corner alone when a line is placed", () => {
    const corner = { x: 7, y: 8 };
    expect(shapeFromClick("vline", corner, { x: 0, y: 0 }, STYLE).rectStart).toBe(corner);
    expect(shapeFromClick("hline", corner, { x: 0, y: 0 }, STYLE).rectStart).toBe(corner);
  });

  it("uses the style it is given", () => {
    const { shape } = shapeFromClick("vline", null, { x: 0, y: 0 }, { color: "#00ff00", dash: "dot" });
    expect(shape).toMatchObject({ color: "#00ff00", dash: "dot" });
  });

  it("places nothing for an unknown mode", () => {
    const corner = { x: 1, y: 1 };
    expect(shapeFromClick("bogus" as never, corner, { x: 0, y: 0 }, STYLE)).toEqual({
      shape: null,
      rectStart: corner,
    });
  });

  it("does not hold on to the clicked point", () => {
    const pt = { x: 1, y: 2 };
    const { rectStart } = shapeFromClick("rect", null, pt, STYLE);
    pt.x = 99;
    expect(rectStart).toEqual({ x: 1, y: 2 });
  });
});

describe("upsertAt", () => {
  it("replaces the item being edited, in place", () => {
    const list = [{ n: 1 }, { n: 2 }, { n: 3 }];
    const same = list;
    upsertAt(list, { n: 20 }, 1);
    expect(list).toBe(same);
    expect(list).toEqual([{ n: 1 }, { n: 20 }, { n: 3 }]);
  });

  it("adds a new item at the end", () => {
    const list = [{ n: 1 }];
    upsertAt(list, { n: 2 }, null);
    expect(list).toEqual([{ n: 1 }, { n: 2 }]);
  });

  it("edits the first item when the index is 0", () => {
    const list = [{ n: 1 }, { n: 2 }];
    upsertAt(list, { n: 10 }, 0);
    expect(list).toEqual([{ n: 10 }, { n: 2 }]);
  });

  it("stores a copy, so later changes to the draft do not reach the list", () => {
    const draft = { n: 5 };
    const edited = [{ n: 1 }];
    const added: Array<{ n: number }> = [];
    upsertAt(edited, draft, 0);
    upsertAt(added, draft, null);
    draft.n = 99;
    expect(edited[0]).toEqual({ n: 5 });
    expect(added[0]).toEqual({ n: 5 });
    expect(edited[0]).not.toBe(draft);
    expect(added[0]).not.toBe(draft);
  });
});

describe("isUsableText", () => {
  it("accepts text with something in it", () => {
    expect(isUsableText("note")).toBe(true);
    expect(isUsableText("  padded  ")).toBe(true);
  });

  it("rejects empty and whitespace-only text", () => {
    expect(isUsableText("")).toBe(false);
    expect(isUsableText("   \t\n")).toBe(false);
  });

  it("rejects a cancelled prompt", () => {
    expect(isUsableText(null)).toBe(false);
  });
});

describe("annotationXRange", () => {
  const xs = Array.from({ length: 101 }, (_, i) => i); // 0..100

  it("is a tenth of the data's extent, centered on the annotation", () => {
    expect(annotationXRange(xs, 50)).toEqual([45, 55]);
  });

  it("slides back inside the data at the start, keeping its width", () => {
    expect(annotationXRange(xs, 0)).toEqual([0, 10]);
    expect(annotationXRange(xs, 2)).toEqual([0, 10]);
  });

  it("slides back inside the data at the end, keeping its width", () => {
    expect(annotationXRange(xs, 100)).toEqual([90, 100]);
    expect(annotationXRange(xs, 98)).toEqual([90, 100]);
  });

  it("leaves a window that already fits alone, right up to the edges", () => {
    expect(annotationXRange(xs, 5)).toEqual([0, 10]);
    expect(annotationXRange(xs, 95)).toEqual([90, 100]);
  });

  it("uses the data's own first and last values, not zero", () => {
    expect(annotationXRange([10, 20, 30], 20)).toEqual([19, 21]);
    expect(annotationXRange([10, 20, 30], 10)).toEqual([10, 12]);
  });

  it("pulls an annotation far outside the data to the nearest end", () => {
    expect(annotationXRange(xs, -30)).toEqual([0, 10]);
    expect(annotationXRange(xs, 500)).toEqual([90, 100]);
  });

  it("falls back to 0 to 100 when there is no x data", () => {
    expect(annotationXRange([], 50)).toEqual([45, 55]);
    expect(annotationXRange([], 0)).toEqual([0, 10]);
    expect(annotationXRange([], 100)).toEqual([90, 100]);
  });
});

describe("annotationYRange", () => {
  it("is a fifth of the full range, centered on the annotation", () => {
    expect(annotationYRange([0, 100], 50)).toEqual([40, 60]);
    expect(annotationYRange([-5, 5], 1)).toEqual([0, 2]);
  });

  it("does not depend on which end of the range comes first", () => {
    expect(annotationYRange([100, 0], 50)).toEqual([40, 60]);
  });

  it("is a point when the range is flat", () => {
    expect(annotationYRange([3, 3], 7)).toEqual([7, 7]);
  });
});

describe("plotlyAnnotations", () => {
  const note: Annotation = { x: 1, y: 2, text: "look here" };

  it("draws a note as an arrow pointing at its position", () => {
    expect(plotlyAnnotations([note], [], COLORS)).toEqual([
      {
        x: 1,
        y: 2,
        text: "look here",
        showarrow: true,
        arrowhead: 2,
        ax: 0,
        ay: -40,
        font: { family: "monospace", size: 12, color: "#111111" },
        bgcolor: "#222222",
        bordercolor: "#333333",
        borderwidth: 1,
        borderpad: 4,
      },
    ]);
  });

  it("passes a note's text through untouched", () => {
    const [a] = plotlyAnnotations([{ x: 0, y: 0, text: "<b>bold</b>" }], [], COLORS) as Array<{ text: string }>;
    expect(a!.text).toBe("<b>bold</b>");
  });

  it("is empty with no notes and no labeled shapes", () => {
    expect(plotlyAnnotations([], [], COLORS)).toEqual([]);
    const unlabeled: Shape[] = [{ type: "vline", x0: 1, color: "#fff" }, { type: "hline", y0: 1, color: "#fff", label: "" }];
    expect(plotlyAnnotations([], unlabeled, COLORS)).toEqual([]);
  });

  it("puts a vertical line's label at the top of the plot", () => {
    const [a] = plotlyAnnotations([], [{ type: "vline", x0: 3, color: "#ff0000", label: "start" }], COLORS) as Array<
      Record<string, unknown>
    >;
    expect(a).toEqual({
      x: 3,
      y: 1,
      xref: "x",
      yref: "paper",
      text: "<b>start</b>",
      showarrow: false,
      xanchor: "left",
      yanchor: "bottom",
      font: { size: 10, color: "#ff0000", family: "monospace" },
      bgcolor: "#444444b3",
      borderpad: 2,
    });
  });

  it("puts a horizontal line's label at the right edge of the plot", () => {
    const [a] = plotlyAnnotations([], [{ type: "hline", y0: 2, color: "#00ff00", label: "limit" }], COLORS) as Array<
      Record<string, unknown>
    >;
    expect(a).toMatchObject({ x: 1, y: 2, xref: "paper", yref: "y", xanchor: "right", yanchor: "bottom", text: "<b>limit</b>" });
  });

  it("puts a rectangle's label at its x0 and y1 corner", () => {
    const [a] = plotlyAnnotations(
      [],
      [{ type: "rect", x0: 1, x1: 2, y0: 3, y1: 4, color: "#abcdef", label: "zone" }],
      COLORS,
    ) as Array<Record<string, unknown>>;
    expect(a).toMatchObject({ x: 1, y: 4, xref: "x", yref: "y", xanchor: "left", yanchor: "bottom" });
  });

  it("labels a shape with no type at the origin", () => {
    const [a] = plotlyAnnotations([], [{ x0: 9, color: "#123456", label: "odd" }], COLORS) as Array<
      Record<string, unknown>
    >;
    expect(a).toMatchObject({ x: 0, y: 0, xref: "x", yref: "y", xanchor: "left", yanchor: "bottom" });
  });

  it("colors a label like its shape, or with the accent when the shape has no color", () => {
    const shapes: Shape[] = [
      { type: "vline", x0: 1, color: "#ff0000", label: "a" },
      { type: "vline", x0: 2, color: "", label: "b" },
    ];
    const out = plotlyAnnotations([], shapes, COLORS) as Array<{ font: { color: string } }>;
    expect(out.map((a) => a.font.color)).toEqual(["#ff0000", "#333333"]);
  });

  it("lists the notes first, then the shape labels in shape order", () => {
    const shapes: Shape[] = [
      { type: "vline", x0: 1, color: "#fff", label: "one" },
      { type: "hline", y0: 1, color: "#fff" },
      { type: "hline", y0: 2, color: "#fff", label: "two" },
    ];
    const out = plotlyAnnotations([note], shapes, COLORS) as Array<{ text: string }>;
    expect(out.map((a) => a.text)).toEqual(["look here", "<b>one</b>", "<b>two</b>"]);
  });
});

describe("plotlyShapes", () => {
  it("is empty with no shapes", () => {
    expect(plotlyShapes([], false, "#333333")).toEqual([]);
  });

  it("draws a vertical line across the whole height", () => {
    expect(plotlyShapes([{ type: "vline", x0: 3, color: "#ff0000", dash: "dash" }], false, "#333333")).toEqual([
      {
        line: { color: "#ff0000", width: 2, dash: "dash" },
        layer: "below",
        type: "line",
        x0: 3,
        x1: 3,
        y0: 0,
        y1: 1,
        yref: "paper",
      },
    ]);
  });

  it("draws a horizontal line across the whole width", () => {
    expect(plotlyShapes([{ type: "hline", y0: 2, color: "#00ff00", dash: "dot" }], false, "#333333")).toEqual([
      {
        line: { color: "#00ff00", width: 2, dash: "dot" },
        layer: "below",
        type: "line",
        y0: 2,
        y1: 2,
        x0: 0,
        x1: 1,
        xref: "paper",
      },
    ]);
  });

  it("draws a rectangle with a thinner outline and a tint", () => {
    const rect: Shape = { type: "rect", x0: 1, x1: 2, y0: 3, y1: 4, color: "#abcdef", dash: "solid" };
    expect(plotlyShapes([rect], false, "#333333")).toEqual([
      {
        line: { color: "#abcdef", width: 1, dash: "solid" },
        layer: "below",
        type: "rect",
        x0: 1,
        x1: 2,
        y0: 3,
        y1: 4,
        fillcolor: "#abcdef26",
      },
    ]);
  });

  it("tints a rectangle less in dark mode", () => {
    const rect: Shape = { type: "rect", x0: 1, x1: 2, y0: 3, y1: 4, color: "#abcdef" };
    expect((plotlyShapes([rect], true, "#333333")[0] as { fillcolor: string }).fillcolor).toBe("#abcdef1A");
    expect((plotlyShapes([rect], false, "#333333")[0] as { fillcolor: string }).fillcolor).toBe("#abcdef26");
  });

  it("is solid when a shape has no dash", () => {
    const shapes: Shape[] = [
      { type: "vline", x0: 1, color: "#fff" },
      { type: "hline", y0: 1, color: "#fff", dash: null },
    ];
    const out = plotlyShapes(shapes, false, "#333333") as Array<{ line: { dash: string } }>;
    expect(out.map((s) => s.line.dash)).toEqual(["solid", "solid"]);
  });

  it("uses the accent color for a shape with none", () => {
    const shapes: Shape[] = [
      { type: "vline", x0: 1, color: "" },
      { type: "rect", x0: 1, x1: 2, y0: 1, y1: 2, color: "" },
    ];
    const out = plotlyShapes(shapes, false, "#333333") as Array<{ line: { color: string }; fillcolor?: string }>;
    expect(out.map((s) => s.line.color)).toEqual(["#333333", "#333333"]);
    expect(out[1]!.fillcolor).toBe("#33333326");
  });

  it("draws a shape with no type as a bare styled outline", () => {
    expect(plotlyShapes([{ x0: 9, color: "#123456" }], false, "#333333")).toEqual([
      { line: { color: "#123456", width: 2, dash: "solid" }, layer: "below" },
    ]);
  });

  it("keeps the shapes in order", () => {
    const shapes: Shape[] = [
      { type: "hline", y0: 1, color: "#fff" },
      { type: "vline", x0: 1, color: "#fff" },
    ];
    expect((plotlyShapes(shapes, false, "#333333") as Array<{ yref?: string; xref?: string }>).map((s) => s.xref ?? s.yref)).toEqual([
      "paper",
      "paper",
    ]);
    expect((plotlyShapes(shapes, false, "#333333")[0] as { y0: number }).y0).toBe(1);
  });
});
