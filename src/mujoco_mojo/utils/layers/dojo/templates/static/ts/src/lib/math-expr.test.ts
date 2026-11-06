import { describe, expect, it } from "vitest";

import { evalMathExpr } from "./math-expr";

describe("evalMathExpr", () => {
  it.each([
    ["3", 3],
    ["  -2.5  ", -2.5],
    ["1e3", 1000],
    ["0", 0],
  ])("reads the plain number %j", (text, value) => {
    expect(evalMathExpr(text)).toBe(value);
  });

  it("returns null for blank input", () => {
    expect(evalMathExpr("")).toBeNull();
    expect(evalMathExpr("   ")).toBeNull();
    expect(evalMathExpr(undefined as unknown as string)).toBeNull();
    expect(evalMathExpr(null as unknown as string)).toBeNull();
  });

  it("accepts a number that was not typed as text", () => {
    expect(evalMathExpr(5 as unknown as string)).toBe(5);
  });

  it("does arithmetic with the usual precedence", () => {
    expect(evalMathExpr("1 + 2 * 3")).toBe(7);
    expect(evalMathExpr("(1 + 2) * 3")).toBe(9);
    expect(evalMathExpr("10 / 4")).toBe(2.5);
    expect(evalMathExpr("2 ** 10")).toBe(1024);
    expect(evalMathExpr("-3 + 1")).toBe(-2);
  });

  it("knows pi and e", () => {
    expect(evalMathExpr("pi")).toBeCloseTo(Math.PI, 12);
    expect(evalMathExpr("2 * pi")).toBeCloseTo(2 * Math.PI, 12);
    expect(evalMathExpr("e")).toBeCloseTo(Math.E, 12);
  });

  it.each([
    ["sin(pi / 2)", 1],
    ["cos(0)", 1],
    ["atan2(1, 1)", Math.PI / 4],
    ["sqrt(16)", 4],
    ["cbrt(27)", 3],
    ["log10(1000)", 3],
    ["log2(8)", 3],
    ["log(e)", 1],
    ["exp(0)", 1],
    ["abs(-4)", 4],
    ["floor(2.7)", 2],
    ["ceil(2.1)", 3],
    ["round(2.5)", 3],
    ["sign(-9)", -1],
    ["pow(2, 8)", 256],
    ["max(1, 5, 3)", 5],
    ["min(4, 2, 9)", 2],
  ])("calls %s", (text, value) => {
    expect(evalMathExpr(text)).toBeCloseTo(value, 12);
  });

  it("returns null for anything that does not come out as a finite number", () => {
    expect(evalMathExpr("1 +")).toBeNull();
    expect(evalMathExpr("hello")).toBeNull();
    expect(evalMathExpr("1 / 0")).toBeNull();
    expect(evalMathExpr("0 / 0")).toBeNull();
    expect(evalMathExpr("sqrt(-1)")).toBeNull();
    expect(evalMathExpr("'a' + 'b'")).toBeNull();
    expect(evalMathExpr("[1, 2]")).toBeNull();
  });

  it("does not know functions outside its list", () => {
    expect(evalMathExpr("sinh(1)")).toBeNull();
    expect(evalMathExpr("random()")).toBeNull();
  });

  it("reads ^ as JavaScript's bitwise xor, not a power", () => {
    // worth knowing before a rewrite: 2^3 is 1 here, and ** is the power operator
    expect(evalMathExpr("2 ^ 3")).toBe(1);
  });
});
