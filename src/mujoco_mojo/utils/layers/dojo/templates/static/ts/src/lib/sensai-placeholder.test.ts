import { describe, expect, it } from "vitest";

import {
  DEFAULT_PLACEHOLDER,
  ERASE_MS,
  GAP_MS,
  HOLD_MS,
  PLACEHOLDER_EXAMPLES,
  TYPE_MS,
  advance,
  pickNext,
  startTyper,
  visibleText,
  type Typer,
} from "./sensai-placeholder";

// every step from `typer` until it has started on the next example, as what is
// showing and how long to wait after it
function walk(typer: Typer, pick: (previous: string) => string, steps: number) {
  const frames: Array<{ text: string; delay: number }> = [];
  let current = typer;
  for (let i = 0; i < steps; i++) {
    const next = advance(current, pick);
    current = next.typer;
    frames.push({ text: visibleText(current), delay: next.delay });
  }
  return frames;
}

describe("starting", () => {
  it("shows the whole default text, held before it is backspaced", () => {
    const typer = startTyper();

    expect(visibleText(typer)).toBe("Ask about your sim...");
    expect(typer.phase).toBe("holding");
  });

  it("can start on another text", () => {
    expect(visibleText(startTyper("hello"))).toBe("hello");
  });
});

describe("one cycle", () => {
  const frames = walk(startTyper("hello"), () => "go on", 14);

  it("backspaces a character at a time until nothing shows", () => {
    expect(frames.slice(0, 5).map((f) => f.text)).toEqual(["hell", "hel", "he", "h", ""]);
    expect(frames.slice(0, 4).every((f) => f.delay === ERASE_MS)).toBe(true);
  });

  it("pauses on the empty box before the next example", () => {
    expect(frames[4]).toEqual({ text: "", delay: GAP_MS });
  });

  it("types the next example a character at a time", () => {
    expect(frames.slice(5, 10).map((f) => f.text)).toEqual(["g", "go", "go ", "go o", "go on"]);
    expect(frames.slice(5, 9).every((f) => f.delay === TYPE_MS)).toBe(true);
  });

  it("holds the finished example before it starts to backspace", () => {
    expect(frames[9]).toEqual({ text: "go on", delay: HOLD_MS });
  });

  it("then backspaces that one", () => {
    expect(frames.slice(10, 14).map((f) => f.text)).toEqual(["go o", "go ", "go", "g"]);
  });

  it("is quicker to delete than to type, and holds longest", () => {
    expect(ERASE_MS).toBeLessThan(TYPE_MS);
    expect(TYPE_MS).toBeLessThan(GAP_MS);
    expect(GAP_MS).toBeLessThan(HOLD_MS);
  });
});

describe("a step does not change the state it was given", () => {
  it("returns a new one", () => {
    const typer = startTyper("abc");
    const copy = { ...typer };

    advance(typer, () => "x");

    expect(typer).toEqual(copy);
  });
});

describe("an example that is one character or none", () => {
  it("one character is shown at once and held", () => {
    const next = advance({ target: "ab", shown: 0, phase: "waiting" }, () => "x");

    expect(next.typer).toEqual({ target: "x", shown: 1, phase: "holding" });
    expect(next.delay).toBe(HOLD_MS);
  });

  it("none shows nothing, is held, and then moves on without stopping", () => {
    const frames = walk({ target: "ab", shown: 0, phase: "waiting" }, (previous) => (previous === "" ? "next" : ""), 4);

    expect(frames.map((f) => f.text)).toEqual(["", "", "n", "ne"]);
  });
});

describe("choosing the next example", () => {
  it("is never the one that was just shown", () => {
    for (const previous of PLACEHOLDER_EXAMPLES) {
      for (let r = 0; r < 1; r += 0.01) {
        expect(pickNext(previous, PLACEHOLDER_EXAMPLES, () => r)).not.toBe(previous);
      }
    }
  });

  it("can be any of the others, by where the random number falls", () => {
    const options = ["a", "b", "c", "d"];

    expect(pickNext("a", options, () => 0)).toBe("b");
    expect(pickNext("a", options, () => 0.5)).toBe("c");
    expect(pickNext("a", options, () => 0.99)).toBe("d");
  });

  it("is in range even when the random number reaches 1", () => {
    expect(pickNext("a", ["a", "b", "c"], () => 1)).toBe("c");
  });

  it("is the only option when that is all there is", () => {
    expect(pickNext("a", ["a"], () => 0)).toBe("a");
  });

  it("is the previous one when there are no options", () => {
    expect(pickNext("a", [], () => 0)).toBe("a");
  });

  it("uses Math.random when no number is given, and stays within the list", () => {
    for (let i = 0; i < 50; i++) {
      expect(PLACEHOLDER_EXAMPLES).toContain(pickNext(DEFAULT_PLACEHOLDER));
    }
  });
});

describe("the examples", () => {
  it("are different from each other and from the default", () => {
    expect(new Set(PLACEHOLDER_EXAMPLES).size).toBe(PLACEHOLDER_EXAMPLES.length);
    expect(PLACEHOLDER_EXAMPLES).not.toContain(DEFAULT_PLACEHOLDER);
  });

  it("are short enough for the one-line box and have no stray spacing", () => {
    for (const example of PLACEHOLDER_EXAMPLES) {
      expect(example.length, example).toBeGreaterThan(0);
      expect(example.length, example).toBeLessThanOrEqual(42);
      expect(example, example).toBe(example.trim());
      expect(example, example).not.toMatch(/\s{2}|\n/);
    }
  });

  it("cover the job, the plot, the signals and how to use Mojo", () => {
    const text = PLACEHOLDER_EXAMPLES.join("\n").toLowerCase();

    for (const word of ["trial", "plot", "signal", "how do i"]) {
      expect(text, word).toContain(word);
    }
  });
});
