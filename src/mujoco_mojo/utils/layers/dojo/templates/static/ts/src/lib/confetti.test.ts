import { describe, expect, it } from "vitest";

import { confettiPlan, confettiShots } from "./confetti";

const seq = (...values: number[]) => {
  let i = 0;
  return () => values[i++ % values.length]!;
};

describe("confettiPlan", () => {
  it("is the standard celebration with no theme details", () => {
    expect(confettiPlan({})).toEqual({
      themeName: "Standard Mojo",
      isSpecial: false,
      isSnow: false,
      duration: 3000,
      colors: ["#06b6d4", "#3b82f6", "#22c55e"],
      ticks: 100,
      scalar: 1,
      gravity: 1.2,
      intervalMs: 250,
    });
  });

  it("takes the theme's name and colors", () => {
    const plan = confettiPlan({ name: "Colors only", colors: ["#123456"] });
    expect(plan.themeName).toBe("Colors only");
    expect(plan.colors).toEqual(["#123456"]);
    expect(plan.isSpecial).toBe(false);
  });

  it("is special, with big slow pieces and slower bursts, when the theme has emoji", () => {
    expect(confettiPlan({ name: "Halloween", emojis: ["🎃"] })).toMatchObject({
      isSpecial: true,
      isSnow: false,
      ticks: 200,
      scalar: 5,
      gravity: 0.4,
      intervalMs: 400,
    });
  });

  it("falls slowly for a snow theme", () => {
    expect(confettiPlan({ isSnow: true })).toMatchObject({ isSnow: true, isSpecial: false, gravity: 0.4, ticks: 100, scalar: 1, intervalMs: 250 });
  });

  it("is special and snowy when a theme is both", () => {
    expect(confettiPlan({ isSnow: true, emojis: ["❄️"] })).toMatchObject({ isSnow: true, isSpecial: true, gravity: 0.4, ticks: 200 });
  });

  it("treats an explicit isSnow of false as no snow", () => {
    expect(confettiPlan({ isSnow: false }).isSnow).toBe(false);
  });
});

describe("confettiShots", () => {
  const plain = confettiPlan({});
  const special = confettiPlan({ emojis: ["🎃"] });
  const snow = confettiPlan({ isSnow: true });

  it("fires a single drifting flake for a snow theme", () => {
    const [shot] = confettiShots(snow, 2000, seq(0.2, 0.7)) as Array<Record<string, any>>;
    expect(confettiShots(snow, 2000, seq(0.2, 0.7))).toHaveLength(1);
    expect(shot).toMatchObject({ particleCount: 1, startVelocity: 0 });
    expect(shot!["drift"]).toBeCloseTo(-0.45);
    expect(shot!["origin"]).toEqual({ x: 0.7, y: -0.2 });
  });

  it("drifts either way and starts above the top of the screen", () => {
    const [left] = confettiShots(snow, 1, seq(0, 0)) as Array<Record<string, any>>;
    const [right] = confettiShots(snow, 1, seq(1, 1)) as Array<Record<string, any>>;
    expect(left!["drift"]).toBe(-0.75);
    expect(right!["drift"]).toBe(0.75);
    expect(left!["origin"].y).toBe(-0.2);
  });

  it("fires three bursts for an ordinary theme", () => {
    const shots = confettiShots(plain, 3000, seq(0.1, 0.2, 0.3, 0.4, 0.5, 0.6)) as Array<Record<string, any>>;
    expect(shots).toHaveLength(3);
    expect(shots.map((s) => s["origin"])).toEqual([
      { x: 0.1, y: 0.2 - 0.2 },
      { x: 0.3, y: 0.4 - 0.2 },
      { x: 0.5, y: 0.6 - 0.2 },
    ]);
    for (const s of shots) expect(s).toMatchObject({ spread: 360, startVelocity: 45 });
  });

  it("splits 150 pieces over three bursts at the start, fewer as time runs out", () => {
    const counts = (timeLeft: number) =>
      (confettiShots(plain, timeLeft, seq(0.5)) as Array<Record<string, any>>).map((s) => s["particleCount"]);
    expect(counts(3000)).toEqual([50, 50, 50]);
    expect(counts(1500)).toEqual([25, 25, 25]);
    expect(counts(1000)).toEqual([17, 17, 17]);
    expect(counts(10)).toEqual([1, 1, 1]);
  });

  it("fires fewer, narrower, slower bursts for a special theme", () => {
    const shots = confettiShots(special, 3000, seq(0.5)) as Array<Record<string, any>>;
    expect(shots).toHaveLength(3);
    for (const s of shots) expect(s).toMatchObject({ particleCount: 14, spread: 90, startVelocity: 15 });
  });

  it("fires bursts, not flakes, for a special theme that is not snow", () => {
    expect(confettiShots(special, 3000, seq(0.5))).toHaveLength(3);
  });

  it("draws its random numbers in a fixed order: x then y for each burst, drift then x for a flake", () => {
    const calls: number[] = [];
    let n = 0;
    confettiShots(plain, 3000, () => {
      calls.push(n);
      return n++ / 10;
    });
    expect(calls).toEqual([0, 1, 2, 3, 4, 5]);
    const shots = confettiShots(plain, 3000, seq(0.1, 0.2, 0.3, 0.4, 0.5, 0.6)) as Array<Record<string, any>>;
    expect(shots[1]!["origin"].x).toBe(0.3);
  });
});
