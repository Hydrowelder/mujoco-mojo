import { describe, expect, it } from "vitest";

import { trialDataUrl, unseenFilterErrors, type DataRequestConfig } from "./trial-data";

const config = (over: Partial<DataRequestConfig> = {}): DataRequestConfig => ({
  yAxes: {},
  xAxis: { col: "time", filters: [] },
  displayUnitSystem: null,
  maxPoints: null,
  ...over,
});

const none = () => false;
const params = (url: string) => new URLSearchParams(url.split("?")[1] ?? "");
const filters = (url: string) => JSON.parse(params(url).get("filters") ?? "null");

describe("trialDataUrl", () => {
  it("is the trial's data route with no query when nothing is asked for", () => {
    expect(trialDataUrl("run_7", [], config(), none)).toBe("/mosaic/run_7/data");
  });

  it("names the columns wanted, comma separated", () => {
    const url = trialDataUrl("run_7", ["time", "a", "b:x"], config(), none);
    expect(url.startsWith("/mosaic/run_7/data?")).toBe(true);
    expect(params(url).get("cols")).toBe("time,a,b:x");
  });

  it("sends no filters for signals that have none", () => {
    const url = trialDataUrl("run_7", ["a"], config({ yAxes: { a: { filters: [] }, b: {} } }), none);
    expect(params(url).has("filters")).toBe(false);
  });

  it("sends a signal's filters, without their enabled flag", () => {
    const url = trialDataUrl(
      "run_7",
      ["a"],
      config({ yAxes: { a: { filters: [{ type: "clip", enabled: true, min: 0, max: 5 }, { type: "lowpass", cutoff: 2 }] } } }),
      none,
    );
    expect(filters(url)).toEqual({ a: [{ type: "clip", min: 0, max: 5 }, { type: "lowpass", cutoff: 2 }] });
  });

  it("leaves out filters that are switched off, and a signal whose filters all are", () => {
    const url = trialDataUrl(
      "run_7",
      ["a", "b"],
      config({
        yAxes: {
          a: { filters: [{ type: "clip", enabled: false }, { type: "unit", toUnit: "km/h" }] },
          b: { filters: [{ type: "clip", enabled: false }] },
        },
      }),
      none,
    );
    expect(filters(url)).toEqual({ a: [{ type: "unit", toUnit: "km/h" }] });
  });

  it("sends filters only for the columns asked for", () => {
    const url = trialDataUrl(
      "run_7",
      ["a"],
      config({ yAxes: { a: { filters: [{ type: "clip" }] }, b: { filters: [{ type: "clip" }] } } }),
      none,
    );
    expect(Object.keys(filters(url))).toEqual(["a"]);
  });

  it("sends no filters for an enum signal, whose codes a filter would scramble", () => {
    const url = trialDataUrl(
      "run_7",
      ["a", "mode"],
      config({ yAxes: { a: { filters: [{ type: "clip" }] }, mode: { filters: [{ type: "clip" }] } } }),
      (c) => c === "mode",
    );
    expect(Object.keys(filters(url))).toEqual(["a"]);
  });

  it("sends the x column's filters", () => {
    const url = trialDataUrl(
      "run_7",
      ["time", "a"],
      config({ xAxis: { col: "time", filters: [{ type: "lowpass", enabled: true, cutoff: 1 }] } }),
      none,
    );
    expect(filters(url)).toEqual({ time: [{ type: "lowpass", cutoff: 1 }] });
  });

  it("does not send the x column's filters when it is not asked for", () => {
    const url = trialDataUrl("run_7", ["a"], config({ xAxis: { col: "time", filters: [{ type: "lowpass" }] } }), none);
    expect(params(url).has("filters")).toBe(false);
  });

  it("sends nothing for an x column whose filters are all switched off", () => {
    const url = trialDataUrl("run_7", ["time"], config({ xAxis: { col: "time", filters: [{ type: "lowpass", enabled: false }] } }), none);
    expect(params(url).has("filters")).toBe(false);
  });

  it("uses the x filters for a column that is both the x column and a signal", () => {
    const url = trialDataUrl(
      "run_7",
      ["a"],
      config({ xAxis: { col: "a", filters: [{ type: "clip", min: 1 }] }, yAxes: { a: { filters: [{ type: "lowpass" }] } } }),
      none,
    );
    expect(filters(url)).toEqual({ a: [{ type: "clip", min: 1 }] });
  });

  it("keeps a signal's own filters for a column that is also the x column with none of its own", () => {
    const url = trialDataUrl(
      "run_7",
      ["a"],
      config({ xAxis: { col: "a", filters: [] }, yAxes: { a: { filters: [{ type: "lowpass" }] } } }),
      none,
    );
    expect(filters(url)).toEqual({ a: [{ type: "lowpass" }] });
  });

  it("sends the display unit system when one is set", () => {
    expect(params(trialDataUrl("run_7", [], config({ displayUnitSystem: "imperial" }), none)).get("display_unit_system")).toBe("imperial");
    for (const unit of [null, undefined, ""]) {
      expect(params(trialDataUrl("run_7", ["a"], config({ displayUnitSystem: unit }), none)).has("display_unit_system")).toBe(false);
    }
  });

  it("sends the point limit when one is set, including zero", () => {
    expect(params(trialDataUrl("run_7", [], config({ maxPoints: 500 }), none)).get("max_points")).toBe("500");
    expect(params(trialDataUrl("run_7", [], config({ maxPoints: 0 }), none)).get("max_points")).toBe("0");
    for (const n of [null, undefined]) {
      expect(params(trialDataUrl("run_7", ["a"], config({ maxPoints: n }), none)).has("max_points")).toBe(false);
    }
  });

  it("adds the parameters in a fixed order", () => {
    const url = trialDataUrl(
      "run_7",
      ["a"],
      config({ yAxes: { a: { filters: [{ type: "clip" }] } }, displayUnitSystem: "si", maxPoints: 10 }),
      none,
    );
    expect([...params(url).keys()]).toEqual(["cols", "filters", "display_unit_system", "max_points"]);
  });

  it("is asked about each column for enum-ness", () => {
    const asked: string[] = [];
    trialDataUrl("run_7", ["a", "b"], config({ yAxes: { a: { filters: [{ type: "clip" }] }, b: { filters: [{ type: "clip" }] } } }), (c) => {
      asked.push(c);
      return false;
    });
    expect(asked).toEqual(["a", "b"]);
  });
});

describe("unseenFilterErrors", () => {
  it("is each message not already shown", () => {
    expect(unseenFilterErrors(["a", "b", "c"], new Set(["b"]))).toEqual(["a", "c"]);
  });

  it("lists a repeated message once, in the order it first appeared", () => {
    expect(unseenFilterErrors(["b", "a", "b", "a", "c"], new Set())).toEqual(["b", "a", "c"]);
  });

  it("is empty when everything is already shown, or there is nothing to show", () => {
    expect(unseenFilterErrors(["a"], new Set(["a"]))).toEqual([]);
    expect(unseenFilterErrors([], new Set(["a"]))).toEqual([]);
  });

  it("does not change the set it was given", () => {
    const shown = new Set(["a"]);
    unseenFilterErrors(["b"], shown);
    expect([...shown]).toEqual(["a"]);
  });
});
