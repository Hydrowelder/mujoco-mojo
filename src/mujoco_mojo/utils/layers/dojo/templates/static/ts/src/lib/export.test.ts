import { describe, expect, it } from "vitest";

import {
  configFileName,
  csvFileName,
  csvText,
  manifestFileName,
  plotExportFileName,
  plotExportSize,
  plotImageFormat,
} from "./export";

describe("plotImageFormat", () => {
  it("calls jpg jpeg, as plotly does", () => {
    expect(plotImageFormat("jpg")).toBe("jpeg");
  });

  it("leaves every other format alone", () => {
    for (const f of ["png", "jpeg", "svg", "webp"]) expect(plotImageFormat(f)).toBe(f);
  });
});

describe("plotExportSize", () => {
  it("is 1280x720 at scale 1", () => {
    expect(plotExportSize(1)).toEqual({ width: 1280, height: 720 });
  });

  it("scales both sides", () => {
    expect(plotExportSize(2)).toEqual({ width: 2560, height: 1440 });
    expect(plotExportSize(0.5)).toEqual({ width: 640, height: 360 });
    expect(plotExportSize(3)).toEqual({ width: 3840, height: 2160 });
  });

  it("rounds to whole pixels", () => {
    // 1280 * 0.3335 = 426.88, 720 * 0.3335 = 240.12
    expect(plotExportSize(0.3335)).toEqual({ width: 427, height: 240 });
    expect(plotExportSize(0.333)).toEqual({ width: 426, height: 240 });
  });
});

describe("file names", () => {
  it("names an image by trial and width", () => {
    expect(plotExportFileName("run_7", 1280, "png")).toBe("run_7_1280p.png");
    expect(plotExportFileName("run_7", 2560, "jpg")).toBe("run_7_2560p.jpg");
  });

  it("names the other exports by trial", () => {
    expect(csvFileName("run_7")).toBe("run_7_filtered.csv");
    expect(configFileName("run_7")).toBe("run_7_config.json");
    expect(manifestFileName("run_7")).toBe("run_7_column_manifest.json");
  });
});

describe("csvText", () => {
  it("is a header of the column names, then a row per point", () => {
    expect(csvText({ time: [1, 2, 3], a: [10, 20, 30] }, "time", ["a"])).toBe("time,a\n1,10\n2,20\n3,30\n");
  });

  it("puts the x column first and then each signal in order", () => {
    expect(csvText({ time: [1], a: [2], b: [3] }, "time", ["b", "a"])).toBe("time,b,a\n1,3,2\n");
  });

  it("is just the x column with no signals", () => {
    expect(csvText({ time: [1, 2] }, "time", [])).toBe("time\n1\n2\n");
  });

  it("has a row for each point of the x column", () => {
    expect(csvText({ time: [1, 2, 3], a: [9] }, "time", ["a"])).toBe("time,a\n1,9\n2,\n3,\n");
    expect(csvText({ time: [1], a: [7, 8, 9] }, "time", ["a"])).toBe("time,a\n1,7\n");
  });

  it("leaves a blank where a column has no value or no data at all", () => {
    expect(csvText({ time: [1, 2], a: [5, null as unknown as number] }, "time", ["a", "missing"])).toBe("time,a,missing\n1,5,\n2,,\n");
  });

  it("writes zero as zero, not as a blank", () => {
    expect(csvText({ time: [0, 1], a: [0, 0] }, "time", ["a"])).toBe("time,a\n0,0\n1,0\n");
  });

  it("writes a missing number as NaN", () => {
    expect(csvText({ time: [1], a: [NaN] }, "time", ["a"])).toBe("time,a\n1,NaN\n");
  });

  it("is only the header when the x column has no data", () => {
    expect(csvText({ a: [1, 2] }, "time", ["a"])).toBe("time,a\n");
    expect(csvText({ time: [], a: [1] }, "time", ["a"])).toBe("time,a\n");
  });
});
