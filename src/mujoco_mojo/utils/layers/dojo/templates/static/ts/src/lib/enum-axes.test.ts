import { describe, expect, it } from "vitest";

import {
  enumAxisIds,
  enumAxisLayout,
  enumGroupKey,
  enumLabels,
  enumMapOf,
  enumRange,
  planEnumAxes,
  type EnumAxisStyle,
  type EnumGroup,
} from "./enum-axes";

// a one-column plan, for the helpers that take a group
function groupOf(map: Record<string, number>): EnumGroup {
  const plan = planEnumAxes(["col"], { col: { enumeration_map: map } });
  return plan.groups[0]!;
}

const STATE = { IDLE: 0, RUNNING: 1, DONE: 2 };

describe("enumMapOf", () => {
  it("returns the label to code map", () => {
    expect(enumMapOf({ enumeration_map: STATE })).toEqual(STATE);
  });

  it.each([
    ["no metadata", null],
    ["undefined metadata", undefined],
    ["no map", {}],
    ["a null map", { enumeration_map: null }],
    ["an array", { enumeration_map: [1, 2] }],
    ["a string", { enumeration_map: "RUNNING" }],
    ["an empty map", { enumeration_map: {} }],
    ["a non-numeric code", { enumeration_map: { A: 0, B: "1" } }],
    ["a NaN code", { enumeration_map: { A: Number.NaN } }],
    ["an infinite code", { enumeration_map: { A: Number.POSITIVE_INFINITY } }],
  ])("returns null for %s", (_label, meta) => {
    expect(enumMapOf(meta)).toBeNull();
  });
});

describe("enumGroupKey", () => {
  it("is the same for the same map in any entry order", () => {
    expect(enumGroupKey({ B: 1, A: 0 })).toBe(enumGroupKey({ A: 0, B: 1 }));
  });

  it("differs when a label or a code differs", () => {
    expect(enumGroupKey({ A: 0 })).not.toBe(enumGroupKey({ A: 1 }));
    expect(enumGroupKey({ A: 0 })).not.toBe(enumGroupKey({ B: 0 }));
  });
});

describe("planEnumAxes", () => {
  it("groups columns that share a map and keeps first-appearance order", () => {
    const plan = planEnumAxes(["x", "s1", "t", "s2"], {
      s1: { enumeration_map: { A: 0, B: 1 } },
      s2: { enumeration_map: { B: 1, A: 0 } },
      t: { enumeration_map: { P: 5 } },
    });
    expect(plan.groups.map((g) => g.columns)).toEqual([["s1", "s2"], ["t"]]);
    expect(plan.groupOf.get("s1")).toBe(0);
    expect(plan.groupOf.get("s2")).toBe(0);
    expect(plan.groupOf.get("t")).toBe(1);
  });

  it("leaves out columns with no usable map", () => {
    const plan = planEnumAxes(["plain", "bad", "missing"], { plain: {}, bad: { enumeration_map: { A: "x" } } });
    expect(plan.groups).toEqual([]);
    expect(plan.groupOf.size).toBe(0);
  });

  it("lists ticks ascending by code", () => {
    expect(groupOf({ DONE: 2, IDLE: 0, RUNNING: 1 }).ticks).toEqual([
      { code: 0, label: "IDLE" },
      { code: 1, label: "RUNNING" },
      { code: 2, label: "DONE" },
    ]);
  });

  it("lets the first label win when two share a code", () => {
    const group = groupOf({ FIRST: 1, SECOND: 1, ZERO: 0 });
    expect(group.ticks).toEqual([
      { code: 0, label: "ZERO" },
      { code: 1, label: "FIRST" },
    ]);
    expect(group.labelByCode.get(1)).toBe("FIRST");
  });
});

describe("enumLabels", () => {
  const group = groupOf(STATE);

  it("shows the label with its code", () => {
    expect(enumLabels([1, 0, 2], group)).toEqual(["RUNNING (1)", "IDLE (0)", "DONE (2)"]);
  });

  it("shows just the number for a code the map does not name", () => {
    expect(enumLabels([7, -1], group)).toEqual(["7", "-1"]);
  });

  it("gives an empty string for gaps", () => {
    expect(enumLabels([null, undefined, Number.NaN, Number.POSITIVE_INFINITY], group)).toEqual(["", "", "", ""]);
  });

  it("treats a float within tolerance of a whole number as that code, and leaves other floats alone", () => {
    expect(enumLabels([1 + 1e-10, 0.5], group)).toEqual(["RUNNING (1)", "0.5"]);
  });

  it("escapes characters Plotly would read as markup", () => {
    expect(enumLabels([0], groupOf({ "a<b&c": 0 }))).toEqual(["a&lt;b&amp;c (0)"]);
  });

  it("accepts typed arrays", () => {
    expect(enumLabels(new Float64Array([2, 1]), group)).toEqual(["DONE (2)", "RUNNING (1)"]);
  });
});

describe("enumRange", () => {
  it("pads the codes by at least half a step", () => {
    expect(enumRange(groupOf(STATE), [])).toEqual([-0.5, 2.5]);
  });

  it("pads a wide map by six percent", () => {
    expect(enumRange(groupOf({ LOW: 0, HIGH: 100 }), [])).toEqual([-6, 106]);
  });

  it("widens to include data outside the map, ignoring gaps", () => {
    expect(enumRange(groupOf(STATE), [[-3, null, Number.NaN], [5]])).toEqual([-3.5, 5.5]);
  });
});

describe("enumAxisIds", () => {
  it("starts enum groups at the second y axis when numeric columns own the first", () => {
    expect(enumAxisIds(0, false)).toEqual({ traceRef: "y2", layoutKey: "yaxis2" });
    expect(enumAxisIds(1, false)).toEqual({ traceRef: "y3", layoutKey: "yaxis3" });
  });

  it("gives the first group the primary axis when it is promoted", () => {
    expect(enumAxisIds(0, true)).toEqual({ traceRef: "y", layoutKey: "yaxis" });
    expect(enumAxisIds(1, true)).toEqual({ traceRef: "y2", layoutKey: "yaxis2" });
  });
});

describe("enumAxisLayout", () => {
  const style: EnumAxisStyle = {
    title: "state",
    range: [-0.5, 2.5],
    color: "#10b981",
    primary: false,
    grid: { color: "#334155", show: true },
  };

  it("is a fixed linear axis on the right, ticked at the codes", () => {
    const layout = enumAxisLayout(groupOf(STATE), style);
    expect(layout).toMatchObject({
      type: "linear",
      side: "right",
      autorange: false,
      fixedrange: true,
      range: [-0.5, 2.5],
      tickmode: "array",
      tickvals: [0, 1, 2],
      ticktext: ["IDLE", "RUNNING", "DONE"],
      tickfont: { color: "#10b981", size: 11 },
      title: { text: "state", font: { color: "#10b981", family: "monospace" } },
    });
  });

  it("truncates long tick labels with an ellipsis and escapes them", () => {
    const layout = enumAxisLayout(groupOf({ "A_VERY_LONG_STATE_NAME": 0, "x<y": 1 }), style);
    expect(layout.ticktext).toEqual(["A_VERY_LONG…", "x&lt;y"]);
  });

  it("overlays the primary axis when it is an extra axis", () => {
    const layout = enumAxisLayout(groupOf(STATE), style);
    expect(layout).toMatchObject({ overlaying: "y", anchor: "free", autoshift: true, showgrid: false });
    expect(layout).not.toHaveProperty("automargin");
  });

  it("takes over the grid when it is the primary axis", () => {
    const layout = enumAxisLayout(groupOf(STATE), { ...style, primary: true });
    expect(layout).toMatchObject({ automargin: true, showgrid: true, gridcolor: "#334155" });
    expect(layout).not.toHaveProperty("overlaying");
  });
});
