// the completion celebration's confetti, moved out of monitor.ts so it can be
// tested without a canvas: how a theme shapes the burst, and what each tick
// fires. the shapes (emoji or circles and squares) and the timer stay in
// monitor.ts since they need the confetti library.

import type { HolidayTheme } from "./monitor-stats";

export interface ConfettiPlan {
  themeName: string;
  // a holiday theme with its own emoji
  isSpecial: boolean;
  isSnow: boolean;
  // how long the celebration lasts, in ms
  duration: number;
  colors: string[];
  // how long a piece stays up, how big it is, how fast it falls
  ticks: number;
  scalar: number;
  gravity: number;
  // how often a burst is fired, in ms
  intervalMs: number;
}

export function confettiPlan(theme: Partial<HolidayTheme>): ConfettiPlan {
  const isSpecial = !!theme.emojis;
  const isSnow = theme.isSnow ?? false;
  return {
    themeName: theme.name ?? "Standard Mojo",
    isSpecial,
    isSnow,
    duration: 3000,
    colors: theme.colors ?? ["#06b6d4", "#3b82f6", "#22c55e"],
    ticks: isSpecial ? 200 : 100,
    scalar: isSpecial ? 5 : 1,
    gravity: isSnow ? 0.4 : isSpecial ? 0.4 : 1.2,
    intervalMs: isSpecial ? 400 : 250,
  };
}

// what one tick fires, as the options that go on top of the shared defaults:
// a single drifting flake for a snow theme, otherwise three bursts from random
// places, fewer pieces as the time runs out. `rand` is Math.random.
export function confettiShots(
  plan: ConfettiPlan,
  timeLeft: number,
  rand: () => number,
): object[] {
  if (plan.isSnow) {
    return [
      {
        particleCount: 1,
        startVelocity: 0,
        drift: (rand() - 0.5) * 1.5,
        origin: { x: rand(), y: -0.2 },
      },
    ];
  }
  const countMultiplier = plan.isSpecial ? 40 : 150;
  const particleCount = countMultiplier * (timeLeft / plan.duration);
  const shots: object[] = [];
  for (let i = 0; i < 3; i++) {
    shots.push({
      particleCount: Math.ceil(particleCount / 3),
      spread: plan.isSpecial ? 90 : 360,
      startVelocity: plan.isSpecial ? 15 : 45,
      origin: { x: rand(), y: rand() - 0.2 },
    });
  }
  return shots;
}
