import { describe, expect, it } from "vitest";

import { notifierText, popupCoords, relayoutRanges, scrubTime } from "./plot-events";

describe("scrubTime", () => {
  describe("with a time x axis", () => {
    it("is the time under the mouse", () => {
      expect(scrubTime(42, 12.5, 100, 800)).toBe(12.5);
    });

    it("is clamped to the video", () => {
      expect(scrubTime(42, -3, 100, 800)).toBe(0);
      expect(scrubTime(42, 99, 100, 800)).toBe(42);
      expect(scrubTime(42, 42, 100, 800)).toBe(42);
    });

    it("counts time zero as a time", () => {
      expect(scrubTime(42, 0, 100, 800)).toBe(0);
    });

    it("ignores the plot width", () => {
      expect(scrubTime(42, 10, 100, 0)).toBe(10);
      expect(scrubTime(42, 10, 100, -5)).toBe(10);
    });
  });

  describe("with any other x axis", () => {
    it("is the mouse's fraction of the way across the plot", () => {
      expect(scrubTime(40, null, 200, 800)).toBe(10);
      expect(scrubTime(40, null, 400, 800)).toBe(20);
    });

    it("is clamped to the ends of the video", () => {
      expect(scrubTime(40, null, -50, 800)).toBe(0);
      expect(scrubTime(40, null, 900, 800)).toBe(40);
      expect(scrubTime(40, null, 800, 800)).toBe(40);
    });

    it("is nothing when the plot has no width", () => {
      expect(scrubTime(40, null, 10, 0)).toBeNull();
      expect(scrubTime(40, null, 10, -20)).toBeNull();
    });

    it("is the start at the left edge", () => {
      expect(scrubTime(40, null, 0, 800)).toBe(0);
    });
  });
});

describe("popupCoords", () => {
  it("puts a popup left of its button, 16px clear of a 288px width, relative to the document", () => {
    expect(popupCoords({ top: 55, left: 700 }, 5, 7)).toEqual({ top: 62, left: 700 + 5 - 288 - 16 });
  });

  it("is the button's own position when the page is not scrolled", () => {
    expect(popupCoords({ top: 10, left: 400 }, 0, 0)).toEqual({ top: 10, left: 96 });
  });

  it("follows the scroll on each axis separately", () => {
    expect(popupCoords({ top: 0, left: 0 }, 100, 0)).toEqual({ top: 0, left: -204 });
    expect(popupCoords({ top: 0, left: 0 }, 0, 100)).toEqual({ top: 100, left: -304 });
  });
});

describe("notifierText", () => {
  it("is the notification's text", () => {
    expect(notifierText("Hello")).toBe("Hello");
  });

  it("drops the close mark and the space around the text", () => {
    expect(notifierText("  Hello ×")).toBe("Hello");
    expect(notifierText("× Hello ×× ")).toBe("Hello");
  });

  it("is empty when only the close mark is left", () => {
    expect(notifierText("×")).toBe("");
    expect(notifierText("")).toBe("");
  });

  it("is undefined when there is no text", () => {
    expect(notifierText(null)).toBeUndefined();
    expect(notifierText(undefined)).toBeUndefined();
  });

  it("keeps an inner close mark's neighbors joined", () => {
    expect(notifierText("a × b")).toBe("a  b");
  });
});

describe("relayoutRanges", () => {
  it("keeps nothing when the event mentions no axis", () => {
    expect(relayoutRanges({})).toEqual({ reset: false });
    expect(relayoutRanges({ "xaxis.showspikes": true })).toEqual({ reset: false });
  });

  it("takes the x range from its two ends", () => {
    expect(relayoutRanges({ "xaxis.range[0]": 1, "xaxis.range[1]": 5 })).toEqual({ reset: false, rangeX: [1, 5] });
  });

  it("takes the y range from its two ends", () => {
    expect(relayoutRanges({ "yaxis.range[0]": -2, "yaxis.range[1]": 2 })).toEqual({ reset: false, rangeY: [-2, 2] });
  });

  it("takes both ranges from one event", () => {
    expect(
      relayoutRanges({ "xaxis.range[0]": 0, "xaxis.range[1]": 10, "yaxis.range[0]": 3, "yaxis.range[1]": 4 }),
    ).toEqual({ reset: false, rangeX: [0, 10], rangeY: [3, 4] });
  });

  it("counts a range that starts at zero as a range", () => {
    expect(relayoutRanges({ "xaxis.range[0]": 0, "xaxis.range[1]": 7 })).toEqual({ reset: false, rangeX: [0, 7] });
    expect(relayoutRanges({ "yaxis.range[0]": 0, "yaxis.range[1]": 7 })).toEqual({ reset: false, rangeY: [0, 7] });
  });

  it("leaves the other axis out when only one moved", () => {
    const out = relayoutRanges({ "xaxis.range[0]": 1, "xaxis.range[1]": 5 });
    expect("rangeY" in out).toBe(false);
  });

  it("reads the two ends of each axis from its own keys", () => {
    const out = relayoutRanges({
      "xaxis.range[0]": 1,
      "xaxis.range[1]": 2,
      "yaxis.range[0]": 3,
      "yaxis.range[1]": 4,
    });
    expect(out).toEqual({ reset: false, rangeX: [1, 2], rangeY: [3, 4] });
  });

  it("resets both axes to automatic on an x autorange", () => {
    expect(relayoutRanges({ "xaxis.autorange": true })).toEqual({ reset: true });
  });

  it("resets both axes to automatic on a y autorange", () => {
    expect(relayoutRanges({ "yaxis.autorange": true })).toEqual({ reset: true });
  });

  it("lets an autorange win over a range in the same event", () => {
    expect(relayoutRanges({ "xaxis.autorange": true, "yaxis.range[0]": 1, "yaxis.range[1]": 2 })).toEqual({
      reset: true,
    });
    expect(relayoutRanges({ "yaxis.autorange": true, "xaxis.range[0]": 1, "xaxis.range[1]": 2 })).toEqual({
      reset: true,
    });
  });

  it("does not reset for an autorange that is off", () => {
    expect(relayoutRanges({ "xaxis.autorange": false, "yaxis.autorange": false })).toEqual({ reset: false });
  });
});
