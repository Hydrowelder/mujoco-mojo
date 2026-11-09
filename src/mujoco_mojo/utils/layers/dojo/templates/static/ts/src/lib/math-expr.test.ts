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

  it("reads ^ and ** as a power", () => {
    expect(evalMathExpr("2 ^ 3")).toBe(8);
    expect(evalMathExpr("2 ** 3")).toBe(8);
    expect(evalMathExpr("2^0.5")).toBeCloseTo(Math.SQRT2, 12);
    expect(evalMathExpr("4^-1")).toBe(0.25);
    expect(evalMathExpr("2^+3")).toBe(8);
  });

  it("groups a power to the right and binds it tighter than a minus on its left", () => {
    expect(evalMathExpr("2^3^2")).toBe(512);
    expect(evalMathExpr("2**3**2")).toBe(512);
    expect(evalMathExpr("-2^2")).toBe(-4);
    expect(evalMathExpr("(-2)^2")).toBe(4);
    expect(evalMathExpr("2*3^2")).toBe(18);
  });

  it("does % as a remainder at the precedence of * and /", () => {
    expect(evalMathExpr("7 % 4")).toBe(3);
    expect(evalMathExpr("1 + 7 % 4 * 2")).toBe(7);
    expect(evalMathExpr("7 % 0")).toBeNull();
  });

  it("goes left to right through + - * and /", () => {
    expect(evalMathExpr("10 - 3 - 2")).toBe(5);
    expect(evalMathExpr("100 / 10 / 5")).toBe(2);
    expect(evalMathExpr("8 / 2 * 3")).toBe(12);
    expect(evalMathExpr("1 - -1")).toBe(2);
    expect(evalMathExpr("--3")).toBe(3);
    expect(evalMathExpr("+3")).toBe(3);
    expect(evalMathExpr("-(2 + 3)")).toBe(-5);
  });

  it("reads decimals and exponents inside an expression", () => {
    expect(evalMathExpr("1e3 * 2")).toBe(2000);
    expect(evalMathExpr("2.5e-1 + .5")).toBe(0.75);
    expect(evalMathExpr("5. + 1")).toBe(6);
    expect(evalMathExpr("1E2 + 1")).toBe(101);
    expect(evalMathExpr("2e+2 + 1")).toBe(201);
  });

  it("reads the e after a number as the constant, not an exponent with no digits", () => {
    expect(evalMathExpr("2*e")).toBeCloseTo(2 * Math.E, 12);
    expect(evalMathExpr("2e")).toBeNull();
    expect(evalMathExpr("2 e3")).toBeNull();
  });

  it("calls nested functions and functions of expressions", () => {
    expect(evalMathExpr("sqrt(abs(-16))")).toBe(4);
    expect(evalMathExpr("max(1, 2 + 3, sqrt(4))")).toBe(5);
    expect(evalMathExpr("sin(pi/2)^2 + cos(pi/2)^2")).toBeCloseTo(1, 12);
    expect(evalMathExpr("pow(2, 3) * 2")).toBe(16);
    expect(evalMathExpr("sqrt( 9 )")).toBe(3);
    expect(evalMathExpr("max(4)")).toBe(4);
  });

  it("returns null for a malformed expression", () => {
    for (const text of ["1 2", "2pi", "(1 + 2", "1 + 2)", "()", "1 +* 2", "* 2", "1,2", "max(1,)", "max(,1)", "max(1 2)", "max(1", "max(1 2", "(1 2", "2 * (3 4", "sin 1", "2 3 4"]) {
      expect(evalMathExpr(text), text).toBeNull();
    }
  });

  it("returns null for a name that is not a constant or a function", () => {
    for (const text of ["x + 1", "Math.PI", "PI", "sin", "pi(2)", "e(1)", "undefined", "NaN", "Infinity", "-Infinity", "true"]) {
      expect(evalMathExpr(text), text).toBeNull();
    }
  });

  it("returns null for a number too large to hold", () => {
    expect(evalMathExpr("1e999")).toBeNull();
    expect(evalMathExpr("1e999 - 1e999")).toBeNull();
    expect(evalMathExpr("2 * 1e308 * 10")).toBeNull();
  });

  it("returns null for operators it does not have", () => {
    for (const text of ["1 < 2", "1 == 1", "1 ? 2 : 3", "1 & 3", "1 | 2", "~1", "!0", "1 << 2", "a = 1", "1; 2", "1 // 2"]) {
      expect(evalMathExpr(text), text).toBeNull();
    }
  });

  it("does not run anything outside the expression grammar", () => {
    const hostile = [
      "(0).constructor.constructor('return 6*7')()",
      "constructor",
      "constructor('return 1')()",
      "toString()",
      "__proto__",
      "globalThis",
      "this",
      "process.exit()",
      "(() => 1)()",
      "`1`",
      "sin.constructor('return 1')()",
      "[].concat(1)",
      "new Date()",
      "(globalThis.__mathExprRan = 1)",
      "constructor(1)",
      "toString(1)",
      "__proto__(1)",
      "hasOwnProperty(1)",
    ];
    for (const text of hostile) {
      expect(evalMathExpr(text), text).toBeNull();
    }
    expect((globalThis as Record<string, unknown>)["__mathExprRan"]).toBeUndefined();
  });

  it("is not fooled by a name that is on the object prototype", () => {
    expect(evalMathExpr("hasOwnProperty(1)")).toBeNull();
    expect(evalMathExpr("valueOf")).toBeNull();
  });

  it("returns null for an expression nested too deeply to read", () => {
    expect(evalMathExpr("(".repeat(100_000) + "1" + ")".repeat(100_000))).toBeNull();
  });

  it("is not thrown by whitespace of any kind between the parts", () => {
    expect(evalMathExpr("\t1\n+\r2 ")).toBe(3);
    expect(evalMathExpr("max (1, 2)")).toBe(2);
  });
});
