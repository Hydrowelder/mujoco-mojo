import { describe, expect, it } from "vitest";

import { DASH_STYLE_VALUES } from "./plot-config.generated";
import {
  DASH_OPTIONS,
  GRID_OPTIONS,
  HOVER_OPTIONS,
  INTERP_OPTIONS,
  LEGEND_POS_OPTIONS,
  LINE_MODE_OPTIONS,
  MARKER_OPTIONS,
  OPTIONS,
  SCALE_OPTIONS,
} from "./options";

const valuesOf = (options: readonly { value: string }[]) => options.map((o) => o.value);

describe("option lists", () => {
  it("are not empty and hold no value twice", () => {
    const lists: readonly (string | { value: string })[][] = [
      DASH_OPTIONS,
      MARKER_OPTIONS,
      GRID_OPTIONS,
      LEGEND_POS_OPTIONS,
      SCALE_OPTIONS,
      [...LINE_MODE_OPTIONS],
      [...INTERP_OPTIONS],
      [...HOVER_OPTIONS],
    ];
    for (const list of lists) {
      const values = list.map((o) => (typeof o === "string" ? o : o.value));
      expect(values.length).toBeGreaterThan(0);
      expect(new Set(values).size).toBe(values.length);
    }
  });

  it("take their plain lists from the values generated from the Python models", () => {
    expect(OPTIONS.dash).toBe(DASH_STYLE_VALUES);
    expect(OPTIONS.dash).toContain("solid");
  });

  it("give every labeled option a label to show", () => {
    for (const list of [LINE_MODE_OPTIONS, INTERP_OPTIONS, HOVER_OPTIONS]) {
      for (const option of list) expect(option.label.length).toBeGreaterThan(0);
    }
  });

  it("include the defaults the plot config starts from", () => {
    expect(valuesOf(LINE_MODE_OPTIONS)).toContain("lines+markers");
    expect(valuesOf(INTERP_OPTIONS)).toContain("linear");
    expect(valuesOf(HOVER_OPTIONS)).toContain("closest");
    expect(GRID_OPTIONS).toContain("all");
  });
});

describe("label lookups", () => {
  it("find the label for a value", () => {
    expect(OPTIONS.lineModeLabel("lines+markers")).toBe("Both");
    expect(OPTIONS.interpLabel("hvh")).toBe("Step (HVH)");
    expect(OPTIONS.hoverLabel("none")).toBe("Off");
  });

  it("show the raw value when it has no label, so an unfamiliar one is still readable", () => {
    expect(OPTIONS.lineModeLabel("dots")).toBe("dots");
    expect(OPTIONS.interpLabel("")).toBe("");
    expect(OPTIONS.hoverLabel("something new")).toBe("something new");
  });
});
