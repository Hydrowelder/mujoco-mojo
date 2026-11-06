import { describe, expect, it } from "vitest";

import type { PlotConfig } from "../models";
import {
  DEFAULT_CONFIG,
  hasPlotDefault,
  isPlotFieldDefault,
  plotDefaultCopy,
  shapeDefName,
  withDefaultNote,
} from "./plot-defaults";

const fresh = (): PlotConfig => JSON.parse(JSON.stringify(DEFAULT_CONFIG)) as PlotConfig;

describe("DEFAULT_CONFIG", () => {
  it("is a plain value that survives a JSON round trip, as the saved config does", () => {
    expect(fresh()).toEqual(DEFAULT_CONFIG);
  });

  it("starts empty: time on x, no signals, the world frame", () => {
    expect(DEFAULT_CONFIG).toMatchObject({
      xAxis: { col: "time", filters: [] },
      yAxes: {},
      refFrame: [null, null],
      shapes: [],
      annotations: [],
    });
  });

  it("starts with automatic axis ranges", () => {
    expect(DEFAULT_CONFIG.rangeX).toBeNull();
    expect(DEFAULT_CONFIG.rangeY).toBeNull();
  });
});

describe("hasPlotDefault", () => {
  it("is true for the config's fields and false for anything else", () => {
    expect(hasPlotDefault("title")).toBe(true);
    expect(hasPlotDefault("rangeX")).toBe(true);
    expect(hasPlotDefault("nope")).toBe(false);
  });
});

describe("withDefaultNote", () => {
  it("adds the default on its own line", () => {
    expect(withDefaultNote("Where the legend goes.", "legendPos")).toBe(
      "Where the legend goes.\n\nDefault: `bottom`.",
    );
  });

  it("writes each kind of default the way the server does", () => {
    expect(withDefaultNote("d", "showSpike")).toBe("d\n\nDefault: `true`.");
    expect(withDefaultNote("d", "title")).toBe("d\n\nDefault: `(empty)`.");
    expect(withDefaultNote("d", "rangeX")).toBe("d\n\nDefault: `None`.");
    expect(withDefaultNote("d", "refFrame")).toBe("d\n\nDefault: `[null,null]`.");
  });

  it("leaves a description that already states its default alone", () => {
    const text = "Grid lines.\n\nDefault: `all`.";
    expect(withDefaultNote(text, "grid")).toBe(text);
  });

  it("leaves a blank description blank, and a field with no default as it was", () => {
    expect(withDefaultNote("", "grid")).toBe("");
    expect(withDefaultNote("Some text.", "nope")).toBe("Some text.");
  });
});

describe("isPlotFieldDefault", () => {
  it("is true for an untouched config", () => {
    const config = fresh();
    for (const key of Object.keys(config)) expect(isPlotFieldDefault(config, key), key).toBe(true);
  });

  it("is false for a field that was changed", () => {
    const config = { ...fresh(), title: "My plot", grid: "none" } as PlotConfig;
    expect(isPlotFieldDefault(config, "title")).toBe(false);
    expect(isPlotFieldDefault(config, "grid")).toBe(false);
    expect(isPlotFieldDefault(config, "interp")).toBe(true);
  });

  it("compares arrays and objects by value, not identity", () => {
    const config = fresh();
    config.rangeX = [0, 1];
    expect(isPlotFieldDefault(config, "rangeX")).toBe(false);
    config.rangeX = null;
    expect(isPlotFieldDefault(config, "rangeX")).toBe(true);
    config.refFrame = [null, null];
    expect(isPlotFieldDefault(config, "refFrame")).toBe(true);
    config.refFrame = ["q", null];
    expect(isPlotFieldDefault(config, "refFrame")).toBe(false);
  });

  it("is true for a field the defaults do not cover, so no reset is offered for it", () => {
    expect(isPlotFieldDefault(fresh(), "nope")).toBe(true);
  });
});

describe("plotDefaultCopy", () => {
  it("returns the default value", () => {
    expect(plotDefaultCopy("grid")).toBe("all");
    expect(plotDefaultCopy("rangeX")).toBeNull();
    expect(plotDefaultCopy("showSpike")).toBe(true);
  });

  it("returns a copy of an object or array, never the default itself", () => {
    const copy = plotDefaultCopy("refFrame") as (string | null)[];
    expect(copy).toEqual([null, null]);
    copy[0] = "leaked";
    expect(DEFAULT_CONFIG.refFrame).toEqual([null, null]);
    const annotations = plotDefaultCopy("annotations") as unknown[];
    annotations.push({});
    expect(DEFAULT_CONFIG.annotations).toEqual([]);
  });

  it("gives a new copy each time", () => {
    expect(plotDefaultCopy("shapes")).not.toBe(plotDefaultCopy("shapes"));
  });
});

describe("shapeDefName", () => {
  it("maps each shape type to its definition in the schema", () => {
    expect(shapeDefName("vline")).toBe("VlineShape");
    expect(shapeDefName("hline")).toBe("HlineShape");
    expect(shapeDefName("rect")).toBe("RectShape");
  });

  it("falls back to the rectangle for anything else", () => {
    expect(shapeDefName("")).toBe("RectShape");
    expect(shapeDefName("circle")).toBe("RectShape");
  });
});
