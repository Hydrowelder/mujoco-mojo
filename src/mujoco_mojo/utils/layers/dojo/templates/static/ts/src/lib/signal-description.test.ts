import { describe, expect, it } from "vitest";

import {
  SIGNAL_TIP_WIDTH,
  signalDescriptions,
  signalTipHtml,
  signalTipPosition,
  wrapText,
} from "./signal-description";

describe("signalTipHtml", () => {
  it("shows the name in bold and the description in italics", () => {
    expect(signalTipHtml("Bodies/box/xpos:x", "Position of body box")).toBe(
      "<b>Bodies/box/xpos:x:</b> <i>Position of body box</i>",
    );
  });

  it("shows the name alone when there is no description", () => {
    expect(signalTipHtml("time", undefined)).toBe("<b>time</b>");
    expect(signalTipHtml("time", "")).toBe("<b>time</b>");
    expect(signalTipHtml("time", "  \n ")).toBe("<b>time</b>");
  });

  it("escapes both, since they are text the model's author wrote", () => {
    expect(signalTipHtml("a<b>", "x & <script>y</script>")).toBe(
      "<b>a&lt;b&gt;:</b> <i>x &amp; &lt;script&gt;y&lt;/script&gt;</i>",
    );
  });

  it("puts a note on a line of its own, with or without a description", () => {
    expect(signalTipHtml("a", "first", "careful")).toBe(
      "<b>a:</b> <i>first</i><br>careful",
    );
    expect(signalTipHtml("a", undefined, "careful")).toBe(
      "<b>a</b><br>careful",
    );
  });

  it("escapes the note too", () => {
    expect(signalTipHtml("a", undefined, "<i>x</i>")).toBe(
      "<b>a</b><br>&lt;i&gt;x&lt;/i&gt;",
    );
  });
});

describe("signalTipPosition", () => {
  const viewport = { width: 1000, height: 800 };

  it("goes to the right of the row, level with its top", () => {
    expect(
      signalTipPosition({ left: 100, right: 300, top: 200 }, viewport),
    ).toEqual({ left: 308, top: 200, flip: false });
  });

  it("goes to the left of the row when the right has no room", () => {
    const right = viewport.width - SIGNAL_TIP_WIDTH;
    expect(
      signalTipPosition({ left: 500, right, top: 200 }, viewport),
    ).toEqual({ left: 492, top: 200, flip: true });
  });

  it("still fits on the right when it just touches the edge", () => {
    const right = viewport.width - SIGNAL_TIP_WIDTH - 8;
    expect(
      signalTipPosition({ left: 0, right, top: 0 }, viewport).flip,
    ).toBe(false);
  });

  it("is pinned to the right edge when neither side has room", () => {
    expect(
      signalTipPosition(
        { left: 100, right: 380, top: 200 },
        { width: 400, height: 800 },
      ),
    ).toEqual({ left: 400 - SIGNAL_TIP_WIDTH - 8, top: 200, flip: false });
    expect(
      signalTipPosition(
        { left: 0, right: 200, top: 0 },
        { width: 200, height: 800 },
      ).left,
    ).toBe(8);
  });

  it("stays on the screen vertically", () => {
    expect(
      signalTipPosition({ left: 0, right: 100, top: -50 }, viewport).top,
    ).toBe(8);
    expect(
      signalTipPosition({ left: 0, right: 100, top: 790 }, viewport).top,
    ).toBe(720);
  });
});

describe("signalDescriptions", () => {
  it("keeps the columns that have a description", () => {
    expect(
      signalDescriptions({
        a: { description: "first" },
        b: {},
        c: undefined,
        d: { description: "  " },
        e: { description: " padded " },
      }),
    ).toEqual({ a: "first", e: "padded" });
  });

  it("is empty for no metadata", () => {
    expect(signalDescriptions({})).toEqual({});
  });
});

describe("wrapText", () => {
  it("fills each line with as many words as fit", () => {
    expect(wrapText("one two three four", 9, 5)).toEqual([
      "one two",
      "three",
      "four",
    ]);
    expect(wrapText("one two three", 13, 5)).toEqual(["one two three"]);
  });

  it("collapses runs of whitespace, newlines included", () => {
    expect(wrapText("  a \n\n b\tc ", 10, 5)).toEqual(["a b c"]);
  });

  it("splits a word longer than a line", () => {
    expect(wrapText("abcdefghij", 4, 5)).toEqual(["abcd", "efgh", "ij"]);
    expect(wrapText("xy abcdefgh", 4, 5)).toEqual(["xy", "abcd", "efgh"]);
    expect(wrapText("abcdefgh", 4, 5)).toEqual(["abcd", "efgh"]);
  });

  it("ends the last line with an ellipsis when it has to cut", () => {
    expect(wrapText("one two three four five six", 9, 2)).toEqual([
      "one two",
      "three…",
    ]);
  });

  it("shortens a full last line to make room for the ellipsis", () => {
    expect(wrapText("abcdefghi jkl", 9, 1)).toEqual(["abcdefgh…"]);
  });

  it("does not add an ellipsis when everything fits", () => {
    expect(wrapText("one two", 7, 1)).toEqual(["one two"]);
  });

  it("returns nothing for no text or no room", () => {
    expect(wrapText("", 10, 3)).toEqual([]);
    expect(wrapText("   ", 10, 3)).toEqual([]);
    expect(wrapText("text", 0, 3)).toEqual([]);
    expect(wrapText("text", 10, 0)).toEqual([]);
  });

  it("never makes a line longer than the limit", () => {
    const lines = wrapText(
      "a rather long description with averyveryverylongwordinit and more",
      12,
      4,
    );
    expect(lines.length).toBeLessThanOrEqual(4);
    for (const line of lines) expect(line.length).toBeLessThanOrEqual(12);
  });
});
