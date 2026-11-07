import { describe, expect, it } from "vitest";

import type { DashStyle } from "./plot-config.generated";
import { nextAvailableStyle } from "./plot-style";

const COLORS = ["#c0", "#c1", "#c2"];
const DASHES: DashStyle[] = ["solid", "dash"];
const colorAt = (i: number) => COLORS[i]!;

const next = (used: { color: string; dash: DashStyle }[]) => nextAvailableStyle(used, COLORS.length, colorAt, DASHES);

describe("nextAvailableStyle", () => {
  it("starts with the first color, solid", () => {
    expect(next([])).toEqual({ color: "#c0", dash: "solid" });
  });

  it("goes through every color before moving to the next dash style", () => {
    expect(next([{ color: "#c0", dash: "solid" }])).toEqual({ color: "#c1", dash: "solid" });
    expect(
      next([
        { color: "#c0", dash: "solid" },
        { color: "#c1", dash: "solid" },
        { color: "#c2", dash: "solid" },
      ]),
    ).toEqual({ color: "#c0", dash: "dash" });
  });

  it("fills a gap left by a removed signal rather than moving on", () => {
    const used: { color: string; dash: DashStyle }[] = [
      { color: "#c0", dash: "solid" },
      { color: "#c2", dash: "solid" },
    ];
    expect(next(used)).toEqual({ color: "#c1", dash: "solid" });
  });

  it("counts a color and dash as taken only together", () => {
    expect(next([{ color: "#c0", dash: "dash" }])).toEqual({ color: "#c0", dash: "solid" });
  });

  it("goes round again by how many are in use once every combination is taken", () => {
    const every = DASHES.flatMap((dash) => COLORS.map((color) => ({ color, dash })));
    expect(every).toHaveLength(6);
    expect(next(every)).toEqual({ color: "#c0", dash: "solid" });
    expect(next([...every, { color: "#c0", dash: "solid" }])).toEqual({ color: "#c1", dash: "solid" });
    expect(next([...every, ...every.slice(0, 4)])).toEqual({ color: "#c1", dash: "dash" });
  });

  it("asks the palette only for positions inside it", () => {
    const asked: number[] = [];
    nextAvailableStyle([], 3, (i) => (asked.push(i), COLORS[i]!), DASHES);
    nextAvailableStyle(
      Array.from({ length: 9 }, () => ({ color: "?", dash: "solid" })),
      3,
      (i) => (asked.push(i), COLORS[i]!),
      DASHES,
    );
    for (const i of asked) expect(i).toBeGreaterThanOrEqual(0);
    for (const i of asked) expect(i).toBeLessThan(3);
  });
});
